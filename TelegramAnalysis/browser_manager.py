# -*- coding: utf-8 -*-
"""
Browser Manager for TelegramAnalysis
Manages Playwright browser connection with automatic recovery on failures

FEATURES:
- Automatic reconnection when browser disconnects
- Health checks before operations
- Retry logic for failed operations
- Graceful recovery from crashes
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional, Callable, Any
from playwright.async_api import async_playwright, Browser, Page, Playwright

logger = logging.getLogger(__name__)


class BrowserManager:
    """
    Manages Playwright browser with automatic recovery

    Usage:
        manager = BrowserManager(cdp_port=9222, chatgpt_url="https://...")

        # Connect initially
        page = await manager.connect()

        # Execute with auto-recovery
        result = await manager.execute_with_recovery(
            async_operation,
            max_retries=3
        )

        # Check health
        if not await manager.is_healthy():
            await manager.reconnect()
    """

    def __init__(
        self,
        cdp_port: int = 9222,
        chatgpt_url: str = "https://chatgpt.com/c/6937098c-d498-832a-8921-8e543d15ff2f"
    ):
        self.cdp_port = cdp_port
        self.chatgpt_url = chatgpt_url
        self.target_chat_id = chatgpt_url.split("/")[-1] if "/" in chatgpt_url else ""

        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None

        self._connected = False
        self._recovery_attempts = 0
        self._max_recovery_attempts = 5

    async def connect(self) -> Optional[Page]:
        """
        Connect to browser via CDP

        Returns:
            Page object or None if failed
        """
        try:
            logger.info("[Browser] Connecting to browser...")
            print("[Browser] Connecting via CDP...")

            # Start playwright if not started
            if not self.playwright:
                self.playwright = await async_playwright().start()

            # Connect to browser
            self.browser = await self.playwright.chromium.connect_over_cdp(
                f"http://localhost:{self.cdp_port}"
            )

            # Get existing contexts
            contexts = self.browser.contexts
            if not contexts:
                logger.error("[Browser] No open tabs in browser")
                print("[X] No open tabs in browser")
                return None

            # Get first context
            context = contexts[0]
            pages = context.pages

            # Find ChatGPT tab
            chatgpt_page = None
            for page in pages:
                if self.target_chat_id in page.url or "chatgpt.com" in page.url:
                    chatgpt_page = page
                    logger.info(f"[Browser] Found ChatGPT tab: {page.url}")
                    break

            if not chatgpt_page:
                if pages:
                    chatgpt_page = pages[-1]
                    logger.warning(f"[Browser] Using active tab: {chatgpt_page.url}")
                else:
                    logger.error("[Browser] No active tabs")
                    return None

            # Navigate to target chat if needed
            if self.target_chat_id and self.target_chat_id not in chatgpt_page.url:
                logger.info(f"[Browser] Navigating to: {self.chatgpt_url}")
                await chatgpt_page.goto(self.chatgpt_url, wait_until="domcontentloaded")
                await asyncio.sleep(3)

            self.page = chatgpt_page
            self._connected = True
            self._recovery_attempts = 0

            logger.info("[Browser] Connected successfully")
            print(f"[OK] Browser connected: {chatgpt_page.url}")

            return self.page

        except Exception as e:
            logger.error(f"[Browser] Connection failed: {e}")
            print(f"[X] Browser connection failed: {e}")
            self._connected = False
            return None

    async def reconnect(self) -> Optional[Page]:
        """
        Reconnect to browser (after disconnect or crash)

        Returns:
            Page object or None if failed
        """
        logger.warning("[Browser] Attempting reconnection...")
        print("\n[!] Browser reconnecting...")

        # Close existing connections
        await self.close()

        # Wait before reconnecting
        await asyncio.sleep(2)

        # Attempt reconnection
        self._recovery_attempts += 1

        if self._recovery_attempts > self._max_recovery_attempts:
            logger.error(f"[Browser] Max recovery attempts ({self._max_recovery_attempts}) exceeded")
            print(f"[X] Browser recovery failed after {self._max_recovery_attempts} attempts")
            return None

        page = await self.connect()

        if page:
            logger.info(f"[Browser] Reconnected (attempt {self._recovery_attempts})")
            print(f"[OK] Browser reconnected (attempt {self._recovery_attempts})")
        else:
            logger.error(f"[Browser] Reconnection failed (attempt {self._recovery_attempts})")

        return page

    async def is_healthy(self) -> bool:
        """
        Check if browser connection is healthy

        Returns:
            True if browser is responsive
        """
        if not self._connected or not self.page:
            return False

        try:
            # Try simple evaluation to check responsiveness
            await asyncio.wait_for(
                self.page.evaluate("() => true"),
                timeout=5.0
            )
            return True
        except Exception as e:
            logger.warning(f"[Browser] Health check failed: {e}")
            self._connected = False
            return False

    async def ensure_connected(self) -> Optional[Page]:
        """
        Ensure browser is connected, reconnect if needed

        Returns:
            Page object or None if failed
        """
        if await self.is_healthy():
            return self.page

        logger.warning("[Browser] Not healthy, reconnecting...")
        return await self.reconnect()

    async def execute_with_recovery(
        self,
        operation: Callable,
        *args,
        max_retries: int = 3,
        **kwargs
    ) -> Optional[Any]:
        """
        Execute async operation with automatic recovery on failure

        Args:
            operation: Async function to execute (receives page as first arg)
            *args: Additional args for operation
            max_retries: Maximum retry attempts
            **kwargs: Additional kwargs for operation

        Returns:
            Operation result or None if all retries failed
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                # Ensure connected
                page = await self.ensure_connected()
                if not page:
                    logger.error("[Browser] Cannot ensure connection")
                    continue

                # Execute operation
                result = await operation(page, *args, **kwargs)
                return result

            except Exception as e:
                last_error = e
                logger.warning(f"[Browser] Operation failed (attempt {attempt + 1}): {e}")
                print(f"   [!] Browser error (attempt {attempt + 1}/{max_retries}): {type(e).__name__}")

                # Check if recoverable
                if self._is_recoverable_error(e):
                    logger.info("[Browser] Attempting recovery...")
                    await self.reconnect()
                    await asyncio.sleep(2)
                else:
                    logger.error(f"[Browser] Non-recoverable error: {e}")
                    break

        logger.error(f"[Browser] All {max_retries} attempts failed. Last error: {last_error}")
        return None

    def _is_recoverable_error(self, error: Exception) -> bool:
        """
        Check if error is recoverable

        Args:
            error: Exception to check

        Returns:
            True if we should attempt recovery
        """
        recoverable_messages = [
            "Target closed",
            "Target crashed",
            "Browser closed",
            "Connection closed",
            "Page closed",
            "Page crashed",
            "crashed",
            "Execution context was destroyed",
            "Protocol error",
            "Navigation failed",
            "net::ERR_",
            "timeout",
            "disconnected",
        ]

        error_str = str(error).lower()
        return any(msg.lower() in error_str for msg in recoverable_messages)

    async def reload_page(self) -> bool:
        """
        Reload current page

        Returns:
            True if reload successful
        """
        if not self.page:
            return False

        try:
            logger.info("[Browser] Reloading page...")
            await self.page.reload(wait_until="domcontentloaded")
            await asyncio.sleep(3)
            logger.info("[Browser] Page reloaded")
            return True
        except Exception as e:
            logger.error(f"[Browser] Reload failed: {e}")
            return False

    async def close(self):
        """Close browser connections"""
        try:
            if self.browser:
                # Don't actually close - just disconnect
                # User's browser should stay open
                pass
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
        except Exception as e:
            logger.debug(f"[Browser] Close error (ignored): {e}")

        self.browser = None
        self.page = None
        self._connected = False

    def reset_recovery_counter(self):
        """Reset recovery attempts counter (call after successful operation)"""
        self._recovery_attempts = 0

    @property
    def is_connected(self) -> bool:
        """Check if currently connected"""
        return self._connected and self.page is not None


# Convenience function for wrapping existing code
async def with_browser_recovery(
    browser_manager: BrowserManager,
    operation: Callable,
    *args,
    **kwargs
) -> Optional[Any]:
    """
    Wrapper function for executing operations with browser recovery

    Usage:
        result = await with_browser_recovery(
            browser_manager,
            send_prompt_file_to_chatgpt,
            file_path
        )
    """
    return await browser_manager.execute_with_recovery(operation, *args, **kwargs)


# Export
__all__ = ['BrowserManager', 'with_browser_recovery']
