"""
Receiving (GRN) Router.
Handles chemical arrival and barrel generation for 25% Ammonia.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any
from app.models import ReceivingRequest
from app.auth import get_current_user, require_roles
from app.services.stock_service import StockService
from app.database import get_connection

router = APIRouter(prefix="/api/receiving", tags=["Receiving"])

@router.post("", dependencies=[Depends(require_roles(["Administrator", "Storekeeper"]))])
def receive_chemical(req: ReceivingRequest, current_user: dict = Depends(get_current_user)):
    return StockService.receive_chemical(req.dict(), current_user["full_name"])

@router.get("")
def list_receipts():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            r.id, r.grn_number, r.received_date, r.manufacturing_date, r.expiry_date,
            c.name as chemical_name, c.code as chemical_code,
            b.batch_number, s.name as supplier_name,
            l.name as storage_location_name,
            r.quantity, r.unit, r.invoice_number, r.remarks, r.created_by, r.created_at
        FROM receipts r
        JOIN chemicals c ON r.chemical_id = c.id
        JOIN batches b ON r.batch_id = b.id
        JOIN suppliers s ON r.supplier_id = s.id
        JOIN storage_locations l ON r.storage_location_id = l.id
        ORDER BY r.received_date DESC, r.id DESC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows
