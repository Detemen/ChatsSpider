# -*- coding: utf-8 -*-
"""
Category definitions and configuration for ChatsSpider
Based on Доп.txt requirements from CommyX project
"""

from typing import Dict, Optional

# Activity thresholds
HIGH_ACTIVITY_THRESHOLD = 40  # messages/day for HIGH activity
LOW_ACTIVITY_THRESHOLD = 20   # messages/day for LOW activity
ACTIVITY_CHECK_DAYS = 7       # days to check for activity

# Category definitions with criteria from Доп.txt
# Keywords розширені для кращої валідації
CATEGORIES = {
    "Crypto и GameFi": {
        "owner": "manager",  # @Commyx_Manager
        "pricing": {"high": 2.25, "low": 1.25},
        "description": "Блокчейн-проекты и игры на крипте: сети, токены, DeFi, NFT, on-chain игры, трейдинг",
        "keywords": ["крипто", "blockchain", "defi", "nft", "токен", "ethereum", "bitcoin", "трейдинг", "web3",
                     "solana", "binance", "usdt", "криптовалют", "майнинг", "стейкинг", "airdrop", "метамаск",
                     "смарт-контракт", "dex", "swap", "холд", "альткоин", "ton", "btc", "eth"],
        "min_keywords": 2,  # Мінімум keywords для підтвердження категорії
    },
    "Арбитраж трафика": {
        "owner": "founder",  # @Commyx_Founder
        "pricing": {"high": 2.5, "low": 1.25},
        "description": "Покупка платного трафика и монетизация через партнёрки: Google Ads, Meta Ads, креативы, трекинг",
        "keywords": ["арбитраж", "трафик", "facebook ads", "google ads", "креатив", "оффер", "roi", "cpa",
                     "тизер", "пуши", "лендинг", "конверсия", "клоака", "фарм", "акки", "бурж", "affiliate",
                     "партнёрка", "профит", "слив", "залив"],
        "min_keywords": 2,
    },
    "Маркетинг/SMM": {
        "owner": "founder",
        "pricing": {"high": 2.25, "low": 1.0},
        "description": "Продвижение через соцсети: SMM, Instagram, TikTok, YouTube, контент-стратегия, инфлюенс",
        "keywords": ["smm", "маркетинг", "instagram", "tiktok", "контент", "продвижение", "реклама",
                     "таргет", "сторис", "рилс", "подписчик", "охват", "вовлечён", "блогер", "инфлюенсер",
                     "ютуб", "посев", "pr", "брендинг"],
        "min_keywords": 2,
    },
    "Дизайн и Графика": {
        "owner": "manager",
        "pricing": {"high": 2.25, "low": 1.0},
        "description": "Визуальная коммуникация: UI/UX, айдентика, графдизайн, motion, 3D-визуализация",
        "keywords": ["дизайн", "ui/ux", "figma", "графика", "айдентика", "логотип", "фотошоп",
                     "иллюстрация", "макет", "прототип", "вектор", "photoshop", "illustrator",
                     "моушн", "3d", "render", "визуал"],
        "min_keywords": 2,
    },
    "Маркет-плейсы": {
        "owner": "founder",
        "pricing": {"high": 2.25, "low": 1.0},
        "description": "Бизнес на маркетплейсах: Wildberries, Ozon, Amazon - FBO/FBS, карточки, продвижение",
        "keywords": ["wildberries", "ozon", "маркетплейс", "fbo", "fbs", "карточка товара", "wb",
                     "озон", "вайлдберриз", "селлер", "поставщик", "склад", "отгрузка", "выкуп",
                     "самовыкуп", "mpstats", "аналитика мп"],
        "min_keywords": 2,
    },
    "IT-сфера": {
        "owner": "manager",
        "pricing": {"high": 1.75, "low": 1.0},
        "description": "Разработка ПО: программирование, веб/мобильная разработка, DevOps, тестирование",
        "keywords": ["python", "javascript", "программирование", "devops", "разработка", "код", "react",
                     "backend", "frontend", "api", "java", "golang", "rust", "docker", "kubernetes",
                     "git", "github", "ci/cd", "тестирование", "qa", "баг", "деплой", "сервер",
                     "база данных", "sql", "mongodb", "linux", "aws", "typescript", "node"],
        "min_keywords": 3,  # IT потребує більше keywords для підтвердження
    },
    "Инвестирование и Акции": {
        "owner": "founder",
        "pricing": {"high": 2.0, "low": 1.0},
        "description": "Легальные инвестиции: акции, облигации, ETF, портфельные стратегии, финансовая грамотность",
        "keywords": ["акции", "инвестиции", "облигации", "etf", "дивиденды", "портфель", "биржа",
                     "тинькофф", "брокер", "iis", "иис", "ценные бумаги", "фондовый рынок",
                     "пассивный доход", "nasdaq", "s&p", "мосбиржа"],
        "min_keywords": 2,
    },
    "Фриланс/Самозанятые": {
        "owner": "founder",
        "pricing": {"high": 1.5, "low": 0.8},
        "description": "Работа на себя: поиск клиентов/заказов, удалёнка, самозанятость, фриланс-сервисы",
        "keywords": ["фриланс", "самозанятый", "удалёнка", "заказы", "upwork", "freelance", "фрилансер",
                     "заказчик", "исполнитель", "kwork", "fl.ru", "проект", "договор гпх"],
        "min_keywords": 2,
    },
    "Спорт (здоровье и форма)": {
        "owner": "founder",
        "pricing": {"high": 1.5, "low": 0.8},
        "description": "Личный фитнес и ЗОЖ: тренировки, похудение, питание, бег, йога, здоровье",
        "keywords": ["фитнес", "тренировка", "похудение", "зал", "бег", "здоровье", "спорт",
                     "качалка", "кроссфит", "йога", "калории", "диета", "белок", "пресс",
                     "мышц", "кардио", "растяжка"],
        "min_keywords": 2,
    },
    "Экспаты": {
        "owner": "manager",
        "pricing": {"high": 1.0, "low": 0.5},
        "description": "Русскоязычные за границей: релокация, виза, ВНЖ, быт, работа, адаптация в стране",
        "keywords": ["релокация", "виза", "внж", "экспат", "переезд", "эмиграция", "жизнь за границей",
                     "пмж", "иммиграция", "за границей", "сербия", "грузия", "турция", "оаэ",
                     "черногория", "казахстан", "армения", "таиланд", "бали"],
        "min_keywords": 2,
    },
    "Інше": {
        "owner": None,  # No specific owner for "other" category
        "pricing": {"high": 0, "low": 0},
        "description": "Не подходит ни под одну категорию",
        "keywords": [],
        "min_keywords": 0,
    }
}

