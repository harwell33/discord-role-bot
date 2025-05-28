import sqlite3
from datetime import datetime, timedelta

DB_PATH = "data/roles.db"

def init_db():
    conn = sqlite3.connect("data/roles.db")
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS roles (
            user_id INTEGER,
            role_id INTEGER,
            expires_at TEXT,
            assigned_by INTEGER
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS log_channels (
            guild_id INTEGER PRIMARY KEY,
            channel_id INTEGER
        )
    ''')

    conn.commit()
    conn.close()

def add_role(user_id, role_id, days=None, assigned_by=None):
    expires_at = (datetime.utcnow() + timedelta(days=days)).isoformat() if days else None
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        try:
            c.execute(
                "INSERT OR REPLACE INTO roles (user_id, role_id, expires_at, assigned_by) VALUES (?, ?, ?, ?)",
                (user_id, role_id, expires_at, assigned_by)
            )
            conn.commit()
        except sqlite3.Error as e:
            print(f"⚠️ Failed to add role: {e}")

def remove_role(user_id, role_id):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM roles WHERE user_id = ? AND role_id = ?", (user_id, role_id))
        conn.commit()

def get_active_roles(user_id):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT role_id, expires_at FROM roles WHERE user_id = ?", (user_id,))
        return c.fetchall()

def get_users_with_role(role_id):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT user_id, expires_at FROM roles WHERE role_id = ?", (role_id,))
        return c.fetchall()

def get_expired_roles():
    now = datetime.utcnow().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT user_id, role_id FROM roles WHERE expires_at IS NOT NULL AND expires_at < ?", (now,))
        return c.fetchall()

def role_exists(user_id, role_id):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT 1 FROM roles WHERE user_id = ? AND role_id = ?", (user_id, role_id))
        return c.fetchone() is not None

def prolong_role(user_id, role_id, days):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT expires_at FROM roles WHERE user_id = ? AND role_id = ?", (user_id, role_id))
        row = c.fetchone()
        if not row or not row[0]:
            new_expires = datetime.utcnow() + timedelta(days=days)
        else:
            new_expires = datetime.fromisoformat(row[0]) + timedelta(days=days)
        c.execute(
            "UPDATE roles SET expires_at = ? WHERE user_id = ? AND role_id = ?",
            (new_expires.isoformat(), user_id, role_id)
        )
        conn.commit()

def set_log_channel(guild_id, channel_id):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("REPLACE INTO log_channels (guild_id, channel_id) VALUES (?, ?)", (guild_id, channel_id))
        conn.commit()

def get_log_channel(guild_id):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT channel_id FROM log_channels WHERE guild_id = ?", (guild_id,))
        row = c.fetchone()
        return row[0] if row else None
