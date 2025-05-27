import sqlite3
from datetime import datetime, timedelta

DB_PATH = "data/roles.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS role_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            assigned_at TEXT NOT NULL,
            expires_at TEXT,
            assigned_by INTEGER
        )
    """)
    conn.commit()
    conn.close()

def role_exists(user_id: int, role_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 1 FROM role_assignments
        WHERE user_id = ? AND role_id = ?
    """, (user_id, role_id))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def add_role(user_id: int, role_id: int, days: int | None, assigned_by: int):
    assigned_at = datetime.utcnow()
    expires_at = assigned_at + timedelta(days=days) if days else None

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO role_assignments (user_id, role_id, assigned_at, expires_at, assigned_by)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, role_id, assigned_at.isoformat(), expires_at.isoformat() if expires_at else None, assigned_by))
    conn.commit()
    conn.close()

def prolong_role(user_id: int, role_id: int, days: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE role_assignments
        SET expires_at = datetime(expires_at, '+%d days')
        WHERE user_id = ? AND role_id = ? AND expires_at IS NOT NULL
    """ % days, (user_id, role_id))
    conn.commit()
    conn.close()

def get_active_roles(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT role_id, expires_at FROM role_assignments
        WHERE user_id = ?
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def remove_role(user_id: int, role_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM role_assignments
        WHERE user_id = ? AND role_id = ?
    """, (user_id, role_id))
    conn.commit()
    conn.close()

def get_users_with_role(role_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, expires_at FROM role_assignments
        WHERE role_id = ?
    """, (role_id,))
    results = cursor.fetchall()
    conn.close()
    return results

def get_expired_roles():
    now = datetime.utcnow().isoformat()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, role_id FROM role_assignments
        WHERE expires_at IS NOT NULL AND expires_at <= ?
    """, (now,))
    expired = cursor.fetchall()
    conn.close()
    return expired
