"""Static accessibility checks for the customer-facing pages (IS 5568, based on WCAG 2.0 AA).

Standard library only. The order screens are drawn by JavaScript, so these tests cover what can be
read from the HTML and CSS files: page structure, names, colour contrast, motion rules and the
accessibility menu wiring. Everything the browser draws (keyboard order, screen reader output, 200%
text) is in the manual checklist in docs/ACCESSIBILITY.md.
"""

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
PAGES = {
    "landing": FRONTEND / "index.html",
    "customer": FRONTEND / "customer" / "index.html",
    "statement": FRONTEND / "accessibility" / "index.html",
}
CSS_FILES = ["base.css", "customer.css", "landing.css", "motion.css"]
VOID = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "source",
    "track",
    "wbr",
}


class Page(HTMLParser):
    """Collects what the checks need: html attrs, ids, images, scripts, links, buttons, headings."""

    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=True)
        self.html_attrs: dict[str, str] = {}
        self.ids: set[str] = set()
        self.images: list[dict[str, str]] = []
        self.scripts: list[str] = []
        self.records: list[dict] = []
        self.main_text = ""
        self._open: list[dict] = []
        self._in_main = False
        self.feed(source)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        if tag == "html":
            self.html_attrs = a
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "img":
            self.images.append(a)
        if tag == "script" and "src" in a:
            self.scripts.append(a["src"])
        if tag == "main":
            self._in_main = True
        if tag in {"a", "button", "title"} or re.fullmatch(r"h[1-6]", tag):
            record = {"tag": tag, "attrs": a, "text": ""}
            self.records.append(record)
            if tag not in VOID:
                self._open.append(record)

    def handle_endtag(self, tag: str) -> None:
        if tag == "main":
            self._in_main = False
        for i in range(len(self._open) - 1, -1, -1):
            if self._open[i]["tag"] == tag:
                del self._open[i]
                break

    def handle_data(self, data: str) -> None:
        for record in self._open:
            record["text"] += data
        if self._in_main:
            self.main_text += data

    def of(self, *tags: str) -> list[dict]:
        return [r for r in self.records if r["tag"] in tags]


def load(name: str) -> Page:
    return Page(PAGES[name].read_text(encoding="utf-8"))


def accessible_name(record: dict) -> str:
    return (record["attrs"].get("aria-label") or "").strip() or record["text"].strip()


page_names = pytest.mark.parametrize("name", list(PAGES))


# ---------- page structure ----------


@page_names
def test_page_language_and_direction(name):
    page = load(name)
    assert page.html_attrs.get("lang") == "he"
    assert page.html_attrs.get("dir") == "rtl"


@page_names
def test_skip_link_points_to_an_existing_id(name):
    page = load(name)
    skip = [r for r in page.of("a") if "skip-link" in r["attrs"].get("class", "")]
    assert len(skip) == 1, "each page needs exactly one skip link"
    assert skip[0]["attrs"]["href"].startswith("#")
    assert skip[0]["attrs"]["href"][1:] in page.ids


@page_names
def test_images_have_alt(name):
    for img in load(name).images:
        assert "alt" in img, f"image without alt: {img.get('src')}"


@page_names
def test_page_has_a_title(name):
    titles = load(name).of("title")
    assert len(titles) == 1
    assert titles[0]["text"].strip()


@pytest.mark.parametrize("name", ["landing", "statement"])
def test_headings_do_not_skip_levels(name):
    levels = [int(r["tag"][1]) for r in load(name).of("h1", "h2", "h3", "h4", "h5", "h6")]
    assert levels.count(1) == 1, "exactly one h1"
    assert levels[0] == 1
    for before, after in zip(levels, levels[1:], strict=False):
        assert after <= before + 1, f"heading level jumps from h{before} to h{after}"


@page_names
def test_links_and_buttons_have_names(name):
    for record in load(name).of("a", "button"):
        assert accessible_name(record), f"unnamed {record['tag']}: {record['attrs']}"


