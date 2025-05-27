import sqlite3
from datetime import datetime, timedelta

DB_PATH = "data/roles.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS roles (
        user_id INTEGER,
        role_id INTEGER,
        expires_at TEXT,
        assigned_by INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS log_channels (
        guild_id INTEGER PRIMARY KEY,
        channel_id INTEGER
    )''')
    conn.commit()
    conn.close()

def add_role(user_id, role_id, days=None, assigned_by=None):
    expires_at = (datetime.utcnow() + timedelta(days=days)).isoformat() if days else None
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO roles (user_id, role_id, expires_at, assigned_by) VALUES (?, ?, ?, ?)",
              (user_id, role_id, expires_at, assigned_by))
    conn.commit()
    conn.close()

def remove_role(user_id, role_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM roles WHERE user_id = ? AND role_id = ?", (user_id, role_id))
    conn.commit()
    conn.close()

def get_active_roles(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT role_id, expires_at FROM roles WHERE user_id = ?", (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_users_with_role(role_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id, expires_at FROM roles WHERE role_id = ?", (role_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_expired_roles():
    now = datetime.utcnow().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id, role_id FROM roles WHERE expires_at IS NOT NULL AND expires_at < ?", (now,))
    rows = c.fetchall()
    conn.close()
    return rows

def role_exists(user_id, role_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM roles WHERE user_id = ? AND role_id = ?", (user_id, role_id))
    exists = c.fetchone() is not None
    conn.close()
    return exists

def prolong_role(user_id, role_id, days):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT expires_at FROM roles WHERE user_id = ? AND role_id = ?", (user_id, role_id))
    row = c.fetchone()
    if row and row[0]:
        new_expires = datetime.fromisoformat(row[0]) + timedelta(days=days)
        c.execute("UPDATE roles SET expires_at = ? WHERE user_id = ? AND role_id = ?",
                  (new_expires.isoformat(), user_id, role_id))
    conn.commit()
    conn.close()

def set_log_channel(guild_id, channel_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("REPLACE INTO log_channels (guild_id, channel_id) VALUES (?, ?)", (guild_id, channel_id))
    conn.commit()
    conn.close()

def get_log_channel(guild_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT channel_id FROM log_channels WHERE guild_id = ?", (guild_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None
