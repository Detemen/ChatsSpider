# -*- coding: utf-8 -*-
"""
TSV Parser for ChatsSpider
Parses tab-separated files: ID\tName\t@username
Priority: 1 (highest)
"""

import logging
from pathlib import Path
from typing import List, Dict
from .base_parser import BaseParser

logger = logging.getLogger(__name__)


class TSVParser(BaseParser):
    """
    Парсер TSV формату (найвищий пріоритет).
    Формат: ID\tНазва\t@username
    """

    def can_parse(self, file_path: Path) -> bool:
        """Перевірка розширення файлу"""
        return file_path.suffix.lower() in ['.txt', '.tsv']

    def parse(self, file_path: Path) -> List[Dict]:
        """
        Парсити TSV формат: ID\tНазва\t@username

        Args:
            file_path: Шлях до TSV файлу

        Returns:
            Список чатів

        Raises:
            ValueError: Якщо файл не в TSV форматі
        """
        chats = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Перевірка чи це дійсно TSV (мінімум 2 табуляції в більшості рядків)
            tab_counts = [line.count('\t') for line in lines[:10] if line.strip()]
            if not tab_counts or max(tab_counts) < 2:
                raise ValueError("Not a valid TSV file (need at least 2 tabs per line)")

            # Парсинг рядків
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line:  # Пропустити порожні рядки
                    continue

                parts = line.split('\t')
                if len(parts) >= 3:
                    chat_id = parts[0].strip()
                    title = parts[1].strip()
                    username = parts[2].strip().replace('@', '')

                    if username:  # Тільки якщо є username
                        chats.append({
                            'id': chat_id,
                            'title': title,
                            'username': username,
                            'url': f"https://t.me/{username}"
                        })
                else:
                    logger.warning(f"TSV parser: пропущено рядок {line_num} (недостатньо стовпців)")

            logger.info(f"TSV parser: знайдено {len(chats)} чатів у {file_path.name}")
            return chats

        except Exception as e:
            logger.error(f"TSV parser помилка: {e}")
            raise
