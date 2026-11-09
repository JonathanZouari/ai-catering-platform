# Accessibility (customer app)

Status: **audit + first round of fixes. Not a conformance claim.** Nothing here has been verified by a
certified accessibility auditor or by manual testing with a screen reader, so the product must not be
described as "fully accessible" or "compliant" yet.

## Reference points (summarised in our own words)

- Israeli Standard **SI 5568** (part 1, web content) builds on the international WCAG guidelines. The
  accessibility-regulation summary on Kol Zchut links to WCAG 2.0 and does not itself state which WCAG
  version the law currently requires; confirm with a legal/accessibility professional. We therefore aim
  for **WCAG 2.1 AA** (a superset of 2.0 AA) and note 2.2 items where cheap.
- Sites and apps serving the public in Israel are covered, and the obligation sits with the operator,
  not the developer. Possible exemptions (economic burden, technical infeasibility, very few users)
  need professional advice.
- The operator is expected to publish an **accessibility statement** describing what was made
  accessible, how to use it, anything not accessible and its alternative, and how to report problems.
- Sources: Kol Zchut, "Accessibility of websites and apps for people with disabilities"
  (kolzchut.org.il), Israeli Standard 5568, W3C WCAG 2.1. Consult them directly; no text is copied here.

## What was checked

| Area | Result |
|---|---|
| Page language / direction | `lang="he" dir="rtl"`; Latin wordmark isolated with `bdi` |
| Zoom / reflow | Viewport does not block zoom; layout uses container queries |
| Colour contrast | Design tokens measured; all text pairs >= 4.5:1, control borders >= 3:1 (enforced in tests) |
| Keyboard | Skip link, focus ring on all controls, focus moved to the step heading on navigation |
| Reduced motion | CSS and JS both respect `prefers-reduced-motion` |
| Touch targets | 44px minimum token for buttons, chips and steppers |

## Changes in this round

1. **Allergen information** is now visible on every dish card (list, "none marked", or an explicit
   warning when unknown, with icon + text, never colour alone). The allergen button's accessible name
   includes the dish name instead of 17 identical "allergen info" buttons.
2. **Repeated controls** have distinct names: guest counter +/- buttons name their field; dish quantity
   announcements include the dish name.
3. **Forms**: adults / dietary errors are linked to their inputs (`aria-describedby`, `aria-invalid`),
   a failed submit announces how many fields need fixing, contact fields are `aria-required`, the city
   field has `autocomplete="address-level2"`.
4. **Announcements**: removed a duplicate live region on the order total (it was read twice); completed
   steps in the stepper now say "completed" in text, not only with a check icon.
5. **Mobile assistant sheet**: while the bottom sheet is open, the page behind is `inert`, so keyboard
   and screen-reader users cannot wander into hidden content.
6. **Windows High Contrast / forced colors**: icons (drawn as masks) and selected choice cards stay visible.
7. Text-link buttons raised to a 44px target; dish header wraps instead of overflowing at high zoom.

## Tests

`backend/tests/test_accessibility.py` runs static checks (token contrast, document basics, zoom, skip
link, focus outlines, reduced motion, forced colors, control names, form error links, inert sheet).
They guard against regressions only and do not replace assistive-technology testing.

## Remaining issues / not verified

- **Not tested** with NVDA / JAWS / VoiceOver / TalkBack, or with Windows High Contrast on real hardware.
- **No automated browser audit** (axe, Lighthouse) was run in this round.
- **Accessibility statement page and named accessibility coordinator** do not exist yet. The business must
  supply the coordinator's contact details and the date of the last review; then add the page and link it
  from every screen (e.g. a footer).
- **Landing page** (`frontend/index.html`) and **admin UI** were out of scope.
- Dish photos use empty `alt` (the dish name sits next to them). Revisit if photos ever carry information.
- Validation messages for the occasion picker and date are still plain text (no error summary list).
- Hebrew copy for the allergen disclaimer is a placeholder pending business input (OPEN_DECISIONS #8).
- Standard 5568 specifics beyond WCAG (and the exact WCAG version required) were not verified against the
  official standard text.
