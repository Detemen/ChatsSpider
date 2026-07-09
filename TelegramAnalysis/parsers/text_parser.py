# -*- coding: utf-8 -*-
"""
Text Parser for ChatsSpider
Parses plain text files with Telegram URLs
Priority: 3 (fallback)
"""

import re
import logging
from pathlib import Path
from typing import List, Dict
from .base_parser import BaseParser

logger = logging.getLogger(__name__)


class TextParser(BaseParser):
    """
    Парсер plain text формату (найнижчий пріоритет - fallback).
    Шукає URL Telegram чатів в тексті.
    """

    # Regex pattern для Telegram URLs
    URL_PATTERN = re.compile(r'https?://t\.me/([a-zA-Z0-9_]+)')

    def can_parse(self, file_path: Path) -> bool:
        """Підтримує .txt файли"""
        return file_path.suffix.lower() == '.txt'

    def parse(self, file_path: Path) -> List[Dict]:
        """
        Парсити текстові файли з URL (один на рядок або в тексті)

        Шукає всі URL вигляду: https://t.me/username

        Args:
            file_path: Шлях до текстового файлу

        Returns:
            Список чатів
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            chats = []
            seen_usernames = set()  # Для дедуплікації

            # Знайти всі Telegram URLs
            for match in self.URL_PATTERN.finditer(content):
                username = match.group(1)
                url = match.group(0)

                # Пропустити дублікати
                if username in seen_usernames:
                    continue

                seen_usernames.add(username)

                chats.append({
                    'username': username,
                    'url': url,
                    'title': username  # Буде оновлено при збиранні даних
                })

            logger.info(f"Text parser: знайдено {len(chats)} унікальних URLs у {file_path.name}")
            return chats

        except Exception as e:
            logger.error(f"Text parser помилка: {e}")
            raise
