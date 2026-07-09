# filter_database.py
# -*- coding: utf-8 -*-
"""
Скрипт для фільтрації та експорту даних з spider.db

Можливості:
- Перегляд статистики бази
- Фільтрація каналів за ключовими словами
- Фільтрація чатів за ключовими словами
- Експорт у текстові файли
- Пошук по title, about, username
"""

import sqlite3
import sys
from pathlib import Path
from typing import List, Optional

DB_PATH = Path("output/spider.db")


class DatabaseFilter:
    def __init__(self, db_path: Path = DB_PATH):
        if not db_path.exists():
            print(f"Baza danykh ne znaidena: {db_path}")
            sys.exit(1)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def get_stats(self):
        """Отримати статистику бази даних"""
        channels_count = self.conn.execute("SELECT COUNT(*) FROM channels").fetchone()[0]
        chats_count = self.conn.execute("SELECT COUNT(*) FROM chats").fetchone()[0]

        print("\n" + "="*60)
        print("STATYSTYKA BAZY DANYKH")
        print("="*60)
        print(f"Kanaliv: {channels_count}")
        print(f"Chativ: {chats_count}")
        print(f"Vsoho zapysiv: {channels_count + chats_count}")
        print("="*60 + "\n")

    def search_channels(self, keyword: Optional[str] = None, limit: Optional[int] = None) -> List[sqlite3.Row]:
        """Пошук каналів за ключовим словом"""
        if keyword:
            query = """
                SELECT username, title, about, source_session
                FROM channels
                WHERE username LIKE ? OR title LIKE ? OR about LIKE ?
                ORDER BY last_seen_ts DESC
            """
            pattern = f"%{keyword}%"
            cursor = self.conn.execute(query, (pattern, pattern, pattern))
        else:
            query = """
                SELECT username, title, about, source_session
                FROM channels
                ORDER BY last_seen_ts DESC
            """
            cursor = self.conn.execute(query)

        if limit:
            return cursor.fetchmany(limit)
        return cursor.fetchall()

    def search_chats(self, keyword: Optional[str] = None, limit: Optional[int] = None) -> List[sqlite3.Row]:
        """Пошук чатів за ключовим словом"""
        if keyword:
            query = """
                SELECT username, title, about, channel_username, source_session
                FROM chats
                WHERE username LIKE ? OR title LIKE ? OR about LIKE ?
                ORDER BY last_seen_ts DESC
            """
            pattern = f"%{keyword}%"
            cursor = self.conn.execute(query, (pattern, pattern, pattern))
        else:
            query = """
                SELECT username, title, about, channel_username, source_session
                FROM chats
                ORDER BY last_seen_ts DESC
            """
            cursor = self.conn.execute(query)

        if limit:
            return cursor.fetchmany(limit)
        return cursor.fetchall()

    def export_channels(self, output_file: str, keyword: Optional[str] = None):
        """Експорт каналів в текстовий файл"""
        channels = self.search_channels(keyword)

        with open(output_file, 'w', encoding='utf-8') as f:
            for ch in channels:
                f.write(f"https://t.me/{ch['username']}\n")

        print(f"Eksportovano {len(channels)} kanaliv v {output_file}")

    def export_chats(self, output_file: str, keyword: Optional[str] = None):
        """Експорт чатів в текстовий файл"""
        chats = self.search_chats(keyword)

        with open(output_file, 'w', encoding='utf-8') as f:
            for chat in chats:
                f.write(f"https://t.me/{chat['username']}\n")

        print(f"Eksportovano {len(chats)} chativ v {output_file}")

    def export_detailed(self, output_file: str, type_: str = "channels", keyword: Optional[str] = None):
        """Детальний експорт з описами"""
        if type_ == "channels":
            items = self.search_channels(keyword)
        else:
            items = self.search_chats(keyword)

        with open(output_file, 'w', encoding='utf-8') as f:
            for item in items:
                f.write(f"Username: {item['username']}\n")
                f.write(f"URL: https://t.me/{item['username']}\n")
                f.write(f"Title: {item['title'] or 'N/A'}\n")
                f.write(f"About: {item['about'] or 'N/A'}\n")
                if type_ == "chats":
                    f.write(f"From Channel: {item['channel_username'] or 'N/A'}\n")
                f.write(f"Source: {item['source_session']}\n")
                f.write("-" * 60 + "\n\n")

        print(f"Detalnyi eksport {len(items)} zapysiv v {output_file}")

    def print_results(self, items: List[sqlite3.Row], type_: str = "channels"):
        """Вивести результати в консоль"""
        if not items:
            print("Nicho ne znaideno")
            return

        print(f"\n{'='*80}")
        print(f"Znaideno: {len(items)} {type_}")
        print(f"{'='*80}\n")

        for i, item in enumerate(items, 1):
            print(f"{i}. https://t.me/{item['username']}")
            if item['title']:
                print(f"   Title: {item['title']}")
            if item['about']:
                about = item['about'][:100] + "..." if len(item['about']) > 100 else item['about']
                print(f"   About: {about}")
            if type_ == "chats" and item['channel_username']:
                print(f"   Vid kanalu: {item['channel_username']}")
            print()

    def close(self):
        self.conn.close()


