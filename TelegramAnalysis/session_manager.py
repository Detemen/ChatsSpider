# -*- coding: utf-8 -*-
"""
Session Manager for TelegramAnalysis
Manages multiple Telegram sessions with automatic rotation on FloodWait

FEATURES:
- Automatic discovery of all .session files in accs/
- FloodWait tracking per session
- Automatic rotation to next available session
- Persistent state in SQLite (survives restarts)
"""

import sqlite3
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class SessionInfo:
    """Information about a Telegram session"""
    path: Path
    name: str
    api_id: int
    api_hash: str
    is_available: bool
    blocked_until: Optional[datetime] = None


class SessionManager:
    """
    Manages multiple Telegram sessions with FloodWait tracking

    Usage:
        manager = SessionManager(db_path="state/chats.db", accs_dir="accs")

        # Get next available session
        session = manager.get_next_available_session()

        # If FloodWait occurs
        manager.mark_session_blocked(session.name, wait_seconds=32750)

        # Get another session
        session = manager.get_next_available_session()
    """

    def __init__(self, db_path: str = "state/chats.db", accs_dir: str = "accs"):
        self.db_path = Path(db_path)
        self.accs_dir = Path(accs_dir)
        self.sessions: List[Path] = []
        self.current_index = 0
        self.blocked_until = {}  # {session_name: datetime}

        self._ensure_db()
        self._load_sessions()
        self._load_blocked_state()

    def _ensure_db(self):
        """Create session_blocks table if not exists"""
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS session_blocks (
                session_name TEXT PRIMARY KEY,
                blocked_until TEXT NOT NULL,
                last_error TEXT
            )
        ''')
        conn.commit()
        conn.close()
        logger.debug("Session blocks table ensured")

    def _load_sessions(self):
        """Load all .session files from accs/ directory"""
        if not self.accs_dir.exists():
            logger.error(f"❌ Папка {self.accs_dir} не знайдена")
            return

        self.sessions = sorted([
            p for p in self.accs_dir.iterdir()
            if p.is_file() and p.suffix == ".session"
        ])

        if not self.sessions:
            logger.error(f"[X] Немає .session файлів в {self.accs_dir}")
        else:
            logger.info(f"[i] Знайдено {len(self.sessions)} сесій: {[s.name for s in self.sessions]}")
            print(f"\n[i] Знайдено {len(self.sessions)} Telegram сесій:")
            for i, s in enumerate(self.sessions, 1):
                print(f"   {i}. {s.name}")

    def _load_blocked_state(self):
        """Load blocked sessions state from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT session_name, blocked_until FROM session_blocks"
        )

        now = datetime.now(timezone.utc)
        for row in cursor.fetchall():
            session_name = row[0]
            blocked_until_str = row[1]
            blocked_until = datetime.fromisoformat(blocked_until_str)

            # Only load if still blocked
            if blocked_until > now:
                self.blocked_until[session_name] = blocked_until
                remaining = (blocked_until - now).total_seconds()
                logger.warning(f"[!] {session_name} заблоковано ще на {int(remaining//60)}хв")

        conn.close()

    def mark_session_blocked(self, session_name: str, wait_seconds: int, error_msg: str = ""):
        """
        Mark session as blocked due to FloodWait

        Args:
            session_name: Name of .session file (e.g., "account1.session")
            wait_seconds: How long to wait (from FloodWaitError.seconds)
            error_msg: Optional error message for logging
        """
        now = datetime.now(timezone.utc)
        blocked_until = now + timedelta(seconds=wait_seconds)

        self.blocked_until[session_name] = blocked_until

        # Save to database
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            INSERT OR REPLACE INTO session_blocks (session_name, blocked_until, last_error)
            VALUES (?, ?, ?)
        ''', (session_name, blocked_until.isoformat(), error_msg))
        conn.commit()
        conn.close()

        logger.warning(f"[X] {session_name} заблоковано на {wait_seconds}s (до {blocked_until.strftime('%H:%M:%S')} UTC)")
        print(f"\n[X] Сесія {session_name} заблокована FloodWait")
        print(f"   [!] Очікування: {int(wait_seconds//60)}хв {int(wait_seconds%60)}с")
        print(f"   [T] Розблокування: {blocked_until.strftime('%H:%M:%S')} UTC")

    def _is_session_available(self, session_path: Path) -> bool:
        """Check if session is not blocked by FloodWait"""
        session_name = session_path.name

        if session_name not in self.blocked_until:
            return True

        blocked_until = self.blocked_until[session_name]
        now = datetime.now(timezone.utc)

        if now >= blocked_until:
            # Unblock session
            del self.blocked_until[session_name]

            # Remove from database
            conn = sqlite3.connect(self.db_path)
            conn.execute("DELETE FROM session_blocks WHERE session_name = ?", (session_name,))
            conn.commit()
            conn.close()

            logger.info(f"[OK] {session_name} розблоковано")
            return True

        return False

    def get_next_available_session(self, api_id: int, api_hash: str) -> Optional[SessionInfo]:
        """
        Get next available (non-blocked) session

        Args:
            api_id: Telegram API ID
            api_hash: Telegram API Hash

        Returns:
            SessionInfo or None if all sessions blocked
        """
        if not self.sessions:
            logger.error("[X] Немає доступних сесій")
            return None

        # Try all sessions starting from current_index
        attempts = 0
        while attempts < len(self.sessions):
            session_path = self.sessions[self.current_index]

            if self._is_session_available(session_path):
                # Found available session
                session_info = SessionInfo(
                    path=session_path,
                    name=session_path.name,
                    api_id=api_id,
                    api_hash=api_hash,
                    is_available=True
                )

                logger.info(f"[OK] Вибрано сесію: {session_path.name}")
                print(f"\n[KEY] Використовується сесія: {session_path.name}")

                # Move to next session for next call
                self.current_index = (self.current_index + 1) % len(self.sessions)

                return session_info
            else:
                # Session blocked, try next
                blocked_until = self.blocked_until[session_path.name]
                remaining = (blocked_until - datetime.now(timezone.utc)).total_seconds()
                logger.debug(f"   [!] {session_path.name} заблоковано ще на {int(remaining)}s")

            # Try next session
            self.current_index = (self.current_index + 1) % len(self.sessions)
            attempts += 1

        # All sessions blocked
        logger.error("[X] ВСІ СЕСІЇ ЗАБЛОКОВАНІ FloodWait!")
        print("\n[X] ВСІ СЕСІЇ ЗАБЛОКОВАНІ!")
        print("\nСтатус:")
        for session_name, blocked_until in self.blocked_until.items():
            remaining = (blocked_until - datetime.now(timezone.utc)).total_seconds()
            print(f"   [X] {session_name}: ще {int(remaining//60)}хв")

        return None

    def get_available_count(self) -> int:
        """Get number of currently available (non-blocked) sessions"""
        return sum(1 for s in self.sessions if self._is_session_available(s))

    def get_total_count(self) -> int:
        """Get total number of sessions"""
        return len(self.sessions)

    def get_status_report(self) -> str:
        """Get formatted status report of all sessions"""
        if not self.sessions:
            return "[X] Немає сесій"

        report = f"\n[i] Статус сесій ({self.get_available_count()}/{self.get_total_count()} доступно):\n"

        for session_path in self.sessions:
            session_name = session_path.name

            if self._is_session_available(session_path):
                report += f"   [OK] {session_name} - доступна\n"
            else:
                blocked_until = self.blocked_until[session_name]
                remaining = (blocked_until - datetime.now(timezone.utc)).total_seconds()
                report += f"   [X] {session_name} - заблоковано ще на {int(remaining//60)}хв\n"

        return report


# Export
__all__ = ['SessionManager', 'SessionInfo']