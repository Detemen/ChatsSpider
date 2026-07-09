# -*- coding: utf-8 -*-
"""
Rate Limiter for ChatsSpider
Limits processing to 150 chats per hour using SQLite with atomic operations
"""

import sqlite3
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Обмеження швидкості обробки чатів.
    150 чатів на годину з фіксованими годинними вікнами (3:00-4:00, 4:00-5:00 і т.д.)
    """

    def __init__(self, db_path: str = "state/chats.db", max_per_hour: int = 150):
        self.db_path = Path(db_path)
        self.max_per_hour = max_per_hour
        self._ensure_db()

    def _ensure_db(self):
        """Створити таблицю rate_limit якщо не існує"""
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS rate_limit (
                hour_window TEXT PRIMARY KEY,
                chats_processed INTEGER DEFAULT 0,
                last_update TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

        logger.debug("Rate limit table ensured")

    def _get_current_hour_window(self) -> str:
        """
        Отримати поточне годинне вікно (фіксоване: 3:00-4:00, 4:00-5:00)

        Returns:
            ISO format string для поточної години (rounded down)
        """
        now = datetime.now(timezone.utc)
        # Округлити до початку години
        window_start = now.replace(minute=0, second=0, microsecond=0)
        return window_start.isoformat()

    def can_process(self) -> bool:
        """
        Чи можна обробити ще чати в поточну годину

        Returns:
            True якщо ще не досягнуто ліміту
        """
        window = self._get_current_hour_window()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT chats_processed FROM rate_limit WHERE hour_window = ?",
            (window,)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            # Нове вікно - створити запис
            self._init_window(window)
            return True

        count = row[0]
        logger.info(f"Rate limit: {count}/{self.max_per_hour} в вікні {window}")
        return count < self.max_per_hour

    def _init_window(self, window: str):
        """
        Ініціалізувати нове годинне вікно

        Args:
            window: ISO format string годинного вікна
        """
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT OR REPLACE INTO rate_limit (hour_window, chats_processed) VALUES (?, 0)",
            (window,)
        )
        conn.commit()
        conn.close()

        logger.info(f"Нове годинне вікно: {window}")

    def increment_processed(self):
        """
        КРИТИЧНО: Викликати ТІЛЬКИ після успішної обробки ChatGPT!
        Використовує SQLite транзакцію для атомарності.
        """
        window = self._get_current_hour_window()

        conn = sqlite3.connect(self.db_path)
        try:
            with conn:  # Автоматична транзакція
                # Atomic increment
                conn.execute('''
                    INSERT INTO rate_limit (hour_window, chats_processed)
                    VALUES (?, 1)
                    ON CONFLICT(hour_window)
                    DO UPDATE SET
                        chats_processed = chats_processed + 1,
                        last_update = CURRENT_TIMESTAMP
                ''', (window,))

                # Отримати поточний count для логування
                cursor = conn.execute(
                    "SELECT chats_processed FROM rate_limit WHERE hour_window = ?",
                    (window,)
                )
                new_count = cursor.fetchone()[0]
                logger.info(f"Rate limit: оброблено {new_count}/{self.max_per_hour}")
        finally:
            conn.close()

    def get_remaining(self) -> int:
        """
        Скільки чатів ще можна обробити в поточну годину

        Returns:
            Кількість чатів що залишилися
        """
        window = self._get_current_hour_window()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT chats_processed FROM rate_limit WHERE hour_window = ?",
            (window,)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return self.max_per_hour

        return max(0, self.max_per_hour - row[0])

    def wait_for_next_window(self):
        """
        Чекати до наступного годинного вікна
        Блокує виконання до початку наступної години
        """
        window_start = datetime.fromisoformat(self._get_current_hour_window())
        next_window = window_start + timedelta(hours=1)
        now = datetime.now(timezone.utc)

        wait_seconds = (next_window - now).total_seconds()

        if wait_seconds > 0:
            logger.warning(f"⏳ Досягнуто ліміт {self.max_per_hour} чатів/годину")
            print(f"\n⏳ Очікування {int(wait_seconds//60)}хв {int(wait_seconds%60)}с до {next_window.strftime('%H:%M')} UTC...")
            time.sleep(wait_seconds)
            logger.info(f"✅ Нове годинне вікно розпочато: {next_window.isoformat()}")

    def get_current_count(self) -> int:
        """
        Отримати кількість оброблених чатів в поточну годину

        Returns:
            Кількість оброблених чатів
        """
        window = self._get_current_hour_window()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT chats_processed FROM rate_limit WHERE hour_window = ?",
            (window,)
        )
        row = cursor.fetchone()
        conn.close()

        return row[0] if row else 0