# Анти-keywords: якщо знайдені - категорія НЕ підходить
ANTI_KEYWORDS = {
    "IT-сфера": ["трансфер", "перевозк", "такси", "доставка", "груз", "логистик", "транспорт"],
    "Crypto и GameFi": ["спорт", "фитнес", "тренировк"],
}

# Owner category mappings for easy lookup
FOUNDER_CATEGORIES = [
    "Фриланс/Самозанятые",
    "Маркетинг/SMM",
    "Арбитраж трафика",
    "Маркет-плейсы",
    "Инвестирование и Акции"
]

MANAGER_CATEGORIES = [
    "Crypto и GameFi",
    "Дизайн и Графика",
    "IT-сфера",
    "Экспаты"
]

# Prohibited content patterns (for validation)
PROHIBITED_PATTERNS = {
    "зсу_донаты": [
        "донат", "зсу", "всу", "збор коштів", "підтримка армії",
        "збір на", "підтримати", "допомога зсу", "армія"
    ],
    "fraud": [
        "обман", "развод", "лохотрон", "скам", "пирамида",
        "100% доход", "гарантированный заработок"
    ],
    "illegal": [
        "нелегал", "черн", "серые схемы", "обнал",
        "отмыв", "купить паспорт", "фейк документ"
    ]
}


