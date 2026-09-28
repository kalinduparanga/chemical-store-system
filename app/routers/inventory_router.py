"""
Inventory Router for Chemicals, Locations, Batches, Alerts, Adjustments, and Transfers.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any
from datetime import date, datetime
from app.database import get_connection
from app.models import CreateBatchRequest, StockAdjustmentRequest, TransferRequest
from app.auth import get_current_user, require_roles
from app.services.stock_service import StockService

router = APIRouter(prefix="/api/inventory", tags=["Inventory"])

@router.get("/dashboard")
def get_dashboard():
    return StockService.get_dashboard_summary()

@router.get("/chemicals")
def list_chemicals():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            c.id, c.name, c.code, c.default_unit, c.storage_location_id,
            l.name as storage_location_name, c.requires_daily_physical_check,
            c.min_stock_level, c.description,
            COALESCE((SELECT SUM(current_quantity) FROM batches WHERE chemical_id = c.id), 0.0) as total_stock
        FROM chemicals c
        LEFT JOIN storage_locations l ON c.storage_location_id = l.id
        WHERE c.is_active = 1
        ORDER BY c.name
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

@router.get("/locations")
def list_locations():
    conn = get_connection()
    locations = conn.execute("SELECT id, name, code, description FROM storage_locations ORDER BY id").fetchall()
    conn.close()
    return [dict(l) for l in locations]

@router.get("/suppliers")
def list_suppliers():
    conn = get_connection()
    suppliers = conn.execute("SELECT id, name, contact_person, phone, email, address FROM suppliers ORDER BY name").fetchall()
    conn.close()
    return [dict(s) for s in suppliers]

@router.get("/customers")
def list_customers():
    conn = get_connection()
    customers = conn.execute("SELECT id, name, contact_person, phone, email, address FROM customers ORDER BY name").fetchall()
    conn.close()
    return [dict(c) for c in customers]

@router.get("/batches")
def list_batches(
    chemical_id: Optional[int] = None,
    storage_location_id: Optional[int] = None,
    status_filter: Optional[str] = None
):
    conn = get_connection()
    cursor = conn.cursor()

    # Recalculate status dynamically based on current date
    today = date.today()
    cursor.execute("SELECT value FROM system_settings WHERE key = 'expiry_warning_days'")
    w_row = cursor.fetchone()
    warn_days = int(w_row["value"]) if w_row else 30

    query = """
        SELECT 
            b.id, b.chemical_id, c.name as chemical_name, c.code as chemical_code,
            b.batch_number, b.manufacturing_date, b.expiry_date, b.date_received,
            b.supplier_id, s.name as supplier_name,
            b.storage_location_id, l.name as storage_location_name,
            b.received_quantity, b.current_quantity, b.unit,
            CASE 
                WHEN b.expiry_date < date(?) THEN 'Expired'
                WHEN b.expiry_date <= date(?, '+' || ? || ' days') THEN 'Expiring Soon'
                ELSE 'Valid'
            END as status,
            b.remarks
        FROM batches b
        JOIN chemicals c ON b.chemical_id = c.id
        JOIN storage_locations l ON b.storage_location_id = l.id
        LEFT JOIN suppliers s ON b.supplier_id = s.id
        WHERE 1=1
    """
    params = [str(today), str(today), warn_days]

    if chemical_id:
        query += " AND b.chemical_id = ?"
        params.append(chemical_id)
    if storage_location_id:
        query += " AND b.storage_location_id = ?"
        params.append(storage_location_id)
    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)

    query += " ORDER BY c.name, b.expiry_date ASC, b.batch_number"
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

@router.post("/batches", dependencies=[Depends(require_roles(["Administrator", "Storekeeper"]))])
def create_batch(req: CreateBatchRequest, current_user: dict = Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        today = date.today()
        exp_date_str = str(req.expiry_date)
        if req.expiry_date < today:
            b_status = "Expired"
        elif (req.expiry_date - today).days <= 30:
            b_status = "Expiring Soon"
        else:
            b_status = "Valid"

        cursor.execute("""
            INSERT INTO batches (
                chemical_id, batch_number, manufacturing_date, expiry_date, date_received,
                supplier_id, storage_location_id, received_quantity, current_quantity,
                unit, status, remarks
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            req.chemical_id, req.batch_number,
            str(req.manufacturing_date) if req.manufacturing_date else None,
            exp_date_str, str(req.date_received), req.supplier_id,
            req.storage_location_id, req.received_quantity, req.received_quantity,
            req.unit, b_status, req.remarks
        ))
        b_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO audit_logs (user_name, action, transaction_type, record_id, details)
            VALUES (?, 'Batch Creation', 'Batch', ?, ?)
        """, (current_user["full_name"], str(b_id), f"Created batch {req.batch_number} for chemical ID {req.chemical_id} ({req.received_quantity} {req.unit})"))

        conn.commit()
        return {"id": b_id, "message": f"Batch '{req.batch_number}' registered successfully"}
    except sqlite3.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=400, detail="Batch with this number already exists for this chemical and location")
    finally:
        conn.close()

@router.get("/alerts")
def get_alerts():
    conn = get_connection()
    cursor = conn.cursor()

    today_str = str(date.today())
    cursor.execute("SELECT value FROM system_settings WHERE key = 'expiry_warning_days'")
    w_row = cursor.fetchone()
    warn_days = int(w_row["value"]) if w_row else 30

    # Expiring Soon and Expired Batches
    cursor.execute("""
        SELECT 
            b.id, b.batch_number, b.expiry_date, b.current_quantity, b.unit,
            c.name as chemical_name, l.name as storage_location_name,
            CASE 
                WHEN b.expiry_date < date(?) THEN 'Expired'
                ELSE 'Expiring Soon'
            END as alert_status,
            CAST(julianday(b.expiry_date) - julianday(?) AS INTEGER) as days_remaining
        FROM batches b
        JOIN chemicals c ON b.chemical_id = c.id
        JOIN storage_locations l ON b.storage_location_id = l.id
        WHERE b.current_quantity > 0 AND b.expiry_date <= date(?, '+' || ? || ' days')
        ORDER BY b.expiry_date ASC
    """, (today_str, today_str, today_str, warn_days))
    expiry_alerts = [dict(r) for r in cursor.fetchall()]

    # Low Stock Alerts
    cursor.execute("""
        SELECT 
            c.id, c.name as chemical_name, c.code, c.min_stock_level, c.default_unit,
            COALESCE(SUM(b.current_quantity), 0.0) as current_stock,
            (c.min_stock_level - COALESCE(SUM(b.current_quantity), 0.0)) as deficit
        FROM chemicals c
        LEFT JOIN batches b ON c.id = b.chemical_id
        WHERE c.is_active = 1
        GROUP BY c.id
        HAVING current_stock < c.min_stock_level
        ORDER BY deficit DESC
    """)
    low_stock_alerts = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return {
        "expiry_alerts": expiry_alerts,
        "low_stock_alerts": low_stock_alerts,
        "total_critical": len(expiry_alerts) + len(low_stock_alerts)
    }

@router.post("/adjustments", dependencies=[Depends(require_roles(["Administrator"]))])
def adjust_stock(req: StockAdjustmentRequest, current_user: dict = Depends(get_current_user)):
    return StockService.adjust_stock(req.dict(), current_user["full_name"])

@router.post("/transfers", dependencies=[Depends(require_roles(["Administrator", "Storekeeper"]))])
def transfer_stock(req: TransferRequest, current_user: dict = Depends(get_current_user)):
    return StockService.transfer_stock(req.dict(), current_user["full_name"])
