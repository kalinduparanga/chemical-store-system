"""
Stock Service implementing core business rules:
- Strict Batch Segregation (Chemical + Location + Batch Number)
- 220 kg Barrel Tracking and History
- Atomic 10% Ammonia Dilution (220 kg 25% + 385 kg H2O = 605 kg 10%)
- Morning Physical Stock Verification (Ammonia stores only)
- Transfers, Usages, Receipts, and Controlled Adjustments
"""

import sqlite3
from datetime import datetime, date, time
from typing import Dict, Any, List, Optional
from fastapi import HTTPException, status
from app.database import get_connection

class StockService:

    @staticmethod
    def get_dashboard_summary() -> Dict[str, Any]:
        """Calculates live KPI metrics and snapshots for dashboard."""
        conn = get_connection()
        cursor = conn.cursor()

        # Total chemicals count
        cursor.execute("SELECT COUNT(*) as cnt FROM chemicals WHERE is_active = 1")
        total_chemicals = cursor.fetchone()["cnt"]

        # Barrels summary
        cursor.execute("""
            SELECT 
                COUNT(*) as total_barrels,
                SUM(CASE WHEN current_quantity >= 220.0 THEN 1 ELSE 0 END) as full_barrels,
                SUM(CASE WHEN current_quantity > 0 AND current_quantity < 220.0 THEN 1 ELSE 0 END) as partial_barrels,
                COALESCE(SUM(current_quantity), 0.0) as total_barrel_kg
            FROM barrels
            WHERE current_quantity > 0
        """)
        barrel_row = cursor.fetchone()

        # Ready to use 25% Ammonia total kg
        cursor.execute("""
            SELECT COALESCE(SUM(b.current_quantity), 0.0) as total_kg
            FROM batches b
            JOIN storage_locations l ON b.storage_location_id = l.id
            JOIN chemicals c ON b.chemical_id = c.id
            WHERE l.name = 'Ready-to-Use 25% Ammonia Store'
        """)
        ready_25_kg = cursor.fetchone()["total_kg"]

        # 10% Ammonia total kg
        cursor.execute("""
            SELECT COALESCE(SUM(b.current_quantity), 0.0) as total_kg
            FROM batches b
            JOIN storage_locations l ON b.storage_location_id = l.id
            JOIN chemicals c ON b.chemical_id = c.id
            WHERE l.name = '10% Ammonia Store'
        """)
        ammonia_10_kg = cursor.fetchone()["total_kg"]

        # Total inventory stock across all chemicals (kg)
        cursor.execute("SELECT COALESCE(SUM(current_quantity), 0.0) as total_stock_kg FROM batches")
        total_stock_kg = cursor.fetchone()["total_stock_kg"]

        # Alerts count: Low stock & Expiring / Expired
        today_str = str(date.today())
        cursor.execute("SELECT value FROM system_settings WHERE key = 'expiry_warning_days'")
        warn_setting = cursor.fetchone()
        warning_days = int(warn_setting["value"]) if warn_setting else 30

        cursor.execute("""
            SELECT COUNT(*) as cnt FROM batches 
            WHERE current_quantity > 0 AND (
                expiry_date < date(?) OR 
                (expiry_date >= date(?) AND expiry_date <= date(?, '+' || ? || ' days'))
            )
        """, (today_str, today_str, today_str, warning_days))
        expiring_batches_count = cursor.fetchone()["cnt"]

        # Low stock items count (grouped by chemical)
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM (
                SELECT c.id, c.min_stock_level, COALESCE(SUM(b.current_quantity), 0) as current_stock
                FROM chemicals c
                LEFT JOIN batches b ON c.id = b.chemical_id
                WHERE c.is_active = 1
                GROUP BY c.id
                HAVING current_stock < c.min_stock_level
            )
        """)
        low_stock_count = cursor.fetchone()["cnt"]

        # Today's transactions count
        cursor.execute("""
            SELECT 
                (SELECT COUNT(*) FROM usage_transactions WHERE date = ?) +
                (SELECT COUNT(*) FROM receipts WHERE received_date = ?) +
                (SELECT COUNT(*) FROM stock_transfers WHERE date = ?) +
                (SELECT COUNT(*) FROM dilution_transactions WHERE production_date = ?) as total_today
        """, (today_str, today_str, today_str, today_str))
        today_trans_count = cursor.fetchone()["total_today"]

        # Today's Physical Stock Status (has it been submitted today?)
        cursor.execute("SELECT COUNT(*) as cnt FROM daily_physical_stock WHERE date = ?", (today_str,))
        has_today_physical_stock = cursor.fetchone()["cnt"] > 0

        # Recent 25% Ammonia Barrel Activity
        cursor.execute("""
            SELECT barrel_id, batch_number, action_date, action_time, original_quantity, 
                   used_or_transferred_quantity, remaining_quantity, usage_purpose, 
                   supplier_customer_name, reference_number
            FROM barrel_history
            ORDER BY id DESC LIMIT 5
        """)
        recent_barrel_activity = [dict(r) for r in cursor.fetchall()]

        # Recent usage transactions
        cursor.execute("""
            SELECT u.id, u.date, u.time, c.name as chemical_name, b.batch_number, 
                   u.quantity_used, u.unit, u.purpose, u.reference_number
            FROM usage_transactions u
            JOIN chemicals c ON u.chemical_id = c.id
            JOIN batches b ON u.batch_id = b.id
            ORDER BY u.id DESC LIMIT 5
        """)
        recent_usage = [dict(r) for r in cursor.fetchall()]

        # Recent receipts
        cursor.execute("""
            SELECT r.id, r.received_date, r.grn_number, c.name as chemical_name, 
                   b.batch_number, s.name as supplier_name, r.quantity, r.unit
            FROM receipts r
            JOIN chemicals c ON r.chemical_id = c.id
            JOIN batches b ON r.batch_id = b.id
            JOIN suppliers s ON r.supplier_id = s.id
            ORDER BY r.id DESC LIMIT 5
        """)
        recent_receiving = [dict(r) for r in cursor.fetchall()]

        conn.close()

        return {
            "total_chemicals": total_chemicals,
            "total_stock_kg": total_stock_kg,
            "barrel_stock": {
                "total_barrels": barrel_row["total_barrels"],
                "full_barrels": barrel_row["full_barrels"],
                "partial_barrels": barrel_row["partial_barrels"],
                "total_kg": barrel_row["total_barrel_kg"]
            },
            "ready_25_kg": ready_25_kg,
            "ammonia_10_kg": ammonia_10_kg,
            "low_stock_count": low_stock_count,
            "expiring_batches_count": expiring_batches_count,
            "today_trans_count": today_trans_count,
            "has_today_physical_stock": has_today_physical_stock,
            "recent_barrel_activity": recent_barrel_activity,
            "recent_usage": recent_usage,
            "recent_receiving": recent_receiving
        }

    @staticmethod
    def receive_chemical(data: Dict[str, Any], operator_name: str) -> Dict[str, Any]:
        """
        Receives an incoming chemical shipment (GRN).
        For 25% Ammonia: automatically creates individual 220 kg barrel records.
        Preserves batch and barrel identity.
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Fetch chemical details
            cursor.execute("SELECT id, name, default_unit FROM chemicals WHERE id = ?", (data["chemical_id"],))
            chem = cursor.fetchone()
            if not chem:
                raise HTTPException(status_code=404, detail="Chemical not found")

            # Check if batch exists in this location
            cursor.execute("""
                SELECT id, current_quantity, received_quantity 
                FROM batches 
                WHERE chemical_id = ? AND storage_location_id = ? AND batch_number = ?
            """, (data["chemical_id"], data["storage_location_id"], data["batch_number"]))
            existing_batch = cursor.fetchone()

            today_str = str(data["received_date"])
            exp_date_str = str(data["expiry_date"])
            mfg_date_str = str(data["manufacturing_date"]) if data.get("manufacturing_date") else None

            # Determine expiry status
            today = date.today()
            exp_obj = datetime.strptime(exp_date_str, "%Y-%m-%d").date()
            if exp_obj < today:
                batch_status = "Expired"
            elif (exp_obj - today).days <= 30:
                batch_status = "Expiring Soon"
            else:
                batch_status = "Valid"

            if existing_batch:
                # Update batch quantities
                batch_id = existing_batch["id"]
                new_current = existing_batch["current_quantity"] + data["quantity"]
                new_received = existing_batch["received_quantity"] + data["quantity"]
                cursor.execute("""
                    UPDATE batches 
                    SET current_quantity = ?, received_quantity = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (new_current, new_received, batch_status, batch_id))
            else:
                cursor.execute("""
                    INSERT INTO batches (
                        chemical_id, batch_number, manufacturing_date, expiry_date, date_received,
                        supplier_id, storage_location_id, received_quantity, current_quantity,
                        unit, status, remarks
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data["chemical_id"], data["batch_number"], mfg_date_str, exp_date_str,
                    today_str, data["supplier_id"], data["storage_location_id"],
                    data["quantity"], data["quantity"], data.get("unit", "kg"),
                    batch_status, data.get("remarks")
                ))
                batch_id = cursor.lastrowid

            # Insert receipt record
            cursor.execute("""
                INSERT INTO receipts (
                    grn_number, chemical_id, batch_id, supplier_id, storage_location_id,
                    quantity, unit, received_date, manufacturing_date, expiry_date,
                    invoice_number, remarks, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data["grn_number"], data["chemical_id"], batch_id, data["supplier_id"],
                data["storage_location_id"], data["quantity"], data.get("unit", "kg"),
                today_str, mfg_date_str, exp_date_str, data.get("invoice_number"),
                data.get("remarks"), operator_name
            ))
            receipt_id = cursor.lastrowid

            created_barrels = []
            # If chemical is 25% Ammonia, create 220 kg barrel records
            if chem["name"] == "Ammonia 25%":
                qty = float(data["quantity"])
                barrel_count = int(qty // 220.0)
                rem_qty = qty % 220.0
                
                # Fetch highest barrel sequence
                cursor.execute("SELECT COUNT(*) as count FROM barrels")
                curr_count = cursor.fetchone()["count"]

                for i in range(1, barrel_count + 1):
                    b_num = curr_count + i
                    barrel_id = f"AM25-BRL-{b_num:04d}"
                    cursor.execute("""
                        INSERT INTO barrels (
                            barrel_id, batch_id, chemical_id, original_quantity, current_quantity,
                            supplier_id, received_date, expiry_date, storage_location_id, status
                        ) VALUES (?, ?, ?, 220.00, 220.00, ?, ?, ?, ?, 'Full')
                    """, (barrel_id, batch_id, data["chemical_id"], data["supplier_id"], today_str, exp_date_str, data["storage_location_id"]))
                    created_barrels.append(barrel_id)

                if rem_qty > 0:
                    b_num = curr_count + barrel_count + 1
                    barrel_id = f"AM25-BRL-{b_num:04d}"
                    cursor.execute("""
                        INSERT INTO barrels (
                            barrel_id, batch_id, chemical_id, original_quantity, current_quantity,
                            supplier_id, received_date, expiry_date, storage_location_id, status
                        ) VALUES (?, ?, ?, 220.00, ?, ?, ?, ?, ?, 'Partial')
                    """, (barrel_id, batch_id, data["chemical_id"], rem_qty, data["supplier_id"], today_str, exp_date_str, data["storage_location_id"]))
                    created_barrels.append(barrel_id)

            # Audit log
            cursor.execute("""
                INSERT INTO audit_logs (user_name, action, transaction_type, record_id, details)
                VALUES (?, 'Receiving (GRN)', 'Receipt', ?, ?)
            """, (operator_name, str(receipt_id), f"Received {data['quantity']} kg of {chem['name']}, Batch {data['batch_number']} (GRN: {data['grn_number']})"))

            conn.commit()
            return {
                "receipt_id": receipt_id,
                "batch_id": batch_id,
                "created_barrels": created_barrels,
                "message": f"Successfully received {data['quantity']} kg of {chem['name']}"
            }
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def record_usage(data: Dict[str, Any], operator_name: str) -> Dict[str, Any]:
        """
        Records chemical consumption for TMTD, Zinc Oxide, Lauric Acid, DAHP, or Ammonia.
        Validates batch stock availability and reduces stock atomically.
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Lock and check batch
            cursor.execute("""
                SELECT b.id, b.batch_number, b.current_quantity, b.unit, c.name as chemical_name
                FROM batches b
                JOIN chemicals c ON b.chemical_id = c.id
                WHERE b.id = ? AND b.chemical_id = ? AND b.storage_location_id = ?
            """, (data["batch_id"], data["chemical_id"], data["storage_location_id"]))
            batch = cursor.fetchone()

            if not batch:
                raise HTTPException(status_code=404, detail="Selected batch not found in the specified location")

            qty_used = float(data["quantity_used"])
            if qty_used <= 0:
                raise HTTPException(status_code=400, detail="Quantity used must be greater than zero")

            if qty_used > batch["current_quantity"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Usage quantity ({qty_used} {batch['unit']}) exceeds available stock ({batch['current_quantity']} {batch['unit']}) for batch {batch['batch_number']}"
                )

            # Atomic decrement
            new_qty = batch["current_quantity"] - qty_used
            cursor.execute("UPDATE batches SET current_quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_qty, batch["id"]))

            use_date = str(data["date"])
            use_time = str(data.get("time") or datetime.now().strftime("%H:%M:%S"))

            cursor.execute("""
                INSERT INTO usage_transactions (
                    reference_number, date, time, chemical_id, batch_id, storage_location_id,
                    quantity_used, unit, purpose, supplier_customer_name, remarks, operator_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data["reference_number"], use_date, use_time, data["chemical_id"],
                batch["id"], data["storage_location_id"], qty_used, batch["unit"],
                data["purpose"], data.get("supplier_customer_name"), data.get("remarks"), operator_name
            ))
            usage_id = cursor.lastrowid

            # Audit log
            cursor.execute("""
                INSERT INTO audit_logs (user_name, action, transaction_type, record_id, details)
                VALUES (?, 'Chemical Usage', 'Usage', ?, ?)
            """, (operator_name, str(usage_id), f"Used {qty_used} {batch['unit']} of {batch['chemical_name']}, Batch {batch['batch_number']} for {data['purpose']}"))

            conn.commit()
            return {
                "usage_id": usage_id,
                "remaining_quantity": new_qty,
                "message": f"Recorded usage of {qty_used} {batch['unit']} from Batch {batch['batch_number']}"
            }
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def barrel_usage_update(data: Dict[str, Any], operator_name: str) -> Dict[str, Any]:
        """
        Dedicated transaction: '25% Ammonia Barrel Usage / Update'.
        Updates barrel stock, records reason/purpose, supplier/customer, maintains permanent barrel history.
        If purpose is 'Transfer to Ready-to-Use 25% Ammonia Store', also updates ready-to-use stock.
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            barrel_id = data["barrel_id"]
            cursor.execute("""
                SELECT b.id, b.barrel_id, b.batch_id, b.chemical_id, b.original_quantity, 
                       b.current_quantity, b.expiry_date, bt.batch_number, c.name as chemical_name
                FROM barrels b
                JOIN batches bt ON b.batch_id = bt.id
                JOIN chemicals c ON b.chemical_id = c.id
                WHERE b.barrel_id = ?
            """, (barrel_id,))
            barrel = cursor.fetchone()

            if not barrel:
                raise HTTPException(status_code=404, detail=f"Barrel {barrel_id} not found")

            qty_used = float(data["quantity_used"])
            if qty_used <= 0:
                raise HTTPException(status_code=400, detail="Quantity used must be greater than zero")

            if qty_used > barrel["current_quantity"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Requested quantity ({qty_used} kg) exceeds barrel stock ({barrel['current_quantity']} kg) for barrel {barrel_id}"
                )

            rem_qty = round(barrel["current_quantity"] - qty_used, 2)
            new_status = "Empty / Consumed" if rem_qty <= 0 else "Partial"

            # Update barrel
            cursor.execute("""
                UPDATE barrels 
                SET current_quantity = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (rem_qty, new_status, barrel["id"]))

            # Decrement source 25% batch in barrel store
            cursor.execute("""
                UPDATE batches 
                SET current_quantity = MAX(0.0, current_quantity - ?), updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (qty_used, barrel["batch_id"]))

            action_date = str(data.get("date") or date.today())
            action_time = str(data.get("time") or datetime.now().strftime("%H:%M:%S"))

            # Record into barrel_history
            cursor.execute("""
                INSERT INTO barrel_history (
                    barrel_id, batch_number, action_date, action_time, original_quantity,
                    used_or_transferred_quantity, remaining_quantity, usage_purpose,
                    supplier_customer_name, destination, reference_number, remarks, operator_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                barrel_id, barrel["batch_number"], action_date, action_time,
                barrel["original_quantity"], qty_used, rem_qty, data["usage_purpose"],
                data.get("supplier_customer_name"), data.get("destination"),
                data.get("reference_number"), data.get("remarks"), operator_name
            ))
            history_id = cursor.lastrowid

            # If purpose is Transfer to Ready-to-Use 25% Ammonia Store
            if data["usage_purpose"] == "Transfer to Ready-to-Use 25% Ammonia Store":
                cursor.execute("SELECT id FROM storage_locations WHERE name = 'Ready-to-Use 25% Ammonia Store'")
                rtu_loc = cursor.fetchone()
                if not rtu_loc:
                    raise HTTPException(status_code=500, detail="Ready-to-Use 25% Ammonia Store location missing")
                
                rtu_loc_id = rtu_loc["id"]

                # Check if batch exists in RTU store
                cursor.execute("""
                    SELECT id, current_quantity, received_quantity 
                    FROM batches 
                    WHERE chemical_id = ? AND storage_location_id = ? AND batch_number = ?
                """, (barrel["chemical_id"], rtu_loc_id, barrel["batch_number"]))
                rtu_batch = cursor.fetchone()

                if rtu_batch:
                    cursor.execute("""
                        UPDATE batches 
                        SET current_quantity = current_quantity + ?, received_quantity = received_quantity + ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (qty_used, qty_used, rtu_batch["id"]))
                else:
                    cursor.execute("""
                        INSERT INTO batches (
                            chemical_id, batch_number, manufacturing_date, expiry_date, date_received,
                            storage_location_id, received_quantity, current_quantity, unit, status, remarks
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'kg', 'Valid', ?)
                    """, (
                        barrel["chemical_id"], barrel["batch_number"], action_date, barrel["expiry_date"],
                        action_date, rtu_loc_id, qty_used, qty_used, f"Transferred from Barrel {barrel_id}"
                    ))

                # Also insert stock_transfers record
                cursor.execute("""
                    INSERT INTO stock_transfers (
                        reference_number, date, time, chemical_id, batch_id, barrel_id,
                        from_location_id, to_location_id, quantity, unit, purpose, remarks, operator_name
                    ) VALUES (?, ?, ?, ?, ?, ?, (SELECT storage_location_id FROM barrels WHERE id = ?), ?, ?, 'kg', ?, ?, ?)
                """, (
                    data.get("reference_number") or f"TRF-BRL-{barrel_id}", action_date, action_time,
                    barrel["chemical_id"], barrel["batch_id"], barrel_id, barrel["id"],
                    rtu_loc_id, qty_used, data["usage_purpose"], data.get("remarks"), operator_name
                ))

            # Audit log
            cursor.execute("""
                INSERT INTO audit_logs (user_name, action, transaction_type, record_id, details)
                VALUES (?, 'Barrel Usage / Update', 'Barrel History', ?, ?)
            """, (operator_name, str(history_id), f"Barrel {barrel_id} ({barrel['batch_number']}): {qty_used} kg for '{data['usage_purpose']}', Rem: {rem_qty} kg"))

            conn.commit()
            return {
                "barrel_id": barrel_id,
                "remaining_quantity": rem_qty,
                "status": new_status,
                "message": f"Successfully updated Barrel {barrel_id}. Remaining: {rem_qty} kg."
            }
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def prepare_10_ammonia(data: Dict[str, Any], operator_name: str) -> Dict[str, Any]:
        """
        STRICT COMPANY BUSINESS RULE:
        Fixed preparation of 10% Ammonia using EXACTLY ONE COMPLETE 220 kg BARREL.
        - 25% Ammonia Used = 220.00 kg (Locked)
        - Water Added = 385.00 kg (Locked)
        - 10% Ammonia Produced = 605.00 kg (Locked)
        Partial barrel preparation is strictly forbidden.
        Requires source barrel to have >= 220.00 kg available.
        Atomic execution: All succeed or none applied.
        """
        conn = get_connection()
        cursor = conn.cursor()

        FIXED_25_USED = 220.00
        FIXED_WATER_ADDED = 385.00
        FIXED_10_PRODUCED = 605.00

        try:
            barrel_id = data["source_barrel_id"]

            cursor.execute("""
                SELECT b.id, b.barrel_id, b.batch_id, b.chemical_id, b.original_quantity,
                       b.current_quantity, b.expiry_date, bt.batch_number, bt.storage_location_id
                FROM barrels b
                JOIN batches bt ON b.batch_id = bt.id
                WHERE b.barrel_id = ?
            """, (barrel_id,))
            barrel = cursor.fetchone()

            if not barrel:
                raise HTTPException(status_code=404, detail=f"25% Ammonia Barrel '{barrel_id}' not found")

            # Check stock threshold: MUST have at least 220.00 kg
            if barrel["current_quantity"] < FIXED_25_USED:
                raise HTTPException(
                    status_code=400,
                    detail="Insufficient 25% Ammonia stock. A complete 220 kg barrel is required for 10% Ammonia preparation."
                )

            # 1. Reduce source barrel by exactly 220.00 kg
            rem_barrel_qty = round(barrel["current_quantity"] - FIXED_25_USED, 2)
            cursor.execute("""
                UPDATE barrels 
                SET current_quantity = ?, status = 'Empty / Consumed', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (rem_barrel_qty, barrel["id"]))

            # 2. Reduce source 25% batch by exactly 220.00 kg
            cursor.execute("""
                UPDATE batches 
                SET current_quantity = MAX(0.0, current_quantity - ?), updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (FIXED_25_USED, barrel["batch_id"]))

            # 3. Create new 10% Ammonia batch record
            cursor.execute("SELECT id FROM chemicals WHERE name = 'Ammonia 10%'")
            chem_10 = cursor.fetchone()
            if not chem_10:
                raise HTTPException(status_code=500, detail="Chemical 'Ammonia 10%' master record not found")
            chem_10_id = chem_10["id"]

            cursor.execute("SELECT id FROM storage_locations WHERE name = '10% Ammonia Store'")
            loc_10 = cursor.fetchone()
            if not loc_10:
                raise HTTPException(status_code=500, detail="Storage Location '10% Ammonia Store' not found")
            loc_10_id = loc_10["id"]

            cursor.execute("SELECT id FROM suppliers WHERE name LIKE '%In-House%' LIMIT 1")
            inhouse_supp = cursor.fetchone()
            inhouse_supp_id = inhouse_supp["id"] if inhouse_supp else None

            prod_date_str = str(data["production_date"])
            exp_date_str = str(data["expiry_date"])

            # Generate new 10% batch number
            cursor.execute("SELECT COUNT(*) as count FROM dilution_transactions")
            prep_count = cursor.fetchone()["count"] + 1
            new_10_batch_number = f"AM10-P{datetime.now().strftime('%y%m%d')}-{prep_count:03d}"

            cursor.execute("""
                INSERT INTO batches (
                    chemical_id, batch_number, manufacturing_date, expiry_date, date_received,
                    supplier_id, storage_location_id, received_quantity, current_quantity,
                    unit, status, remarks
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'kg', 'Valid', ?)
            """, (
                chem_10_id, new_10_batch_number, prod_date_str, exp_date_str, prod_date_str,
                inhouse_supp_id, loc_10_id, FIXED_10_PRODUCED, FIXED_10_PRODUCED,
                f"Prepared from 25% Barrel {barrel_id} (Batch {barrel['batch_number']})"
            ))
            new_10_batch_id = cursor.lastrowid

            # 4. Insert Dilution Transaction
            cursor.execute("""
                INSERT INTO dilution_transactions (
                    reference_number, production_date, expiry_date, source_25_batch_id,
                    source_barrel_id, source_quantity, water_quantity, produced_quantity,
                    new_10_batch_id, operator_name, remarks
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data["reference_number"], prod_date_str, exp_date_str, barrel["batch_id"],
                barrel_id, FIXED_25_USED, FIXED_WATER_ADDED, FIXED_10_PRODUCED,
                new_10_batch_id, operator_name, data.get("remarks")
            ))
            dilution_id = cursor.lastrowid

            # 5. Insert Barrel History record
            action_time = datetime.now().strftime("%H:%M:%S")
            cursor.execute("""
                INSERT INTO barrel_history (
                    barrel_id, batch_number, action_date, action_time, original_quantity,
                    used_or_transferred_quantity, remaining_quantity, usage_purpose,
                    supplier_customer_name, destination, reference_number, remarks, operator_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, '10% Ammonia Preparation', 'Internal Preparation', '10% Ammonia Store', ?, ?, ?)
            """, (
                barrel_id, barrel["batch_number"], prod_date_str, action_time,
                barrel["original_quantity"], FIXED_25_USED, rem_barrel_qty,
                data["reference_number"], data.get("remarks"), operator_name
            ))

            # 6. Audit Log
            cursor.execute("""
                INSERT INTO audit_logs (user_name, action, transaction_type, record_id, details)
                VALUES (?, '10% Ammonia Preparation', 'Dilution', ?, ?)
            """, (
                operator_name, str(dilution_id),
                f"Prepared 605 kg of 10% Ammonia (Batch {new_10_batch_number}) using 220 kg from Barrel {barrel_id} (Batch {barrel['batch_number']}) + 385 kg Water"
            ))

            conn.commit()

            return {
                "dilution_id": dilution_id,
                "new_10_batch_id": new_10_batch_id,
                "new_10_batch_number": new_10_batch_number,
                "source_barrel_id": barrel_id,
                "source_25_batch": barrel["batch_number"],
                "source_quantity_used": FIXED_25_USED,
                "water_quantity_added": FIXED_WATER_ADDED,
                "quantity_produced": FIXED_10_PRODUCED,
                "message": f"Successfully prepared 605.00 kg of 10% Ammonia (Batch {new_10_batch_number}). Source barrel {barrel_id} consumed."
            }
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def transfer_stock(data: Dict[str, Any], operator_name: str) -> Dict[str, Any]:
        """Transfers chemical stock between storage locations while strictly preserving batch number."""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Check source batch
            cursor.execute("""
                SELECT b.id, b.batch_number, b.manufacturing_date, b.expiry_date, b.current_quantity,
                       b.unit, c.name as chemical_name, s.id as supplier_id
                FROM batches b
                JOIN chemicals c ON b.chemical_id = c.id
                LEFT JOIN suppliers s ON b.supplier_id = s.id
                WHERE b.id = ? AND b.chemical_id = ? AND b.storage_location_id = ?
            """, (data["batch_id"], data["chemical_id"], data["from_location_id"]))
            src_batch = cursor.fetchone()

            if not src_batch:
                raise HTTPException(status_code=404, detail="Source batch not found in the source location")

            qty = float(data["quantity"])
            if qty <= 0:
                raise HTTPException(status_code=400, detail="Transfer quantity must be greater than zero")

            if qty > src_batch["current_quantity"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Transfer quantity ({qty} kg) exceeds available source stock ({src_batch['current_quantity']} kg)"
                )

            # Reduce source batch
            cursor.execute("UPDATE batches SET current_quantity = current_quantity - ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (qty, src_batch["id"]))

            # Destination batch: find or create with SAME batch_number
            cursor.execute("""
                SELECT id, current_quantity, received_quantity 
                FROM batches 
                WHERE chemical_id = ? AND storage_location_id = ? AND batch_number = ?
            """, (data["chemical_id"], data["to_location_id"], src_batch["batch_number"]))
            dest_batch = cursor.fetchone()

            transfer_date = str(data["date"])
            transfer_time = str(data.get("time") or datetime.now().strftime("%H:%M:%S"))

            if dest_batch:
                cursor.execute("""
                    UPDATE batches 
                    SET current_quantity = current_quantity + ?, received_quantity = received_quantity + ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (qty, qty, dest_batch["id"]))
                dest_batch_id = dest_batch["id"]
            else:
                cursor.execute("""
                    INSERT INTO batches (
                        chemical_id, batch_number, manufacturing_date, expiry_date, date_received,
                        supplier_id, storage_location_id, received_quantity, current_quantity,
                        unit, status, remarks
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Valid', ?)
                """, (
                    data["chemical_id"], src_batch["batch_number"], src_batch["manufacturing_date"],
                    src_batch["expiry_date"], transfer_date, src_batch["supplier_id"],
                    data["to_location_id"], qty, qty, src_batch["unit"],
                    f"Transferred from location ID {data['from_location_id']}"
                ))
                dest_batch_id = cursor.lastrowid

            # Insert stock transfer record
            cursor.execute("""
                INSERT INTO stock_transfers (
                    reference_number, date, time, chemical_id, batch_id, barrel_id,
                    from_location_id, to_location_id, quantity, unit, purpose, remarks, operator_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data["reference_number"], transfer_date, transfer_time, data["chemical_id"],
                src_batch["id"], data.get("barrel_id"), data["from_location_id"],
                data["to_location_id"], qty, src_batch["unit"], data["purpose"],
                data.get("remarks"), operator_name
            ))
            transfer_id = cursor.lastrowid

            # Audit log
            cursor.execute("""
                INSERT INTO audit_logs (user_name, action, transaction_type, record_id, details)
                VALUES (?, 'Stock Transfer', 'Transfer', ?, ?)
            """, (
                operator_name, str(transfer_id),
                f"Transferred {qty} kg of {src_batch['chemical_name']} (Batch {src_batch['batch_number']}) from loc {data['from_location_id']} to loc {data['to_location_id']}"
            ))

            conn.commit()
            return {
                "transfer_id": transfer_id,
                "transferred_quantity": qty,
                "message": f"Transferred {qty} kg of Batch {src_batch['batch_number']} successfully"
            }
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def adjust_stock(data: Dict[str, Any], operator_name: str) -> Dict[str, Any]:
        """Admin-only controlled stock adjustment with required reason and variance calculation."""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT b.id, b.batch_number, b.current_quantity, b.unit, c.name as chemical_name
                FROM batches b
                JOIN chemicals c ON b.chemical_id = c.id
                WHERE b.id = ? AND b.chemical_id = ? AND b.storage_location_id = ?
            """, (data["batch_id"], data["chemical_id"], data["storage_location_id"]))
            batch = cursor.fetchone()

            if not batch:
                raise HTTPException(status_code=404, detail="Batch not found in the specified location")

            prev_qty = batch["current_quantity"]
            new_qty = float(data["new_quantity"])
            variance = round(new_qty - prev_qty, 2)

            cursor.execute("UPDATE batches SET current_quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_qty, batch["id"]))

            cursor.execute("""
                INSERT INTO stock_adjustments (
                    chemical_id, batch_id, storage_location_id, previous_quantity,
                    new_quantity, variance, unit, reason, operator_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data["chemical_id"], batch["id"], data["storage_location_id"],
                prev_qty, new_qty, variance, batch["unit"], data["reason"], operator_name
            ))
            adj_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO audit_logs (user_name, action, transaction_type, record_id, details)
                VALUES (?, 'Stock Adjustment', 'Adjustment', ?, ?)
            """, (
                operator_name, str(adj_id),
                f"Adjusted {batch['chemical_name']} (Batch {batch['batch_number']}): {prev_qty} -> {new_qty} {batch['unit']} (Var: {variance:+.2f}). Reason: {data['reason']}"
            ))

            conn.commit()
            return {
                "adjustment_id": adj_id,
                "previous_quantity": prev_qty,
                "new_quantity": new_qty,
                "variance": variance,
                "message": f"Stock adjusted from {prev_qty} to {new_qty} {batch['unit']} (Variance: {variance:+.2f})"
            }
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def record_daily_physical_stock(data: Dict[str, Any], operator_name: str) -> Dict[str, Any]:
        """
        Records morning physical stock verification for Ammonia stores ONLY:
        - 25% Ammonia Barrel Stock
        - Ready-to-Use 25% Ammonia Stock
        - 10% Ammonia Stock
        Formula: Variance = Physical Quantity - System Quantity
        Preserves all records historically without overwriting.
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            entry_date = str(data["date"])
            entry_time = str(data.get("time") or datetime.now().strftime("%H:%M:%S"))
            results = []

            for item in data["entries"]:
                loc_id = item["storage_location_id"]
                chem_id = item["chemical_id"]
                phys_qty = float(item["physical_quantity"])

                # Calculate current system quantity for this chemical in this location
                cursor.execute("""
                    SELECT COALESCE(SUM(current_quantity), 0.0) as sys_qty
                    FROM batches
                    WHERE chemical_id = ? AND storage_location_id = ?
                """, (chem_id, loc_id))
                sys_row = cursor.fetchone()
                sys_qty = sys_row["sys_qty"] if sys_row else 0.0

                variance = round(phys_qty - sys_qty, 2)

                cursor.execute("""
                    INSERT INTO daily_physical_stock (
                        date, time, storage_location_id, chemical_id, physical_quantity,
                        system_quantity, variance, unit, remarks, operator_name
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'kg', ?, ?)
                """, (
                    entry_date, entry_time, loc_id, chem_id, phys_qty,
                    sys_qty, variance, item.get("remarks"), operator_name
                ))
                rec_id = cursor.lastrowid
                results.append({
                    "id": rec_id,
                    "location_id": loc_id,
                    "chemical_id": chem_id,
                    "physical_quantity": phys_qty,
                    "system_quantity": sys_qty,
                    "variance": variance
                })

            cursor.execute("""
                INSERT INTO audit_logs (user_name, action, transaction_type, record_id, details)
                VALUES (?, 'Daily Physical Stock Entry', 'Daily Check', ?, ?)
            """, (operator_name, entry_date, f"Recorded morning physical verification for {len(results)} ammonia store locations."))

            conn.commit()
            return {
                "date": entry_date,
                "recorded_entries": len(results),
                "entries": results,
                "message": f"Successfully saved {len(results)} daily physical stock checks for {entry_date}"
            }
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
