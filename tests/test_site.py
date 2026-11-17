"""The static site and the repository conventions."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
EM_DASH = chr(0x2014)  # written as a code point so this file stays clean
TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".html",
    ".css",
    ".js",
    ".svg",
    ".txt",
    ".csv",
}
SKIP_DIRS = {
    ".git",
    ".venv",
    ".cache",
    "_site",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
}


def text_files():
    for path in ROOT.rglob("*"):
        if path.is_file() and path.suffix in TEXT_SUFFIXES and not (SKIP_DIRS & set(path.parts)):
            yield path


def test_no_em_dash_anywhere():
    offenders = [
        str(p.relative_to(ROOT))
        for p in text_files()
        if EM_DASH in p.read_text(encoding="utf-8", errors="ignore")
    ]
    assert offenders == []


def test_site_loads_nothing_from_third_parties():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    css = (SITE / "assets" / "styles.css").read_text(encoding="utf-8")
    scripts = "".join(p.read_text(encoding="utf-8") for p in (SITE / "assets").glob("*.js"))
    for tag in re.findall(r"<(?:script|link|img|iframe)\b[^>]*>", html):
        assert not re.search(r"""(?:src|href)=["']https?://""", tag), tag
    assert "url(http" not in css
    assert not re.search(r"""import[^;]*from\s+["']https?://""", scripts)
    for tracker in ("googletagmanager", "google-analytics", "plausible.io", "gtag(", "clarity.ms"):
        assert tracker not in html + scripts, tracker


def test_fonts_are_self_hosted():
    css = (SITE / "assets" / "styles.css").read_text(encoding="utf-8")
    for url in re.findall(r'url\("([^"]+)"\)', css):
        assert (SITE / "assets" / url).exists(), url
    assert (SITE / "assets" / "fonts" / "OFL.txt").exists()


def test_every_i18n_key_exists_in_both_languages():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    app = (SITE / "assets" / "app.js").read_text(encoding="utf-8")
    keys = set(re.findall(r'data-i18n(?:-html)?="([a-z_]+)"', html))
    keys |= {k.split(":")[1] for k in re.findall(r'data-i18n-attr="([a-z-]+:[a-z_]+)"', html)}
    blocks = re.split(r"\n  en: \{", app.split("const T = {", 1)[1], maxsplit=1)
    for block in blocks:
        defined = set(re.findall(r"\b([a-z_]+): ", block))
        assert keys <= defined, keys - defined


def test_html_basics():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    assert '<html lang="es">' in html
    assert 'name="viewport"' in html
    assert 'class="skip"' in html
    assert html.count("<h1") == 1
