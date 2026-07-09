# -*- coding: utf-8 -*-
"""
Logging configuration for ChatsSpider
Replaces print() statements with proper logging
"""

import logging
import sys
from pathlib import Path


def setup_logging(log_file: str = "state/chats_spider.log", level=logging.INFO):
    """
    Налаштувати логування для всієї системи

    Args:
        log_file: Шлях до файлу логів
        level: Рівень логування (DEBUG, INFO, WARNING, ERROR)

    Returns:
        Root logger instance
    """

    # Створити папку для логів якщо не існує
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Створити formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # File handler (всі логи в файл)
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Console handler (тільки INFO і вище в консоль)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Очистити попередні handlers якщо є
    root_logger.handlers.clear()

    # Додати нові handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    return root_logger
