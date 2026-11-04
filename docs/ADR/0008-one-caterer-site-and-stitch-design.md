# ADR 0008 — One caterer's site, with the Stitch design

## Status
Accepted (2026-11-04, product owner). Changes how the product is presented; the multi-caterer code and ADR 0005 stay.

## Context
The product owner decided that Yummai is the website of one caterer, טעם של יחד, rather than a platform marketed to many caterers. They also chose the Stitch designs in `stitch_catering_website_ux_design/` (kept out of git, as a local reference) as the primary design for every screen, replacing the old interface.

Two ways to get there were weighed:
- Remove multi-caterer support from the code. A large rewrite of tested code, which would lose tenant isolation and its tests for no gain to the customer.
- Keep the code and run it for one caterer. Chosen.

## Decision
- A `SITE_CATERER` setting names the site's caterer by slug. `/api/config` returns it.
- `/` serves the customer site for that caterer: homepage, event details, menu, summary and status, all in `frontend/customer/`. `/c/{slug}/` still works, for old private links and for any other caterer in the database.
- The Yummai landing page for caterers is removed. Private links for the site's caterer point at `/#order=…`.
- Tenant isolation, private-link tokens, backend-authoritative prices and the approval flow are unchanged.
- The design system follows Stitch's "Culinary Elegance" (`culinary_elegance/DESIGN.md`): navy `#00162d`, saffron `#8b5000` for text and `#fd9d2b` for fills, Rubik, 12–16 px radii. It is written in plain CSS (`frontend/css/base.css`). Tailwind, Google Fonts and Material Symbols are not loaded from CDNs, because the security policy allows only our own files (ADR 0006). Rubik and the icons are served from our own files.
- The homepage video `frontend/media/hero.mp4` keeps the behaviour agreed on the Stitch site: speed 0.6, a 0.6 s crossfade between two layers that never dips to a solid colour, text that never moves, and the still photo for reduced motion or when the video can't play. The security policy gains `media-src 'self' blob:` for it.
- Content from Stitch that isn't backed by data (ratings, "chef recommended" badges, sub-categories, kitchen statuses, revenue, manual orders, printing) is not shown. Menu, prices, dietary facts, allergens, phone and kashrut come from the database.

## Consequences
- The site's brand (logo, colours, homepage copy) is fixed in the frontend. Another caterer at `/c/{slug}/` would show their name, logo and kashrut, but the same look and homepage copy.
- Going back to a multi-caterer platform would need a new landing page and per-caterer branding, but no backend change.
- `hero.mp4` (7.5 MB) is part of the repository and the Docker image.
