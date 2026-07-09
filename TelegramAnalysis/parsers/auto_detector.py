# -*- coding: utf-8 -*-
"""
Auto Format Detector for ChatsSpider
Automatically detects file format and uses appropriate parser
Uses priority ordering: TSV > JSON > Text
"""

import logging
from pathlib import Path
from typing import List, Dict
from .tsv_parser import TSVParser
from .json_parser import JSONParser
from .text_parser import TextParser

logger = logging.getLogger(__name__)


class FormatDetector:
    """
    Автоматичне визначення формату файлу з пріоритетами.
    Пріоритет: TSV (1) > JSON (2) > Text (3)
    """

    def __init__(self):
        # Порядок має значення! Найвищий пріоритет перший
        self.parsers = [
            ('TSV', TSVParser()),      # Пріоритет 1
            ('JSON', JSONParser()),    # Пріоритет 2
            ('Text', TextParser()),    # Пріоритет 3 (fallback)
        ]

    def detect_and_parse(self, file_path: Path) -> List[Dict]:
        """
        Автоматично визначити формат і парсити файл

        Спробує кожен парсер в порядку пріоритету.
        Повертає результат першого успішного парсера.

        Args:
            file_path: Шлях до файлу

        Returns:
            Список чатів або порожній список якщо не вдалося парсити
        """
        if not file_path.exists():
            logger.error(f"Файл не знайдено: {file_path}")
            return []

        for parser_name, parser in self.parsers:
            # Перевірка чи парсер підтримує файл
            if not parser.can_parse(file_path):
                continue

            # Спроба парсингу
            try:
                logger.debug(f"Спроба парсингу {file_path.name} з {parser_name} parser...")
                chats = parser.parse(file_path)

                # Валідація результату
                if self._validate_result(chats):
                    logger.info(f"✅ Файл {file_path.name} успішно оброблено через {parser_name} parser ({len(chats)} чатів)")
                    return chats
                else:
                    logger.warning(f"⚠️ {parser_name} parser повернув невалідний результат для {file_path.name}")
                    continue

            except ValueError as e:
                # Очікувана помилка - формат не підходить, спробуємо наступний
                logger.debug(f"{parser_name} parser: формат не підходить для {file_path.name} ({e})")
                continue

            except Exception as e:
                # Неочікувана помилка - логуємо і продовжуємо
                logger.warning(f"⚠️ {parser_name} parser помилка для {file_path.name}: {e}")
                continue

        # Жоден парсер не спрацював
        logger.error(f"❌ Не вдалося визначити формат файлу: {file_path.name}")
        return []

    def _validate_result(self, chats: List[Dict]) -> bool:
        """
        Валідація результату парсингу

        Args:
            chats: Список чатів від парсера

        Returns:
            True якщо результат валідний
        """
        if not chats:
            return False

        if not isinstance(chats, list):
            return False

        # Перевірка що кожен чат має url
        for chat in chats:
            if not isinstance(chat, dict):
                return False
            if 'url' not in chat:
                return False

        return True

    def get_supported_extensions(self) -> List[str]:
        """
        Отримати список підтримуваних розширень

        Returns:
            Список розширень: ['.txt', '.json', '.tsv']
        """
        extensions = set()
        for _, parser in self.parsers:
            # Перевірка різних розширень
            for ext in ['.txt', '.tsv', '.json']:
                dummy_path = Path(f"test{ext}")
                if parser.can_parse(dummy_path):
                    extensions.add(ext)

        return sorted(extensions)
