"""数据层测试：建表、唯一约束、外键与级联删除。"""
import sqlite3

import pytest

import models

NOW = "2026-09-27T10:00:00"


def _insert_user(email="a@example.com", username="alice"):
    return models.execute(
        "INSERT INTO users (email, username, password_hash, created_at) VALUES (?, ?, ?, ?)",
        (email, username, "hash", NOW),
    )


def _insert_note(user_id, title="第一篇", status="draft"):
    return models.execute(
        "INSERT INTO notes (user_id, title, content, tags, status, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, title, "正文", "生活", status, NOW, NOW),
    )


def test_init_db_creates_all_four_tables(app):
    with app.app_context():
        rows = models.query_all("SELECT name FROM sqlite_master WHERE type = 'table'")
        names = {row["name"] for row in rows}
    assert {"users", "notes", "comments", "favorites"} <= names


def test_init_db_creates_expected_indexes(app):
    with app.app_context():
        rows = models.query_all("SELECT name FROM sqlite_master WHERE type = 'index'")
        names = {row["name"] for row in rows}
    assert {"idx_notes_user_status", "idx_notes_share_token", "idx_comments_note"} <= names


def test_users_email_must_be_unique(app):
    with app.app_context():
        _insert_user(email="dup@example.com", username="alice")
        with pytest.raises(sqlite3.IntegrityError):
            _insert_user(email="dup@example.com", username="bob")


def test_users_username_must_be_unique(app):
    with app.app_context():
        _insert_user(email="a@example.com", username="same")
        with pytest.raises(sqlite3.IntegrityError):
            _insert_user(email="b@example.com", username="same")


def test_favorites_pair_must_be_unique(app):
    with app.app_context():
        user_id = _insert_user()
        note_id = _insert_note(user_id)
        models.execute(
            "INSERT INTO favorites (user_id, note_id, created_at) VALUES (?, ?, ?)",
            (user_id, note_id, NOW),
        )
        with pytest.raises(sqlite3.IntegrityError):
            models.execute(
                "INSERT INTO favorites (user_id, note_id, created_at) VALUES (?, ?, ?)",
                (user_id, note_id, NOW),
            )


def test_foreign_keys_pragma_is_enabled(app):
    with app.app_context():
        assert models.query_one("PRAGMA foreign_keys")[0] == 1


def test_foreign_key_violation_is_rejected(app):
    with app.app_context():
        user_id = _insert_user()
        with pytest.raises(sqlite3.IntegrityError):
            models.execute(
                "INSERT INTO comments (note_id, user_id, content, created_at) VALUES (?, ?, ?, ?)",
                (999, user_id, "幽灵评论", NOW),
            )


def test_deleting_note_cascades_comments_and_favorites(app):
    with app.app_context():
        user_id = _insert_user()
        note_id = _insert_note(user_id)
        models.execute(
            "INSERT INTO comments (note_id, user_id, content, created_at) VALUES (?, ?, ?, ?)",
            (note_id, user_id, "写得真好", NOW),
        )
        models.execute(
            "INSERT INTO favorites (user_id, note_id, created_at) VALUES (?, ?, ?)",
            (user_id, note_id, NOW),
        )

        models.execute("DELETE FROM notes WHERE id = ?", (note_id,))

        comments = models.query_one("SELECT COUNT(*) AS c FROM comments")
        favorites = models.query_one("SELECT COUNT(*) AS c FROM favorites")
    assert comments["c"] == 0
    assert favorites["c"] == 0