def validate_category_by_content(category: str, content: str) -> tuple:
    """
    Validates if the category matches the actual content based on keywords.

    Args:
        category: Category name assigned by ChatGPT
        content: Chat content/description to validate against

    Returns:
        tuple: (is_valid: bool, reason: str, matched_keywords: list)
    """
    if not content or not category:
        return (False, "Empty content or category", [])

    # "Інше" category always passes - no validation needed
    if category == "Інше":
        return (True, "Category 'Інше' - no validation needed", [])

    # Get category config
    category_config = CATEGORIES.get(category)
    if not category_config:
        return (False, f"Unknown category: {category}", [])

    content_lower = content.lower()

    # Check anti-keywords first (disqualifying)
    anti_kw = ANTI_KEYWORDS.get(category, [])
    for anti in anti_kw:
        if anti.lower() in content_lower:
            return (False, f"Anti-keyword found: '{anti}'", [])

    # Count matching keywords
    keywords = category_config.get("keywords", [])
    min_required = category_config.get("min_keywords", 2)

    matched = []
    for kw in keywords:
        if kw.lower() in content_lower:
            matched.append(kw)

    # Check if minimum threshold met
    if len(matched) >= min_required:
        return (True, f"Found {len(matched)} keywords (min: {min_required})", matched)
    else:
        return (False, f"Only {len(matched)} keywords found (min: {min_required})", matched)


def find_best_category_by_keywords(content: str) -> tuple:
    """
    Find the best matching category based on keyword analysis.
    Used as fallback when ChatGPT category doesn't validate.

    Args:
        content: Chat content/description to analyze

    Returns:
        tuple: (best_category: str, score: int, matched_keywords: list)
    """
    if not content:
        return ("Інше", 0, [])

    content_lower = content.lower()
    best_category = "Інше"
    best_score = 0
    best_keywords = []

    for cat_name, cat_config in CATEGORIES.items():
        if cat_name == "Інше":
            continue

        # Check anti-keywords first
        anti_kw = ANTI_KEYWORDS.get(cat_name, [])
        has_anti = any(anti.lower() in content_lower for anti in anti_kw)
        if has_anti:
            continue

        # Count matching keywords
        keywords = cat_config.get("keywords", [])
        min_required = cat_config.get("min_keywords", 2)

        matched = [kw for kw in keywords if kw.lower() in content_lower]

        # Calculate score (weighted by how much it exceeds minimum)
        if len(matched) >= min_required:
            score = len(matched)
            if score > best_score:
                best_score = score
                best_category = cat_name
                best_keywords = matched

    return (best_category, best_score, best_keywords)


def get_category_owner(category: str) -> Optional[str]:
    """
    Returns category owner: 'founder', 'manager', or None

    Args:
        category: Category name from CATEGORIES dict

    Returns:
        'founder', 'manager', or None for "Інше" category
    """
    category_info = CATEGORIES.get(category, {})
    return category_info.get("owner")


def get_pricing(category: str, activity_level: str) -> float:
    """
    Returns price for category and activity level

    Args:
        category: Category name from CATEGORIES dict
        activity_level: "high" or "low"

    Returns:
        Price in USD (float)
    """
    category_info = CATEGORIES.get(category, {})
    pricing = category_info.get("pricing", {})
    level = activity_level.lower() if activity_level else "low"
    return pricing.get(level, 0.0)


def is_valid_category(category: str) -> bool:
    """
    Check if category name is valid

    Args:
        category: Category name to check

    Returns:
        True if category exists in CATEGORIES
    """
    return category in CATEGORIES


def get_all_category_names() -> list:
    """
    Get list of all valid category names

    Returns:
        List of category names
    """
    return list(CATEGORIES.keys())


# Export main constants and functions
__all__ = [
    'CATEGORIES',
    'ANTI_KEYWORDS',
    'FOUNDER_CATEGORIES',
    'MANAGER_CATEGORIES',
    'PROHIBITED_PATTERNS',
    'HIGH_ACTIVITY_THRESHOLD',
    'LOW_ACTIVITY_THRESHOLD',
    'ACTIVITY_CHECK_DAYS',
    'get_category_owner',
    'get_pricing',
    'is_valid_category',
    'get_all_category_names',
    'validate_category_by_content',
    'find_best_category_by_keywords',
]
