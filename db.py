# db.py
# طبقة قاعدة البيانات SQLite (متوافق 100% مع Pydroid3 + Termux)
# ملاحظة مهمة: يوجد init_db واحدة فقط لتجنب ضياع الجداول (مثل balance)

import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Optional, Tuple, List, Dict, Any

DB_PATH = "bot.db"
_db_lock = threading.Lock()


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        yield conn
        conn.commit()
    finally:
        conn.close()


def add_referrer_column():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
    ALTER TABLE users ADD COLUMN referrer_id INTEGER DEFAULT NULL
    """)
    conn.commit()



def _ensure_accounts_schema(conn: sqlite3.Connection) -> None:
    cols = conn.execute("PRAGMA table_info(accounts)").fetchall()
    col_names = {c["name"] for c in cols} if cols else set()
    if not col_names:
        return
    if "price" not in col_names:
        conn.execute("ALTER TABLE accounts ADD COLUMN price REAL NOT NULL DEFAULT 0")
    if "added_by" not in col_names:
        conn.execute("ALTER TABLE accounts ADD COLUMN added_by INTEGER NOT NULL DEFAULT 0")


def init_db() -> None:
    """
    إنشاء كل الجداول الأساسية + جداول الإيميل + جداول المشتركين + جداول (وصّينا)
    """
    with _db_lock, _connect() as conn:
        # =========================
        # Core tables (بوت الأرقام)
        # =========================
        conn.execute("""
        CREATE TABLE IF NOT EXISTS balance (
            user_id INTEGER PRIMARY KEY,
            balance REAL NOT NULL DEFAULT 0
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            email TEXT,
            username TEXT,
            password TEXT,
            price REAL NOT NULL DEFAULT 0,
            added_by INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL
        )
        """)
        _ensure_accounts_schema(conn)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS services (
            name TEXT PRIMARY KEY,
            code TEXT NOT NULL,
            price REAL NOT NULL,
            country TEXT
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS services_uk (
            name TEXT PRIMARY KEY,
            code TEXT NOT NULL,
            price REAL NOT NULL,
            country TEXT
        )
        """)

        # =========================
        # Temp Email (mail.tm)
        # =========================
        conn.execute("""
        CREATE TABLE IF NOT EXISTS temp_email (
            user_id INTEGER PRIMARY KEY,
            email TEXT NOT NULL,
            token TEXT NOT NULL,
            charged INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL
        )
        """)

        # =========================
        # Users (اسماء المشتركين)
        # =========================
        conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            joined_at INTEGER NOT NULL,
            last_seen INTEGER NOT NULL
        )
        """)

        # =========================
        # Waseena (وصّينا)
        # =========================
        conn.execute("""
        CREATE TABLE IF NOT EXISTS driver_requests (
            user_id INTEGER PRIMARY KEY,
            note TEXT,
            status TEXT NOT NULL DEFAULT 'pending',  -- pending/approved/rejected
            created_at INTEGER NOT NULL
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS drivers (
            user_id INTEGER PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'active',   -- active/blocked
            created_at INTEGER NOT NULL
        )
        """)
        
        _ensure_drivers_schema(conn) 

        conn.execute("""
        CREATE TABLE IF NOT EXISTS stores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,                     -- restaurant/mall
            name TEXT NOT NULL,
            owner_driver_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',  -- pending/active/blocked
            created_at INTEGER NOT NULL
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_id INTEGER NOT NULL,
            added_by_driver_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            real_price REAL NOT NULL,
            final_price REAL NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at INTEGER NOT NULL,
            FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            store_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            qty INTEGER NOT NULL DEFAULT 1,
            address_text TEXT NOT NULL,

            -- Snapshot prices وقت الطلب
            real_price REAL NOT NULL DEFAULT 0,
            final_price REAL NOT NULL DEFAULT 0,

            -- Finance (يُحسب عند التسليم)
            profit_total REAL NOT NULL DEFAULT 0,
            bot_cut REAL NOT NULL DEFAULT 0,
            driver_cut REAL NOT NULL DEFAULT 0,
            bot_cut_rate REAL NOT NULL DEFAULT 0,

            status TEXT NOT NULL DEFAULT 'pending', -- pending/accepted/delivered/canceled
            driver_id INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL,
            accepted_at INTEGER NOT NULL DEFAULT 0,
            delivered_at INTEGER NOT NULL DEFAULT 0,
            delivered_confirmed INTEGER NOT NULL DEFAULT 0
        )
        """)


# =========================
# Balance
# =========================

def register_user(user_id: int, is_admin: bool = False) -> None:
    initial = -1.0 if is_admin else 0.0
    with _db_lock, _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO balance (user_id, balance) VALUES (?, ?)",
            (int(user_id), float(initial)),
        )


def get_balance(user_id: int) -> float:
    with _db_lock, _connect() as conn:
        row = conn.execute("SELECT balance FROM balance WHERE user_id=?", (int(user_id),)).fetchone()
        return float(row["balance"]) if row else 0.0


def set_balance(user_id: int, new_balance: float) -> None:
    with _db_lock, _connect() as conn:
        conn.execute(
            "INSERT INTO balance (user_id, balance) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET balance=excluded.balance",
            (int(user_id), float(new_balance)),
        )


def add_balance(user_id: int, delta: float) -> float:
    with _db_lock, _connect() as conn:
        conn.execute("INSERT OR IGNORE INTO balance (user_id, balance) VALUES (?, 0)", (int(user_id),))
        conn.execute("UPDATE balance SET balance = balance + ? WHERE user_id=?", (float(delta), int(user_id)))
        row = conn.execute("SELECT balance FROM balance WHERE user_id=?", (int(user_id),)).fetchone()
        return float(row["balance"]) if row else 0.0


def transfer_balance(sender_id: int, recipient_id: int, amount: float) -> Tuple[bool, str]:
    if amount <= 0:
        return False, "Amount must be positive."

    with _db_lock, _connect() as conn:
        conn.execute("INSERT OR IGNORE INTO balance (user_id, balance) VALUES (?, 0)", (int(sender_id),))
        conn.execute("INSERT OR IGNORE INTO balance (user_id, balance) VALUES (?, 0)", (int(recipient_id),))

        s = conn.execute("SELECT balance FROM balance WHERE user_id=?", (int(sender_id),)).fetchone()
        r = conn.execute("SELECT balance FROM balance WHERE user_id=?", (int(recipient_id),)).fetchone()

        sender_balance = float(s["balance"]) if s else 0.0
        recipient_balance = float(r["balance"]) if r else 0.0

        if sender_balance != -1.0 and sender_balance < amount:
            return False, "Insufficient balance."

        if sender_balance != -1.0:
            sender_balance -= amount

        recipient_balance += amount

        conn.execute("UPDATE balance SET balance=? WHERE user_id=?", (float(sender_balance), int(sender_id)))
        conn.execute("UPDATE balance SET balance=? WHERE user_id=?", (float(recipient_balance), int(recipient_id)))
        return True, "OK"


# =========================
# Users profiles (اسماء المشتركين)
# =========================

def upsert_user_profile(user_id: int, username: str = "", first_name: str = "", last_name: str = "") -> None:
    now = int(time.time())
    with _db_lock, _connect() as conn:
        conn.execute("""
            INSERT INTO users (user_id, username, first_name, last_name, joined_at, last_seen)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                last_name=excluded.last_name,
                last_seen=excluded.last_seen
        """, (int(user_id), str(username or ""), str(first_name or ""), str(last_name or ""), now, now))


def touch_user_seen(user_id: int) -> None:
    now = int(time.time())
    with _db_lock, _connect() as conn:
        conn.execute("UPDATE users SET last_seen=? WHERE user_id=?", (now, int(user_id)))


def list_last_users(limit: int = 10) -> List[Dict[str, Any]]:
    with _db_lock, _connect() as conn:
        rows = conn.execute("""
            SELECT user_id, username, first_name, last_name, joined_at, last_seen
            FROM users
            ORDER BY last_seen DESC
            LIMIT ?
        """, (int(limit),)).fetchall()
        return [dict(r) for r in rows]


def search_users(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    q = (query or "").strip()
    if not q:
        return []
    with _db_lock, _connect() as conn:
        if q.isdigit():
            rows = conn.execute("""
                SELECT user_id, username, first_name, last_name, joined_at, last_seen
                FROM users
                WHERE user_id=?
                LIMIT ?
            """, (int(q), int(limit))).fetchall()
            if rows:
                return [dict(r) for r in rows]

        like = f"%{q}%"
        rows = conn.execute("""
            SELECT user_id, username, first_name, last_name, joined_at, last_seen
            FROM users
            WHERE username LIKE ?
               OR first_name LIKE ?
               OR last_name LIKE ?
            ORDER BY last_seen DESC
            LIMIT ?
        """, (like, like, like, int(limit))).fetchall()
        return [dict(r) for r in rows]


# =========================
# Accounts (Sell accounts)
# =========================

def add_account(platform: str, email: str, username: str, password: str, price: float, created_at: int, added_by: int = 0) -> None:
    platform = platform.strip().lower()
    with _db_lock, _connect() as conn:
        _ensure_accounts_schema(conn)
        conn.execute(
            "INSERT INTO accounts (platform, email, username, password, price, added_by, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (platform, email, username, password, float(price), int(added_by), int(created_at)),
        )


def peek_account(platform: str) -> Optional[Dict[str, Any]]:
    platform = platform.strip().lower()
    with _db_lock, _connect() as conn:
        _ensure_accounts_schema(conn)
        row = conn.execute(
            "SELECT * FROM accounts WHERE platform=? ORDER BY id ASC LIMIT 1",
            (platform,),
        ).fetchone()
        if not row:
            return None
        return {
            "platform": row["platform"],
            "email": row["email"],
            "username": row["username"],
            "password": row["password"],
            "price": float(row["price"]) if "price" in row.keys() else 0.0,
            "added_by": int(row["added_by"]) if "added_by" in row.keys() else 0,
        }


def pop_account(platform: str) -> Optional[Dict[str, Any]]:
    platform = platform.strip().lower()
    with _db_lock, _connect() as conn:
        _ensure_accounts_schema(conn)
        row = conn.execute(
            "SELECT * FROM accounts WHERE platform=? ORDER BY id ASC LIMIT 1",
            (platform,),
        ).fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM accounts WHERE id=?", (int(row["id"]),))
        return {
            "platform": row["platform"],
            "email": row["email"],
            "username": row["username"],
            "password": row["password"],
            "price": float(row["price"]) if "price" in row.keys() else 0.0,
            "added_by": int(row["added_by"]) if "added_by" in row.keys() else 0,
        }


# =========================
# Temp Email (One active per user)
# =========================

def set_active_temp_email(user_id: int, email: str, token: str) -> None:
    with _db_lock, _connect() as conn:
        conn.execute(
            "INSERT INTO temp_email (user_id, email, token, charged, created_at) VALUES (?, ?, ?, 0, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET email=excluded.email, token=excluded.token, charged=0, created_at=excluded.created_at",
            (int(user_id), str(email), str(token), int(time.time())),
        )


def get_active_temp_email(user_id: int) -> Optional[Dict[str, Any]]:
    with _db_lock, _connect() as conn:
        row = conn.execute(
            "SELECT user_id, email, token, charged, created_at FROM temp_email WHERE user_id=?",
            (int(user_id),),
        ).fetchone()
        if not row:
            return None
        return {
            "user_id": int(row["user_id"]),
            "email": str(row["email"]),
            "token": str(row["token"]),
            "charged": int(row["charged"]),
            "created_at": int(row["created_at"]),
        }


def mark_temp_email_charged(user_id: int) -> None:
    with _db_lock, _connect() as conn:
        conn.execute("UPDATE temp_email SET charged=1 WHERE user_id=?", (int(user_id),))


def clear_active_temp_email(user_id: int) -> None:
    with _db_lock, _connect() as conn:
        conn.execute("DELETE FROM temp_email WHERE user_id=?", (int(user_id),))


# =========================
# Services (optional)
# =========================

def upsert_service(name: str, code: str, price: float, country: Optional[str] = None, uk: bool = False) -> None:
    table = "services_uk" if uk else "services"
    with _db_lock, _connect() as conn:
        conn.execute(
            f"INSERT INTO {table} (name, code, price, country) VALUES (?, ?, ?, ?) "
            f"ON CONFLICT(name) DO UPDATE SET code=excluded.code, price=excluded.price, country=excluded.country",
            (name, code, float(price), country),
        )


def list_services(uk: bool = False) -> List[Dict[str, Any]]:
    table = "services_uk" if uk else "services"
    with _db_lock, _connect() as conn:
        rows = conn.execute(f"SELECT name, code, price, country FROM {table} ORDER BY name ASC").fetchall()
        return [dict(r) for r in rows]




def _ensure_column(conn: sqlite3.Connection, table: str, col: str, ddl: str) -> None:
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    names = {c["name"] for c in cols} if cols else set()
    if col not in names:
        conn.execute(ddl)

def _ensure_waseena_orders_schema(conn: sqlite3.Connection) -> None:
    _ensure_column(conn, "orders", "real_price", "ALTER TABLE orders ADD COLUMN real_price REAL NOT NULL DEFAULT 0")
    _ensure_column(conn, "orders", "final_price", "ALTER TABLE orders ADD COLUMN final_price REAL NOT NULL DEFAULT 0")
    _ensure_column(conn, "orders", "profit_total", "ALTER TABLE orders ADD COLUMN profit_total REAL NOT NULL DEFAULT 0")
    _ensure_column(conn, "orders", "bot_cut", "ALTER TABLE orders ADD COLUMN bot_cut REAL NOT NULL DEFAULT 0")
    _ensure_column(conn, "orders", "driver_cut", "ALTER TABLE orders ADD COLUMN driver_cut REAL NOT NULL DEFAULT 0")
    _ensure_column(conn, "orders", "bot_cut_rate", "ALTER TABLE orders ADD COLUMN bot_cut_rate REAL NOT NULL DEFAULT 0")
    _ensure_column(conn, "orders", "delivered_confirmed", "ALTER TABLE orders ADD COLUMN delivered_confirmed INTEGER NOT NULL DEFAULT 0")





# =========================
# Waseena (وصّينا)
# =========================

def request_driver_join(user_id: int, note: str = "") -> None:
    with _db_lock, _connect() as conn:
        conn.execute(
            "INSERT INTO driver_requests (user_id, note, status, created_at) "
            "VALUES (?, ?, 'pending', ?) "
            "ON CONFLICT(user_id) DO UPDATE SET note=excluded.note, status='pending', created_at=excluded.created_at",
            (int(user_id), str(note), int(time.time())),
        )


def list_driver_requests(status: str = "pending") -> List[Dict[str, Any]]:
    with _db_lock, _connect() as conn:
        rows = conn.execute(
            "SELECT user_id, note, status, created_at FROM driver_requests WHERE status=? ORDER BY created_at DESC",
            (str(status),),
        ).fetchall()
        return [dict(r) for r in rows]


def driver_is_busy(driver_id: int) -> bool:
    with _db_lock, _connect() as conn:
        row = conn.execute(
            "SELECT busy FROM drivers WHERE user_id=?",
            (int(driver_id),)
        ).fetchone()
        return bool(row and int(row["busy"] or 0) == 1)


def approve_driver(user_id: int) -> None:
    with _db_lock, _connect() as conn:
        conn.execute("UPDATE driver_requests SET status='approved' WHERE user_id=?", (int(user_id),))
        conn.execute(
            "INSERT INTO drivers (user_id, status, created_at) VALUES (?, 'active', ?) "
            "ON CONFLICT(user_id) DO UPDATE SET status='active'",
            (int(user_id), int(time.time())),
        )
        # مهم: اجعل السائق غير مشغول عند التفعيل
        conn.execute("UPDATE drivers SET busy=0 WHERE user_id=?", (int(user_id),))


def reject_driver(user_id: int) -> None:
    with _db_lock, _connect() as conn:
        conn.execute("UPDATE driver_requests SET status='rejected' WHERE user_id=?", (int(user_id),))


def is_driver_active(user_id: int) -> bool:
    with _db_lock, _connect() as conn:
        row = conn.execute("SELECT status FROM drivers WHERE user_id=?", (int(user_id),)).fetchone()
        return bool(row and str(row["status"]) == "active")
        
        


def block_driver(user_id: int) -> None:
    with _db_lock, _connect() as conn:
        conn.execute(
            "INSERT INTO drivers (user_id, status, created_at) VALUES (?, 'blocked', ?) "
            "ON CONFLICT(user_id) DO UPDATE SET status='blocked'",
            (int(user_id), int(time.time())),
        )


def list_drivers(status: str = "active") -> List[Dict[str, Any]]:
    with _db_lock, _connect() as conn:
        rows = conn.execute(
            "SELECT user_id, status, created_at FROM drivers WHERE status=? ORDER BY created_at DESC",
            (str(status),),
        ).fetchall()
        return [dict(r) for r in rows]


def add_store(store_type: str, name: str, owner_driver_id: int) -> int:
    store_type = store_type.strip().lower()
    with _db_lock, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO stores (type, name, owner_driver_id, status, created_at) VALUES (?, ?, ?, 'pending', ?)",
            (store_type, str(name).strip(), int(owner_driver_id), int(time.time())),
        )
        return int(cur.lastrowid)


def list_stores(store_type: str, status: str = "active") -> List[Dict[str, Any]]:
    store_type = store_type.strip().lower()
    with _db_lock, _connect() as conn:
        rows = conn.execute(
            "SELECT id, type, name, owner_driver_id, status, created_at FROM stores "
            "WHERE type=? AND status=? ORDER BY id DESC",
            (store_type, str(status)),
        ).fetchall()
        return [dict(r) for r in rows]


def list_driver_stores(owner_driver_id: int, store_type: Optional[str] = None) -> List[Dict[str, Any]]:
    with _db_lock, _connect() as conn:
        if store_type:
            rows = conn.execute(
                "SELECT id, type, name, owner_driver_id, status, created_at FROM stores "
                "WHERE owner_driver_id=? AND type=? ORDER BY id DESC",
                (int(owner_driver_id), store_type.strip().lower()),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, type, name, owner_driver_id, status, created_at FROM stores "
                "WHERE owner_driver_id=? ORDER BY id DESC",
                (int(owner_driver_id),),
            ).fetchall()
        return [dict(r) for r in rows]


def list_pending_stores(limit: int = 20) -> List[Dict[str, Any]]:
    with _db_lock, _connect() as conn:
        rows = conn.execute(
            "SELECT id, type, name, owner_driver_id, status, created_at FROM stores "
            "WHERE status='pending' ORDER BY created_at ASC LIMIT ?",
            (int(limit),),
        ).fetchall()
        return [dict(r) for r in rows]


def approve_store(store_id: int) -> None:
    with _db_lock, _connect() as conn:
        conn.execute("UPDATE stores SET status='active' WHERE id=?", (int(store_id),))


def block_store(store_id: int) -> None:
    with _db_lock, _connect() as conn:
        conn.execute("UPDATE stores SET status='blocked' WHERE id=?", (int(store_id),))


def add_product(store_id: int, driver_id: int, name: str, real_price: float, final_price: float) -> int:
    with _db_lock, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO products (store_id, added_by_driver_id, name, real_price, final_price, is_active, created_at) "
            "VALUES (?, ?, ?, ?, ?, 1, ?)",
            (int(store_id), int(driver_id), str(name).strip(), float(real_price), float(final_price), int(time.time())),
        )
        return int(cur.lastrowid)


def list_products(store_id: int, only_active: bool = True) -> List[Dict[str, Any]]:
    with _db_lock, _connect() as conn:
        if only_active:
            rows = conn.execute(
                "SELECT id, store_id, name, real_price, final_price, is_active FROM products "
                "WHERE store_id=? AND is_active=1 ORDER BY id DESC",
                (int(store_id),),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, store_id, name, real_price, final_price, is_active FROM products "
                "WHERE store_id=? ORDER BY id DESC",
                (int(store_id),),
            ).fetchall()
        return [dict(r) for r in rows]


def deactivate_product(product_id: int) -> None:
    with _db_lock, _connect() as conn:
        conn.execute("UPDATE products SET is_active=0 WHERE id=?", (int(product_id),))


def create_order(user_id: int, store_id: int, product_id: int, qty: int, address_text: str,
                 real_price: float, final_price: float) -> int:
    with _db_lock, _connect() as conn:
        _ensure_waseena_orders_schema(conn)
        cur = conn.execute(
            "INSERT INTO orders (user_id, store_id, product_id, qty, address_text, status, driver_id, created_at, real_price, final_price) "
            "VALUES (?, ?, ?, ?, ?, 'pending', 0, ?, ?, ?)",
            (int(user_id), int(store_id), int(product_id), int(qty), str(address_text).strip(),
             int(time.time()), float(real_price), float(final_price)),
        )
        return int(cur.lastrowid)


def list_pending_orders(limit: int = 10) -> List[Dict[str, Any]]:
    with _db_lock, _connect() as conn:
        rows = conn.execute(
            "SELECT id, user_id, store_id, product_id, qty, address_text, status, driver_id, created_at "
            "FROM orders WHERE status='pending' ORDER BY created_at ASC LIMIT ?",
            (int(limit),),
        ).fetchall()
        return [dict(r) for r in rows]


def get_order(order_id: int) -> Optional[Dict[str, Any]]:
    with _db_lock, _connect() as conn:
        row = conn.execute("SELECT * FROM orders WHERE id=?", (int(order_id),)).fetchone()
        return dict(row) if row else None


def accept_order(order_id: int, driver_id: int) -> bool:
    """
    يقبل الطلب فقط إذا كان pending والسائق غير مشغول.
    """
    with _db_lock, _connect() as conn:
        # هل السائق مشغول؟
        d = conn.execute("SELECT status, busy FROM drivers WHERE user_id=?", (int(driver_id),)).fetchone()
        if not d or str(d["status"]) != "active" or int(d["busy"] or 0) == 1:
            return False

        row = conn.execute("SELECT status FROM orders WHERE id=?", (int(order_id),)).fetchone()
        if not row or str(row["status"]) != "pending":
            return False

        conn.execute(
            "UPDATE orders SET status='accepted', driver_id=?, accepted_at=? WHERE id=?",
            (int(driver_id), int(time.time()), int(order_id)),
        )

        # اجعل السائق مشغول
        conn.execute("UPDATE drivers SET busy=1 WHERE user_id=?", (int(driver_id),))
        return True


def list_user_orders(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    with _db_lock, _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (int(user_id), int(limit)),
        ).fetchall()
        return [dict(r) for r in rows]


def get_store(store_id: int) -> Optional[Dict[str, Any]]:
    with _db_lock, _connect() as conn:
        row = conn.execute("SELECT * FROM stores WHERE id=?", (int(store_id),)).fetchone()
        return dict(row) if row else None


def _ensure_column(conn: sqlite3.Connection, table: str, col: str, ddl: str) -> None:
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    names = {c["name"] for c in cols} if cols else set()
    if col not in names:
        conn.execute(ddl)

def _ensure_drivers_schema(conn: sqlite3.Connection) -> None:
    _ensure_column(conn, "drivers", "busy", "ALTER TABLE drivers ADD COLUMN busy INTEGER NOT NULL DEFAULT 0")



def confirm_order_delivered_by_user(order_id: int, user_id: int, bot_cut_rate: float) -> bool:
    """
    يؤكد الاستلام فقط إذا:
    - الطلب للـ user_id
    - الحالة accepted
    ثم يحسب الربح وحصة البوت والسائق.
    """
    now = int(time.time())
    with _db_lock, _connect() as conn:
        _ensure_waseena_orders_schema(conn)
        row = conn.execute("SELECT * FROM orders WHERE id=?", (int(order_id),)).fetchone()
        if not row:
            return False
        if int(row["user_id"]) != int(user_id):
            return False
        if str(row["status"]) != "accepted":
            return False

        qty = int(row["qty"] or 1)
        real_price = float(row["real_price"] or 0)
        final_price = float(row["final_price"] or 0)

        profit_total = max(0.0, (final_price - real_price) * qty)
        bot_cut = profit_total * float(bot_cut_rate)
        driver_cut = profit_total - bot_cut

        conn.execute("""
            UPDATE orders
            SET status='delivered',
                delivered_at=?,
                delivered_confirmed=1,
                profit_total=?,
                bot_cut=?,
                driver_cut=?,
                bot_cut_rate=?
            WHERE id=?
        """, (now, float(profit_total), float(bot_cut), float(driver_cut), float(bot_cut_rate), int(order_id)))
        
        conn.execute("UPDATE drivers SET busy=0 WHERE user_id=?", (int(row["driver_id"]),))

        return True


def weekly_driver_report(start_ts: int, end_ts: int) -> List[Dict[str, Any]]:
    """
    تقرير للسائقين عن الطلبات delivered_confirmed=1 ضمن الفترة
    """
    with _db_lock, _connect() as conn:
        _ensure_waseena_orders_schema(conn)
        rows = conn.execute("""
            SELECT
                driver_id,
                COUNT(*) AS orders_count,
                SUM(qty * final_price) AS gross_total,
                SUM(qty * real_price) AS real_total,
                SUM(profit_total) AS profit_total,
                SUM(bot_cut) AS bot_cut_total,
                SUM(driver_cut) AS driver_cut_total
            FROM orders
            WHERE delivered_confirmed=1
              AND delivered_at >= ?
              AND delivered_at < ?
              AND driver_id != 0
            GROUP BY driver_id
            ORDER BY profit_total DESC
        """, (int(start_ts), int(end_ts))).fetchall()
        return [dict(r) for r in rows]



def get_product(product_id: int) -> Optional[Dict[str, Any]]:
    with _db_lock, _connect() as conn:
        row = conn.execute("SELECT * FROM products WHERE id=?", (int(product_id),)).fetchone()
        return dict(row) if row else None
       
      
     
    
def has_referrer(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
    r = c.fetchone()
    return r and r[0] is not None


def set_referrer(user_id, referrer_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "UPDATE users SET referrer_id = ? WHERE user_id = ?",
        (referrer_id, user_id)
    )
    conn.commit()


def add_points(user_id, amount):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
        (amount, user_id)
    )
    conn.commit()   
  
 
 