"""
Backtests для перевірки всіх виправлень після bug-fixing сесії.
Запуск: python3 test_fixes.py
Не потребує Telegram/ChatGPT підключення.
"""
import sys
import os
import ast
import tempfile
import traceback
from pathlib import Path

# Запускаємо з директорії проекту
os.chdir(Path(__file__).parent)

PASS = "✅"
FAIL = "❌"
results = []


def test(name, fn):
    try:
        fn()
        results.append((PASS, name))
        print(f"  {PASS} {name}")
    except Exception as e:
        results.append((FAIL, name))
        print(f"  {FAIL} {name}")
        print(f"       {type(e).__name__}: {e}")


# ────────────────────────────────────────────────
print("\n══ 1. Синтаксис (AST parse) ══")
# ────────────────────────────────────────────────

MODIFIED_FILES = [
    "database.py",
    "spider_telethon.py",
    "generate_descriptions_only.py",
    "analyze_chats.py",
    "filter_database.py",
    "make_session.py",
    "make_session_verbose.py",
]

for fname in MODIFIED_FILES:
    def _test_syntax(f=fname):
        src = Path(f).read_text(encoding="utf-8")
        ast.parse(src, filename=f)
    test(f"syntax: {fname}", _test_syntax)


# ────────────────────────────────────────────────
print("\n══ 2. database.py — Database class ══")
# ────────────────────────────────────────────────

import importlib.util

def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def test_database_module():
    with tempfile.TemporaryDirectory() as tmp:
        # patch DB_PATH to use temp dir
        import database as db_mod
        original_path = db_mod.DB_PATH
        db_mod.DB_PATH = Path(tmp) / "test.db"

        db = db_mod.Database(path=db_mod.DB_PATH)

        # upsert_channel
        db.upsert_channel("testchan", "Test Channel", "About text", "session1")
        db.upsert_channel("testchan", None, None, "session1")  # should not overwrite with NULL

        # upsert_chat
        db.upsert_chat("testchat", "Test Chat", "Chat about", "testchan", "session1")

        # get_all_channel_usernames (new method — fix #2)
        usernames = db.get_all_channel_usernames(limit=10)
        assert isinstance(usernames, list), "must return list"
        assert "testchan" in usernames, f"testchan missing, got {usernames}"

        # limit works
        for i in range(5):
            db.upsert_channel(f"chan{i}", f"Ch{i}", None, "s")
        all_u = db.get_all_channel_usernames(limit=3)
        assert len(all_u) <= 3, f"limit not respected: {len(all_u)}"

        db.close()
        db_mod.DB_PATH = original_path

test("Database instantiation + upsert_channel", lambda: test_database_module() or True)

# Test separately for clarity
def _test_get_usernames():
    with tempfile.TemporaryDirectory() as tmp:
        import database as db_mod
        db = db_mod.Database(path=Path(tmp) / "t.db")
        for i in range(10):
            db.upsert_channel(f"ch{i}", f"Title{i}", None, "s")
        result = db.get_all_channel_usernames(limit=5)
        assert len(result) == 5, f"expected 5, got {len(result)}"
        assert all(isinstance(u, str) for u in result)
        db.close()

test("get_all_channel_usernames(limit=5) returns exactly 5", _test_get_usernames)

def _test_no_null_overwrite():
    with tempfile.TemporaryDirectory() as tmp:
        import database as db_mod
        db = db_mod.Database(path=Path(tmp) / "t.db")
        db.upsert_channel("chan", "Original Title", "Original About", "s1")
        db.upsert_channel("chan", None, None, "s2")  # NULL update
        cur = db.conn.execute("SELECT title, about FROM channels WHERE username='chan'")
        row = cur.fetchone()
        assert row[0] == "Original Title", f"title was overwritten: {row[0]}"
        assert row[1] == "Original About", f"about was overwritten: {row[1]}"
        db.close()

test("upsert COALESCE: NULL не перезаписує існуючі дані", _test_no_null_overwrite)


# ────────────────────────────────────────────────
print("\n══ 3. spider_telethon.py — утиліти ══")
# ────────────────────────────────────────────────

