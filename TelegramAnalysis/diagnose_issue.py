"""
Діагностика проблеми - чому було зібрано тільки 1 чат
"""
import json
import re
from pathlib import Path


def analyze_collected_data():
    """Аналізуємо що було зібрано"""
    print("=" * 80)
    print("  DIAGNOSIS: COLLECTED DATA ANALYSIS")
    print("=" * 80 + "\n")

    data_file = Path(__file__).parent / "output" / "chat_analysis_data.txt"

    if not data_file.exists():
        print(f"   FAIL File not found: {data_file}")
        return

    print(f"   OK File found: {data_file}")
    print(f"   OK Size: {data_file.stat().st_size} bytes")

    # Read file
    with open(data_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Count chats
    chat_count = content.count("ЧАТ #")
    print(f"\n   OK Chats found in file: {chat_count}")

    if chat_count == 0:
        print("   FAIL No chats in file!")
        return

    # Find chat info
    urls = re.findall(r'URL: (.+)', content)

    print(f"\n   Collected chats:")
    for i, url in enumerate(urls, 1):
        print(f"      {i}. {url}")

    print("\n" + "=" * 80)
    print("  CONCLUSION")
    print("=" * 80)

    if chat_count == 1:
        print("\n   PROBLEM: Only 1 chat collected instead of expected ~44+")
        print("\n   Possible causes:")
        print("      1. Script was stopped manually (Ctrl+C)")
        print("      2. Telegram connection error")
        print("      3. FloodWait from Telegram API")
        print("      4. System timeout or crash")
        print("\n   RECOMMENDATION:")
        print("      Run test_collection_only.py to test collection")
        print("      with first 5 chats and see if there are errors")
    else:
        print(f"\n   OK Collected {chat_count} chats - this is normal")


def check_input_file():
    """Check input file"""
    print("\n" + "=" * 80)
    print("  INPUT FILE CHECK")
    print("=" * 80 + "\n")

    input_file = Path(__file__).parent / "@mt_offer.txt"

    if not input_file.exists():
        print(f"   FAIL File not found: {input_file}")
        return

    print(f"   OK File found: {input_file}")

    # Count chats with username
    count_with_username = 0
    count_total = 0

    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                count_total += 1
                if '\t@' in line:
                    count_with_username += 1

    print(f"   OK Total chats in file: {count_total}")
    print(f"   OK Chats with @username: {count_with_username}")
    print(f"   OK Chats without username: {count_total - count_with_username}")

    if count_with_username == 0:
        print("\n   FAIL No chats with @username!")
        print("   Script can only process chats with public username")


def check_output_files():
    """Check output files"""
    print("\n" + "=" * 80)
    print("  OUTPUT FILES CHECK")
    print("=" * 80 + "\n")

    output_dir = Path(__file__).parent / "output"

    files_to_check = [
        ("detailed/founder_chats_detailed.txt", "Founder detailed"),
        ("detailed/manager_chats_detailed.txt", "Manager detailed"),
        ("compact/founder_chats_compact.txt", "Founder compact"),
        ("compact/manager_chats_compact.txt", "Manager compact"),
        ("rejected/rejected_chats.txt", "Rejected"),
        ("other/other_category_chats.txt", "Other"),
    ]

    for file_path, description in files_to_check:
        full_path = output_dir / file_path
        if full_path.exists():
            size = full_path.stat().st_size
            if size > 0:
                # Count chats
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    count = content.count("https://t.me/")
                print(f"   OK {description}: {count} chats ({size} bytes)")
            else:
                print(f"   -- {description}: empty file")
        else:
            print(f"   -- {description}: file does not exist")


if __name__ == "__main__":
    check_input_file()
    analyze_collected_data()
    check_output_files()

    print("\n" + "=" * 80)
    print("  NEXT STEPS")
    print("=" * 80)
    print("\n  1. Run test_collection_only.py to test data collection:")
    print("     venv\\Scripts\\python.exe test_collection_only.py")
    print("\n  2. If collection works, run full analysis again:")
    print("     START.bat")
    print()
