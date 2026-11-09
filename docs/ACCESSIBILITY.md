# Accessibility (IS 5568)

Status: **implemented; automated checks pass; manual checks still to be run** (section 5 is the checklist, section 6 the results log).

The customer-facing pages (landing, the four ordering steps, the statement page) follow the Israeli standard **IS 5568**, which is based on **WCAG 2.0 level AA**. The product already targeted WCAG 2.2 AA (`PRODUCT.md`), which includes everything in 2.0 AA, so IS 5568 is the legal minimum and 2.2 AA stays the target. The admin page is still a placeholder and is out of scope.

No third-party accessibility overlay or widget is used. The accessibility menu is part of this codebase.

## 1. Where each criterion is met

| WCAG 2.0 criterion | How it is met | Where |
|---|---|---|
| 1.1.1 Text alternatives | Informative images carry alt text; decorative art uses `alt=""`; icons are `aria-hidden` unless they carry meaning | `js/lib/illustrations.js`, `js/lib/dom.js` (`icon`), all HTML |
| 1.3.1 Info and relationships | One `h1` per screen and no skipped levels; every field has a `<label>`; groups use `fieldset`/`legend`; hints and errors are linked with `aria-describedby`; required fields have `aria-required` | `js/customer/views/*.js` |
| 1.3.2 Meaningful sequence | DOM order is reading order; layout uses logical properties, so RTL needs no reordering | `css/*.css` |
| 1.4.1 Use of colour | Errors have an icon and text; kashrut and diet badges are text; the current step has `aria-current`; the menu's on/off state is a word and a check mark; price changes carry a sign | `views/*.js`, `css/base.css` |
| 1.4.3 Contrast (minimum) | Text at least 4.5:1; high-contrast mode at least 7:1. Tested from the tokens | `css/base.css`, `test_accessibility.py` |
| 1.4.4 Resize text | All font sizes are in rem; layout reflows; the menu adds 125% and 150% on top of browser zoom; below 480px of height the sticky header and bottom bar scroll with the page | `css/*.css` |
| 1.4.5 Images of text | None; headings are real text in a web font | |
| 2.1.1 Keyboard | Every action is a native `button`, `a`, `input` or `select`; the allergen dialog is a native `<dialog>`; Esc closes the dialog, the assistant and the menu | `js/customer/components/*.js` |
| 2.1.2 No keyboard trap | The assistant sheet makes the page behind it `inert` only while it covers the page, and Esc closes it | `components/chat.js` |
| 2.2.2 Pause, stop, hide | Nothing moves on page load; motion answers an action; "עצירת אנימציות" and `prefers-reduced-motion` stop all of it | `css/motion.css`, `js/lib/motion.js` |
| 2.3.1 Three flashes | None | |
| 2.4.1 Bypass blocks | "דילוג לתוכן" skip link on every page | all HTML |
| 2.4.2 Page titled | Each page has a title; the title changes on every ordering step | `js/customer/main.js` |
| 2.4.3 Focus order | Native order, which follows RTL reading order; focus moves to the `h1` on each step change; the "no dishes" error takes focus on submit | `main.js`, `views/summary.js` |
| 2.4.4 Link purpose | Link and button names say what they do; repeated buttons name the dish or the field; external links say they open a new tab | `dish-card.js`, `counter.js`, `index.html` |
| 2.4.6 Headings and labels | Descriptive Hebrew headings and labels | |
| 2.4.7 Focus visible | 3px ring on every interactive element (4px black in high contrast) | `css/base.css` |
| 3.1.1 Language of page | `lang="he" dir="rtl"` on every page | all HTML |
| 3.2.x Predictable | No change of context on focus or input; steps change only on a button press | |
| 3.3.1 / 3.3.2 Errors and labels | Hebrew error text beside the field, the first invalid field takes focus; visible labels, hints and "(חובה)" | `views/event.js`, `views/summary.js` |
| 3.3.3 Error suggestion | Messages say what to fix ("בחרו תאריך לאירוע", "התאריך הזה סגור להזמנות. בחרו תאריך אחר.") | `mock-backend.js` |
| 4.1.2 Name, role, value | Native elements; `aria-pressed`, `aria-expanded`, `aria-controls`, `aria-current`, `aria-live`, `role="log"` where needed | |