# Завантажуємо тільки функції, не виконуємо main()
def _import_spider_utils():
    src = Path("spider_telethon.py").read_text(encoding="utf-8")
    # Виконуємо тільки визначення функцій без __main__ блоку
    tree = ast.parse(src)
    # Перевіряємо наявність DB.conn.execute (має бути відсутній у воркері)
    raw_src = Path("spider_telethon.py").read_text()
    assert "DB.conn.execute" not in raw_src, "DB.conn.execute still present — fix not applied!"

test("spider_telethon: DB.conn.execute видалено з воркера", _import_spider_utils)

def _test_spider_logging():
    src = Path("spider_telethon.py").read_text()
    assert 'logging.getLogger("telethon").setLevel(logging.WARNING)' in src
    assert 'logging.getLogger("telethon.network").setLevel(logging.ERROR)' in src

test("spider_telethon: Telethon logging = WARNING/ERROR", _test_spider_logging)

def _test_spider_keyboard_interrupt():
    src = Path("spider_telethon.py").read_text()
    # Стара версія мала тільки KeyboardInterrupt — мала не спрацьовувати в asyncio
    # Нова версія має CancelledError
    assert "asyncio.CancelledError" in src, "CancelledError missing"
    # Перевіряємо що except блок з gather містить CancelledError
    lines = src.splitlines()
    gather_idx = next(i for i, l in enumerate(lines) if "asyncio.gather(*tasks)" in l)
    nearby = "\n".join(lines[gather_idx:gather_idx+5])
    assert "CancelledError" in nearby, f"CancelledError not near asyncio.gather: {nearby}"

test("spider_telethon: asyncio.gather except KeyboardInterrupt → CancelledError", _test_spider_keyboard_interrupt)

def _test_parse_proxy():
    # parse_proxy_line має існувати і коректно парсити рядки
    import importlib
    # Мокаємо залежності яких немає
    sys.modules.setdefault('telethon', type(sys)('telethon'))
    sys.modules.setdefault('telethon.sync', type(sys)('telethon.sync'))
    sys.modules.setdefault('telethon.errors', type(sys)('telethon.errors'))
    sys.modules.setdefault('colorama', type(sys)('colorama'))

    src = Path("spider_telethon.py").read_text()
    # Витягуємо функцію parse_proxy_line через exec у namespace
    import re as _re
    ns = {"__name__": "test_ns", "re": _re}
    # Знаходимо функцію
    assert "def parse_proxy_line" in src, "parse_proxy_line not found"
    start = src.index("def parse_proxy_line")
    # Парсимо AST щоб знайти кінець функції
    func_src = ""
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.FunctionDef) and node.name == "parse_proxy_line":
            func_src = ast.get_source_segment(src, node)
            break
    assert func_src, "could not extract parse_proxy_line source"
    exec(func_src, ns)
    fn = ns["parse_proxy_line"]

    # ip:port
    r = fn("1.2.3.4:1080")
    assert r is not None and r[1] == "1.2.3.4" and r[2] == 1080, f"basic proxy failed: {r}"

    # ip:port:user:pass
    r = fn("1.2.3.4:1080:user:pass")
    assert r is not None and r[4] == "user", f"auth proxy failed: {r}"

    # invalid
    r = fn("not_a_proxy")
    assert r is None, f"invalid proxy should be None, got {r}"

test("parse_proxy_line: ip:port, ip:port:user:pass, invalid", _test_parse_proxy)


# ────────────────────────────────────────────────
print("\n══ 4. generate_descriptions_only.py — env config ══")
# ────────────────────────────────────────────────

def _test_chatgpt_url_from_env():
    src = Path("generate_descriptions_only.py").read_text()
    # Hardcoded UUID не має бути напряму у CHATGPT_URL
    assert 'CHATGPT_URL = "https://chatgpt.com/c/6937098c' not in src, \
        "UUID still hardcoded in CHATGPT_URL!"
    # Має читатись з env
    assert 'os.getenv("CHATGPT_CONVERSATION_URL"' in src, \
        "CHATGPT_URL not reading from env"

