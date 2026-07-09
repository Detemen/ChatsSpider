# -*- coding: utf-8 -*-
"""
Test BrowserManager module
Run with browser already open with CDP enabled
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from browser_manager import BrowserManager


async def test_browser_manager():
    print("=" * 60)
    print("TEST: BrowserManager")
    print("=" * 60)

    # Test 1: Import
    print("\n1. Testing import...")
    print("   [OK] Import successful")

    # Test 2: Initialization
    print("\n2. Testing initialization...")
    manager = BrowserManager(
        cdp_port=9222,
        chatgpt_url="https://chatgpt.com/c/test"
    )
    print(f"   [OK] BrowserManager created")
    print(f"   CDP port: {manager.cdp_port}")
    print(f"   Target chat ID: {manager.target_chat_id}")

    # Test 3: Health check (before connection)
    print("\n3. Testing health check (not connected)...")
    is_healthy = await manager.is_healthy()
    if not is_healthy:
        print("   [OK] Correctly reports not healthy before connection")
    else:
        print("   [!] Unexpected: healthy before connection")

    # Test 4: Connection attempt
    print("\n4. Testing connection...")
    print("   NOTE: This requires browser to be running with --remote-debugging-port=9222")

    try:
        page = await manager.connect()
        if page:
            print(f"   [OK] Connected to browser")
            print(f"   Page URL: {page.url}")

            # Test 5: Health check after connection
            print("\n5. Testing health check (connected)...")
            is_healthy = await manager.is_healthy()
            if is_healthy:
                print("   [OK] Browser is healthy")
            else:
                print("   [!] Browser not healthy after connection")

            # Test 6: Reload
            print("\n6. Testing page reload...")
            reload_ok = await manager.reload_page()
            if reload_ok:
                print("   [OK] Page reloaded successfully")
            else:
                print("   [!] Page reload failed")

            # Test 7: Ensure connected
            print("\n7. Testing ensure_connected...")
            page2 = await manager.ensure_connected()
            if page2:
                print("   [OK] ensure_connected works")
            else:
                print("   [!] ensure_connected failed")

        else:
            print("   [!] Could not connect to browser")
            print("   Make sure browser is running with CDP enabled:")
            print('   msedge.exe --remote-debugging-port=9222 --user-data-dir="C:\\edge-profile"')

    except Exception as e:
        print(f"   [!] Connection error: {e}")
        print("   Make sure browser is running with CDP enabled")

    # Test 8: Recoverable error detection
    print("\n8. Testing error recovery detection...")
    test_errors = [
        ("Target closed", True),
        ("Connection closed", True),
        ("Page crashed", True),
        ("timeout exceeded", True),
        ("Random error", False),
        ("net::ERR_CONNECTION_REFUSED", True),
    ]

    for error_msg, expected in test_errors:
        error = Exception(error_msg)
        is_recoverable = manager._is_recoverable_error(error)
        status = "[OK]" if is_recoverable == expected else "[FAIL]"
        print(f"   {status} '{error_msg}' -> recoverable={is_recoverable} (expected {expected})")

    # Cleanup
    print("\n9. Testing close...")
    await manager.close()
    print("   [OK] Manager closed")

    print("\n" + "=" * 60)
    print("TEST COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_browser_manager())
