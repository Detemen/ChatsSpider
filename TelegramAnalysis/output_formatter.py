# -*- coding: utf-8 -*-
"""
Output formatting and file routing for ChatsSpider
Handles detailed/compact formats and splits by owner (founder/manager)

MODIFIED: Додано in-memory dedup cache для O(1) перевірки дублікатів
"""

from pathlib import Path
from typing import Dict, Optional, Set
from categories_config import get_category_owner, get_pricing
import logging

logger = logging.getLogger(__name__)

# Output directories
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output"
DETAILED_DIR = OUTPUT_DIR / "detailed"
COMPACT_DIR = OUTPUT_DIR / "compact"
REJECTED_DIR = OUTPUT_DIR / "rejected"
OTHER_DIR = OUTPUT_DIR / "other"

# Create directories on module import
for dir_path in [DETAILED_DIR, COMPACT_DIR, REJECTED_DIR, OTHER_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# НОВИЙ: In-memory dedup cache для швидкої перевірки дублікатів (O(1))
_written_urls: Set[str] = set()


def get_category_tags(category: str) -> str:
    """
    Генерує теги для категорії з categories_config

    Args:
        category: Назва категорії з CATEGORIES dict

    Returns:
        "Категорія, тег1, тег2, тег3, тег4" або просто "Категорія" якщо немає keywords

    Example:
        >>> get_category_tags("Crypto и GameFi")
        "Crypto и GameFi, крипто, blockchain, defi, nft, токен"
    """
    from categories_config import CATEGORIES

    category_info = CATEGORIES.get(category, {})
    keywords = category_info.get('keywords', [])

    # Взяти перші 5 keywords
    tags = keywords[:5] if keywords else []

    # Формат: "Категорія, тег1, тег2, тег3"
    if tags:
        return f"{category}, {', '.join(tags)}"
    else:
        return category


def format_detailed(chat_data: Dict, analysis_result: Dict) -> str:
    """
    Medium format для швидкого читання

    Формат:
    Категорія, тег1, тег2, тег3, тег4
    URL
    @username
    [порожній рядок]

    Args:
        chat_data: Chat metadata from Telegram
        analysis_result: ChatGPT analysis with category, validation, description

    Returns:
        Formatted string (4 рядки на чат)

    Example output:
        Crypto и GameFi, крипто, blockchain, defi, nft, токен
        https://t.me/crypto_chat
        @crypto_admin

    """
    category = analysis_result.get('category', 'Невідомо')
    chat_url = chat_data.get('url', 'N/A')
    username = chat_data.get('username', 'N/A')

    # Обробка граничних випадків
    if username == 'N/A' or not username:
        username = 'unknown'
    if chat_url == 'N/A' or not chat_url:
        chat_url = 'https://t.me/unknown'

    # Генерувати теги
    tags_line = get_category_tags(category)

    # Формат: 4 рядки (категорія+теги, URL, @username, порожній)
    output = f"""{tags_line}
{chat_url}
@{username}

"""
    return output


def format_compact(chat_data: Dict, analysis_result: Dict) -> str:
    """
    Compact format for quick sending
    Format: URL | @username | Category | Activity

    Args:
        chat_data: Chat metadata from Telegram
        analysis_result: ChatGPT analysis with category

    Returns:
        One-line formatted string
    """
    category = analysis_result.get('category', 'Невідомо')
    activity_level = chat_data.get('activity_level', 'UNKNOWN')

    return f"{chat_data.get('url', 'N/A')} | @{chat_data.get('username', 'N/A')} | {category} | {activity_level}\n"


def format_rejected(chat_data: Dict, analysis_result: Dict) -> str:
    """
    Format for rejected chats with detailed rejection reasons

    Args:
        chat_data: Chat metadata
        analysis_result: ChatGPT analysis with validation results

    Returns:
        Formatted rejection entry
    """
    rejection_reasons = []

    # Check language
    lang_check = analysis_result.get('language_check', {})
    if lang_check.get('status') == 'FAIL':
        rejection_reasons.append(f"Мова: {lang_check.get('details', 'не вказано')}")

    # Check prohibited content
    prohibited_check = analysis_result.get('prohibited_content', {})
    if prohibited_check.get('status') == 'FAIL':
        rejection_reasons.append(f"Заборонений контент: {prohibited_check.get('details', 'не вказано')}")

    # Check category fit
    fit_check = analysis_result.get('category_fit', {})
    if fit_check.get('status') == 'FAIL':
        rejection_reasons.append(f"Не відповідає категорії: {fit_check.get('details', 'не вказано')}")

    reason_text = "; ".join(rejection_reasons) if rejection_reasons else "Невідома причина"

    return f"""
{chat_data.get('url', 'N/A')} | @{chat_data.get('username', 'N/A')} | {chat_data.get('title', 'N/A')}
❌ ВІДХИЛЕНО: {reason_text}
{'='*80}
"""


def save_chat_to_files(chat_data: Dict, analysis_result: Dict):
    """
    Route chat to appropriate output files based on validation and category
    MODIFIED: Перевірка дублікатів через in-memory cache перед записом

    Routing logic:
    - Invalid (failed validation) → rejected/rejected_chats.txt
    - Category "Інше" → other/other_category_chats.txt
    - Owner "founder" → detailed/founder_*.txt, compact/founder_*.txt
    - Owner "manager" → detailed/manager_*.txt, compact/manager_*.txt

    Args:
        chat_data: Chat metadata from Telegram
        analysis_result: ChatGPT analysis results
    """
    global _written_urls

    chat_url = chat_data.get('url', '')

    # НОВЕ: Перевірка дублікатів (O(1) через set)
    if chat_url in _written_urls:
        logger.warning(f"Дублікат виявлено, пропущено: {chat_url}")
        print(f"   ⚠️  Дублікат пропущено: {chat_url}")
        return

    category = analysis_result.get('category', 'Інше')
    is_valid = analysis_result.get('is_valid', False)

    # Handle rejected chats
    if not is_valid:
        rejected_file = REJECTED_DIR / "rejected_chats.txt"
        with open(rejected_file, 'a', encoding='utf-8') as f:
            f.write(format_rejected(chat_data, analysis_result))
        print(f"   ❌ Чат відхилено: {rejected_file.name}")

        # НОВЕ: Додати до cache навіть відхилені чати
        _written_urls.add(chat_url)
        return

    # Handle "Інше" category
    if category == "Інше":
        other_file = OTHER_DIR / "other_category_chats.txt"
        with open(other_file, 'a', encoding='utf-8') as f:
            f.write(format_detailed(chat_data, analysis_result))
        print(f"   ⚠️  Категорія 'Інше': {other_file.name}")

        # НОВЕ: Додати до cache
        _written_urls.add(chat_url)
        return

    # Determine owner and file paths
    owner = get_category_owner(category)

    if owner == "founder":
        detailed_file = DETAILED_DIR / "founder_chats_detailed.txt"
        compact_file = COMPACT_DIR / "founder_chats_compact.txt"
        owner_name = "@Commyx_Founder"
    elif owner == "manager":
        detailed_file = DETAILED_DIR / "manager_chats_detailed.txt"
        compact_file = COMPACT_DIR / "manager_chats_compact.txt"
        owner_name = "@Commyx_Manager"
    else:
        print(f"   ⚠️  Невідомий власник для категорії: {category}")
        return

    # Write detailed format
    with open(detailed_file, 'a', encoding='utf-8') as f:
        f.write(format_detailed(chat_data, analysis_result))

    # Write compact format
    with open(compact_file, 'a', encoding='utf-8') as f:
        f.write(format_compact(chat_data, analysis_result))

    # НОВЕ: Додати до cache після успішного запису
    _written_urls.add(chat_url)

    print(f"   ✅ Збережено для {owner_name}: {detailed_file.name}")


def load_dedup_cache_from_state(state_manager):
    """
    НОВИЙ: Завантажити dedup cache з state manager при старті.
    Це дозволяє продовжувати роботу без перезаписування існуючих файлів.

    Args:
        state_manager: Екземпляр StateManager з доступом до БД
    """
    global _written_urls

    # Завантажити всі оброблені URL з state manager
    _written_urls = state_manager._processed_cache.copy()

    logger.info(f"Dedup cache завантажено: {len(_written_urls)} URLs")
    print(f"📋 Dedup cache: {len(_written_urls)} вже оброблених чатів\n")


def clear_dedup_cache():
    """
    НОВИЙ: Очистити dedup cache (для --fresh-start)
    """
    global _written_urls
    _written_urls.clear()
    logger.info("Dedup cache очищено")


def clear_output_files():
    """
    Clear all output files at start of new run
    Removes all .txt files from output directories

    ВАЖЛИВО: Викликати тільки з --fresh-start flag!
    В нормальному режимі система використовує append mode.
    """
    global _written_urls

    for dir_path in [DETAILED_DIR, COMPACT_DIR, REJECTED_DIR, OTHER_DIR]:
        for file_path in dir_path.glob("*.txt"):
            try:
                file_path.unlink()
                logger.debug(f"Видалено: {file_path}")
            except Exception as e:
                logger.error(f"Не вдалося видалити {file_path}: {e}")
                print(f"⚠️  Не вдалося видалити {file_path}: {e}")

    # Очистити dedup cache
    _written_urls.clear()

    logger.warning("🗑️  Очищено ВСІ попередні результати (--fresh-start)")
    print("🗑️  Очищено попередні результати\n")


def get_output_statistics() -> Dict:
    """
    Get statistics about processed chats from output files

    Returns:
        Dict with counts: {
            'founder_total': int,
            'manager_total': int,
            'rejected': int,
            'other': int
        }
    """
    stats = {
        'founder_total': 0,
        'manager_total': 0,
        'rejected': 0,
        'other': 0
    }

    # Count founder chats (compact file has one chat per line)
    founder_compact = COMPACT_DIR / "founder_chats_compact.txt"
    if founder_compact.exists():
        with open(founder_compact, 'r', encoding='utf-8') as f:
            stats['founder_total'] = len(f.readlines())

    # Count manager chats
    manager_compact = COMPACT_DIR / "manager_chats_compact.txt"
    if manager_compact.exists():
        with open(manager_compact, 'r', encoding='utf-8') as f:
            stats['manager_total'] = len(f.readlines())

    # Count rejected (count occurrences of "ВІДХИЛЕНО")
    rejected_file = REJECTED_DIR / "rejected_chats.txt"
    if rejected_file.exists():
        with open(rejected_file, 'r', encoding='utf-8') as f:
            content = f.read()
            stats['rejected'] = content.count('ВІДХИЛЕНО')

    # Count other (count URLs as начало запису)
    other_file = OTHER_DIR / "other_category_chats.txt"
    if other_file.exists():
        with open(other_file, 'r', encoding='utf-8') as f:
            content = f.read()
            stats['other'] = content.count('https://t.me/')

    return stats


def print_final_statistics():
    """
    Print final statistics report after processing completes
    """
    stats = get_output_statistics()

    print("\n" + "="*80)
    print("📊 ФІНАЛЬНА СТАТИСТИКА:")
    print("="*80)
    print(f"   ✅ @Commyx_Founder: {stats['founder_total']} чатів")
    print(f"   ✅ @Commyx_Manager: {stats['manager_total']} чатів")
    print(f"   ⚠️  Категорія 'Інше': {stats['other']} чатів")
    print(f"   ❌ Відхилено: {stats['rejected']} чатів")
    print(f"   📈 Всього прийнято: {stats['founder_total'] + stats['manager_total']} чатів")
    print("="*80)
    print("\n💾 Файли збережено в:")
    print(f"   Детально: {DETAILED_DIR}")
    print(f"   Компактно: {COMPACT_DIR}")
    print(f"   Відхилені: {REJECTED_DIR}")
    print(f"   Інше: {OTHER_DIR}")
    print("="*80 + "\n")


# Export functions
__all__ = [
    'format_detailed',
    'format_compact',
    'format_rejected',
    'save_chat_to_files',
    'clear_output_files',
    'get_output_statistics',
    'print_final_statistics',
]