test("generate_descriptions: CHATGPT_URL читається з env (не hardcoded)", _test_chatgpt_url_from_env)

def _test_playwright_resource_leak_fixed():
    src = Path("generate_descriptions_only.py").read_text()
    # connect_to_browser має повертати 3 значення
    assert "return browser, chatgpt_page, playwright" in src, \
        "connect_to_browser still returns only 2 values"
    # caller має розпаковувати 3
    assert "browser, page, pw = await connect_to_browser()" in src, \
        "caller still unpacks only 2 values"
    # pw.stop() має бути в finally
    assert "await pw.stop()" in src, "pw.stop() missing in finally"

test("generate_descriptions: Playwright resource leak виправлено (3 повернень + pw.stop)", _test_playwright_resource_leak_fixed)

def _test_target_chat_id_dynamic():
    src = Path("generate_descriptions_only.py").read_text()
    assert 'target_chat_id = "6937098c-d498-832a-8921-8e543d15ff2f"' not in src, \
        "target_chat_id UUID still hardcoded"
    assert 'split("/c/")' in src, "dynamic target_chat_id extraction missing"

test("generate_descriptions: target_chat_id динамічно з URL (не hardcoded)", _test_target_chat_id_dynamic)

def _test_os_import_in_generate():
    src = Path("generate_descriptions_only.py").read_text()
    assert "import os" in src, "import os missing in generate_descriptions_only.py"

test("generate_descriptions: import os присутній", _test_os_import_in_generate)


# ────────────────────────────────────────────────
print("\n══ 5. analyze_chats.py — FloodWait fix ══")
# ────────────────────────────────────────────────

def _test_floodwait_no_continue():
    src = Path("analyze_chats.py").read_text()
    lines = src.splitlines()
    # Знаходимо FloodWait блок
    flood_idx = next((i for i, l in enumerate(lines) if "FloodWaitError as e:" in l), None)
    assert flood_idx is not None, "FloodWaitError block not found"
    # Перевіряємо наступні ~5 рядків після catch — continue не має бути там
    block = lines[flood_idx:flood_idx + 6]
    for line in block:
        stripped = line.strip()
        assert stripped != "continue", \
            f"'continue' still present after FloodWait at ~line {flood_idx}: {line!r}"

test("analyze_chats: 'continue' після FloodWait видалено", _test_floodwait_no_continue)

def _test_results_append_reachable():
    src = Path("analyze_chats.py").read_text()
    # results.append(chat_data) має існувати
    assert "results.append(chat_data)" in src, "results.append(chat_data) missing"

test("analyze_chats: results.append(chat_data) присутній (дані не губляться)", _test_results_append_reachable)


# ────────────────────────────────────────────────
print("\n══ 6. filter_database.py — finally close ══")
# ────────────────────────────────────────────────

def _test_finally_db_close():
    src = Path("filter_database.py").read_text()
    lines = src.splitlines()
    # Знаходимо finally: db.close() структуру в main()
    finally_indices = [i for i, l in enumerate(lines) if l.strip() == "finally:"]
    assert finally_indices, "finally: block not found in filter_database.py"
    # Перевіряємо що db.close() йде після finally
    for fi in finally_indices:
        next_lines = [l.strip() for l in lines[fi+1:fi+3]]
        if "db.close()" in next_lines:
            return  # знайшли правильний finally
    raise AssertionError("db.close() not found inside finally block")

test("filter_database: db.close() у finally блоці", _test_finally_db_close)


# ────────────────────────────────────────────────
print("\n══ 7. make_session.py — credentials з .env ══")
# ────────────────────────────────────────────────

def _test_make_session_no_hardcode():
    src = Path("make_session.py").read_text()
    assert "23246805" not in src, "api_id hardcoded in make_session.py"
    assert "8bc2e1aceeac87146f9c8d94f836b35e" not in src, "api_hash hardcoded in make_session.py"
    assert 'os.getenv("API_ID"' in src, "API_ID not read from env"
    assert 'os.getenv("API_HASH"' in src, "API_HASH not read from env"
    assert "accs/my_account" in src, "session not writing to accs/ directory"

