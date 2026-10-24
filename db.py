"""SQLite 数据访问层：用户、任务、每用户大模型配置。"""
import sqlite3
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

DB_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DB_DIR / "campus.db"


def get_conn() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                raw_input TEXT NOT NULL,
                notice TEXT,
                todos TEXT,
                timeline TEXT,
                risks TEXT,
                summary TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS user_config (
                user_id INTEGER PRIMARY KEY,
                provider TEXT,
                api_base TEXT,
                api_key TEXT,
                model TEXT,
                temperature REAL DEFAULT 0.7,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )


# ---------- 用户 ----------
def get_user_by_name(username: str):
    with db() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE username=?", (username,)
        ).fetchone()


def get_user_by_id(user_id: int):
    with db() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE id=?", (user_id,)
        ).fetchone()


def create_user(username: str, password_hash: str, salt: str) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO users(username, password_hash, salt, created_at) VALUES (?,?,?,?)",
            (username, password_hash, salt, now),
        )
        return cur.lastrowid


# ---------- 任务 ----------
def list_tasks(user_id: int):
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE user_id=? ORDER BY id DESC", (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_task(user_id: int, task_id: int):
    with db() as conn:
        r = conn.execute(
            "SELECT * FROM tasks WHERE id=? AND user_id=?", (task_id, user_id)
        ).fetchone()
        return dict(r) if r else None


def save_task(user_id: int, title: str, raw_input: str, result: dict) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO tasks(user_id, title, raw_input, notice, todos, timeline,
                                   risks, summary, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                user_id, title, raw_input,
                result.get("notice", ""), result.get("todos", ""),
                result.get("timeline", ""), result.get("risks", ""),
                result.get("summary", ""), now, now,
            ),
        )
        return cur.lastrowid


def delete_task(user_id: int, task_id: int) -> bool:
    with db() as conn:
        cur = conn.execute(
            "DELETE FROM tasks WHERE id=? AND user_id=?", (task_id, user_id)
        )
        return cur.rowcount > 0


# ---------- 配置 ----------
def get_config(user_id: int) -> dict | None:
    with db() as conn:
        r = conn.execute(
            "SELECT * FROM user_config WHERE user_id=?", (user_id,)
        ).fetchone()
        return dict(r) if r else None


def upsert_config(user_id: int, provider: str, api_base: str,
                  api_key: str, model: str, temperature: float) -> None:
    with db() as conn:
        conn.execute(
            """INSERT INTO user_config(user_id, provider, api_base, api_key, model, temperature)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(user_id) DO UPDATE SET
                 provider=excluded.provider,
                 api_base=excluded.api_base,
                 api_key=excluded.api_key,
                 model=excluded.model,
                 temperature=excluded.temperature""",
            (user_id, provider, api_base, api_key, model, temperature),
        )