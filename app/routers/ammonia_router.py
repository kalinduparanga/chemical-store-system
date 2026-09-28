"""
Ammonia Module Router:
- 25% Ammonia Barrels Tracking & History
- 25% Ammonia Barrel Usage / Update
- 10% Ammonia Preparation (Strict Fixed Ratio: 220kg + 385kg = 605kg)
- Ready-to-Use 25% Ammonia Store
- 10% Ammonia Diluted Stock
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional
from app.models import BarrelUsageRequest, DilutionRequest
from app.auth import get_current_user, require_roles
from app.services.stock_service import StockService
from app.database import get_connection

router = APIRouter(prefix="/api/ammonia", tags=["Ammonia"])

@router.get("/barrels")
def list_barrels(status_filter: Optional[str] = None):
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        SELECT 
            b.id, b.barrel_id, b.batch_id, bt.batch_number,
            b.chemical_id, c.name as chemical_name,
            b.original_quantity, b.current_quantity,
            b.supplier_id, s.name as supplier_name,
            b.received_date, b.expiry_date,
            b.storage_location_id, l.name as storage_location_name,
            b.status, b.created_at, b.updated_at
        FROM barrels b
        JOIN batches bt ON b.batch_id = bt.id
        JOIN chemicals c ON b.chemical_id = c.id
        LEFT JOIN suppliers s ON b.supplier_id = s.id
        JOIN storage_locations l ON b.storage_location_id = l.id
        WHERE 1=1
    """
    params = []
    if status_filter:
        query += " AND b.status = ?"
        params.append(status_filter)
    query += " ORDER BY b.current_quantity DESC, b.barrel_id ASC"

    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

@router.get("/barrels/{barrel_id}")
def get_barrel_detail(barrel_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            b.id, b.barrel_id, b.batch_id, bt.batch_number,
            b.chemical_id, c.name as chemical_name,
            b.original_quantity, b.current_quantity,
            b.supplier_id, s.name as supplier_name,
            b.received_date, b.expiry_date,
            b.storage_location_id, l.name as storage_location_name,
            b.status, b.created_at, b.updated_at
        FROM barrels b
        JOIN batches bt ON b.batch_id = bt.id
        JOIN chemicals c ON b.chemical_id = c.id
        LEFT JOIN suppliers s ON b.supplier_id = s.id
        JOIN storage_locations l ON b.storage_location_id = l.id
        WHERE b.barrel_id = ?
    """, (barrel_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Barrel {barrel_id} not found")

    # Get this barrel's transaction history
    cursor.execute("""
        SELECT * FROM barrel_history WHERE barrel_id = ? ORDER BY id DESC
    """, (barrel_id,))
    history = [dict(h) for h in cursor.fetchall()]
    conn.close()

    result = dict(row)
    result["history"] = history
    return result

@router.get("/barrel-history")
def list_barrel_history(barrel_id: Optional[str] = None):
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        SELECT 
            id, barrel_id, batch_number, action_date, action_time,
            original_quantity, used_or_transferred_quantity, remaining_quantity,
            usage_purpose, supplier_customer_name, destination, reference_number,
            remarks, operator_name, created_at
        FROM barrel_history
        WHERE 1=1
    """
    params = []
    if barrel_id:
        query += " AND barrel_id = ?"
        params.append(barrel_id)
    query += " ORDER BY id DESC"

    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

@router.post("/barrel-usage", dependencies=[Depends(require_roles(["Administrator", "Storekeeper"]))])
def record_barrel_usage(req: BarrelUsageRequest, current_user: dict = Depends(get_current_user)):
    return StockService.barrel_usage_update(req.dict(), current_user["full_name"])

@router.post("/prepare-10", dependencies=[Depends(require_roles(["Administrator", "Storekeeper"]))])
def prepare_10_ammonia(req: DilutionRequest, current_user: dict = Depends(get_current_user)):
    return StockService.prepare_10_ammonia(req.dict(), current_user["full_name"])

@router.get("/dilutions")
def list_dilutions():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            d.id, d.reference_number, d.production_date, d.expiry_date,
            d.source_barrel_id, b25.batch_number as source_25_batch,
            d.source_quantity, d.water_quantity, d.produced_quantity,
            b10.batch_number as new_10_batch, b10.current_quantity as current_10_stock,
            d.operator_name, d.remarks, d.created_at
        FROM dilution_transactions d
        JOIN batches b25 ON d.source_25_batch_id = b25.id
        JOIN batches b10 ON d.new_10_batch_id = b10.id
        ORDER BY d.production_date DESC, d.id DESC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

@router.get("/ready-stock")
def get_ready_to_use_stock():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            b.id, b.batch_number, b.manufacturing_date, b.expiry_date,
            b.received_quantity, b.current_quantity, b.unit, b.status, b.remarks,
            l.name as storage_location_name
        FROM batches b
        JOIN storage_locations l ON b.storage_location_id = l.id
        WHERE l.name = 'Ready-to-Use 25% Ammonia Store' AND b.current_quantity > 0
        ORDER BY b.expiry_date ASC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    total_qty = sum(r["current_quantity"] for r in rows)
    conn.close()
    return {
        "batches": rows,
        "total_quantity": total_qty
    }

@router.get("/stock-10")
def get_10_ammonia_stock():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            b.id, b.batch_number, b.manufacturing_date, b.expiry_date,
            b.received_quantity, b.current_quantity, b.unit, b.status, b.remarks,
            l.name as storage_location_name
        FROM batches b
        JOIN storage_locations l ON b.storage_location_id = l.id
        WHERE l.name = '10% Ammonia Store'
        ORDER BY b.manufacturing_date DESC, b.id DESC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    total_qty = sum(r["current_quantity"] for r in rows)
    conn.close()
    return {
        "batches": rows,
        "total_quantity": total_qty
    }
