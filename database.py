# database.py
# -*- coding: utf-8 -*-
import sqlite3
from pathlib import Path
from typing import Optional
import time

DB_PATH = Path("output/spider.db")

_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS channels (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    username         TEXT UNIQUE NOT NULL,      -- t.me/<name> (без https://)
    title            TEXT,                      -- название канала (Channel.title)
    about            TEXT,                      -- описание канала (ChannelFull.about)
    first_seen_ts    INTEGER NOT NULL,
    last_seen_ts     INTEGER NOT NULL,
    source_session   TEXT
);

CREATE TABLE IF NOT EXISTS chats (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    username         TEXT UNIQUE NOT NULL,      -- t.me/<name> обсуждения (публичный)
    title            TEXT,                      -- название чата (Channel.title)
    about            TEXT,                      -- описание (ChannelFull.about)
    channel_username TEXT,                      -- из какого канала получили ссылку
    first_seen_ts    INTEGER NOT NULL,
    last_seen_ts     INTEGER NOT NULL,
    source_session   TEXT
);

CREATE INDEX IF NOT EXISTS idx_channels_last_seen ON channels(last_seen_ts DESC);
CREATE INDEX IF NOT EXISTS idx_chats_last_seen    ON chats(last_seen_ts DESC);
"""

class Database:
    def __init__(self, path: Path = DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        # isolation_level=None -> autocommit режим, удобно для ON CONFLICT upsert
        self.conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        # Выполняем сразу всю схему одним вызовом
        self.conn.executescript(_SCHEMA)

    def _now(self) -> int:
        return int(time.time())

    # ---------- CHANNELS ----------
    def upsert_channel(self, username: str, title: Optional[str], about: Optional[str], source_session: Optional[str]) -> None:
        """
        Вставка/обновление канала по username.
        title/about обновляются, если пришли НЕ NULL.
        """
        ts = self._now()
        self.conn.execute(
            """
            INSERT INTO channels (username, title, about, first_seen_ts, last_seen_ts, source_session)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                title = COALESCE(excluded.title, channels.title),
                about = COALESCE(excluded.about, channels.about),
                last_seen_ts = excluded.last_seen_ts,
                source_session = COALESCE(excluded.source_session, channels.source_session)
            """,
            (username, title, about, ts, ts, source_session)
        )

    # ---------- CHATS ----------
    def upsert_chat(self, username: str, title: Optional[str], about: Optional[str],
                    channel_username: Optional[str], source_session: Optional[str]) -> None:
        """
        Вставка/обновление чата (обсуждения) по username.
        """
        ts = self._now()
        self.conn.execute(
            """
            INSERT INTO chats (username, title, about, channel_username, first_seen_ts, last_seen_ts, source_session)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                title = COALESCE(excluded.title, chats.title),
                about = COALESCE(excluded.about, chats.about),
                channel_username = COALESCE(excluded.channel_username, chats.channel_username),
                last_seen_ts = excluded.last_seen_ts,
                source_session = COALESCE(excluded.source_session, chats.source_session)
            """,
            (username, title, about, channel_username, ts, ts, source_session)
        )

    def get_all_channel_usernames(self, limit: int = 200) -> list:
        """Повертає список username каналів, відсортованих за давністю останнього перегляду (oldest first).
        limit захищає від OOM при великих БД."""
        cur = self.conn.execute(
            "SELECT username FROM channels WHERE username IS NOT NULL "
            "ORDER BY last_seen_ts ASC LIMIT ?",
            (limit,)
        )
        return [r[0] for r in cur.fetchall()]

    # ---------- STATS ----------
    def count_channels(self) -> int:
        cur = self.conn.execute("SELECT COUNT(*) FROM channels")
        return int(cur.fetchone()[0])

    def count_chats(self) -> int:
        cur = self.conn.execute("SELECT COUNT(*) FROM chats")
        return int(cur.fetchone()[0])

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass
