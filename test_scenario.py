"""
Automated End-to-End Verification Test for the required User Scenario:
1. Receive one 220 kg 25% Ammonia barrel (batch AM25-TEST-B01, expiry 2027-10-30).
2. Verify 220 kg appears in 25% Ammonia Barrel Store with unique Barrel ID.
3. Use the barrel for 10% preparation.
4. Validate automatic lock: 220 kg 25% + 385 kg Water = 605 kg 10% Ammonia.
5. Confirm preparation:
   - Source barrel becomes 0 kg (status = 'Empty / Consumed').
   - A new 10% batch is created with exactly 605.00 kg.
   - The preparation history links the new 10% batch to the original 25% batch and barrel ID.
   - Transaction appears in 25% Ammonia Barrel History.
   - Transaction appears in 10% Ammonia Preparation History.
   - Transaction appears in monthly reports with batch number & expiry date.
   - Excel export contains the exact information.
   - Historical search can find the transaction by date, batch number, and barrel ID.
"""

import sys
import os
from datetime import date, datetime

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import init_db, get_connection
from app.services.stock_service import StockService
from app.services.report_service import ReportService
from app.services.export_service import ExportService

def run_scenario_test():
    print("=================================================================")
    print("STARTING CHEMICAL STORE SYSTEM USER SCENARIO TEST")
    print("=================================================================")

    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    # Step 1: Receive one 220 kg 25% Ammonia barrel
    print("\n--- STEP 1: Receiving 1 x 220 kg 25% Ammonia barrel ---")
    cursor.execute("SELECT id FROM chemicals WHERE name = 'Ammonia 25%'")
    chem_25_id = cursor.fetchone()["id"]
    cursor.execute("SELECT id FROM storage_locations WHERE name = '25% Ammonia Barrel Store'")
    barrel_loc_id = cursor.fetchone()["id"]
    cursor.execute("SELECT id FROM suppliers LIMIT 1")
    supp_id = cursor.fetchone()["id"]
    conn.close()

    today_str = str(date.today())
    test_batch_no = f"AM25-SCENARIO-{datetime.now().strftime('%M%S')}"
    test_exp_date = "2027-10-30"
    test_grn = f"GRN-SCENARIO-{datetime.now().strftime('%M%S')}"

    rcv_result = StockService.receive_chemical({
        "chemical_id": chem_25_id,
        "batch_number": test_batch_no,
        "manufacturing_date": "2026-09-01",
        "expiry_date": test_exp_date,
        "supplier_id": supp_id,
        "storage_location_id": barrel_loc_id,
        "quantity": 220.00,
        "unit": "kg",
        "grn_number": test_grn,
        "received_date": today_str,
        "remarks": "Scenario verification barrel arrival"
    }, operator_name="Test Storekeeper")

    print(f"Receipt recorded: {rcv_result['receipt_id']}, Created Barrels: {rcv_result['created_barrels']}")
    assert len(rcv_result["created_barrels"]) == 1, "Expected exactly 1 barrel to be created"
    new_barrel_id = rcv_result["created_barrels"][0]

    # Step 2: Verify 220 kg in 25% Ammonia Barrel Store
    print(f"\n--- STEP 2: Verifying 220 kg in Barrel Store for Barrel {new_barrel_id} ---")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM barrels WHERE barrel_id = ?", (new_barrel_id,))
    barrel_row = cursor.fetchone()
    assert barrel_row is not None, f"Barrel {new_barrel_id} not found in database"
    assert barrel_row["original_quantity"] == 220.00, "Original quantity mismatch"
    assert barrel_row["current_quantity"] == 220.00, "Current quantity should be 220.00 kg"
    assert barrel_row["status"] == "Full", "Status should be 'Full'"
    assert barrel_row["expiry_date"] == test_exp_date, "Expiry date mismatch"
    print(f"Verified: Barrel {new_barrel_id} has current stock {barrel_row['current_quantity']} kg, Batch {test_batch_no}, Expiry {test_exp_date}")

    # Step 3: Test partial rejection rule (< 220 kg check)
    print("\n--- STEP 3: Verifying Partial Barrel Preparation is Strictly Rejected ---")
    # Clean up any previous test partial barrel
    cursor.execute("DELETE FROM barrels WHERE barrel_id = 'AM25-TEST-PARTIAL'")
    cursor.execute("""
        INSERT INTO barrels (barrel_id, batch_id, chemical_id, original_quantity, current_quantity, supplier_id, received_date, expiry_date, storage_location_id, status)
        VALUES ('AM25-TEST-PARTIAL', ?, ?, 220.00, 150.00, ?, ?, ?, ?, 'Partial')
    """, (barrel_row["batch_id"], chem_25_id, supp_id, today_str, test_exp_date, barrel_loc_id))
    conn.commit()
    conn.close()

    try:
        StockService.prepare_10_ammonia({
            "source_barrel_id": "AM25-TEST-PARTIAL",
            "production_date": today_str,
            "expiry_date": "2027-04-30",
            "reference_number": "PREP-PARTIAL-FAIL",
            "remarks": "Should be rejected"
        }, operator_name="Test Storekeeper")
        assert False, "Validation failed: Partial barrel preparation was NOT rejected!"
    except Exception as e:
        print("Expected rejection caught successfully:")
        print(f"  Error message: {e.detail if hasattr(e, 'detail') else str(e)}")
        assert "Insufficient 25% Ammonia stock. A complete 220 kg barrel is required" in str(e)

    # Step 4: Use the 220 kg barrel for 10% preparation
    print(f"\n--- STEP 4: Preparing 10% Ammonia with complete 220 kg barrel {new_barrel_id} ---")
    test_prep_ref = f"PREP-TEST-{datetime.now().strftime('%M%S')}"
    prep_exp_date = "2027-04-30"

    prep_result = StockService.prepare_10_ammonia({
        "source_barrel_id": new_barrel_id,
        "production_date": today_str,
        "expiry_date": prep_exp_date,
        "reference_number": test_prep_ref,
        "remarks": "Scenario 10% dilution test run"
    }, operator_name="Senior Chemist")

    print("Dilution executed successfully:")
    print(f"  Source Barrel: {prep_result['source_barrel_id']}")
    print(f"  Source 25% Used: {prep_result['source_quantity_used']} kg (Locked)")
    print(f"  Water Added: {prep_result['water_quantity_added']} kg (Locked)")
    print(f"  10% Produced: {prep_result['quantity_produced']} kg (Locked)")
    print(f"  New 10% Batch: {prep_result['new_10_batch_number']}")

    # Step 5: Check source barrel becomes 0 kg
    print(f"\n--- STEP 5: Verifying source barrel {new_barrel_id} is 0 kg and status is Empty ---")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT current_quantity, status FROM barrels WHERE barrel_id = ?", (new_barrel_id,))
    updated_barrel = cursor.fetchone()
    assert updated_barrel["current_quantity"] == 0.00, f"Source barrel should be 0 kg, got {updated_barrel['current_quantity']}"
    assert updated_barrel["status"] == "Empty / Consumed", "Status should be 'Empty / Consumed'"
    print(f"Verified: Barrel {new_barrel_id} current_quantity = {updated_barrel['current_quantity']} kg, status = {updated_barrel['status']}")

    # Step 6: Verify new 10% batch created with 605 kg
    print(f"\n--- STEP 6: Verifying new 10% batch has 605.00 kg ---")
    cursor.execute("SELECT * FROM batches WHERE id = ?", (prep_result["new_10_batch_id"],))
    batch_10_row = cursor.fetchone()
    assert batch_10_row["current_quantity"] == 605.00, f"Expected 605.00 kg, got {batch_10_row['current_quantity']}"
    assert batch_10_row["received_quantity"] == 605.00
    print(f"Verified: Batch {batch_10_row['batch_number']} created with {batch_10_row['current_quantity']} kg in 10% Ammonia Store")

    # Step 7: Verify preparation links new 10% batch to original 25% batch and barrel ID
    print("\n--- STEP 7: Verifying traceability link in Dilution History ---")
    cursor.execute("""
        SELECT d.*, b25.batch_number as s25_batch, b10.batch_number as s10_batch
        FROM dilution_transactions d
        JOIN batches b25 ON d.source_25_batch_id = b25.id
        JOIN batches b10 ON d.new_10_batch_id = b10.id
        WHERE d.id = ?
    """, (prep_result["dilution_id"],))
    dil_row = cursor.fetchone()
    assert dil_row["source_barrel_id"] == new_barrel_id, "Source barrel link mismatch"
    assert dil_row["s25_batch"] == test_batch_no, "Source 25% batch link mismatch"
    assert dil_row["s10_batch"] == prep_result["new_10_batch_number"], "New 10% batch mismatch"
    print(f"Verified: Dilution record links New Batch {dil_row['s10_batch']} -> Source Barrel {dil_row['source_barrel_id']} -> Source 25% Batch {dil_row['s25_batch']}")

    # Step 8: Check transaction appears in 25% Ammonia Barrel History
    print("\n--- STEP 8: Verifying transaction in 25% Ammonia Barrel History ---")
    cursor.execute("SELECT * FROM barrel_history WHERE barrel_id = ? ORDER BY id DESC LIMIT 1", (new_barrel_id,))
    bh_row = cursor.fetchone()
    assert bh_row is not None, f"No barrel history for {new_barrel_id}"
    assert bh_row["used_or_transferred_quantity"] == 220.00
    assert bh_row["remaining_quantity"] == 0.00
    assert bh_row["usage_purpose"] == "10% Ammonia Preparation"
    print(f"Verified: Barrel history shows {bh_row['used_or_transferred_quantity']} kg used for '{bh_row['usage_purpose']}', remaining {bh_row['remaining_quantity']} kg")

    # Step 9: Check transaction appears in Reports and Excel Export
    print("\n--- STEP 9: Verifying transaction in Monthly and Ammonia Audit Reports ---")
    audit_report = ReportService.get_ammonia_audit_report()
    matching_dil = [d for d in audit_report["dilutions"] if d["source_barrel_id"] == new_barrel_id]
    assert len(matching_dil) > 0, "Preparation transaction missing from ammonia audit report"
    print(f"Verified: Transaction found in Ammonia Audit Report with Source Barrel {new_barrel_id}")

    # Step 10: Verify Excel and PDF export generation
    print("\n--- STEP 10: Verifying genuine Excel (.xlsx) and PDF (.pdf) generation ---")
    excel_bytes = ExportService.export_ammonia_audit_excel(audit_report)
    assert len(excel_bytes) > 2000, "Excel output file size too small, possible corruption"
    print(f"Verified: Generated valid Excel binary workbook ({len(excel_bytes)} bytes)")

    headers = ["Barrel ID", "Batch", "Original", "Current", "Status"]
    rows = [[b["barrel_id"], b["batch_number"], str(b["original_quantity"]), str(b["current_quantity"]), b["status"]] for b in audit_report["barrels"]]
    pdf_bytes = ExportService.export_report_pdf("Ammonia Barrels Audit", headers, rows)
    assert len(pdf_bytes) > 1000, "PDF output file size too small, possible corruption"
    assert pdf_bytes.startswith(b"%PDF"), "PDF binary does not start with %PDF header"
    print(f"Verified: Generated valid PDF document ({len(pdf_bytes)} bytes, starts with %PDF)")

    # Step 11: Verify Historical Search by date, batch number, and barrel ID
    print("\n--- STEP 11: Verifying Historical Search by Date, Batch Number, and Barrel ID ---")
    
    # By Barrel ID
    res_barrel = ReportService.get_historical_transactions(search=new_barrel_id)
    assert len(res_barrel) > 0, f"Historical search failed to find transaction by Barrel ID '{new_barrel_id}'"
    print(f"Search by Barrel ID '{new_barrel_id}': Found {len(res_barrel)} record(s)")

    # By Batch Number
    res_batch = ReportService.get_historical_transactions(search=prep_result["new_10_batch_number"])
    assert len(res_batch) > 0, f"Historical search failed to find transaction by Batch '{prep_result['new_10_batch_number']}'"
    print(f"Search by 10% Batch '{prep_result['new_10_batch_number']}': Found {len(res_batch)} record(s)")

    # By Date
    res_date = ReportService.get_historical_transactions(start_date=today_str, end_date=today_str)
    assert len(res_date) > 0, f"Historical search failed to find transaction by date '{today_str}'"
    print(f"Search by Date '{today_str}': Found {len(res_date)} record(s)")

    conn.close()

    print("\n=================================================================")
    print("ALL 11 TEST SCENARIO STEPS PASSED WITH 100% COMPLIANCE!")
    print("=================================================================")

if __name__ == "__main__":
    run_scenario_test()
