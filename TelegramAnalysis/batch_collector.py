# -*- coding: utf-8 -*-
"""
Batch Collector for ChatsSpider
Collects batches of 10 ACTIVE chats from Telegram before processing with ChatGPT
IMPORTANT: This is NOT about ChatGPT batching - Playwright doesn't support parallel requests
"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)


class BatchCollector:
    """
    Збирає батчі АКТИВНИХ чатів з Telegram.
    ВАЖЛИВО: Це НЕ про ChatGPT batching - Playwright не підтримує паралельні запити.
    Батчинг = організаційне групування, збір 10 активних чатів ПЕРЕД обробкою.
    """

    def __init__(self, db_path: str = "state/chats.db", batch_size: int = 10):
        self.db_path = Path(db_path)
        self.batch_size = batch_size
        self._ensure_db()

    def _ensure_db(self):
        """Створити таблицю pending_batch якщо не існує"""
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS pending_batch (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_number INTEGER,
                chat_url TEXT,
                chat_data TEXT,
                added_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_batch_number ON pending_batch(batch_number)')
        conn.commit()
        conn.close()

        logger.debug("Batch collector table ensured")

    def add_to_batch(self, chat_data: Dict) -> bool:
        """
        Додати активний чат до поточного батчу.

        Args:
            chat_data: Дані чату з Telegram

        Returns:
            True якщо батч готовий (досягнуто batch_size)
        """
        current_batch_num = self._get_current_batch_number()

        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            INSERT INTO pending_batch (batch_number, chat_url, chat_data)
            VALUES (?, ?, ?)
        ''', (current_batch_num, chat_data['url'], json.dumps(chat_data, ensure_ascii=False)))
        conn.commit()
        conn.close()

        logger.info(f"Додано до батчу #{current_batch_num}: {chat_data['url']}")

        # Перевірка чи батч готовий
        current_size = self._get_batch_size(current_batch_num)
        is_ready = current_size >= self.batch_size

        if is_ready:
            logger.info(f"✅ Батч #{current_batch_num} готовий ({current_size} чатів)")

        return is_ready

    def get_current_batch(self) -> List[Dict]:
        """
        Отримати всі чати в поточному батчі

        Returns:
            Список чатів в поточному батчі
        """
        batch_num = self._get_current_batch_number()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute('''
            SELECT chat_data FROM pending_batch
            WHERE batch_number = ?
            ORDER BY id
        ''', (batch_num,))

        batch = [json.loads(row[0]) for row in cursor.fetchall()]
        conn.close()

        logger.info(f"Поточний батч #{batch_num}: {len(batch)} чатів")
        return batch

    def clear_current_batch(self):
        """
        Очистити поточний батч після обробки.
        Інкрементувати batch_number для наступного батчу.
        """
        batch_num = self._get_current_batch_number()

        conn = sqlite3.connect(self.db_path)
        # Видалити оброблений батч
        conn.execute('DELETE FROM pending_batch WHERE batch_number = ?', (batch_num,))
        conn.commit()
        conn.close()

        logger.info(f"Батч #{batch_num} очищено")

    def _get_current_batch_number(self) -> int:
        """
        Отримати номер поточного батчу

        Returns:
            Номер поточного батчу (або 1 якщо це перший)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute('SELECT MAX(batch_number) FROM pending_batch')
        max_num = cursor.fetchone()[0]
        conn.close()

        return max_num if max_num is not None else 1

    def _get_batch_size(self, batch_num: int) -> int:
        """
        Скільки чатів в батчі

        Args:
            batch_num: Номер батчу

        Returns:
            Кількість чатів в батчі
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            'SELECT COUNT(*) FROM pending_batch WHERE batch_number = ?',
            (batch_num,)
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def has_pending_chats(self) -> bool:
        """
        Чи є чати в поточному батчі (навіть якщо не повний)

        Returns:
            True якщо є хоча б один чат
        """
        batch_num = self._get_current_batch_number()
        return self._get_batch_size(batch_num) > 0

    def get_pending_count(self) -> int:
        """
        Скільки чатів в поточному батчі

        Returns:
            Кількість чатів що чекають обробки
        """
        batch_num = self._get_current_batch_number()
        return self._get_batch_size(batch_num)
