# -*- coding: utf-8 -*-
"""
Test keyword validation for category checking
"""

import sys
from pathlib import Path

# Add project directory to path
sys.path.insert(0, str(Path(__file__).parent))

from categories_config import validate_category_by_content, find_best_category_by_keywords

print("=" * 60)
print("ТЕСТ KEYWORD-ВАЛІДАЦІЇ")
print("=" * 60)

# Test 1: Transfer company incorrectly classified as IT
print("\n1. Тест: Трансфер-компанія класифікована як IT-сфера")
print("-" * 50)

transfer_content = """
Восток ТрансмNRU - трансферы Монголия-Россия
Перевозки грузов и пассажиров из Улан-Батора в Улан-Удэ
Расписание рейсов, цены на доставку
Контактный телефон для заказа трансфера
"""

is_valid, reason, matched = validate_category_by_content("IT-сфера", transfer_content)
print(f"   Категорія: IT-сфера")
print(f"   Результат: {'PASS' if is_valid else 'FAIL'}")
print(f"   Причина: {reason}")
print(f"   Keywords: {matched}")

if not is_valid:
    print("\n   [OK] Anti-keyword працює - трансфер НЕ проходить як IT")
    best_cat, score, best_kw = find_best_category_by_keywords(transfer_content)
    print(f"   Пропонована категорія: {best_cat} (score: {score})")
else:
    print("\n   [ERROR] Трансфер помилково пройшов як IT!")

# Test 2: Real IT content
print("\n2. Тест: Справжній IT контент")
print("-" * 50)

it_content = """
Python разработчики чат
Обсуждаем JavaScript, React и Backend
Деплоим на Docker и Kubernetes
Git, GitHub, CI/CD пайплайны
База данных PostgreSQL и MongoDB
"""

is_valid, reason, matched = validate_category_by_content("IT-сфера", it_content)
print(f"   Категорія: IT-сфера")
print(f"   Результат: {'PASS' if is_valid else 'FAIL'}")
print(f"   Причина: {reason}")
print(f"   Keywords знайдено: {matched}")

if is_valid:
    print("\n   [OK] Справжній IT контент проходить валідацію")
else:
    print("\n   [ERROR] IT контент не пройшов валідацію!")

# Test 3: Crypto content
print("\n3. Тест: Crypto контент")
print("-" * 50)

crypto_content = """
Крипто трейдеры Украина
Обсуждаем Bitcoin, Ethereum, DeFi
Стейкинг, airdrop, смарт-контракты
Биржа Binance, кошелек MetaMask
"""

is_valid, reason, matched = validate_category_by_content("Crypto и GameFi", crypto_content)
print(f"   Категорія: Crypto и GameFi")
print(f"   Результат: {'PASS' if is_valid else 'FAIL'}")
print(f"   Причина: {reason}")
print(f"   Keywords: {matched}")

# Test 4: Find best category
print("\n4. Тест: Автовизначення категорії")
print("-" * 50)

smm_content = """
SMM продвижение Instagram и TikTok
Маркетинг, таргет, рилс, сторис
Подписчики и охваты, инфлюенсеры
"""

best_cat, score, keywords = find_best_category_by_keywords(smm_content)
print(f"   Контент: SMM тематика")
print(f"   Знайдена категорія: {best_cat}")
print(f"   Score: {score}")
print(f"   Keywords: {keywords}")

if best_cat == "Маркетинг/SMM":
    print("\n   [OK] Правильно визначено Маркетинг/SMM")
else:
    print(f"\n   [!] Очікувалось Маркетинг/SMM, отримано {best_cat}")

# Test 5: Інше category
print("\n5. Тест: Невідома тематика -> Інше")
print("-" * 50)

random_content = """
Привет всем в чате
Как дела у вас сегодня?
Погода хорошая
"""

best_cat, score, keywords = find_best_category_by_keywords(random_content)
print(f"   Контент: Загальний чат")
print(f"   Знайдена категорія: {best_cat}")
print(f"   Score: {score}")

if best_cat == "Інше":
    print("\n   [OK] Правильно - жодна категорія не підходить")

print("\n" + "=" * 60)
print("ТЕСТ ЗАВЕРШЕНО")
print("=" * 60)
