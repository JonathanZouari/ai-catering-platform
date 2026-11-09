"""Static accessibility checks for the customer app (no browser needed).

These guard the basics that are easy to regress: page language/direction, zoom, skip link, colour
contrast of the design tokens, reduced motion, labels on repeated controls, forced-colors.
They do NOT prove WCAG / SI 5568 conformance; that needs manual testing with assistive technology.
"""

import re
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
CUSTOMER_HTML = (FRONTEND / "customer" / "index.html").read_text(encoding="utf-8")
BASE_CSS = (FRONTEND / "css" / "base.css").read_text(encoding="utf-8")
CUSTOMER_CSS = (FRONTEND / "css" / "customer.css").read_text(encoding="utf-8")
MOTION_CSS = (FRONTEND / "css" / "motion.css").read_text(encoding="utf-8")


def js(name: str) -> str:
    return (FRONTEND / "js" / "customer" / name).read_text(encoding="utf-8")


# ---------- colour tokens ----------


def tokens() -> dict[str, str]:
    root = re.search(r":root\s*\{(.*?)\n\}", BASE_CSS, re.S).group(1)
    raw = dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", root))

    def resolve(value: str) -> str:
        value = value.split("/*")[0].strip()
        match = re.fullmatch(r"var\((--[\w-]+)\)", value)
        return resolve(raw[match.group(1)]) if match else value

    return {k: resolve(v) for k, v in raw.items()}


def luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    channels = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


# (foreground token, background token, minimum ratio). 4.5 for text, 3 for UI component boundaries.
PAIRS = [
    ("--color-text", "--color-bg", 4.5),
    ("--color-muted", "--color-bg", 4.5),
    ("--color-muted", "--color-surface-2", 4.5),
    ("--color-muted", "--color-accent-soft", 4.5),
    ("--color-on-accent", "--color-accent", 4.5),
    ("--color-on-accent", "--color-accent-strong", 4.5),
    ("--color-accent", "--color-bg", 4.5),
    ("--color-accent", "--color-accent-soft", 4.5),
    ("--color-danger", "--color-danger-soft", 4.5),
    ("--color-danger", "--color-surface", 4.5),
    ("--color-warning", "--color-warning-soft", 4.5),
    ("--color-warning", "--color-surface", 4.5),
    ("--color-success", "--color-success-soft", 4.5),
    ("--color-success", "--color-surface", 4.5),
    ("--color-control-border", "--color-bg", 3.0),
    ("--color-control-border", "--color-surface", 3.0),
    ("--color-accent", "--color-surface-2", 3.0),  # focus ring on warm panels
]


@pytest.mark.parametrize(("fg", "bg", "minimum"), PAIRS)
def test_token_contrast(fg: str, bg: str, minimum: float) -> None:
    t = tokens()
    assert contrast(t[fg], t[bg]) >= minimum, f"{fg} on {bg}"


# ---------- document basics ----------


def test_page_language_direction_and_title() -> None:
    assert '<html lang="he" dir="rtl">' in CUSTOMER_HTML
    assert re.search(r"<title>[^<]+</title>", CUSTOMER_HTML)


def test_zoom_is_not_blocked() -> None:
    viewport = re.search(r'<meta name="viewport" content="([^"]+)"', CUSTOMER_HTML).group(1)
    assert "user-scalable=no" not in viewport
    assert "maximum-scale" not in viewport


def test_skip_link_and_landmarks() -> None:
    assert 'class="skip-link" href="#app"' in CUSTOMER_HTML
    assert '<main id="app"' in CUSTOMER_HTML
    assert 'aria-label="שלבי ההזמנה"' in CUSTOMER_HTML
    assert 'role="status"' in CUSTOMER_HTML and 'aria-live="polite"' in CUSTOMER_HTML


# ---------- focus, motion, touch, forced colors ----------


def test_focus_outline_is_never_removed_from_interactive_elements() -> None:
    for name, css in {"base": BASE_CSS, "customer": CUSTOMER_CSS}.items():
        for selector in re.findall(r"([^{}]+)\{[^{}]*outline:\s*none", css):
            assert "tabindex" in selector or ".app" in selector, f"{name}.css: {selector.strip()}"
    assert ":focus-visible" in BASE_CSS


def test_reduced_motion_is_respected() -> None:
    assert "prefers-reduced-motion: reduce" in BASE_CSS
    assert "prefers-reduced-motion: reduce" in MOTION_CSS
    assert "prefers-reduced-motion" in (FRONTEND / "js" / "lib" / "motion.js").read_text(
        encoding="utf-8"
    )


def test_touch_target_token_is_at_least_44px() -> None:
    assert int(tokens()["--touch-target"].removesuffix("px")) >= 44


def test_forced_colors_keeps_icons_visible() -> None:
    assert "forced-colors: active" in CUSTOMER_CSS
    assert re.search(r"forced-colors: active\)\s*\{\s*\.icon\s*\{[^}]*CanvasText", CUSTOMER_CSS)


# ---------- repeated controls need distinct names; allergen safety ----------


def test_allergen_button_names_the_dish() -> None:
    card = js("components/dish-card.js")
    assert re.search(r'"aria-label": `מידע על אלרגנים: \$\{dish\.name\}`', card)


def test_unknown_allergens_are_visible_and_never_shown_as_safe() -> None:
    card = js("components/dish-card.js")
    unknown = re.search(r"dish\.allergens === null\)\s*\{(.*?)\n  \}", card, re.S).group(1)
    assert "is-unknown" in unknown and 'icon("warning")' in unknown
    assert "לא סומנו" not in unknown
    dialog = js("components/allergen-dialog.js")
    assert "אי אפשר להניח שהיא נקייה מאלרגנים" in dialog


def test_counter_buttons_include_the_field_name() -> None:
    counter = js("components/counter.js")
    assert "label ?" in counter and "הפחתת ${label}" in counter and "הוספת ${label}" in counter
    assert "label: labelText" in js("views/event.js")


def test_quantity_buttons_name_the_dish() -> None:
    for name in ("components/dish-card.js", "views/summary.js"):
        source = js(name)
        assert "הפחתת כמות: ${dish.name}" in source
        assert "הוספת כמות: ${dish.name}" in source


def test_icon_only_buttons_have_accessible_names() -> None:
    """Every `btn-icon` button in the JS must carry an aria-label."""
    for path in (FRONTEND / "js" / "customer").rglob("*.js"):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r'h\("button",\s*\{[^\n]*btn-icon', text):
            # The props may continue on the next line; the label is always within the same call.
            call = text[match.start() : match.start() + 400].split("icon(")[0]
            assert "aria-label" in call, f"{path.name}: {match.group(0)[:70]}"


# ---------- forms ----------


def test_form_errors_are_linked_to_their_inputs() -> None:
    event = js("views/event.js")
    assert '"err-adults"' in event and '"err-dietary"' in event
    assert "aria-describedby" in event and 'autocomplete: "address-level2"' in event
    summary = js("views/summary.js")
    assert summary.count('"aria-required": "true"') == 2


def test_chat_sheet_makes_background_inert() -> None:
    chat = js("components/chat.js")
    assert ".inert" in chat and "max-width: 991px" in chat
    assert "Escape" in chat


def test_no_duplicate_live_region_on_summary_total() -> None:
    # The total is announced through announce(); a second aria-live on the row would read it twice.
    assert 'class: "total-row grand", "aria-live"' not in js("views/summary.js")