@page_names
def test_new_tab_links_say_so(name):
    for record in load(name).of("a"):
        if record["attrs"].get("target") == "_blank":
            assert "בלשונית חדשה" in accessible_name(record) + record["text"]


@page_names
def test_page_has_accessibility_menu_and_statement_link(name):
    page = load(name)
    assert "/js/a11y-boot.js" in page.scripts, "saved settings must apply before first paint"
    toggles = [r for r in page.of("button") if "a11y-toggle" in r["attrs"].get("class", "")]
    assert len(toggles) == 1
    assert toggles[0]["attrs"].get("aria-expanded") == "false"
    hrefs = {r["attrs"].get("href") for r in page.of("a")}
    if name == "statement":
        assert "/" in hrefs
    else:
        assert "/accessibility/" in hrefs


# ---------- the statement ----------


def test_statement_has_required_sections_and_only_placeholder_contacts():
    page = load("statement")
    headings = " | ".join(r["text"] for r in page.of("h2"))
    for needed in ("רמת הנגישות", "תפריט הנגישות", "ליקויים ידועים", "פניות בנושא נגישות"):
        assert needed in headings
    source = PAGES["statement"].read_text(encoding="utf-8")
    assert source.count("[להשלמה") >= 5, "contact details must stay marked as placeholders"
    assert "@" not in page.main_text, "no invented email address"
    assert not re.search(r"0\d{1,2}[- ]?\d{7}", page.main_text), "no invented phone number"
    assert re.search(r'<time datetime="\d{4}-\d{2}-\d{2}"', source), "last-updated date"


# ---------- colour contrast ----------


def strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def tokens(block: str) -> dict[str, str]:
    return {
        m.group(1): m.group(2).strip() for m in re.finditer(r"(--[\w-]+)\s*:\s*([^;]+);", block)
    }


def resolve(value: str, table: dict[str, str]) -> str:
    while m := re.search(r"var\((--[\w-]+)\)", value):
        value = value.replace(m.group(0), table[m.group(1)])
    return value