test("make_session: hardcoded credentials видалено, читає з .env, пише в accs/", _test_make_session_no_hardcode)

def _test_make_session_verbose_no_hardcode():
    src = Path("make_session_verbose.py").read_text()
    assert "23246805" not in src, "api_id hardcoded in make_session_verbose.py"
    assert "8bc2e1aceeac87146f9c8d94f836b35e" not in src, "api_hash hardcoded in make_session_verbose.py"
    assert 'os.getenv("API_ID"' in src, "API_ID not read from env"

test("make_session_verbose: hardcoded credentials видалено", _test_make_session_verbose_no_hardcode)


# ────────────────────────────────────────────────
print("\n══ 8. .gitignore та permissions ══")
# ────────────────────────────────────────────────

def _test_gitignore_exists():
    gi = Path(".gitignore")
    assert gi.exists(), ".gitignore не існує"
    content = gi.read_text()
    for entry in [".env", "*.session", "accs/", "output/"]:
        assert entry in content, f"{entry!r} відсутній у .gitignore"

test(".gitignore існує і містить ключові виключення", _test_gitignore_exists)

def _test_env_permissions():
    import stat
    env_path = Path(".env")
    if env_path.exists():
        mode = env_path.stat().st_mode
        # Перевіряємо що group/other не мають read доступу
        group_read = bool(mode & stat.S_IRGRP)
        other_read = bool(mode & stat.S_IROTH)
        assert not group_read, ".env readable by group"
        assert not other_read, ".env readable by others"

test(".env permissions: тільки власник має доступ (600)", _test_env_permissions)

def _test_session_permissions():
    import stat
    session_files = list(Path("accs").glob("*.session"))
    if not session_files:
        return  # немає файлів — пропускаємо
    for sf in session_files:
        mode = sf.stat().st_mode
        assert not bool(mode & stat.S_IRGRP), f"{sf.name} readable by group"
        assert not bool(mode & stat.S_IROTH), f"{sf.name} readable by others"

test("accs/*.session permissions: тільки власник (600)", _test_session_permissions)


# ────────────────────────────────────────────────
print("\n══ 9. Інтеграційний: Database end-to-end ══")
# ────────────────────────────────────────────────

def _test_db_full_flow():
    with tempfile.TemporaryDirectory() as tmp:
        import database as db_mod
        db = db_mod.Database(path=Path(tmp) / "spider.db")

        # Вставляємо канали і чати
        for i in range(50):
            db.upsert_channel(f"channel_{i}", f"Channel {i}", f"About {i}", "s1")
        for i in range(20):
            db.upsert_chat(f"chat_{i}", f"Chat {i}", None, f"channel_{i}", "s1")

        # Перевіряємо limit
        batch = db.get_all_channel_usernames(limit=10)
        assert len(batch) == 10, f"Expected 10, got {len(batch)}"

        # Перевіряємо ORDER BY last_seen_ts ASC — найстарші перші
        batch_all = db.get_all_channel_usernames(limit=50)
        assert len(batch_all) == 50

        # UPSERT оновлює last_seen_ts
        import time; time.sleep(0.01)
        db.upsert_channel("channel_0", "Updated Title", None, "s2")
        batch_after = db.get_all_channel_usernames(limit=50)
        # channel_0 має бути останнім (найновіший last_seen_ts)
        assert batch_after[-1] == "channel_0", \
            f"channel_0 not last after update: {batch_after[-3:]}"

        db.close()

test("DB end-to-end: 50 каналів, limit=10, ORDER BY last_seen_ts", _test_db_full_flow)


# ────────────────────────────────────────────────
print("\n══ Підсумок ══")
# ────────────────────────────────────────────────

passed = sum(1 for r, _ in results if r == PASS)
failed = sum(1 for r, _ in results if r == FAIL)
total = len(results)

print(f"\n  Пройшло: {passed}/{total}")
if failed:
    print(f"  Провалено: {failed}/{total}")
    print("\n  Провалені тести:")
    for r, name in results:
        if r == FAIL:
            print(f"    {FAIL} {name}")
    sys.exit(1)
else:
    print(f"\n  Всі тести пройшли ✅")
