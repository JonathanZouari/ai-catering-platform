# Leads System — Plan **[PROPOSED]**

Status: proposal, not yet built. Extends the MVP scope in `PRD.md`; the PRD and `OPEN_DECISIONS.md` must be updated once this is approved.

## 1. Definition

A **lead** is a short "call me back" inquiry from someone who is not ready to build a full order. It is not an order, has no price, and must never look like a quotation or a confirmed booking.

Confirmed choices:

| Topic | Decision |
|---|---|
| What a lead is | Short inquiry form (not abandoned drafts, not a full CRM pipeline) |
| Sources | Landing page form, AI chat (with explicit customer approval), manual entry by the owner |
| Owner tools | Status + notes, click-to-call / WhatsApp links |
| Notifications | Admin dashboard only, live via Supabase Realtime. No email/SMS |

## 2. Data model (one new migration)

New enum types: `lead_source` (`landing_form`, `ai_chat`, `manual`), `lead_status` (`new`, `contacted`, `converted`, `lost`).

### `leads`

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `full_name` | text not null | 1–100 chars |
| `phone` | text not null | Israeli number, normalized to E.164 (`+972…`), check constraint |
| `email` | text null | |
| `event_type` | text null | |
| `event_date` | date null | |
| `guest_count` | int null | check 1–5000 |
| `message` | text null | ≤ 1000 chars |
| `source` | `lead_source` not null | |
| `status` | `lead_status` not null default `new` | |
| `lost_reason` | text null | required when `status = 'lost'` (check constraint) |
| `customer_id` | uuid null FK `customers` | set when submitted by a logged-in customer |
| `consent_at` | timestamptz null | required for `landing_form` and `ai_chat` (check constraint) |
| `created_at`, `updated_at` | timestamptz | `updated_at` trigger as on other tables |

Indexes: `(status, created_at desc)`, `phone`.

### `lead_notes`

`id`, `lead_id` (FK `leads`, on delete cascade), `author_id` (FK `staff_users`), `body` (text, 1–2000 chars), `created_at`.

### Security

- RLS enabled on both tables. Policies: active staff can select/insert/update. **No anon or customer policies**: public submissions go through the backend (privileged `DATABASE_URL`) so they are validated and rate-limited.
- `leads` added to the Realtime publication for the admin view.
- `supabase/tests/rls_check.sql` must keep passing; run `supabase db advisors --remote` before merging.

## 3. Backend API

Layering `api → services → repositories`; Pydantic schemas in `schemas/`. Errors use the standard `{ error: { code, message, details } }` shape. Contracts to be added to `API_CONTRACTS.md`.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/leads` | public | Create a lead from the landing form. Returns `{ id }` only |
| GET | `/api/admin/leads?status=&page=` | staff | List, newest first |
| GET | `/api/admin/leads/{id}` | staff | Lead + notes |
| PATCH | `/api/admin/leads/{id}` | staff | Change `status` / `lost_reason` |
| POST | `/api/admin/leads/{id}/notes` | staff | Add a note |
| POST | `/api/admin/leads` | staff | Manual entry (`source = manual`, no consent required) |

Public endpoint protections:
- Strict Pydantic validation (lengths, phone format, date not in the past, extra fields forbidden).
- Hidden honeypot field; non-empty → respond 201 without saving.
- Rate limit per IP (initial value ~5/hour, configurable).
- Response never echoes stored data and never reveals whether a phone number already exists.

Staff endpoints verify the Supabase JWT and require an active `staff_users` row (role from DB, never `user_metadata`).

## 4. Sources

### Landing page form

New section on `/` ("רוצים שנחזור אליכם?"): name, phone, optional event type/date/guest count/message, consent checkbox linking to the privacy policy.

Accessibility: visible labels, required-field markers, `autocomplete="name"` / `"tel"`, `inputmode="tel"`, inline errors linked via `aria-describedby`, success message in an `aria-live` region, 44px targets, logical CSS properties. `backend/tests/test_accessibility.py` keeps passing.

### AI chat

New agent tool `propose_lead_handoff` following the existing propose → approve → execute pattern (`AI_AGENT_DESIGN.md`):
- The assistant only proposes; the customer sees a card with **exactly** the fields that will be sent and approves or rejects it.
- Approval executes once on the backend and creates the lead with `source = ai_chat` and `consent_at` set.
- The model never creates a lead directly and never sends data the customer has not seen on the card (prompt-injection guard).
- Proposal storage: decide whether `ai_change_proposals` gets a proposal type or leads use a separate path (currently proposals are order-bound).

### Manual entry

"Add lead" form in the admin tab.

## 5. Admin UI

New "לידים" tab in `/admin/`:
- Badge with count of `new` leads, updated via Realtime.
- List filterable by status, newest first.
- Detail view: fields, source, notes timeline, `tel:` and `https://wa.me/` links.
- Status buttons; marking as lost requires a reason.

## 6. Privacy — open decisions (to add to `OPEN_DECISIONS.md`)

Israeli privacy law requires informing people of the purpose of collection. There is **no privacy policy page yet**; it must exist before the public form goes live.

| # | Question | Owner |
|---|---|---|
| L1 | Privacy policy text and page (`/privacy/`) | Business |
| L2 | Retention period for `lost` / stale leads, and deletion method | Business |
| L3 | Required fields: is phone alone enough? | Business |
| L4 | Duplicate phone submissions: flag or merge? | Business |
| L5 | Should a logged-in customer's details be prefilled? | Product |

## 7. Build order

1. Migration + RLS check, tested together with `seed.sql` inside `BEGIN … ROLLBACK`, then pushed with approval.
2. Backend endpoints + pytest (validation, honeypot, rate limit, staff-only access).
3. Landing page form.
4. Admin tab.
5. AI chat handoff.
6. Docs: `DATABASE_SCHEMA.md`, `ERD.md`, `API_CONTRACTS.md`, `AI_AGENT_DESIGN.md`, `PRD.md` scope, `OPEN_DECISIONS.md`.

Each step ends with E2E, regression and edge-case tests, plus a security review (injection, prompt injection, input validation, secrets), per `CLAUDE.md`.
