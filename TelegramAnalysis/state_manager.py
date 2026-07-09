# -*- coding: utf-8 -*-
"""
State Manager for ChatsSpider
Manages processed chats using SQLite with in-memory cache for O(1) lookups
"""

import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Set
from datetime import datetime, timezone
import shutil

logger = logging.getLogger(__name__)


class StateManager:
    """
    Управління станом через SQLite.
    Використовує in-memory cache для швидких перевірок is_processed().
    """

    def __init__(self, db_path: str = "state/chats.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # In-memory cache для швидких lookup (O(1) замість O(n))
        self._processed_cache: Set[str] = set()

        self._ensure_db()
        self._load_cache()

    def _ensure_db(self):
        """Створити таблиці якщо не існують"""
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS processed_chats (
                url TEXT PRIMARY KEY,
                processed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                session_id TEXT,
                validation_result TEXT,
                category TEXT,
                owner TEXT,
                rejection_reason TEXT
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_processed_at ON processed_chats(processed_at)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_validation ON processed_chats(validation_result)')
        conn.commit()
        conn.close()

        logger.debug("Database tables ensured")

    def _load_cache(self):
        """Завантажити всі URL в пам'ять для швидких lookup"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute('SELECT url FROM processed_chats')
        self._processed_cache = {row[0] for row in cursor.fetchall()}
        conn.close()

        logger.info(f"Завантажено {len(self._processed_cache)} оброблених чатів в cache")

    def is_processed(self, chat_url: str) -> bool:
        """
        O(1) перевірка через in-memory cache.
        Набагато швидше ніж запит до БД кожен раз.

        Args:
            chat_url: URL чату для перевірки

        Returns:
            True якщо чат вже оброблений
        """
        return chat_url in self._processed_cache

    def mark_processed(self, chat_url: str, analysis_result: Dict, session_id: str = "default"):
        """
        Позначити чат як оброблений.
        ВАЖЛИВО: Викликати ТІЛЬКИ після успішного збереження в output файли!

        Args:
            chat_url: URL чату
            analysis_result: Результат аналізу від ChatGPT
            session_id: ID сесії обробки
        """
        validation_result = "PASS" if analysis_result.get('is_valid', False) else "FAIL"
        rejection_reason = None

        if not analysis_result.get('is_valid'):
            # Збрати причини відхилення
            reasons = []
            if analysis_result.get('language_check', {}).get('status') == 'FAIL':
                reasons.append("Language")
            if analysis_result.get('prohibited_content', {}).get('status') == 'FAIL':
                reasons.append("Prohibited")
            if analysis_result.get('category_fit', {}).get('status') == 'FAIL':
                reasons.append("CategoryFit")
            rejection_reason = ", ".join(reasons) if reasons else "Unknown"

        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            INSERT OR REPLACE INTO processed_chats
            (url, processed_at, session_id, validation_result, category, owner, rejection_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            chat_url,
            datetime.now(timezone.utc).isoformat(),
            session_id,
            validation_result,
            analysis_result.get('category', 'N/A'),
            analysis_result.get('owner', 'N/A'),
            rejection_reason
        ))
        conn.commit()
        conn.close()

        # Оновити cache
        self._processed_cache.add(chat_url)

        logger.info(f"Позначено як оброблений: {chat_url} ({validation_result})")

    def get_unprocessed_chats(self, all_chats: List[Dict]) -> List[Dict]:
        """
        Отримати тільки необроблені чати.
        Використовує in-memory cache для швидкості.

        Args:
            all_chats: Список всіх чатів для перевірки

        Returns:
            Список необроблених чатів
        """
        unprocessed = [chat for chat in all_chats if not self.is_processed(chat['url'])]
        logger.info(f"Необроблених чатів: {len(unprocessed)} з {len(all_chats)}")
        return unprocessed

    def get_stats(self) -> Dict:
        """
        Отримати статистику оброблених чатів

        Returns:
            Dict з статистикою: total, passed, failed, pass_rate
        """
        conn = sqlite3.connect(self.db_path)

        # Загальна кількість
        total = conn.execute('SELECT COUNT(*) FROM processed_chats').fetchone()[0]

        # За validation_result
        passed = conn.execute(
            'SELECT COUNT(*) FROM processed_chats WHERE validation_result = "PASS"'
        ).fetchone()[0]

        failed = conn.execute(
            'SELECT COUNT(*) FROM processed_chats WHERE validation_result = "FAIL"'
        ).fetchone()[0]

        conn.close()

        return {
            'total': total,
            'passed': passed,
            'failed': failed,
            'pass_rate': f"{passed/total*100:.1f}%" if total > 0 else "N/A"
        }

    def backup_db(self, backup_dir: str = "state/backups"):
        """
        Створити бекап бази даних

        Args:
            backup_dir: Папка для бекапів

        Returns:
            Path до створеного бекапу
        """
        backup_path = Path(backup_dir)
        backup_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_path / f"chats_{timestamp}.db"

        shutil.copy2(self.db_path, backup_file)
        logger.info(f"Створено бекап: {backup_file}")

        return backup_file

    def clear_all(self):
        """
        Очистити всі дані (для --fresh-start)
        УВАГА: Видаляє всі оброблені чати з БД!
        """
        conn = sqlite3.connect(self.db_path)
        conn.execute('DELETE FROM processed_chats')
        conn.commit()
        conn.close()

        # Очистити cache
        self._processed_cache.clear()

        logger.warning("ВСІ дані очищено з state manager!")