Also in this pass: Windows High Contrast (`forced-colors`) keeps the mask icons visible, and the statement page at `/accessibility/` (Hebrew, with placeholder contact details) is linked from every page.

## 2. Accessibility menu

A "נגישות" button in the header of every page opens a panel with: text size (100 / 125 / 150%), high contrast, stop animations, underline links, reset, and a link to the statement. Settings are saved per visitor in `localStorage` (`yumm.a11y.v1`); nothing is sent anywhere.

| File | Role |
|---|---|
| `js/a11y-boot.js` | Classic script in `<head>`. Applies the saved classes to `<html>` before first paint |
| `js/lib/a11y-menu.js` | The button, the panel, saving. Every storage access is in try/catch |
| `css/base.css` | `html.a11y-size-1/2`, `:root.a11y-contrast`, `html.a11y-no-motion`, `html.a11y-links`, the panel |

The button stays hidden until the script has run (`html.a11y-ready`), so it never shows as a dead control.

## 3. Automated checks

```bash
cd backend
uv run pytest tests/test_accessibility.py     # 63 cases, 18 test functions
uv run pytest                                  # whole suite; the same tests run in CI
```

Python standard library only, nothing to install. The order screens are drawn by JavaScript, so these tests read the HTML and CSS files; they do **not** replace the manual checks.

| Test | Cases | What it checks |
|---|---|---|
| language and direction | 3 | `lang="he"`, `dir="rtl"` on landing, customer, statement |
| skip link | 3 | exactly one, and it points at an id that exists |
| image alt | 3 | every `<img>` has an `alt` attribute |
| page title | 3 | one non-empty `<title>` |
| heading levels | 2 | one `h1`, no skipped levels (landing, statement) |
| link and button names | 3 | every `a` and `button` has a name |
| new-tab links | 3 | `target="_blank"` links say they open a new tab |
| menu and statement link | 3 | boot script, one menu button, link to `/accessibility/` |
| statement content | 1 | required sections, contact details still placeholders (no invented phone or email), updated date |
| default contrast | 13 | token pairs at least 4.5:1 |
| high-contrast contrast | 13 | the same pairs at least 7:1 |
| borders and focus ring | 4 | at least 3:1, both modes |
| font sizes | 4 | no `font-size` in px, per CSS file |
| page-load animation | 1 | `motion.css` animates only an allowlist of action-triggered selectors |
| endless animation | 1 | only the skeleton and the typing dots repeat |
| overrides present | 1 | reduced-motion, `a11y-no-motion`, forced-colors, contrast, size and link classes exist; `reduced()` reads the switch |
| boot and menu agree | 1 | same storage key and class names |
| statement served | 1 | `/accessibility/` returns the page |

`test_health.py` also checks that `/`, `/customer/`, `/admin/` and `/accessibility/` are served.

## 4. Known gaps

- The date field is the browser's native date control; its accessibility varies by browser and screen reader.
- Assistant replies are generated text and were not reviewed for accessibility.
- Mock data: dishes, prices and closed dates are placeholders.
- Only one screen reader (Orca) is available for testing. NVDA, JAWS, VoiceOver and TalkBack are untested.
- No review by a certified accessibility specialist; an external audit is needed before any compliance claim.
- The statement's contact details are placeholders (`[להשלמה: …]`) until the business supplies them.

## 5. Manual checklist

Tools already on the development machine: **Google Chrome** (Lighthouse, DevTools "Rendering" panel), **Firefox** (Accessibility Inspector with "Show tabbing order", Zoom Text Only), **Orca** screen reader. Start the app with `cd backend && uv run uvicorn app.main:app` and open `http://localhost:8000`.

Screens: **landing** `/`, **event** `/customer/`, **menu**, **summary**, **status** (`/customer/?demo=pending`, also `approved`, `rejected`), **statement** `/accessibility/`. To reach menu and summary, fill in the event step; add a dish to reach summary.

