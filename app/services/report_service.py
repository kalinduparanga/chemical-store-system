"""
Report Service for calculating ledger summaries, daily balances, monthly usage, ammonia audits, and physical reconciliations.
"""

import sqlite3
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
from app.database import get_connection

class ReportService:

    @staticmethod
    def get_stock_balance_report() -> List[Dict[str, Any]]:
        """Returns live stock balance grouped strictly by Chemical + Storage Location + Batch Number."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                b.id as batch_id,
                c.id as chemical_id,
                c.name as chemical_name,
                c.code as chemical_code,
                l.id as storage_location_id,
                l.name as storage_location_name,
                b.batch_number,
                b.manufacturing_date,
                b.expiry_date,
                b.date_received,
                s.name as supplier_name,
                b.received_quantity,
                b.current_quantity,
                b.unit,
                b.status,
                b.remarks
            FROM batches b
            JOIN chemicals c ON b.chemical_id = c.id
            JOIN storage_locations l ON b.storage_location_id = l.id
            LEFT JOIN suppliers s ON b.supplier_id = s.id
            ORDER BY c.name, l.name, b.batch_number
        """)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    @staticmethod
    def get_daily_movement_report(report_date: str) -> List[Dict[str, Any]]:
        """
        Calculates daily movements for each batch:
        Opening Stock, Received, Used, Transfer In, Transfer Out, Production In, Production Consumption, Adjustments, Closing Stock.
        Formula:
        Normal: Closing = Opening + Received - Used +/- Adjustments
        Ammonia: Closing = Opening + Received + Transfer In + Production In - Used - Transfer Out - Production Consumption +/- Adjustments
        """
        conn = get_connection()
        cursor = conn.cursor()

        # Get all batches
        cursor.execute("""
            SELECT 
                b.id, b.batch_number, b.expiry_date, b.current_quantity, b.unit,
                c.name as chemical_name, c.id as chemical_id,
                l.name as storage_location_name, l.id as storage_location_id
            FROM batches b
            JOIN chemicals c ON b.chemical_id = c.id
            JOIN storage_locations l ON b.storage_location_id = l.id
            ORDER BY c.name, b.batch_number
        """)
        batches = cursor.fetchall()
        report_data = []

        for b in batches:
            b_id = b["id"]
            loc_id = b["storage_location_id"]

            # Received on date
            cursor.execute("""
                SELECT COALESCE(SUM(quantity), 0.0) as qty 
                FROM receipts 
                WHERE batch_id = ? AND storage_location_id = ? AND received_date = ?
            """, (b_id, loc_id, report_date))
            received = cursor.fetchone()["qty"]

            # Used on date
            cursor.execute("""
                SELECT COALESCE(SUM(quantity_used), 0.0) as qty 
                FROM usage_transactions 
                WHERE batch_id = ? AND storage_location_id = ? AND date = ? AND is_reversed = 0
            """, (b_id, loc_id, report_date))
            used = cursor.fetchone()["qty"]

            # Transfer In on date
            cursor.execute("""
                SELECT COALESCE(SUM(quantity), 0.0) as qty 
                FROM stock_transfers 
                WHERE batch_id = ? AND to_location_id = ? AND date = ? AND is_reversed = 0
            """, (b_id, loc_id, report_date))
            trf_in = cursor.fetchone()["qty"]

            # Transfer Out on date
            cursor.execute("""
                SELECT COALESCE(SUM(quantity), 0.0) as qty 
                FROM stock_transfers 
                WHERE batch_id = ? AND from_location_id = ? AND date = ? AND is_reversed = 0
            """, (b_id, loc_id, report_date))
            trf_out = cursor.fetchone()["qty"]

            # Production In (if this batch was produced via dilution on this date)
            cursor.execute("""
                SELECT COALESCE(SUM(produced_quantity), 0.0) as qty 
                FROM dilution_transactions 
                WHERE new_10_batch_id = ? AND production_date = ?
            """, (b_id, report_date))
            prod_in = cursor.fetchone()["qty"]

            # Production Consumption (if this batch was consumed as 25% source on this date)
            cursor.execute("""
                SELECT COALESCE(SUM(source_quantity), 0.0) as qty 
                FROM dilution_transactions 
                WHERE source_25_batch_id = ? AND production_date = ?
            """, (b_id, report_date))
            prod_consumed = cursor.fetchone()["qty"]

            # Adjustments on date
            cursor.execute("""
                SELECT COALESCE(SUM(variance), 0.0) as qty 
                FROM stock_adjustments 
                WHERE batch_id = ? AND storage_location_id = ? AND date(created_at) = ?
            """, (b_id, loc_id, report_date))
            adjustments = cursor.fetchone()["qty"]

            net_change = (received + trf_in + prod_in) - (used + trf_out + prod_consumed) + adjustments
            closing_stock = b["current_quantity"]
            opening_stock = closing_stock - net_change

            # Include if there is stock or any movement
            if closing_stock > 0 or abs(net_change) > 0 or opening_stock > 0:
                report_data.append({
                    "date": report_date,
                    "chemical_name": b["chemical_name"],
                    "batch_number": b["batch_number"],
                    "expiry_date": b["expiry_date"],
                    "storage_location": b["storage_location_name"],
                    "opening_stock": round(opening_stock, 2),
                    "received": round(received, 2),
                    "used": round(used, 2),
                    "transfer_in": round(trf_in, 2),
                    "transfer_out": round(trf_out, 2),
                    "production_in": round(prod_in, 2),
                    "production_consumption": round(prod_consumed, 2),
                    "adjustments": round(adjustments, 2),
                    "closing_stock": round(closing_stock, 2),
                    "unit": b["unit"]
                })

        conn.close()
        return report_data

    @staticmethod
    def get_monthly_usage_report(year_month: str) -> List[Dict[str, Any]]:
        """Returns chemical usage summary for the given YYYY-MM."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                c.name as chemical_name,
                b.batch_number,
                b.expiry_date,
                l.name as storage_location,
                COUNT(u.id) as transaction_count,
                SUM(u.quantity_used) as total_quantity_used,
                u.unit,
                GROUP_CONCAT(DISTINCT u.purpose) as purposes,
                GROUP_CONCAT(DISTINCT u.reference_number) as reference_numbers
            FROM usage_transactions u
            JOIN chemicals c ON u.chemical_id = c.id
            JOIN batches b ON u.batch_id = b.id
            JOIN storage_locations l ON u.storage_location_id = l.id
            WHERE strftime('%Y-%m', u.date) = ? AND u.is_reversed = 0
            GROUP BY c.name, b.batch_number, b.expiry_date, l.name, u.unit
            ORDER BY c.name, total_quantity_used DESC
        """, (year_month,))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    @staticmethod
    def get_ammonia_audit_report() -> Dict[str, Any]:
        """Comprehensive audit report for Ammonia operations: Barrels, Ready-to-Use, and 10% Preparations."""
        conn = get_connection()
        cursor = conn.cursor()

        # 1. Barrels Ledger
        cursor.execute("""
            SELECT 
                b.barrel_id, bt.batch_number, b.original_quantity, b.current_quantity,
                s.name as supplier_name, b.received_date, b.expiry_date,
                l.name as location_name, b.status
            FROM barrels b
            JOIN batches bt ON b.batch_id = bt.id
            LEFT JOIN suppliers s ON b.supplier_id = s.id
            JOIN storage_locations l ON b.storage_location_id = l.id
            ORDER BY b.barrel_id
        """)
        barrels = [dict(r) for r in cursor.fetchall()]

        # 2. Barrel Transactions History
        cursor.execute("""
            SELECT 
                barrel_id, batch_number, action_date, action_time, original_quantity,
                used_or_transferred_quantity, remaining_quantity, usage_purpose,
                supplier_customer_name, destination, reference_number, remarks, operator_name
            FROM barrel_history
            ORDER BY id DESC
        """)
        barrel_history = [dict(r) for r in cursor.fetchall()]

        # 3. 10% Ammonia Preparation History
        cursor.execute("""
            SELECT 
                d.id, d.reference_number, d.production_date, d.expiry_date,
                d.source_barrel_id, b25.batch_number as source_25_batch,
                d.source_quantity, d.water_quantity, d.produced_quantity,
                b10.batch_number as new_10_batch, b10.current_quantity as current_10_stock,
                d.operator_name, d.remarks
            FROM dilution_transactions d
            JOIN batches b25 ON d.source_25_batch_id = b25.id
            JOIN batches b10 ON d.new_10_batch_id = b10.id
            ORDER BY d.id DESC
        """)
        dilutions = [dict(r) for r in cursor.fetchall()]

        conn.close()
        return {
            "barrels": barrels,
            "barrel_history": barrel_history,
            "dilutions": dilutions
        }

    @staticmethod
    def get_physical_vs_system_report(start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns history of physical vs system stock verifications."""
        conn = get_connection()
        cursor = conn.cursor()

        query = """
            SELECT 
                d.id, d.date, d.time, l.name as storage_location_name,
                c.name as chemical_name, d.physical_quantity, d.system_quantity,
                d.variance, d.unit, d.remarks, d.operator_name, d.created_at
            FROM daily_physical_stock d
            JOIN storage_locations l ON d.storage_location_id = l.id
            JOIN chemicals c ON d.chemical_id = c.id
            WHERE 1=1
        """
        params = []
        if start_date:
            query += " AND d.date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND d.date <= ?"
            params.append(end_date)
        query += " ORDER BY d.date DESC, d.time DESC, d.id DESC"

        cursor.execute(query, params)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    @staticmethod
    def get_historical_transactions(
        search: Optional[str] = None,
        transaction_type: Optional[str] = None,
        chemical_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Multi-criteria searchable historical transactions across usage, receiving, transfers, dilutions, adjustments."""
        conn = get_connection()
        cursor = conn.cursor()

        records = []

        # 1. Usages
        if not transaction_type or transaction_type == "Usage":
            q = """
                SELECT 
                    u.date as trans_date, u.time as trans_time, 'Usage' as trans_type,
                    c.name as chemical_name, b.batch_number, '' as barrel_id,
                    u.quantity_used as quantity, u.unit, u.purpose,
                    u.supplier_customer_name, l.name as location_name,
                    u.reference_number, u.operator_name, u.remarks, u.is_reversed
                FROM usage_transactions u
                JOIN chemicals c ON u.chemical_id = c.id
                JOIN batches b ON u.batch_id = b.id
                JOIN storage_locations l ON u.storage_location_id = l.id
                WHERE 1=1
            """
            p = []
            if chemical_id:
                q += " AND u.chemical_id = ?"
                p.append(chemical_id)
            if start_date:
                q += " AND u.date >= ?"
                p.append(start_date)
            if end_date:
                q += " AND u.date <= ?"
                p.append(end_date)
            cursor.execute(q, p)
            for r in cursor.fetchall():
                records.append(dict(r))

        # 2. Receipts
        if not transaction_type or transaction_type == "Receiving":
            q = """
                SELECT 
                    r.received_date as trans_date, '00:00:00' as trans_time, 'Receiving' as trans_type,
                    c.name as chemical_name, b.batch_number, '' as barrel_id,
                    r.quantity, r.unit, 'Incoming Shipment (GRN)' as purpose,
                    s.name as supplier_customer_name, l.name as location_name,
                    r.grn_number as reference_number, r.created_by as operator_name, r.remarks, 0 as is_reversed
                FROM receipts r
                JOIN chemicals c ON r.chemical_id = c.id
                JOIN batches b ON r.batch_id = b.id
                JOIN suppliers s ON r.supplier_id = s.id
                JOIN storage_locations l ON r.storage_location_id = l.id
                WHERE 1=1
            """
            p = []
            if chemical_id:
                q += " AND r.chemical_id = ?"
                p.append(chemical_id)
            if start_date:
                q += " AND r.received_date >= ?"
                p.append(start_date)
            if end_date:
                q += " AND r.received_date <= ?"
                p.append(end_date)
            cursor.execute(q, p)
            for r in cursor.fetchall():
                records.append(dict(r))

        # 3. Transfers
        if not transaction_type or transaction_type == "Transfer":
            q = """
                SELECT 
                    t.date as trans_date, t.time as trans_time, 'Transfer' as trans_type,
                    c.name as chemical_name, b.batch_number, COALESCE(t.barrel_id, '') as barrel_id,
                    t.quantity, t.unit, t.purpose, '' as supplier_customer_name,
                    fl.name || ' -> ' || tl.name as location_name,
                    t.reference_number, t.operator_name, t.remarks, t.is_reversed
                FROM stock_transfers t
                JOIN chemicals c ON t.chemical_id = c.id
                JOIN batches b ON t.batch_id = b.id
                JOIN storage_locations fl ON t.from_location_id = fl.id
                JOIN storage_locations tl ON t.to_location_id = tl.id
                WHERE 1=1
            """
            p = []
            if chemical_id:
                q += " AND t.chemical_id = ?"
                p.append(chemical_id)
            if start_date:
                q += " AND t.date >= ?"
                p.append(start_date)
            if end_date:
                q += " AND t.date <= ?"
                p.append(end_date)
            cursor.execute(q, p)
            for r in cursor.fetchall():
                records.append(dict(r))

        # 4. Dilutions
        if not transaction_type or transaction_type == "Preparation":
            q = """
                SELECT 
                    d.production_date as trans_date, '00:00:00' as trans_time, 'Preparation' as trans_type,
                    'Ammonia 10%' as chemical_name, b10.batch_number, d.source_barrel_id as barrel_id,
                    d.produced_quantity as quantity, 'kg' as unit,
                    '10% Ammonia Dilution (605kg yield)' as purpose,
                    'In-House Prep' as supplier_customer_name, '10% Ammonia Store' as location_name,
                    d.reference_number, d.operator_name, d.remarks, 0 as is_reversed
                FROM dilution_transactions d
                JOIN batches b10 ON d.new_10_batch_id = b10.id
                WHERE 1=1
            """
            p = []
            if start_date:
                q += " AND d.production_date >= ?"
                p.append(start_date)
            if end_date:
                q += " AND d.production_date <= ?"
                p.append(end_date)
            cursor.execute(q, p)
            for r in cursor.fetchall():
                records.append(dict(r))

        # Filter by search string if provided
        if search:
            s_low = search.lower()
            filtered = []
            for rec in records:
                haystack = " ".join([
                    str(rec.get("chemical_name", "")),
                    str(rec.get("batch_number", "")),
                    str(rec.get("barrel_id", "")),
                    str(rec.get("reference_number", "")),
                    str(rec.get("supplier_customer_name", "")),
                    str(rec.get("purpose", "")),
                    str(rec.get("operator_name", ""))
                ]).lower()
                if s_low in haystack:
                    filtered.append(rec)
            records = filtered

        # Sort descending by date and time
        records.sort(key=lambda x: (x["trans_date"], x["trans_time"]), reverse=True)
        conn.close()
        return records
