# -*- coding: utf-8 -*-
"""
JSON Parser for ChatsSpider
Parses JSON files with chat data
Priority: 2
"""

import json
import logging
from pathlib import Path
from typing import List, Dict
from .base_parser import BaseParser

logger = logging.getLogger(__name__)


class JSONParser(BaseParser):
    """
    Парсер JSON формату (пріоритет 2).
    Підтримує різні структури JSON.
    """

    def can_parse(self, file_path: Path) -> bool:
        """Перевірка розширення файлу"""
        return file_path.suffix.lower() == '.json'

    def parse(self, file_path: Path) -> List[Dict]:
        """
        Парсити JSON формат

        Підтримувані структури:
        - Прямий список: [{"url": "...", ...}, ...]
        - З ключем "chats": {"chats": [...]}
        - Один чат: {"url": "...", ...}

        Args:
            file_path: Шлях до JSON файлу

        Returns:
            Список чатів
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            chats = []

            # Підтримка різних JSON структур
            if isinstance(data, list):
                # Прямий список чатів
                chats = data
            elif isinstance(data, dict):
                if 'chats' in data:
                    # {'chats': [...]}
                    chats = data['chats']
                elif 'url' in data or 'username' in data:
                    # Один чат
                    chats = [data]
                else:
                    logger.warning(f"JSON parser: невідома структура у {file_path.name}")
                    return []
            else:
                logger.warning(f"JSON parser: непідтримуваний тип даних у {file_path.name}")
                return []

            # Нормалізація даних
            normalized_chats = []
            for chat in chats:
                if isinstance(chat, dict):
                    # Переконатися що є url або username
                    if 'url' in chat:
                        normalized_chats.append(chat)
                    elif 'username' in chat:
                        username = chat['username'].replace('@', '')
                        chat['url'] = f"https://t.me/{username}"
                        normalized_chats.append(chat)
                    else:
                        logger.warning(f"JSON parser: чат без url/username: {chat}")

            logger.info(f"JSON parser: знайдено {len(normalized_chats)} чатів у {file_path.name}")
            return normalized_chats

        except json.JSONDecodeError as e:
            logger.error(f"JSON parser: помилка декодування {file_path.name}: {e}")
            raise
        except Exception as e:
            logger.error(f"JSON parser помилка: {e}")
            raise
