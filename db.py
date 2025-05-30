import sqlite3

def init_db():
    with sqlite3.connect("bot.db") as conn:
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)")
        cur.execute("CREATE TABLE IF NOT EXISTS channels (user_id INTEGER, channel TEXT)")
        conn.commit()

def is_admin(user_id):
    with sqlite3.connect("bot.db") as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,))
        return cur.fetchone() is not None

def add_user(user_id):
    with sqlite3.connect("bot.db") as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
        conn.commit()

def remove_user(user_id):
    with sqlite3.connect("bot.db") as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM admins WHERE user_id=?", (user_id,))
        cur.execute("DELETE FROM channels WHERE user_id=?", (user_id,))
        conn.commit()

def get_user_channels(user_id):
    with sqlite3.connect("bot.db") as conn:
        cur = conn.cursor()
        cur.execute("SELECT channel FROM channels WHERE user_id=?", (user_id,))
        return [row[0] for row in cur.fetchall()]

def add_channel(user_id, channel):
    with sqlite3.connect("bot.db") as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO channels (user_id, channel) VALUES (?, ?)", (user_id, channel))
        conn.commit()

def remove_channel(user_id, channel):
    with sqlite3.connect("bot.db") as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM channels WHERE user_id=? AND channel=?", (user_id, channel))
        conn.commit()
