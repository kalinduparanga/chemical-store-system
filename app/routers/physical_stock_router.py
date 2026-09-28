"""
Physical Stock Check Router.
Morning physical stock verification for Ammonia stores only (TMTD, Zinc Oxide, Lauric Acid, DAHP excluded).
Preserves all historical checks without overwriting.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional
from datetime import date
from app.models import DailyStockSubmitRequest
from app.auth import get_current_user, require_roles
from app.services.stock_service import StockService
from app.database import get_connection

router = APIRouter(prefix="/api/physical-stock", tags=["Physical Stock"])

@router.get("/current-system")
def get_current_ammonia_system_stock():
    """Returns real-time system quantity for the three morning physical verification stores."""
    conn = get_connection()
    cursor = conn.cursor()

    stores = [
        ("25% Ammonia Barrel Store", "Ammonia 25%"),
        ("Ready-to-Use 25% Ammonia Store", "Ammonia 25%"),
        ("10% Ammonia Store", "Ammonia 10%")
    ]

    data = []
    for loc_name, chem_name in stores:
        cursor.execute("SELECT id FROM storage_locations WHERE name = ?", (loc_name,))
        loc_row = cursor.fetchone()
        cursor.execute("SELECT id, default_unit FROM chemicals WHERE name = ?", (chem_name,))
        chem_row = cursor.fetchone()

        if loc_row and chem_row:
            loc_id = loc_row["id"]
            chem_id = chem_row["id"]

            cursor.execute("""
                SELECT COALESCE(SUM(current_quantity), 0.0) as sys_qty
                FROM batches
                WHERE chemical_id = ? AND storage_location_id = ?
            """, (chem_id, loc_id))
            sys_qty = cursor.fetchone()["sys_qty"]

            # If barrel store, also count full barrels
            extra_info = ""
            if "Barrel" in loc_name:
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_barrels,
                        SUM(CASE WHEN current_quantity >= 220.0 THEN 1 ELSE 0 END) as full_count
                    FROM barrels WHERE current_quantity > 0
                """)
                b_row = cursor.fetchone()
                extra_info = f"{b_row['full_count'] or 0} Full Barrels"

            data.append({
                "storage_location_id": loc_id,
                "storage_location_name": loc_name,
                "chemical_id": chem_id,
                "chemical_name": chem_name,
                "system_quantity": sys_qty,
                "unit": chem_row["default_unit"],
                "extra_info": extra_info
            })

    conn.close()
    return data

@router.post("", dependencies=[Depends(require_roles(["Administrator", "Storekeeper"]))])
def submit_physical_stock(req: DailyStockSubmitRequest, current_user: dict = Depends(get_current_user)):
    op_name = req.operator_name or current_user["full_name"]
    return StockService.record_daily_physical_stock(req.dict(), op_name)

@router.get("/history")
def list_physical_stock_history(start_date: Optional[str] = None, end_date: Optional[str] = None):
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
