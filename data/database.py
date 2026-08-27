import os
import sqlite3
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "merchantmesh.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;") # Enable WAL mode for high concurrency
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Merchants Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS merchants (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        phone_number TEXT UNIQUE NOT NULL,
        reliability_score REAL DEFAULT 5.0,
        merchant_dna_json TEXT, -- stores "Generous", "Firm", categories, etc.
        api_key TEXT DEFAULT 'merchant_key_demo',
        razorpay_account_id TEXT, -- Real Razorpay Route Linked Account ID (e.g. acc_LKd89FmN...)
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 2. Buyers Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS buyers (
        id TEXT PRIMARY KEY,
        phone_number TEXT UNIQUE NOT NULL,
        buyer_trust_score REAL DEFAULT 5.0,
        return_rate REAL DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 3. Products Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id TEXT PRIMARY KEY,
        merchant_id TEXT NOT NULL,
        product_name TEXT NOT NULL,
        category TEXT,
        search_tags_json TEXT,
        sizes_json TEXT,
        listed_price INTEGER CHECK(listed_price >= 0),
        floor_price INTEGER CHECK(floor_price >= 0),
        stock_quantity INTEGER DEFAULT 0 CHECK(stock_quantity >= 0),
        image_path TEXT,
        is_prohibited BOOLEAN DEFAULT 0,
        confidence_score REAL DEFAULT 100.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        stock_last_confirmed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (merchant_id) REFERENCES merchants (id) ON DELETE CASCADE
    )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_sessions (
            session_id TEXT PRIMARY KEY,
            chat_data TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 4. Negotiations Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS negotiations (
        id TEXT PRIMARY KEY,
        product_id TEXT NOT NULL,
        buyer_id TEXT NOT NULL,
        quantity INTEGER DEFAULT 1,
        turns_json TEXT NOT NULL, 
        final_price INTEGER,
        outcome TEXT, 
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE,
        FOREIGN KEY (buyer_id) REFERENCES buyers (id) ON DELETE CASCADE
    )
    ''')

    # 5. Orders Table (With explicit state transitions and settlement lifecycle)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id TEXT PRIMARY KEY,
        negotiation_id TEXT,
        product_id TEXT NOT NULL,
        merchant_id TEXT NOT NULL,
        buyer_id TEXT NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1 CHECK(quantity > 0),
        amount INTEGER NOT NULL CHECK(amount > 0),
        payment_status TEXT NOT NULL DEFAULT 'AWAITING_MERCHANT' CHECK(payment_status IN (
            'NEGOTIATED', 'AWAITING_MERCHANT', 'PENDING_PAYMENT', 'PAYMENT_LINK_RECONCILIATION_REQUIRED', 'PAID', 'EXPIRED', 'TIMEOUT_EXPIRED', 'REJECTED_BY_MERCHANT', 'CANCELLED', 'PAYMENT_RECONCILIATION_REQUIRED'
        )),
        settlement_status TEXT NOT NULL DEFAULT 'PENDING_SETTLEMENT' CHECK(settlement_status IN (
            'NOT_APPLICABLE', 'PENDING_SETTLEMENT', 'SETTLEMENT_IN_PROGRESS', 'SETTLEMENT_RECONCILIATION_REQUIRED', 'SETTLED', 'SETTLEMENT_FAILED', 'REFUND_PENDING', 'REFUNDED'
        )),
        payment_link_id TEXT,
        payment_link_url TEXT,
        payment_id TEXT,
        merchant_confirmed INTEGER DEFAULT 0,
        expires_at TIMESTAMP,
        confirmation_expires_at TIMESTAMP,
        settlement_started_at TIMESTAMP,
        settlement_attempt_id TEXT,
        settlement_error TEXT,
        unboxing_video_url TEXT,
        dispute_status TEXT DEFAULT 'NONE',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (negotiation_id) REFERENCES negotiations (id) ON DELETE SET NULL,
        FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE RESTRICT,
        FOREIGN KEY (merchant_id) REFERENCES merchants (id) ON DELETE RESTRICT,
        FOREIGN KEY (buyer_id) REFERENCES buyers (id) ON DELETE RESTRICT
    )
    ''')

    # Safe dynamic schema migration for existing databases
    cursor.execute("PRAGMA table_info(orders)")
    existing_cols = {row["name"]: row for row in cursor.fetchall()}

    # Migration from legacy escrow_status -> settlement_status
    if "settlement_status" not in existing_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN settlement_status TEXT DEFAULT 'PENDING_SETTLEMENT'")
        if "escrow_status" in existing_cols:
            cursor.execute("""
                UPDATE orders 
                SET settlement_status = CASE 
                    WHEN escrow_status = 'RELEASED' THEN 'SETTLED'
                    WHEN escrow_status = 'REFUNDED' THEN 'REFUNDED'
                    ELSE 'PENDING_SETTLEMENT'
                END
            """)

    if "confirmation_expires_at" not in existing_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN confirmation_expires_at TIMESTAMP")
        from datetime import timezone
        default_deadline = (datetime.now(timezone.utc) + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "UPDATE orders SET confirmation_expires_at = ? WHERE payment_status = 'AWAITING_MERCHANT' AND confirmation_expires_at IS NULL",
            (default_deadline,)
        )

    new_order_cols = [
        ("product_id", "TEXT"),
        ("merchant_id", "TEXT"),
        ("buyer_id", "TEXT"),
        ("quantity", "INTEGER DEFAULT 1"),
        ("amount", "INTEGER"),
        ("payment_link_id", "TEXT"),
        ("payment_link_url", "TEXT"),
        ("payment_id", "TEXT"),
        ("merchant_confirmed", "INTEGER DEFAULT 0"),
        ("expires_at", "TIMESTAMP"),
        ("confirmation_expires_at", "TIMESTAMP"),
        ("settlement_started_at", "TIMESTAMP"),
        ("settlement_attempt_id", "TEXT"),
        ("settlement_error", "TEXT"),
        ("created_at", "TIMESTAMP"),
        ("updated_at", "TIMESTAMP")
    ]
    for col_name, col_type in new_order_cols:
        if col_name not in existing_cols and col_name not in ["settlement_status"]:
            cursor.execute(f"ALTER TABLE orders ADD COLUMN {col_name} {col_type}")

    # Dynamic migration for negotiations table
    cursor.execute("PRAGMA table_info(negotiations)")
    neg_cols = {row["name"]: row for row in cursor.fetchall()}
    if "quantity" not in neg_cols:
        cursor.execute("ALTER TABLE negotiations ADD COLUMN quantity INTEGER DEFAULT 1")

    # 6. Stock Reservations Table (For concurrency-safe 15-minute checkout windows)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS stock_reservations (
        id TEXT PRIMARY KEY,
        order_id TEXT NOT NULL UNIQUE,
        product_id TEXT NOT NULL,
        quantity INTEGER NOT NULL CHECK(quantity > 0),
        status TEXT NOT NULL CHECK(status IN ('ACTIVE', 'CONSUMED', 'EXPIRED')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
    )
    ''')

    # 7. Webhook Events Table (For strict at-most-once payment idempotency & payload binding)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS webhook_events (
        event_id TEXT PRIMARY KEY,
        payload_hash TEXT,
        event_type TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('RECEIVED', 'PROCESSING', 'PROCESSED', 'FAILED')),
        received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        processed_at TIMESTAMP
    )
    ''')

    cursor.execute("PRAGMA table_info(webhook_events)")
    webhook_cols = {row["name"]: row for row in cursor.fetchall()}
    if "payload_hash" not in webhook_cols:
        cursor.execute("ALTER TABLE webhook_events ADD COLUMN payload_hash TEXT")

    # Dynamic schema migration for merchants
    cursor.execute("PRAGMA table_info(merchants)")
    merchant_cols = {row["name"]: row for row in cursor.fetchall()}
    if "api_key" not in merchant_cols:
        cursor.execute("ALTER TABLE merchants ADD COLUMN api_key TEXT")
    if "razorpay_account_id" not in merchant_cols:
        cursor.execute("ALTER TABLE merchants ADD COLUMN razorpay_account_id TEXT")

    # 8. Outbox Events Table (For crash-durable, idempotent timeout side-effect execution)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS outbox_events (
        id TEXT PRIMARY KEY,
        event_key TEXT UNIQUE NOT NULL,
        event_type TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('PENDING', 'PROCESSING', 'PROCESSED', 'FAILED')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        processed_at TIMESTAMP
    )
    ''')

    # 9. Merchant Settlements Table (Real Razorpay Route / Transfer split ledger)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS merchant_settlements (
        id TEXT PRIMARY KEY,
        order_id TEXT NOT NULL UNIQUE,
        merchant_id TEXT NOT NULL,
        payment_id TEXT NOT NULL,
        idempotency_key TEXT UNIQUE,
        gross_amount INTEGER NOT NULL,
        platform_fee INTEGER NOT NULL,
        net_payout INTEGER NOT NULL,
        razorpay_transfer_id TEXT,
        settlement_status TEXT NOT NULL CHECK(settlement_status IN ('INITIATED', 'SETTLED', 'FAILED')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        settled_at TIMESTAMP,
        FOREIGN KEY (order_id) REFERENCES orders (id),
        FOREIGN KEY (merchant_id) REFERENCES merchants (id)
    )
    ''')

    cursor.execute("PRAGMA table_info(merchant_settlements)")
    settlement_cols = {row["name"]: row for row in cursor.fetchall()}
    if "payment_id" not in settlement_cols:
        cursor.execute("ALTER TABLE merchant_settlements ADD COLUMN payment_id TEXT DEFAULT ''")
    if "idempotency_key" not in settlement_cols:
        cursor.execute("ALTER TABLE merchant_settlements ADD COLUMN idempotency_key TEXT")

    # 10. Audit Log
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT NOT NULL, 
        agent TEXT NOT NULL,
        reasoning TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 11. Search Trends Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS search_trends (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query TEXT NOT NULL,
        category_intent TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Dynamic schema migration for session_id isolation
    cursor.execute("PRAGMA table_info(products)")
    prod_cols = {row["name"]: row for row in cursor.fetchall()}
    if "session_id" not in prod_cols:
        cursor.execute("ALTER TABLE products ADD COLUMN session_id TEXT")

    if "session_id" not in merchant_cols:
        cursor.execute("ALTER TABLE merchants ADD COLUMN session_id TEXT")

    if "session_id" not in existing_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN session_id TEXT")

    cursor.execute("PRAGMA table_info(negotiations)")
    neg_cols = {row["name"]: row for row in cursor.fetchall()}

    if "session_id" not in neg_cols:
        cursor.execute("ALTER TABLE negotiations ADD COLUMN session_id TEXT")
        
    if "merchant_id" not in neg_cols:
        cursor.execute("ALTER TABLE negotiations ADD COLUMN merchant_id TEXT")


    # 12. Performance Indices
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(payment_status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_merchant ON orders(merchant_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reservations_lookup ON stock_reservations(product_id, status, expires_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_webhook_events_status ON webhook_events(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_session ON products(session_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_session ON orders(session_id);")
    
    # New Backend Hardening Indices
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_merchant ON products(merchant_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_negotiations_session ON negotiations(session_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_negotiations_merchant ON negotiations(merchant_id);")

    conn.commit()
    conn.close()
    print("✅ Database schema initialized successfully with fintech constraints and session isolation!")

if __name__ == "__main__":
    init_db()
