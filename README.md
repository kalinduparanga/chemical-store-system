# Chemical Store Management System

A real, production-ready desktop-first chemical inventory and warehouse management system designed for rubber, latex compounding, and chemical processing facilities.

---

## Key Capabilities & Business Logic Highlights

1. **Persistent Relational Database**:
   - Built on SQLite with Write-Ahead Logging (`WAL`) and strict foreign key integrity (`PRAGMA foreign_keys = ON;`).
   - ACID-compliant transactions ensure atomic stock updates across receipts, usages, transfers, dilutions, and physical reconciliations.

2. **Core Chemicals Tracked**:
   - **TMTD** (Tetramethylthiuram Disulfide)
   - **Zinc Oxide**
   - **Lauric Acid**
   - **DAHP** (Diammonium hydrogen phosphate)
   - **Ammonia 25%**
   - **Ammonia 10%**

3. **Separate Storage Locations**:
   - `Main Chemical Store`
   - `25% Ammonia Barrel Store`
   - `Ready-to-Use 25% Ammonia Store`
   - `10% Ammonia Store`

4. **Strict Stock Segregation**:
   - Stock is strictly tracked by `Chemical + Storage Location + Batch Number` (and individual `Barrel ID` for 25% Ammonia).
   - Batches are never merged.

5. **25% Ammonia 220 kg Barrel Traceability**:
   - 25% Ammonia is received and tracked in individual 220 kg barrels (`AM25-BRL-xxxx`).
   - Every barrel preserves its original quantity (220 kg), current quantity, supplier, received date, expiry date, location, and status (`Full`, `Partial`, `Empty / Consumed`).
   - Dedicated **25% Ammonia Barrel Usage / Update** transaction logging with purpose (`10% Ammonia Preparation`, `25% Ammonia Usage`, `Transfer to Ready-to-Use 25% Ammonia Store`, `Latex Supplier / Customer Supply`, `Other`), supplier/customer name, and destination.
   - All transactions are permanently preserved in the barrel's history ledger.

6. **10% Ammonia Preparation — Fixed Business Rule**:
   - **Standard Ratio**: Exactly **ONE 220.00 kg** barrel of 25% Ammonia + **385.00 kg** purified water = **605.00 kg** of 10% Ammonia solution.
   - Partial barrel preparations (e.g. 100 kg, 110 kg, 150 kg) are **strictly forbidden** and automatically rejected.
   - The preparation form features read-only locked formula inputs.
   - If the selected barrel has < 220.00 kg, the system rejects the transaction with:
     > *"Insufficient 25% Ammonia stock. A complete 220 kg barrel is required for 10% Ammonia preparation."*
   - On confirmation, the source barrel is decremented by 220 kg (status becomes `Empty / Consumed`), a new 10% batch is generated with 605 kg, and the dilution transaction permanently links the new batch to the source barrel and batch.

7. **Daily Morning Physical Stock Verification**:
   - Required every working morning **ONLY** for:
     1. `25% Ammonia Barrel Store`
     2. `Ready-to-Use 25% Ammonia Store`
     3. `10% Ammonia Store`
   - *TMTD, Zinc Oxide, Lauric Acid, and DAHP do not require daily morning entry (recorded on usage only).*
   - Formula: `Variance = Physical Quantity - System Quantity`.
   - All daily records are permanently preserved historically (never overwritten).

8. **Role-Based Access Control (RBAC)**:
   - **Administrator**: Full system access, controlled stock adjustments, settings, user management, audit logs.
   - **Storekeeper**: Daily morning entries, chemical usage, receiving (GRN), transfers, 10% ammonia dilution, barrel updates.
   - **Viewer**: Read-only access to dashboards, batches, and reports.

9. **Genuine File Exports**:
   - **Excel (.xlsx)**: Generated using OpenPyXL with stylized title banners, colored headers, borders, number formatting, and auto-fitted columns.
   - **PDF (.pdf)**: Generated using ReportLab with corporate headers, clean data grids, and generation timestamps.

---

## Directory Structure

```
chemical_store_system/
├── app/
│   ├── __init__.py
│   ├── database.py              # SQLite connection (WAL), schema definition, and baseline seeding
│   ├── models.py                # Pydantic schemas for request validation & responses
│   ├── auth.py                  # Token signing, authentication, and RBAC dependencies
│   ├── services/
│   │   ├── __init__.py
│   │   ├── stock_service.py     # Core business logic (Receiving, Usage, Dilution, Barrel updates)
│   │   ├── report_service.py    # Report aggregations & historical transaction searches
│   │   └── export_service.py    # OpenPyXL & ReportLab file generation
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth_router.py
│   │   ├── inventory_router.py
│   │   ├── receiving_router.py
│   │   ├── usage_router.py
│   │   ├── ammonia_router.py
│   │   ├── physical_stock_router.py
│   │   ├── reports_router.py
│   │   ├── export_router.py
│   │   └── settings_router.py
│   └── main.py                  # FastAPI app with static file mounting
├── static/
│   ├── index.html               # Responsive desktop-first single page UI
│   └── js/
│       └── app.js               # Client JavaScript application logic
├── chemical_store.db            # Persistent SQLite database file
├── test_scenario.py             # Automated end-to-end user scenario test
└── run.py                       # Server startup script
```

---

## Quick Start & Running the Server

### 1. Run the Application
From the project folder:
```powershell
python run.py
```
Open your browser and navigate to:
```
http://127.0.0.1:8000
```

### 2. Default User Accounts

| Username | Password | Role | Description |
| :--- | :--- | :--- | :--- |
| `storekeeper` | `store123` | **Storekeeper** | Default account for daily chemical and ammonia operations |
| `admin` | `admin123` | **Administrator** | Full access, settings, controlled adjustments, audit logs |
| `viewer` | `view123` | **Viewer** | Read-only dashboards and report views |

*You can switch between active accounts at any time using the User Switcher icon in the lower-left corner of the sidebar.*

---

## Automated Verification Scenario

To execute the complete end-to-end verification test:
```powershell
python test_scenario.py
```
The script validates:
- Receiving one 220 kg barrel of 25% Ammonia.
- Verifying the 220 kg balance in the 25% Ammonia Barrel Store.
- Attempting partial dilution (150 kg) and confirming rejection.
- Executing fixed 10% dilution (220 kg 25% + 385 kg H2O = 605 kg 10%).
- Verifying source barrel becomes 0 kg (`Empty / Consumed`).
- Verifying new 10% batch has 605 kg.
- Checking traceability link in dilution history and barrel history.
- Verifying transaction in reports, Excel (.xlsx), and PDF (.pdf).
- Verifying historical search by barrel ID, batch number, and date.