def hex_color(value: str) -> tuple[float, float, float]:
    m = re.search(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b", value)
    assert m, f"not a hex colour: {value}"
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def luminance(rgb: tuple[float, float, float]) -> float:
    r, g, b = (c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((luminance(hex_color(a)), luminance(hex_color(b))), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def palettes() -> dict[str, dict[str, str]]:
    css = strip_comments((FRONTEND / "css" / "base.css").read_text(encoding="utf-8"))
    default = tokens(re.search(r":root\s*\{([^}]*)\}", css).group(1))
    high = {**default, **tokens(re.search(r":root\.a11y-contrast\s*\{([^}]*)\}", css).group(1))}
    return {"default": default, "contrast": high}


# (foreground token, background token). Text needs 4.5:1 normally and 7:1 in high-contrast mode.
TEXT_PAIRS = [
    ("--color-text", "--color-bg"),
    ("--color-text", "--color-surface"),
    ("--color-muted", "--color-bg"),
    ("--color-muted", "--color-surface"),
    ("--color-muted", "--color-surface-2"),
    ("--color-accent", "--color-bg"),
    ("--color-accent", "--color-surface"),
    ("--color-on-accent", "--color-accent"),
    ("--color-danger", "--color-bg"),
    ("--color-danger", "--color-danger-soft"),
    ("--color-success", "--color-success-soft"),
    ("--color-warning", "--color-warning-soft"),
    ("--color-accent", "--color-accent-soft"),
]
# Borders of controls and the focus ring must reach 3:1 against the page (WCAG 1.4.11, kept in 2.2).
NON_TEXT_PAIRS = [("--color-control-border", "--color-bg"), ("--focus-ring", "--color-bg")]


def colour_of(token: str, table: dict[str, str]) -> str:
    return resolve(table[token], table)


@pytest.mark.parametrize(("fg", "bg"), TEXT_PAIRS)
def test_default_text_contrast_is_at_least_4_5(fg, bg):
    table = palettes()["default"]
    assert contrast(colour_of(fg, table), colour_of(bg, table)) >= 4.5


@pytest.mark.parametrize(("fg", "bg"), TEXT_PAIRS)
def test_high_contrast_text_contrast_is_at_least_7(fg, bg):
    table = palettes()["contrast"]
    assert contrast(colour_of(fg, table), colour_of(bg, table)) >= 7.0


@pytest.mark.parametrize("mode", ["default", "contrast"])
@pytest.mark.parametrize(("fg", "bg"), NON_TEXT_PAIRS)
def test_borders_and_focus_ring_contrast_is_at_least_3(mode, fg, bg):
    table = palettes()[mode]
    assert contrast(colour_of(fg, table), colour_of(bg, table)) >= 3.0


# ---------- text size and motion ----------


@pytest.mark.parametrize("css_file", CSS_FILES)
def test_font_sizes_are_not_in_pixels(css_file):
    css = strip_comments((FRONTEND / "css" / css_file).read_text(encoding="utf-8"))
    offenders = re.findall(r"font-size\s*:[^;}]*\d\s*px", css)
    assert not offenders, f"pixel font sizes do not scale with the text-size setting: {offenders}"


def rules(css: str) -> list[tuple[str, str]]:
    """(selector, body) for every rule, including rules nested one level inside @media."""
    css = strip_comments(css)
    return [(m.group(1).strip(), m.group(2)) for m in re.finditer(r"([^{}@]+)\{([^{}]*)\}", css)]


# Animations that answer something the visitor did (or a loading state).
# Anything else would play on page load.
ALLOWED_ANIMATION_SELECTORS = {
    ".confetti i",
    ".dish-card.bump",
    ".side-line.is-new, .ln.is-new",
    ".msg.is-new",
    ".mascot-avatar.is-thinking",
}
ALLOWED_INFINITE_SELECTORS = {".skeleton", ".typing::after"}


def test_no_animation_plays_on_page_load():
    for selector, body in rules((FRONTEND / "css" / "motion.css").read_text(encoding="utf-8")):
        if re.search(r"\banimation(-name)?\s*:", body):
            assert selector in ALLOWED_ANIMATION_SELECTORS, f"page-load animation on: {selector}"


def test_endless_animations_are_only_loading_indicators():
    for css_file in CSS_FILES:
        for selector, body in rules((FRONTEND / "css" / css_file).read_text(encoding="utf-8")):
            if re.search(r"\banimation\s*:[^;]*\binfinite\b", body):
                assert selector in ALLOWED_INFINITE_SELECTORS, (
                    f"{css_file}: endless animation on {selector}"
                )


def test_motion_and_display_overrides_exist():
    base = strip_comments((FRONTEND / "css" / "base.css").read_text(encoding="utf-8"))
    for needle in (
        "prefers-reduced-motion: reduce",
        "html.a11y-no-motion",
        "forced-colors: active",
        ":root.a11y-contrast",
        "html.a11y-size-1",
        "html.a11y-size-2",
        "html.a11y-links",
    ):
        assert needle in base, f"base.css is missing {needle}"
    motion_js = (FRONTEND / "js" / "lib" / "motion.js").read_text(encoding="utf-8")
    assert "a11y-no-motion" in motion_js, (
        "reduced() must also honour the menu's stop-animations switch"
    )


def test_boot_script_and_menu_share_the_storage_key_and_classes():
    boot = (FRONTEND / "js" / "a11y-boot.js").read_text(encoding="utf-8")
    menu = (FRONTEND / "js" / "lib" / "a11y-menu.js").read_text(encoding="utf-8")
    assert "yumm.a11y.v1" in boot
    assert "yumm.a11y.v1" in menu
    for cls in ("a11y-size-", "a11y-contrast", "a11y-no-motion", "a11y-links"):
        assert cls in boot
        assert cls in menu


# ---------- served by the app ----------


def test_statement_page_is_served():
    response = TestClient(app).get("/accessibility/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "הצהרת נגישות" in response.text
