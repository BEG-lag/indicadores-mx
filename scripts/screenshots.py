"""Serve the built site locally and capture the README screenshots with real Chrome.

    uv run indicadores-mx build --out _site
    uv sync --group screenshots
    uv run --group screenshots python scripts/screenshots.py

Uses the locally installed Google Chrome through Playwright (no browser download;
set CHROME_PATH for another Chromium). It also runs smoke checks and fails if one
breaks: no console errors, no horizontal scroll at 375 px, the cards and the chart
render, the converters compute, the language toggle switches to English, every
form control has a label.
"""

from __future__ import annotations

import functools
import http.server
import os
import socketserver
import sys
import threading
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "_site"
OUT = ROOT / "assets" / "screenshots"
PREFIX = "/indicadores-mx/"
# Hero, the latest-values panel and the cards, at 1280 px.
TOP = {"x": 0, "y": 0, "width": 1280, "height": 1480}
CHROME = os.environ.get(
    "CHROME_PATH", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
)


class Handler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        if path.startswith(PREFIX):
            path = "/" + path[len(PREFIX) :]
        return super().translate_path(path)

    def log_message(self, *args: object) -> None:
        pass


def serve() -> tuple[socketserver.TCPServer, str]:
    handler = functools.partial(Handler, directory=str(SITE))
    server = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}{PREFIX}"


def ready(page: Page) -> None:
    page.wait_for_selector(".card .value")
    page.wait_for_selector(".card svg.spark", state="attached")
    page.wait_for_selector("#chart svg path.line", state="attached")
    page.wait_for_function("document.querySelector('#udi-result .big') !== null")
    page.wait_for_function("document.querySelector('#inf-result .big') !== null")
    page.wait_for_function("document.querySelector('#live-response').textContent.length > 50")
    page.evaluate("document.fonts.ready")


def checks(page: Page, errors: list[str]) -> None:
    unlabeled = page.evaluate(
        """() => [...document.querySelectorAll('input, select')].filter((el) => {
            if (el.type === 'radio') return !el.closest('label');
            return !el.closest('label') && !el.getAttribute('aria-label');
        }).map((el) => el.id || el.name)"""
    )
    assert not unlabeled, f"controls without a label: {unlabeled}"
    assert not errors, f"console errors: {errors}"


def main() -> int:
    if not (SITE / "v1" / "index.json").exists():
        print("build the site first: uv run indicadores-mx build --out _site", file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    server, url = serve()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROME)

            # Desktop, Spanish
            context = browser.new_context(
                viewport={"width": 1280, "height": 900},
                device_scale_factor=1.5,
                color_scheme="dark",
            )
            page = context.new_page()
            errors: list[str] = []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(url)
            ready(page)
            checks(page, errors)
            page.screenshot(path=str(OUT / "home.png"), full_page=True, clip=TOP)
            page.locator("#graficas").scroll_into_view_if_needed()
            page.select_option("#chart-series", "udis")
            page.click("#chart-ranges button[data-range='all']")
            page.wait_for_timeout(300)
            box = page.locator("#chart").bounding_box()
            assert box is not None
            page.mouse.move(box["x"] + box["width"] * 0.72, box["y"] + box["height"] / 2)
            page.wait_for_timeout(200)
            page.locator("#graficas").screenshot(path=str(OUT / "chart.png"))
            page.locator("#convertidor").screenshot(path=str(OUT / "converter.png"))
            page.locator("#api").screenshot(path=str(OUT / "api.png"))

            # English toggle
            page.click("#lang")
            page.wait_for_function("document.documentElement.lang === 'en'")
            assert "Latest values" in page.inner_text("#values-title")
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(300)
            page.screenshot(path=str(OUT / "home-en.png"), full_page=True, clip=TOP)
            checks(page, errors)
            context.close()

            # Mobile, 375 px
            context = browser.new_context(
                viewport={"width": 375, "height": 812},
                device_scale_factor=2,
                is_mobile=True,
                has_touch=True,
                color_scheme="dark",
            )
            page = context.new_page()
            errors = []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.goto(url + "?lang=es")
            ready(page)
            overflow = page.evaluate(
                "document.documentElement.scrollWidth - document.documentElement.clientWidth"
            )
            assert overflow <= 0, f"horizontal scroll of {overflow}px at 375px"
            checks(page, errors)
            page.screenshot(path=str(OUT / "mobile.png"))
            context.close()

            # Social card (site/assets/og.png): the banner on a 1200 x 630 canvas
            banner = (ROOT / "assets" / "banner.svg").read_text(encoding="utf-8")
            page = browser.new_page(viewport={"width": 1200, "height": 630})
            page.emulate_media(reduced_motion="reduce")
            fonts = "".join(
                f"@font-face{{font-family:'{family}';font-style:{style};font-weight:{weight};"
                f"src:url('{url}assets/fonts/{file}')}}"
                for family, style, weight, file in (
                    ("JetBrains Mono", "normal", 400, "jetbrains-mono-latin-400-normal.woff2"),
                    ("JetBrains Mono", "normal", 700, "jetbrains-mono-latin-700-normal.woff2"),
                    ("Inter", "normal", 400, "inter-latin-400-normal.woff2"),
                    (
                        "Cormorant Garamond",
                        "italic",
                        500,
                        "cormorant-garamond-latin-500-italic.woff2",
                    ),
                )
            )
            page.set_content(
                f"<style>{fonts}</style><body style='margin:0;background:#0a0c10;display:flex;"
                f"align-items:center;height:630px'>{banner}</body>"
            )
            page.evaluate("document.fonts.ready")
            page.wait_for_timeout(300)
            page.screenshot(path=str(ROOT / "site" / "assets" / "og.png"))
            browser.close()
    finally:
        server.shutdown()
    for path in sorted(OUT.glob("*.png")):
        print(f"{path.relative_to(ROOT)} {path.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
