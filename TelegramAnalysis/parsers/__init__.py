# -*- coding: utf-8 -*-
"""
Parsers package for ChatsSpider
Supports multiple input formats: TSV, JSON, plain text URLs
"""

from .base_parser import BaseParser
from .tsv_parser import TSVParser
from .json_parser import JSONParser
from .text_parser import TextParser
from .auto_detector import FormatDetector

__all__ = [
    'BaseParser',
    'TSVParser',
    'JSONParser',
    'TextParser',
    'FormatDetector'
]
