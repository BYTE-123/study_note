"""SQLite 数据访问层：连接封装、建表与通用 CRUD 工具。

约定：
- 配置一律通过 ``flask.current_app.config`` 读取（便于测试覆盖）。
- 所有 SQL 使用 ``?`` 占位参数化，禁止字符串拼接。
- 本层只做数据存取，不含业务规则（归属校验由蓝图负责）。
"""
import sqlite3

from flask import current_app

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT UNIQUE NOT NULL,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    bio           TEXT DEFAULT '',
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notes (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL,
    title               TEXT NOT NULL,
    content             TEXT DEFAULT '',
    tags                TEXT DEFAULT '',
    status              TEXT NOT NULL DEFAULT 'draft',
    is_shared           INTEGER DEFAULT 0,
    share_token         TEXT UNIQUE,
    share_password_hash TEXT,
    comments_enabled    INTEGER DEFAULT 1,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS comments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id    INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (note_id) REFERENCES notes (id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS favorites (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    note_id    INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (user_id, note_id),
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (note_id) REFERENCES notes (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_notes_user_status ON notes (user_id, status);
CREATE INDEX IF NOT EXISTS idx_notes_share_token ON notes (share_token);
CREATE INDEX IF NOT EXISTS idx_comments_note ON comments (note_id, created_at);
"""


def get_conn():
    """返回配置化的 SQLite 连接（Row 工厂 + 开启外键约束）。"""
    conn = sqlite3.connect(current_app.config["DB_PATH"])
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """建立四张表与索引（幂等）。"""
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def query_one(sql, params=()):
    """查询单行，返回 sqlite3.Row 或 None。"""
    conn = get_conn()
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def query_all(sql, params=()):
    """查询多行，返回 list[sqlite3.Row]。"""
    conn = get_conn()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def execute(sql, params=()):
    """执行写操作并提交，返回 lastrowid。"""
    conn = get_conn()
    try:
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor.lastrowid
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()
