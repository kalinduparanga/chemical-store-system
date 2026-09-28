"""
Database initialization, schema management, and connection helpers for Chemical Store Management System.
Uses SQLite with Write-Ahead Logging (WAL) and enforced foreign keys for ACID compliance.
"""

import sqlite3
import os
import hashlib
from datetime import datetime, date, timedelta

DB_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(DB_DIR, ".."))
DB_PATH = os.path.join(PROJECT_ROOT, "chemical_store.db")

def get_connection():
    """Returns a SQLite connection with foreign keys enabled and row_factory set to sqlite3.Row."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str) -> str:
    """Returns SHA-256 hash of password with a fixed salt for simplicity and portability."""
    salt = "chemstore_secure_salt_2026"
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return hash_password(plain_password) == hashed_password

def init_db():
    """Initializes all database tables and seeds initial master and baseline data if not present."""
    conn = get_connection()
    cursor = conn.cursor()

    # 1. System Settings
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS system_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        description TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Users & Roles
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        email TEXT,
        role TEXT NOT NULL CHECK(role IN ('Administrator', 'Storekeeper', 'Viewer')),
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 3. Storage Locations
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS storage_locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        code TEXT UNIQUE NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 4. Chemicals Master
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chemicals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        code TEXT UNIQUE NOT NULL,
        default_unit TEXT NOT NULL DEFAULT 'kg',
        storage_location_id INTEGER,
        requires_daily_physical_check INTEGER DEFAULT 0,
        min_stock_level REAL DEFAULT 100.0,
        description TEXT,
        is_active INTEGER DEFAULT 1,
        FOREIGN KEY (storage_location_id) REFERENCES storage_locations(id)
    );
    """)

    # 5. Suppliers & Customers
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        contact_person TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        contact_person TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 6. Batches
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chemical_id INTEGER NOT NULL,
        batch_number TEXT NOT NULL,
        manufacturing_date DATE,
        expiry_date DATE NOT NULL,
        date_received DATE NOT NULL,
        supplier_id INTEGER,
        storage_location_id INTEGER NOT NULL,
        received_quantity REAL NOT NULL,
        current_quantity REAL NOT NULL CHECK(current_quantity >= 0),
        unit TEXT NOT NULL DEFAULT 'kg',
        status TEXT DEFAULT 'Valid' CHECK(status IN ('Valid', 'Expiring Soon', 'Expired')),
        remarks TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (chemical_id) REFERENCES chemicals(id),
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
        FOREIGN KEY (storage_location_id) REFERENCES storage_locations(id),
        UNIQUE(chemical_id, storage_location_id, batch_number)
    );
    """)

    # 7. Barrels (For 25% Ammonia 220kg traceability)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS barrels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        barrel_id TEXT UNIQUE NOT NULL,
        batch_id INTEGER NOT NULL,
        chemical_id INTEGER NOT NULL,
        original_quantity REAL NOT NULL DEFAULT 220.00,
        current_quantity REAL NOT NULL DEFAULT 220.00 CHECK(current_quantity >= 0),
        supplier_id INTEGER,
        received_date DATE NOT NULL,
        expiry_date DATE NOT NULL,
        storage_location_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'Full' CHECK(status IN ('Full', 'Partial', 'Empty / Consumed')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (batch_id) REFERENCES batches(id),
        FOREIGN KEY (chemical_id) REFERENCES chemicals(id),
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
        FOREIGN KEY (storage_location_id) REFERENCES storage_locations(id)
    );
    """)

    # 8. Barrel History Log
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS barrel_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        barrel_id TEXT NOT NULL,
        batch_number TEXT NOT NULL,
        action_date DATE NOT NULL,
        action_time TIME NOT NULL,
        original_quantity REAL NOT NULL,
        used_or_transferred_quantity REAL NOT NULL,
        remaining_quantity REAL NOT NULL,
        usage_purpose TEXT NOT NULL,
        supplier_customer_name TEXT,
        destination TEXT,
        reference_number TEXT,
        remarks TEXT,
        operator_name TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 9. Receipts / GRN
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS receipts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        grn_number TEXT UNIQUE NOT NULL,
        chemical_id INTEGER NOT NULL,
        batch_id INTEGER NOT NULL,
        supplier_id INTEGER NOT NULL,
        storage_location_id INTEGER NOT NULL,
        quantity REAL NOT NULL,
        unit TEXT NOT NULL DEFAULT 'kg',
        received_date DATE NOT NULL,
        manufacturing_date DATE,
        expiry_date DATE NOT NULL,
        invoice_number TEXT,
        remarks TEXT,
        created_by TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (chemical_id) REFERENCES chemicals(id),
        FOREIGN KEY (batch_id) REFERENCES batches(id),
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
        FOREIGN KEY (storage_location_id) REFERENCES storage_locations(id)
    );
    """)

    # 10. Usage Transactions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usage_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reference_number TEXT NOT NULL,
        date DATE NOT NULL,
        time TIME NOT NULL,
        chemical_id INTEGER NOT NULL,
        batch_id INTEGER NOT NULL,
        storage_location_id INTEGER NOT NULL,
        quantity_used REAL NOT NULL CHECK(quantity_used > 0),
        unit TEXT NOT NULL DEFAULT 'kg',
        purpose TEXT NOT NULL,
        supplier_customer_name TEXT,
        remarks TEXT,
        operator_name TEXT NOT NULL,
        is_reversed INTEGER DEFAULT 0,
        reversal_reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (chemical_id) REFERENCES chemicals(id),
        FOREIGN KEY (batch_id) REFERENCES batches(id),
        FOREIGN KEY (storage_location_id) REFERENCES storage_locations(id)
    );
    """)

    # 11. Stock Transfers
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stock_transfers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reference_number TEXT NOT NULL,
        date DATE NOT NULL,
        time TIME NOT NULL,
        chemical_id INTEGER NOT NULL,
        batch_id INTEGER NOT NULL,
        barrel_id TEXT,
        from_location_id INTEGER NOT NULL,
        to_location_id INTEGER NOT NULL,
        quantity REAL NOT NULL CHECK(quantity > 0),
        unit TEXT NOT NULL DEFAULT 'kg',
        purpose TEXT NOT NULL,
        remarks TEXT,
        operator_name TEXT NOT NULL,
        is_reversed INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (chemical_id) REFERENCES chemicals(id),
        FOREIGN KEY (batch_id) REFERENCES batches(id),
        FOREIGN KEY (from_location_id) REFERENCES storage_locations(id),
        FOREIGN KEY (to_location_id) REFERENCES storage_locations(id)
    );
    """)

    # 12. Dilution Transactions (10% Ammonia Preparation - EXACT 220kg + 385kg = 605kg)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dilution_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reference_number TEXT NOT NULL,
        production_date DATE NOT NULL,
        expiry_date DATE NOT NULL,
        source_25_batch_id INTEGER NOT NULL,
        source_barrel_id TEXT NOT NULL,
        source_quantity REAL NOT NULL DEFAULT 220.00 CHECK(source_quantity = 220.00),
        water_quantity REAL NOT NULL DEFAULT 385.00 CHECK(water_quantity = 385.00),
        produced_quantity REAL NOT NULL DEFAULT 605.00 CHECK(produced_quantity = 605.00),
        new_10_batch_id INTEGER NOT NULL,
        operator_name TEXT NOT NULL,
        remarks TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (source_25_batch_id) REFERENCES batches(id),
        FOREIGN KEY (new_10_batch_id) REFERENCES batches(id)
    );
    """)

    # 13. Daily Physical Stock Checks (Recorded every morning for Ammonia stores ONLY)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS daily_physical_stock (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date DATE NOT NULL,
        time TIME NOT NULL,
        storage_location_id INTEGER NOT NULL,
        chemical_id INTEGER NOT NULL,
        physical_quantity REAL NOT NULL,
        system_quantity REAL NOT NULL,
        variance REAL NOT NULL,
        unit TEXT NOT NULL DEFAULT 'kg',
        remarks TEXT,
        operator_name TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (storage_location_id) REFERENCES storage_locations(id),
        FOREIGN KEY (chemical_id) REFERENCES chemicals(id)
    );
    """)

    # 14. Stock Adjustments (Admin-only controlled adjustments)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stock_adjustments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chemical_id INTEGER NOT NULL,
        batch_id INTEGER NOT NULL,
        storage_location_id INTEGER NOT NULL,
        previous_quantity REAL NOT NULL,
        new_quantity REAL NOT NULL,
        variance REAL NOT NULL,
        unit TEXT NOT NULL DEFAULT 'kg',
        reason TEXT NOT NULL,
        operator_name TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (chemical_id) REFERENCES chemicals(id),
        FOREIGN KEY (batch_id) REFERENCES batches(id),
        FOREIGN KEY (storage_location_id) REFERENCES storage_locations(id)
    );
    """)

    # 15. Audit Logs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_name TEXT NOT NULL,
        action TEXT NOT NULL,
        transaction_type TEXT NOT NULL,
        record_id TEXT,
        details TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    seed_initial_data(conn)
    conn.close()

