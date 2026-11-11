# Database schema — MVP

The primary application database is Supabase Postgres. SQLite remains an explicit local fallback with the same customer quotation contract. A cloud failure never silently writes to SQLite.

## Scope and identifiers

PR 37 contains customer quotations, a normalized menu, owner catalog access, availability configuration and the schema foundation for the customer AI assistant. Employees, dispatch execution, payments, equipment and ingredient inventory are an optional, separate operations extension.

Domain identifiers use integer keys (`bigint` identities in Postgres, `INTEGER PRIMARY KEY` in SQLite). Join tables use composite integer foreign keys. The public API keeps legacy dish codes such as `d1` as a compatibility alias so stored carts and retry payloads remain valid; these are not database primary keys. Receipt tokens are unique credentials, not entity identifiers.

Money is stored as integer minor units. Quantities use integer thousandths. Submitted order names, units and prices are snapshots; editing the catalog cannot change an existing receipt.

## Core tables

- `customers`: contact details, with email or telephone required.
- `addresses`: address book entries associated with a customer.
- `events`: private event date and guest composition; at least one guest.
- `orders`: quotation state, version, fulfillment, frozen totals and timestamps. Composite foreign keys ensure the event and delivery address belong to the order's customer.
- `order_items`: integer dish references and historical line snapshots.
- `order_submissions`: unique hashed retry/retrieval credential and original request payload. No anonymous or browser access.
- `delivery_zones`: integer identity, unique city and fee in minor units.

## Normalized catalog

- `dish_categories`: category identities and owner-managed names/order/availability.
- `dishes`: integer identity, unique legacy code, category FK, name, description, pricing unit, canonical integer price, quantity step and image reference. There is no authoritative JSON metadata catalog or second price.
- `dish_dietary`: one row per dish, nullable kashrut/vegetarian/vegan properties. Null means unknown.
- `allergens`: named allergen identities.
- `dish_allergens`: dish/allergen relation with `contains`, `free` or `unknown`. A missing relation means unknown, never free. A historical empty array does not establish that a dish is allergen-free.

Migration snapshots retain original metadata for recovery/audit only. They are not exposed by the catalog API. The legacy code remains available for old media paths and customer payload compatibility.

## Availability (Postgres)

- `time_slots`: fulfillment type, optional weekday, start/end time, optional positive capacity, active flag.
- `blocked_dates`: unique date and optional reason.
- `orders.time_slot_id`: nullable reference, allowing old quotations to remain intact.

These tables are schema foundations. The existing customer slot rules are still demonstrations: this change does not claim reservation/capacity enforcement or a complete scheduling UI.

## Customer assistant foundation (Postgres)

- `ai_conversations`: associated order and timestamp.
- `ai_messages`: conversation FK, role (`user`, `assistant`, `tool`), structured content and timestamp.
- `ai_change_proposals`: order/conversation association, base order version, proposed operations, integer before/after prices, decision and execution timestamps.

Composite references prevent a proposal from using another order's conversation. Executed proposal records cannot be rewritten or deleted. Browser roles cannot access these tables. No AI executor or customer approval endpoint is enabled by this schema change. A future implementation must enforce authenticated/capability-based order ownership, check the order version and apply approved changes once under a transaction; see `AI_AGENT_DESIGN.md`.

## Access control

Every exposed Postgres table has RLS enabled and explicit grants. Owner access uses server-controlled `app_metadata`, never editable user metadata. Customer writes and private receipt reads go through backend-only invoker RPCs. Server credentials stay in the ignored environment file.

## Migration paths

Fresh Postgres installs start with `mvp_core_baseline`, then apply the availability and normalized-catalog migrations. The baseline skips an already initialized course database; it does not delete its rows. The previous broad bootstraps are preserved on the operations history branch and are no longer part of the MVP install path.

The existing hosted project was initially created through the SQL editor, not tracked CLI migrations. Reconcile the exact applied versions before any CLI push. Never reset the hosted project to perform this split. Original optional tables remain historical data until a separate, reviewed transition is performed.

SQLite fresh installs apply migrations `0004` and `0005`. Existing course databases with exact known checksums for `0001`–`0003` are recognized and upgraded without rewriting their ledger or deleting optional tables. Unknown checksums fail closed. Catalog IDs/FKs are migrated transactionally; receipt snapshots and hashed credentials are preserved.

## Validation

- `backend/tests`: local order submission/recovery, normalized catalog constraints, migration integrity and mocked cloud failures.
- `frontend/tests`: receipt recovery and three-state allergen behavior.
- `supabase/tests/mvp-postgres.mjs`: fresh MVP scope, RLS, schedule constraints and proposal association/history.
- Catalog migration tests cover upgrade preservation and normalized catalog RPC behavior.

Local SQL execution uses PGlite with Auth/Storage stubs. It is not proof of hosted authentication, Realtime, Storage API or concurrent connections. Historical hosted restart screenshots predate this review revision.