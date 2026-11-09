# Accessibility implementation and review

Reviewed on 2026-11-09 against Jonathan's integration branch `dev`, commit
`c29f0c529ad2d3b06e10aa3087c70c2ee8c37e6b`. This change does not import the
still-open database/order-decision PRs #37 or #61. Recheck the accessibility
statement and affected UI when those features are merged.

## Sources

- [Kol Zchut: website and application accessibility](https://www.kolzchut.org.il/he/הנגשת_אתרי_אינטרנט_ואפליקציות_לאנשים_עם_מוגבלות), revision 619668, consulted and downloaded locally on 2026-11-09. Its practical guidance points to Israeli Standard 5568, accessible operation and an accessibility statement explaining usage, limitations, alternatives and contact. The source is a general explanation; it does not certify this application or establish that an exemption applies.
- [W3C WCAG quick reference](https://www.w3.org/WAI/WCAG22/quickref/): technical reference for the repository's existing WCAG 2.2 AA target in `UX_UI_SPEC.md`. This target is distinct from a legal compliance determination.
- [W3C modal dialog pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/): keyboard containment, initial/return focus, dismissal and inert background.

The source HTML is retained locally rather than redistributed in the product;
this document is an implementation record, not a copy of the source article.

## Changes

| Area | Implemented behavior |
| --- | --- |
| Statement | Public `/accessibility/`, reachable from home/customer/admin; Hebrew usage guidance, limitations and the owner-authorized contact email. No full-conformance claim. |
| Keyboard | Focusable skip targets; fixed skip links remain visible after scrolling; sticky-control scroll clearance; reveal content becomes visible on keyboard focus. |
| Event form | Guest-count errors describe the relevant inputs; dietary-only errors focus an invalid field and prevent continuation. Counter buttons include the field name. |
| Catalog/summary | Dish actions identify the dish. Required contact fields expose their requirement. Removing the final dish focuses the return-to-menu button. |
| Assistant | On narrow screens the sheet is a labelled modal, traps forward/reverse Tab, makes background content inert and restores focus on dismissal. At 992px it returns to a non-modal panel. Live messages keep valid list semantics; removed action buttons return focus to the input. |
| Controls | Small text buttons and chat suggestion chips have a 44px minimum height. Existing colors, RTL, reduced-motion support and branding are retained. |

## Validation

Five browser scenarios pass using isolated Chromium contexts with synthetic
demo data. Automated axe-core 4.10.3 scans found no WCAG A/AA violations in the
tested landing, statement, event errors, catalog, allergen dialog, summary,
status, mobile assistant and admin placeholder states. The scenarios also
verify keyboard wrapping and restoration, viewport transition, 320px landing
reflow, form errors, last-item removal, demo submission and reload persistence.
No browser JavaScript errors were observed. Evidence is in `docs/evidence/`.

Backend regression: 2 tests passed; Ruff lint passed; all 12 Python files passed
format checking. The existing Starlette/httpx deprecation warning is unrelated.

Reproduce with a local app on port 8770, Node.js and test-only dependencies:

```sh
npm install --no-save playwright axe-core
npx playwright install chromium
node frontend/tests/accessibility.mjs
```

Optional environment variables: `TEST_BASE_URL` (localhost only),
`CHROME_PATH`, `PLAYWRIGHT_MODULE`, `AXE_PATH`, `EVIDENCE_DIR` (existing directory)
and `RESULT_PATH`. The frontend remains build-free with no runtime dependencies.

## Security and remaining checks

Local manual review found no new security issue in this diff: no API, database,
authentication, permission or pricing changes; untrusted display strings still
use the existing text-only DOM helper; no secrets or real orders in evidence.
The requested external Claude `/security-review` submission was blocked by
automatic approval review, so that command was not completed. A local manual
review was performed instead; this is explicitly not an automated security scan.

This is not a complete accessibility certification. Assistive-technology user
testing, additional browser/screen-reader combinations, comprehensive zoom/text
spacing checks and physical-service accessibility details still need review.
The current upstream admin is a placeholder and ordering uses a mock backend;
these tests do not assert cloud order persistence or exercise the unmerged PRs.
