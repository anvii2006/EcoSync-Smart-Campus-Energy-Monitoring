"""Durable local equivalent of the DynamoDB key and transaction operations."""

import json
import sqlite3
from threading import RLock

from store import Conflict, Put


class SQLiteStore:
    def __init__(self, path):
        self.lock = RLock()
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS items (
                pk TEXT NOT NULL, sk TEXT NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY (pk, sk)
            ) WITHOUT ROWID
        """)
        self.connection.commit()

    def close(self):
        self.connection.close()

    def get(self, pk, sk):
        with self.lock:
            row = self.connection.execute(
                "SELECT payload FROM items WHERE pk = ? AND sk = ?", (pk, sk)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def query(self, pk, lower, upper, limit=None, newest=False):
        order = "DESC" if newest else "ASC"
        with self.lock:
            rows = self.connection.execute(f"""
                SELECT sk, payload FROM items
                WHERE pk = ? AND sk BETWEEN ? AND ?
                ORDER BY sk {order} LIMIT ?
            """, (pk, lower, upper, -1 if limit is None else limit)).fetchall()
        return [(sk, json.loads(payload)) for sk, payload in rows]

    def commit(self, changes):
        with self.lock, self.connection:
            self.connection.execute("BEGIN IMMEDIATE")
            for change in changes:
                if isinstance(change, Put):
                    value = change.value
                    if change.guard is not None:
                        field, expected = change.guard
                        current = self.get(change.pk, change.sk)
                        if (current or {}).get(field) != expected:
                            raise Conflict
                else:
                    value = self.get(change.pk, change.sk) or {}
                    for field, amount in change.fields.items():
                        value[field] = value.get(field, 0) + amount
                self.connection.execute(
                    "INSERT OR REPLACE INTO items VALUES (?, ?, ?)",
                    (change.pk, change.sk, json.dumps(value, separators=(",", ":"))),
                )
