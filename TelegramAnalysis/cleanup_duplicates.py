"""
Видалення дублікатів файлів TelegramAnalysis з кореня ChatsSpider
"""
import os
from pathlib import Path

# Папка ChatsSpider
CHATSPIDER_DIR = Path("f:/PY/ChatsSpider")
# Папка TelegramAnalysis (нова локація)
TELEGRAM_ANALYSIS_DIR = CHATSPIDER_DIR / "TelegramAnalysis"

# Файли проекту TelegramAnalysis які можуть бути дублікатами в корені
TELEGRAM_ANALYSIS_FILES = [
    # Основні скрипти
    "analyze_chats_playwright.py",
    "categories_config.py",
    "validation.py",
    "output_formatter.py",
    "RUN_ALL.py",

    # Тести
    "test_collection_only.py",
    "test_chatgpt_parsing.py",
    "test_imports.py",
    "diagnose_issue.py",

    # Лаунчери
    "START.bat",

    # Документація
    "STATUS_AND_NEXT_STEPS.txt",
    "CHANGELOG.txt",
    "ІНСТРУКЦІЯ.txt",
    "МІГРАЦІЯ_ЗАВЕРШЕНА.txt",
    "РЕОРГАНІЗАЦІЯ_ЗАВЕРШЕНА.txt",
    "README.txt",

    # Скрипти міграції
    "migrate_to_new_folder.py",
    "reorganize.py",
    "update_paths.py",
    "cleanup_duplicates.py",
]


def cleanup_duplicates():
    """Видаляє дублікати файлів з кореня ChatsSpider"""
    print("=" * 80)
    print("  ОЧИЩЕННЯ ДУБЛІКАТІВ ФАЙЛІВ")
    print("=" * 80 + "\n")

    print(f"Перевірка кореня: {CHATSPIDER_DIR}")
    print(f"Проект знаходиться в: {TELEGRAM_ANALYSIS_DIR}\n")

    deleted_count = 0
    skipped_count = 0

    print("Видалення дублікатів:\n")

    for filename in TELEGRAM_ANALYSIS_FILES:
        file_in_root = CHATSPIDER_DIR / filename
        file_in_project = TELEGRAM_ANALYSIS_DIR / filename

        # Перевіряємо чи файл існує в корені
        if file_in_root.exists():
            # Перевіряємо чи файл є в папці проекту
            if file_in_project.exists():
                try:
                    os.remove(file_in_root)
                    print(f"   OK Видалено: {filename}")
                    deleted_count += 1
                except Exception as e:
                    print(f"   ПОМИЛКА видалення {filename}: {e}")
                    skipped_count += 1
            else:
                print(f"   -- Пропущено {filename} (немає в TelegramAnalysis)")
                skipped_count += 1

    # Перевірка папки temp_prompts в корені
    temp_prompts_root = CHATSPIDER_DIR / "temp_prompts"
    if temp_prompts_root.exists() and temp_prompts_root.is_dir():
        try:
            import shutil
            shutil.rmtree(temp_prompts_root)
            print(f"\n   OK Видалено папку: temp_prompts/")
            deleted_count += 1
        except Exception as e:
            print(f"\n   ПОМИЛКА видалення temp_prompts: {e}")

    print("\n" + "=" * 80)
    print("  РЕЗУЛЬТАТ")
    print("=" * 80)
    print(f"\n   Видалено файлів: {deleted_count}")
    print(f"   Пропущено: {skipped_count}")

    print("\n" + "=" * 80)
    print("  ФАЙЛИ ЗАЛИШАЮТЬСЯ В ChatsSpider")
    print("=" * 80)
    print("\nЦі файли НЕ належать TelegramAnalysis і залишаються:")

    # Показуємо які файли залишаються
    other_files = []
    for item in CHATSPIDER_DIR.iterdir():
        if item.is_file() and item.suffix in ['.py', '.bat', '.txt']:
            if item.name not in TELEGRAM_ANALYSIS_FILES:
                other_files.append(item.name)

    if other_files:
        for filename in sorted(other_files)[:10]:  # Показуємо перші 10
            print(f"   - {filename}")
        if len(other_files) > 10:
            print(f"   ... та ще {len(other_files) - 10} файлів")

    print("\n" + "=" * 80)
    print("  ГОТОВО")
    print("=" * 80)
    print(f"\nПроект TelegramAnalysis знаходиться в:")
    print(f"   {TELEGRAM_ANALYSIS_DIR}")
    print("\nДля запуску:")
    print(f"   cd {TELEGRAM_ANALYSIS_DIR}")
    print("   START.bat\n")


if __name__ == "__main__":
    try:
        cleanup_duplicates()
    except Exception as e:
        print(f"\n❌ ПОМИЛКА: {e}")
        import traceback
        traceback.print_exc()
