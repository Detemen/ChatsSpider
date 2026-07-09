"""
Скрипт міграції проекту Telegram Analysis в нову папку
"""
import shutil
from pathlib import Path

# Поточна папка
SOURCE_DIR = Path(__file__).parent
# Нова папка
TARGET_DIR = Path("f:/PY/TelegramAnalysis")

# Файли які потрібно скопіювати
FILES_TO_COPY = [
    # Основні скрипти
    "analyze_chats_playwright.py",
    "categories_config.py",
    "validation.py",
    "output_formatter.py",
    "RUN_ALL.py",

    # Тести та діагностика
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
    "Доп.txt",

    # Дані
    "@mt_offer.txt",
    "test_active_chats.txt",
    "requirements.txt",

    # Конфігурація (якщо є)
    ".env",
]

# Папки які потрібно створити
DIRS_TO_CREATE = [
    "output/detailed",
    "output/compact",
    "output/rejected",
    "output/other",
    "temp_prompts",
]


def migrate():
    """Виконує міграцію файлів"""
    print("=" * 80)
    print("  МІГРАЦІЯ ПРОЕКТУ TELEGRAM ANALYSIS")
    print("=" * 80 + "\n")

    print(f"Джерело: {SOURCE_DIR}")
    print(f"Призначення: {TARGET_DIR}\n")

    # Створюємо цільову папку
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    print(f"   OK Створено папку: {TARGET_DIR}\n")

    # Створюємо підпапки
    print("Створення структури папок:")
    for dir_path in DIRS_TO_CREATE:
        full_path = TARGET_DIR / dir_path
        full_path.mkdir(parents=True, exist_ok=True)
        print(f"   OK {dir_path}")

    # Копіюємо файли
    print("\nКопіювання файлів:")
    copied_count = 0
    skipped_count = 0

    for file_name in FILES_TO_COPY:
        source_file = SOURCE_DIR / file_name
        target_file = TARGET_DIR / file_name

        if source_file.exists():
            shutil.copy2(source_file, target_file)
            print(f"   OK {file_name}")
            copied_count += 1
        else:
            print(f"   -- ПРОПУЩЕНО {file_name} (не знайдено)")
            skipped_count += 1

    # Копіюємо виртуальне середовище (це може зайняти час)
    print("\nКопіювання віртуального середовища...")
    source_venv = SOURCE_DIR / "venv"
    target_venv = TARGET_DIR / "venv"

    if source_venv.exists():
        print("   Це може зайняти 1-2 хвилини...")
        try:
            shutil.copytree(source_venv, target_venv, dirs_exist_ok=True)
            print("   OK venv скопійовано")
        except Exception as e:
            print(f"   ПОМИЛКА копіювання venv: {e}")
            print("   РЕКОМЕНДАЦІЯ: Створіть нове віртуальне середовище після міграції:")
            print("      cd TelegramAnalysis")
            print("      python -m venv venv")
            print("      venv\\Scripts\\activate")
            print("      pip install -r requirements.txt")
            print("      playwright install")
    else:
        print("   -- venv не знайдено, створіть нове після міграції")

    # Статистика
    print("\n" + "=" * 80)
    print("  РЕЗУЛЬТАТ МІГРАЦІЇ")
    print("=" * 80)
    print(f"\n   Скопійовано файлів: {copied_count}")
    print(f"   Пропущено файлів: {skipped_count}")
    print(f"\n   Нова папка проекту: {TARGET_DIR}")

    # Інструкції
    print("\n" + "=" * 80)
    print("  НАСТУПНІ КРОКИ")
    print("=" * 80)
    print("\n1. Перейдіть в нову папку:")
    print(f"   cd {TARGET_DIR}")

    print("\n2. Якщо venv не скопіювалось, створіть нове віртуальне середовище:")
    print("   python -m venv venv")
    print("   venv\\Scripts\\activate")
    print("   pip install -r requirements.txt")
    print("   playwright install")

    print("\n3. Перевірте що все працює:")
    print("   venv\\Scripts\\python.exe test_imports.py")

    print("\n4. Запустіть аналіз:")
    print("   START.bat")

    print("\n")


if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"\n❌ ПОМИЛКА: {e}")
        import traceback
        traceback.print_exc()