Mark each box when the check passes; write failures in section 6.

### A. Keyboard only (12)

- [ ] A1 First Tab shows the skip link; Enter jumps to the content (landing, customer, statement)
- [ ] A2 A focus ring is visible on every control, on the cream page, on panels and on green buttons
- [ ] A3 Tab order follows RTL reading order (right to left, top to bottom); check with Firefox "Show tabbing order"
- [ ] A4 Event step: pick the occasion with the arrow keys, then date, time slot, the counters and pickup/delivery
- [ ] A5 Submit the event step empty: focus lands on the first invalid field and the Hebrew error is next to it
- [ ] A6 Menu: category chips, diet filters, add a dish; focus stays on the +/- buttons when the quantity changes
- [ ] A7 Allergen dialog opens with Enter, Esc closes it, focus returns to its button
- [ ] A8 Assistant: opens with focus in the message box; at phone width Tab stays inside the panel; Esc closes it and focus returns to the assistant button
- [ ] A9 Approve and reject a proposal with the keyboard
- [ ] A10 Summary: submit empty moves focus to the name error; with no dishes, focus moves to that error
- [ ] A11 Accessibility menu: open it, switch every option with Space, Esc closes it, focus returns to the button
- [ ] A12 No keyboard trap anywhere; the statement is reachable from every footer

### B. Screen reader: Orca with Firefox (11)

- [ ] B1 Hebrew voice; the page title changes on each step
- [ ] B2 The headings list (H key) makes sense on every screen
- [ ] B3 Each field reads its label, hint and "required"
- [ ] B4 Errors are read out, and read again with their field
- [ ] B5 Counter buttons read their field ("הוספת מבוגרים", "הפחתת ילדים")
- [ ] B6 Dish buttons read the dish name, and the new quantity is announced
- [ ] B7 A change in the total is announced once, not on every animation frame
- [ ] B8 Assistant replies are announced; approving a proposal announces "השינוי הוחל בהזמנה"
- [ ] B9 Decorative images are skipped
- [ ] B10 The status page says the status in words (not only by colour)
- [ ] B11 The menu toggles read their on/off state

### C. Text at 200% (8)

Firefox: View > Zoom > Zoom Text Only, 200%. Then Chrome page zoom 200%. Both at 1280px wide.

- [ ] C1–C6 On each of the 6 screens: no clipped or overlapping text, no lost content or function; horizontal scrolling only inside the category chip row
- [ ] C7 The header and bottom bar do not cover the focused field
- [ ] C8 The menu's 150% setting together with 200% zoom still works on the event and summary screens

### D. Contrast and colour (5)

- [ ] D1 Chrome Lighthouse accessibility audit on all 6 screens; log the score and remaining issues
- [ ] D2 High-contrast mode looks right on all screens
- [ ] D3 DevTools > Rendering > emulate `forced-colors: active`: icons stay visible
- [ ] D4 Emulate `prefers-reduced-motion`, and separately turn on "עצירת אנימציות": nothing moves
- [ ] D5 Nothing relies on colour alone: errors, kashrut badges, current step, selected chips, price change (+/−)

**36 manual checks in total.**

## 6. Results log

Automated: `uv run pytest` and `uv run ruff check . && uv run ruff format --check .` pass (75 passed, 1 skipped at the time of writing).

Scripted browser smoke check, done once during implementation in headless Chrome with throwaway pages that were deleted afterwards (not part of the repo, and not a substitute for section 5): the menu opens, closes with Esc and restores focus, saves and reloads its settings before first paint, and resets; the event form shows Hebrew errors and focuses the first invalid field; counter and dish buttons have distinct names; the page behind the assistant sheet is inert and is released on close; no animation runs on the menu step; at 320px and at 640×360 (200% zoom of a 1280×720 window) with 150% text there is no horizontal scroll on the landing, statement and event screens.

Manual (section 5): **not yet run.**

| Date | Who | Browser / screen reader | Checks run | Failures and notes |
|---|---|---|---|---|
| | | | | |
