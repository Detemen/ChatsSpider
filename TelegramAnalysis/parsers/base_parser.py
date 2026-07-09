# -*- coding: utf-8 -*-
"""
Base Parser class for ChatsSpider
Defines abstract interface for all format parsers
"""

from abc import ABC, abstractmethod
from typing import List, Dict
from pathlib import Path


class BaseParser(ABC):
    """
    Абстрактний базовий клас для всіх парсерів.
    Кожен парсер має реалізувати can_parse() та parse().
    """

    @abstractmethod
    def can_parse(self, file_path: Path) -> bool:
        """
        Чи може парсер обробити цей файл

        Args:
            file_path: Шлях до файлу

        Returns:
            True якщо парсер може обробити файл
        """
        pass

    @abstractmethod
    def parse(self, file_path: Path) -> List[Dict]:
        """
        Парсити файл і повернути список чатів

        Args:
            file_path: Шлях до файлу

        Returns:
            Список чатів: [{'url': '...', 'username': '...', 'title': '...'}, ...]
        """
        pass
