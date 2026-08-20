from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path
from typing import Iterable

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright

from ..config import (
    BROWSER_CHANNEL,
    BROWSER_HEADLESS,
    BROWSER_NAV_TIMEOUT_MS,
    BROWSER_PROFILE_DIR,
    BROWSER_WAIT_MS,
    BROWSER_RANDOM_DELAY_MIN_MS,
    BROWSER_RANDOM_DELAY_MAX_MS,
)
from ..utils import normalize_space


class BrowserRuntime(AbstractContextManager):
    """Persistent Edge/Chromium session shared across all journals in one provider run."""

    def __init__(self) -> None:
        self.pw: Playwright | None = None
        self.context: BrowserContext | None = None

    def __enter__(self) -> "BrowserRuntime":
        BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        self.pw = sync_playwright().start()
        kwargs = dict(
            user_data_dir=str(BROWSER_PROFILE_DIR),
            headless=BROWSER_HEADLESS,
            locale="en-US",
            viewport={"width": 1440, "height": 1000},
        )
        if BROWSER_CHANNEL:
            kwargs["channel"] = BROWSER_CHANNEL
        try:
            self.context = self.pw.chromium.launch_persistent_context(**kwargs)
            print(f"[browser] engine=chromium channel={BROWSER_CHANNEL or 'bundled'} headless={BROWSER_HEADLESS}")
        except Exception as exc:
            if BROWSER_CHANNEL:
                print(f"[browser] channel {BROWSER_CHANNEL!r} unavailable ({type(exc).__name__}); falling back to bundled Chromium")
                kwargs.pop("channel", None)
                self.context = self.pw.chromium.launch_persistent_context(**kwargs)
                print(f"[browser] engine=bundled-chromium headless={BROWSER_HEADLESS}")
            else:
                raise
        self.context.set_default_navigation_timeout(BROWSER_NAV_TIMEOUT_MS)
        self.context.set_default_timeout(BROWSER_NAV_TIMEOUT_MS)
        return self

    def new_page(self) -> Page:
        assert self.context is not None
        return self.context.new_page()

    def goto(self, page: Page, url: str, *, label: str = "page") -> None:
        response = page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(max(0, BROWSER_WAIT_MS))
        if response is not None and response.status >= 400:
            raise RuntimeError(f"{label} HTTP {response.status}: {url}")


    def human_delay(self) -> None:
        import random
        import time
        time.sleep(random.uniform(BROWSER_RANDOM_DELAY_MIN_MS, BROWSER_RANDOM_DELAY_MAX_MS) / 1000.0)

    def __exit__(self, exc_type, exc, tb):
        try:
            if self.context is not None:
                self.context.close()
        finally:
            if self.pw is not None:
                self.pw.stop()
        return False


def meta_values(page: Page, names: Iterable[str]) -> list[str]:
    values: list[str] = []
    for name in names:
        try:
            loc = page.locator(f'meta[name="{name}"]')
            for i in range(loc.count()):
                value = normalize_space(loc.nth(i).get_attribute("content") or "")
                if value and value not in values:
                    values.append(value)
        except Exception:
            continue
    return values


def first_meta(page: Page, names: Iterable[str]) -> str:
    values = meta_values(page, names)
    return values[0] if values else ""