def seed_initial_data(conn):
    """Populates master entities and baseline records if missing."""
    cursor = conn.cursor()

    # 1. System Settings Defaults
    settings_data = [
        ("expiry_warning_days", "30", "Days before expiration to flag as Expiring Soon"),
        ("company_name", "Chemical Store Management System", "Organization / Application Title"),
        ("fixed_ammonia_source_qty", "220.00", "Locked 25% Ammonia barrel input for 10% dilution (kg)"),
        ("fixed_ammonia_water_qty", "385.00", "Locked purified water addition for 10% dilution (kg)"),
        ("fixed_ammonia_yield_qty", "605.00", "Locked 10% Ammonia output yield (kg)")
    ]
    for key, val, desc in settings_data:
        cursor.execute("INSERT OR IGNORE INTO system_settings (key, value, description) VALUES (?, ?, ?)", (key, val, desc))

    # 2. Users (Admin, Storekeeper, Viewer)
    users_data = [
        ("admin", hash_password("admin123"), "System Administrator", "admin@chemstore.internal", "Administrator"),
        ("storekeeper", hash_password("store123"), "Samitha K. (Storekeeper)", "storekeeper@chemstore.internal", "Storekeeper"),
        ("viewer", hash_password("view123"), "Audit Viewer", "viewer@chemstore.internal", "Viewer")
    ]
    for u, pwd, full_name, email, role in users_data:
        cursor.execute("INSERT OR IGNORE INTO users (username, password_hash, full_name, email, role) VALUES (?, ?, ?, ?, ?)",
                       (u, pwd, full_name, email, role))

    # 3. Storage Locations
    locations_data = [
        ("Main Chemical Store", "LOC-MCS", "Primary warehouse for dry & liquid compounding chemicals"),
        ("25% Ammonia Barrel Store", "LOC-AM25-BRL", "Dedicated storage warehouse for sealed 220kg 25% Ammonia barrels"),
        ("Ready-to-Use 25% Ammonia Store", "LOC-AM25-RTU", "Active unsealed dispensing day-tank store for 25% Ammonia"),
        ("10% Ammonia Store", "LOC-AM10", "Prepared 10% Ammonia batch storage tanks")
    ]
    for name, code, desc in locations_data:
        cursor.execute("INSERT OR IGNORE INTO storage_locations (name, code, description) VALUES (?, ?, ?)", (name, code, desc))

    # 4. Chemicals Master
    # Fetch location IDs
    cursor.execute("SELECT name, id FROM storage_locations")
    loc_map = {row["name"]: row["id"] for row in cursor.fetchall()}

    chemicals_data = [
        ("TMTD", "CHEM-TMTD", "kg", loc_map.get("Main Chemical Store"), 0, 200.0, "Tetramethylthiuram Disulfide compound"),
        ("Zinc Oxide", "CHEM-ZNO", "kg", loc_map.get("Main Chemical Store"), 0, 500.0, "Vulcanization activator powder"),
        ("Lauric Acid", "CHEM-LA", "kg", loc_map.get("Main Chemical Store"), 0, 150.0, "Latex stabilizer & surfactant"),
        ("DAHP", "CHEM-DAHP", "kg", loc_map.get("Main Chemical Store"), 0, 100.0, "Diammonium hydrogen phosphate coagulant"),
        ("Ammonia 25%", "CHEM-AM25", "kg", loc_map.get("25% Ammonia Barrel Store"), 1, 660.0, "Concentrated 25% Ammonia solution (220kg barrels)"),
        ("Ammonia 10%", "CHEM-AM10", "kg", loc_map.get("10% Ammonia Store"), 1, 600.0, "Diluted 10% Ammonia solution")
    ]
    for name, code, unit, loc_id, req_check, min_stock, desc in chemicals_data:
        cursor.execute("""
        INSERT OR IGNORE INTO chemicals (name, code, default_unit, storage_location_id, requires_daily_physical_check, min_stock_level, description)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, code, unit, loc_id, req_check, min_stock, desc))

    # 5. Suppliers & Customers
    suppliers_data = [
        ("Lanka Latex Supplies Ltd", "Nimal Fernando", "+94 11 234 5678", "sales@lankalatex.lk", "Industrial Zone, Colombo"),
        ("PetroChem Asia International", "David Zhang", "+65 6789 0123", "orders@petrochemasia.com", "Jurong Island, Singapore"),
        ("Global Polymer Additives Co.", "A. K. Perera", "+94 33 221 4455", "support@globalpolymer.lk", "Biyagama EPZ, Sri Lanka"),
        ("Oleochem Industries", "R. Wickramasinghe", "+94 11 443 2190", "info@oleochem.lk", "Kelaniya, Sri Lanka"),
        ("In-House Dilution Plant", "Internal Production", "+94 11 000 0000", "production@chemstore.internal", "On-site Preparation Vat")
    ]
    for name, cp, phone, email, addr in suppliers_data:
        cursor.execute("INSERT OR IGNORE INTO suppliers (name, contact_person, phone, email, address) VALUES (?, ?, ?, ?, ?)",
                       (name, cp, phone, email, addr))

    customers_data = [
        ("Latex Compounding Plant 1", "Operations Mgr", "+94 11 555 1001", "plant1@company.com", "Factory Wing A"),
        ("Latex Dipping Unit 2", "Production Lead", "+94 11 555 1002", "dipping@company.com", "Factory Wing B"),
        ("Direct Latex Supplier Transfer", "External Coordinator", "+94 77 123 4567", "latexsupply@partner.lk", "External Supply")
    ]
    for name, cp, phone, email, addr in customers_data:
        cursor.execute("INSERT OR IGNORE INTO customers (name, contact_person, phone, email, address) VALUES (?, ?, ?, ?, ?)",
                       (name, cp, phone, email, addr))

    # Check if baseline batches already exist
    cursor.execute("SELECT COUNT(*) as count FROM batches")
    if cursor.fetchone()["count"] == 0:
        # Seed realistic baseline batches with distinct batch numbers
        cursor.execute("SELECT name, id FROM chemicals")
        chem_map = {row["name"]: row["id"] for row in cursor.fetchall()}
        cursor.execute("SELECT name, id FROM suppliers")
        supp_map = {row["name"]: row["id"] for row in cursor.fetchall()}

        today = date.today()
        d_mfg_past = today - timedelta(days=60)
        d_exp_normal = today + timedelta(days=240)
        d_exp_soon = today + timedelta(days=18)
        d_exp_expired = today - timedelta(days=20)
        d_rcv_past = today - timedelta(days=30)

        # Baseline Batches
        batches_to_add = [
            # TMTD: Expiring soon batch (210 kg)
            (chem_map["TMTD"], "TMTD-2026-A1", str(d_mfg_past), str(d_exp_soon), str(d_rcv_past),
             supp_map["Global Polymer Additives Co."], loc_map["Main Chemical Store"], 500.0, 210.0, "kg", "Expiring Soon", "Baseline batch nearing expiry"),
            
            # Zinc Oxide: Active batch (740 kg)
            (chem_map["Zinc Oxide"], "ZNO-2026-99", str(d_mfg_past), str(d_exp_normal), str(d_rcv_past),
             supp_map["Global Polymer Additives Co."], loc_map["Main Chemical Store"], 1000.0, 740.0, "kg", "Valid", "Baseline stock"),

            # Lauric Acid: Active batch (180 kg)
            (chem_map["Lauric Acid"], "LA-2026-V1", str(d_mfg_past), str(d_exp_normal), str(d_rcv_past),
             supp_map["Oleochem Industries"], loc_map["Main Chemical Store"], 300.0, 180.0, "kg", "Valid", "Baseline stock"),

            # DAHP: Expired batch (45 kg)
            (chem_map["DAHP"], "DAHP-2025-X", str(d_mfg_past - timedelta(days=300)), str(d_exp_expired), str(d_rcv_past - timedelta(days=200)),
             supp_map["Global Polymer Additives Co."], loc_map["Main Chemical Store"], 250.0, 45.0, "kg", "Expired", "Quarantined expired stock"),

            # 25% Ammonia: Batch 1 (3 Barrels = 660 kg)
            (chem_map["Ammonia 25%"], "AM25-B001", str(d_mfg_past), str(d_exp_normal), str(d_rcv_past),
             supp_map["Lanka Latex Supplies Ltd"], loc_map["25% Ammonia Barrel Store"], 660.0, 660.0, "kg", "Valid", "Sealed 220kg barrels"),

            # 25% Ammonia: Batch 2 (3 Barrels = 660 kg)
            (chem_map["Ammonia 25%"], "AM25-B002", str(d_mfg_past), str(d_exp_normal), str(d_rcv_past),
             supp_map["PetroChem Asia International"], loc_map["25% Ammonia Barrel Store"], 660.0, 660.0, "kg", "Valid", "Sealed 220kg barrels"),

            # Ready-to-Use 25% Ammonia Store (180 kg from earlier opened barrel)
            (chem_map["Ammonia 25%"], "AM25-RTU-01", str(d_mfg_past), str(d_exp_normal), str(d_rcv_past),
             supp_map["Lanka Latex Supplies Ltd"], loc_map["Ready-to-Use 25% Ammonia Store"], 220.0, 180.0, "kg", "Valid", "Active unsealed day-tank stock"),

            # 10% Ammonia: Batch P101 (605 kg)
            (chem_map["Ammonia 10%"], "AM10-P101", str(today - timedelta(days=10)), str(today + timedelta(days=170)), str(today - timedelta(days=10)),
             supp_map["In-House Dilution Plant"], loc_map["10% Ammonia Store"], 605.0, 605.0, "kg", "Valid", "Prepared from AM25-B000"),

            # 10% Ammonia: Batch P102 (605 kg)
            (chem_map["Ammonia 10%"], "AM10-P102", str(today - timedelta(days=3)), str(today + timedelta(days=177)), str(today - timedelta(days=3)),
             supp_map["In-House Dilution Plant"], loc_map["10% Ammonia Store"], 605.0, 605.0, "kg", "Valid", "Prepared from AM25-B000")
        ]

        batch_id_map = {}
        for b in batches_to_add:
            cursor.execute("""
            INSERT INTO batches (chemical_id, batch_number, manufacturing_date, expiry_date, date_received,
                                 supplier_id, storage_location_id, received_quantity, current_quantity, unit, status, remarks)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, b)
            batch_id_map[b[1]] = cursor.lastrowid

        # Seed 6 Barrels of 25% Ammonia
        # 3 barrels for AM25-B001
        for i in range(1, 4):
            b_id = f"AM25-BRL-00{i}"
            cursor.execute("""
            INSERT INTO barrels (barrel_id, batch_id, chemical_id, original_quantity, current_quantity, supplier_id, received_date, expiry_date, storage_location_id, status)
            VALUES (?, ?, ?, 220.00, 220.00, ?, ?, ?, ?, 'Full')
            """, (b_id, batch_id_map["AM25-B001"], chem_map["Ammonia 25%"], supp_map["Lanka Latex Supplies Ltd"], str(d_rcv_past), str(d_exp_normal), loc_map["25% Ammonia Barrel Store"]))

        # 3 barrels for AM25-B002
        for i in range(4, 7):
            b_id = f"AM25-BRL-00{i}"
            cursor.execute("""
            INSERT INTO barrels (barrel_id, batch_id, chemical_id, original_quantity, current_quantity, supplier_id, received_date, expiry_date, storage_location_id, status)
            VALUES (?, ?, ?, 220.00, 220.00, ?, ?, ?, ?, 'Full')
            """, (b_id, batch_id_map["AM25-B002"], chem_map["Ammonia 25%"], supp_map["PetroChem Asia International"], str(d_rcv_past), str(d_exp_normal), loc_map["25% Ammonia Barrel Store"]))

        # Seed baseline usage transactions
        cursor.execute("""
        INSERT INTO usage_transactions (reference_number, date, time, chemical_id, batch_id, storage_location_id, quantity_used, unit, purpose, supplier_customer_name, remarks, operator_name)
        VALUES ('USG-2026-081', ?, '08:30:00', ?, ?, ?, 15.0, 'kg', 'Compounding Line A', 'Factory Wing A', 'Standard compound batch', 'Samitha K. (Storekeeper)')
        """, (str(today), chem_map["TMTD"], batch_id_map["TMTD-2026-A1"], loc_map["Main Chemical Store"]))

        cursor.execute("""
        INSERT INTO usage_transactions (reference_number, date, time, chemical_id, batch_id, storage_location_id, quantity_used, unit, purpose, supplier_customer_name, remarks, operator_name)
        VALUES ('USG-2026-080', ?, '14:15:00', ?, ?, ?, 25.0, 'kg', 'Vulcanization Batch 12', 'Factory Wing B', 'Regular run dosage', 'Samitha K. (Storekeeper)')
        """, (str(today - timedelta(days=1)), chem_map["Zinc Oxide"], batch_id_map["ZNO-2026-99"], loc_map["Main Chemical Store"]))

        # Seed baseline morning physical stock check for ammonia stores
        cursor.execute("""
        INSERT INTO daily_physical_stock (date, time, storage_location_id, chemical_id, physical_quantity, system_quantity, variance, unit, remarks, operator_name)
        VALUES (?, '07:45:00', ?, ?, 1320.0, 1320.0, 0.0, 'kg', 'All 6 unopened 220kg barrels verified intact', 'Samitha K. (Storekeeper)')
        """, (str(today), loc_map["25% Ammonia Barrel Store"], chem_map["Ammonia 25%"]))

        cursor.execute("""
        INSERT INTO daily_physical_stock (date, time, storage_location_id, chemical_id, physical_quantity, system_quantity, variance, unit, remarks, operator_name)
        VALUES (?, '07:45:00', ?, ?, 180.0, 180.0, 0.0, 'kg', 'Ready day-tank level sensor reading confirmed', 'Samitha K. (Storekeeper)')
        """, (str(today), loc_map["Ready-to-Use 25% Ammonia Store"], chem_map["Ammonia 25%"]))

        cursor.execute("""
        INSERT INTO daily_physical_stock (date, time, storage_location_id, chemical_id, physical_quantity, system_quantity, variance, unit, remarks, operator_name)
        VALUES (?, '07:45:00', ?, ?, 1210.0, 1210.0, 0.0, 'kg', 'Tank 1 (605kg) & Tank 2 (605kg) verified', 'Samitha K. (Storekeeper)')
        """, (str(today), loc_map["10% Ammonia Store"], chem_map["Ammonia 10%"]))

        # Initial Audit Log
        cursor.execute("""
        INSERT INTO audit_logs (user_name, action, transaction_type, record_id, details)
        VALUES ('System', 'Initialization', 'System Setup', '0', 'Chemical Store Management System relational database initialized with baseline records.')
        """)

    conn.commit()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)