def print_menu():
    print("\n" + "="*60)
    print("FILTRATSIIA BAZY DANYKH TELEGRAM SPIDER")
    print("="*60)
    print("1. Pokazaty statystyku")
    print("2. Shukaty kanaly")
    print("3. Shukaty chaty")
    print("4. Eksport vsikh kanaliv (spysok URL)")
    print("5. Eksport vsikh chativ (spysok URL)")
    print("6. Eksport kanaliv z filtrom (spysok URL)")
    print("7. Eksport chativ z filtrom (spysok URL)")
    print("8. Detalnyi eksport kanaliv")
    print("9. Detalnyi eksport chativ")
    print("0. Vykhid")
    print("="*60)


def main():
    db = DatabaseFilter()
    try:
        while True:
            print_menu()
            choice = input("\nВиберіть опцію (0-9): ").strip()

            if choice == "0":
                print("Do pobachennia!")
                break

            elif choice == "1":
                db.get_stats()

            elif choice == "2":
                keyword = input("Введіть ключове слово для пошуку (Enter для всіх): ").strip()
                limit = input("Скільки показати? (Enter для всіх): ").strip()
                limit = int(limit) if limit else None

                keyword = keyword if keyword else None
                results = db.search_channels(keyword, limit)
                db.print_results(results, "channels")

            elif choice == "3":
                keyword = input("Введіть ключове слово для пошуку (Enter для всіх): ").strip()
                limit = input("Скільки показати? (Enter для всіх): ").strip()
                limit = int(limit) if limit else None

                keyword = keyword if keyword else None
                results = db.search_chats(keyword, limit)
                db.print_results(results, "chats")

            elif choice == "4":
                output = input("Назва файлу (за замовчуванням: output/all_channels.txt): ").strip()
                output = output if output else "output/all_channels.txt"
                db.export_channels(output)

            elif choice == "5":
                output = input("Назва файлу (за замовчуванням: output/all_chats.txt): ").strip()
                output = output if output else "output/all_chats.txt"
                db.export_chats(output)

            elif choice == "6":
                keyword = input("Введіть ключове слово для фільтру: ").strip()
                if not keyword:
                    print("Potribno vvesty kliuchove slovo!")
                    continue
                output = input(f"Назва файлу (за замовчуванням: output/channels_{keyword}.txt): ").strip()
                output = output if output else f"output/channels_{keyword}.txt"
                db.export_channels(output, keyword)

            elif choice == "7":
                keyword = input("Введіть ключове слово для фільтру: ").strip()
                if not keyword:
                    print("Potribno vvesty kliuchove slovo!")
                    continue
                output = input(f"Назва файлу (за замовчуванням: output/chats_{keyword}.txt): ").strip()
                output = output if output else f"output/chats_{keyword}.txt"
                db.export_chats(output, keyword)

            elif choice == "8":
                keyword = input("Введіть ключове слово для фільтру (Enter для всіх): ").strip()
                keyword = keyword if keyword else None
                output = input("Назва файлу (за замовчуванням: output/channels_detailed.txt): ").strip()
                output = output if output else "output/channels_detailed.txt"
                db.export_detailed(output, "channels", keyword)

            elif choice == "9":
                keyword = input("Введіть ключове слово для фільтру (Enter для всіх): ").strip()
                keyword = keyword if keyword else None
                output = input("Назва файлу (за замовчуванням: output/chats_detailed.txt): ").strip()
                output = output if output else "output/chats_detailed.txt"
                db.export_detailed(output, "chats", keyword)

            else:
                print("Nevirnyi vybir! Sprobuite shche raz.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
