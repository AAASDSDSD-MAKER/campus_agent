"""校园统筹 Agent —— 公开查询门户服务（轻量，仅用 Python 标准库）。

启动后访问 http://localhost:8010 即可查询浏览已生成的会议通知与待办。
不依赖任何第三方库，直接读取 Streamlit 应用写入的 data/campus.db。
"""
import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "campus.db"
INDEX_HTML = ROOT / "index.html"
PORT = 8010


def _conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def query_tasks(q: str = "") -> list[dict]:
    if not DB_PATH.exists():
        return []
    conn = _conn()
    sql = (
        "SELECT t.id, t.title, t.notice, t.todos, t.timeline, t.risks, "
        "t.summary, t.created_at, u.username "
        "FROM tasks t LEFT JOIN users u ON t.user_id = u.id"
    )
    params: list = []
    if q.strip():
        sql += (
            " WHERE t.title LIKE ? OR t.notice LIKE ? OR t.summary LIKE ? "
            "OR t.raw_input LIKE ?"
        )
        like = f"%{q}%"
        params = [like, like, like, like]
    sql += " ORDER BY t.id DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_task(task_id: int) -> dict | None:
    if not DB_PATH.exists():
        return None
    conn = _conn()
    r = conn.execute(
        "SELECT t.id, t.title, t.notice, t.todos, t.timeline, t.risks, "
        "t.summary, t.raw_input, t.created_at, u.username "
        "FROM tasks t LEFT JOIN users u ON t.user_id = u.id WHERE t.id=?",
        (task_id,),
    ).fetchone()
    conn.close()
    return dict(r) if r else None


def task_stats() -> dict:
    if not DB_PATH.exists():
        return {"total": 0, "latest": None}
    conn = _conn()
    total = conn.execute("SELECT count(*) FROM tasks").fetchone()[0]
    latest = conn.execute(
        "SELECT created_at FROM tasks ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return {"total": total, "latest": latest["created_at"] if latest else None}


class Handler(BaseHTTPRequestHandler):
    def _send(self, body: bytes, content_type: str, code: int = 200):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, code: int = 200):
        self._send(
            json.dumps(data, ensure_ascii=False).encode("utf-8"),
            "application/json; charset=utf-8",
            code,
        )

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        if path in ("/", "/index.html"):
            if INDEX_HTML.exists():
                self._send(
                    INDEX_HTML.read_text(encoding="utf-8").encode("utf-8"),
                    "text/html; charset=utf-8",
                )
            else:
                self._json({"error": "index.html 不存在"}, 404)
            return
        if path == "/api/tasks":
            self._json(query_tasks(qs.get("q", [""])[0]))
            return
        if path == "/api/stats":
            self._json(task_stats())
            return
        if path.startswith("/api/task/"):
            try:
                tid = int(path.rsplit("/", 1)[-1])
            except ValueError:
                self._json({"error": "无效的任务ID"}, 400)
                return
            task = get_task(tid)
            self._json(task or {"error": "未找到"}, 200 if task else 404)
            return
        self.send_error(404, "Not Found")

    def log_message(self, *args):
        pass


def main():
    print(f"查询门户已启动：http://localhost:{PORT}")
    print("按 Ctrl+C 停止。")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()