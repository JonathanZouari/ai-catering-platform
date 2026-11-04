# Database Schema (SQLite)

Status: **v1.2 — migrations 0001 through 0003** (`database/migrations/`). The database is SQLite
([ADR 0005](ADR/0005-sqlite-database.md)), which supersedes the earlier Supabase Postgres draft
([ADR 0002](ADR/0002-supabase-postgres-sqlalchemy.md)). The migration file is the source of truth. This
page explains it.

## Initialise and migrate

```bash
cd backend
uv run python -m app.db            # create data/catering.sqlite3 or apply pending migrations
uv run python -m app.db status     # list applied / pending migrations
```

The app also migrates on startup (`DB_AUTO_MIGRATE=true`). Both paths are **non-destructive and
repeatable**:

- Each `database/migrations/NNNN_name.sql` runs once, in order, inside its own `BEGIN IMMEDIATE`
  transaction, and is recorded in `schema_migrations` (version, name, SHA-256 checksum, applied_at).
  Running again applies only new files. Migration 0002 adds history guards and backfills delivery
  snapshots using the current address book; it cannot recover addresses changed before that upgrade.
- A failing migration rolls back completely and is not recorded.
- An applied migration whose file changed, or a database that has a version the code does not know,
  stops the run with an error. Fix it with a **new** migration, never by editing an old one.
- Checksums ignore CRLF/LF differences, so Windows and Linux checkouts agree.
- Transaction control, configuration pragmas and database attachment are rejected by an authorizer
  before execution, so a rogue COMMIT cannot persist half a migration. SQLite's internal read-only
  `quick_check` during ALTER TABLE is allowed.

## Connections

Always use `app.db.connect()` (or the FastAPI dependency `app.db.get_db`). Every connection runs
`PRAGMA foreign_keys = ON` and checks that it took effect. SQLite turns this off by default on each
new connection, and the pragma does nothing inside a transaction, so it is set before the connection
switches to transactional mode. It also sets `busy_timeout = 5000` and `journal_mode = WAL`.
SQLite 3.37+ is required for `STRICT` tables.

`GET /health` reports `{"engine": "sqlite", "schema_version": "0002", "foreign_keys": true}`. It
returns 503 if the schema is missing or foreign keys are off.

## Conventions

| Topic | Rule |
|---|---|
| Tables | `STRICT`. Values that cannot be converted losslessly to the declared type are rejected (`'twenty'` into an INTEGER fails). |
| Keys | `id INTEGER PRIMARY KEY` |
| Money | `INTEGER` **minor units** (agorot for ILS) in `*_minor` columns. Never REAL. Convert with `app.db.money.to_minor` / `from_minor` (Decimal only, floats rejected, more than 2 decimals rejected). |
| Currency | `TEXT` ISO-4217 code, 3 upper-case letters, default `ILS` (**[OPEN #17]**) |
| Ingredient quantities | `INTEGER` in the ingredient's base unit: `g`, `ml`, or `unit` |
| Timestamps | `TEXT` UTC `YYYY-MM-DDTHH:MM:SSZ`, CHECKed with `strftime`, so text order = time order. Use `app.db.timestamps.format_utc`. |
| Dates | `TEXT` `YYYY-MM-DD`, CHECKed with `date(x) IS x` (rejects `2026-02-30`) |
| Booleans | `INTEGER` `0`/`1` with CHECK |
| Enums | `TEXT` with a CHECK list |
| Foreign keys | Default `NO ACTION` (acts as restrict). History is never cascade-deleted. |
| Ledgers | `payments`, `equipment_movements`, `ingredient_movements` are **append-only** (UPDATE/DELETE and conflicting INSERT OR REPLACE raise). Correct them with a refund or adjustment row. |
| `updated_at` | Maintained by triggers unless the statement sets it explicitly |

## Tables

### customers
`id` · `full_name` not blank · `email` unique (case-insensitive), nullable · `phone` nullable ·
`created_at`, `updated_at` · CHECK: email **or** phone is present.

### employees
`id` · `full_name` · `role` ∈ `owner, manager, chef, cook, kitchen_assistant, driver, server, other` ·
`email` unique (case-insensitive) · `phone` · `hired_on` date · `is_active` 0/1 · timestamps.

### addresses
`id` · `customer_id` → customers, **null = business address** (kitchen, warehouse) · `label` · `street`
· `house_number` · `apartment` · `floor` · `city` · `postal_code` · `access_notes` · timestamps ·
UNIQUE(`id`, `customer_id`) so orders can require an address of their own customer.

### events
`id` · `customer_id` → customers · `event_type` · `event_date` · `adults`, `children`,
`vegetarian_guests`, `vegan_guests`, `restricted_guests` (all ≥ 0; subset semantics **[OPEN #4]**) ·
`dietary_notes` · timestamps · CHECK `adults + children > 0`.

### orders
| Column | Rule |
|---|---|
| `customer_id` | → customers |
| `event_id` | unique. Composite FK (`event_id`, `customer_id`) → events: the event belongs to the same customer |
| `status` | `draft` → `pending_approval` → `approved` \| `rejected`. Other transitions raise (trigger) |
| `version` | ≥ 1. Optimistic lock for AI proposals (ADR 0003) |
| `fulfillment_type` | `pickup` \| `delivery` |
| `requested_at` | timestamp |
| `delivery_address_id` | composite FK (`delivery_address_id`, `customer_id`) → addresses. Only for delivery. Required once submitted |
| `currency` | default `ILS` |
| `subtotal_minor`, `delivery_fee_minor`, `total_minor` | ≥ 0. Required once submitted (price frozen). `total = subtotal + fee`. Pickup fee is 0 |
| `submitted_at`, `decided_at`, `decision_note` | `decided_at` is set exactly when approved/rejected |

### deliveries
`order_id` → orders · `purpose` ∈ `food_drop_off, equipment_collection` (food drop-off only for
delivery orders, trigger) · `address_id` → addresses · `driver_employee_id` → employees ·
`status` ∈ `scheduled, out_for_delivery, delivered, failed, cancelled` · `window_start` < `window_end` ·
`dispatched_at`, `completed_at` · `notes`.
Rules: out_for_delivery/delivered need a driver and `dispatched_at`. delivered/failed ⇔ `completed_at`
is set. `completed_at ≥ dispatched_at`.
`address_snapshot` stores destination fields as JSON at creation and remains unchanged when the
address book is edited. A changed destination requires a new delivery record. The food-drop-off
requirement is enforced when either the delivery or its order is updated.

### payments — income receipts and refunds
| Column | Rule |
|---|---|
| `kind` | `receipt` \| `refund` |
| `order_id`, `currency` | composite FK → orders(`id`, `currency`): same currency as the order |
| `amount_minor` | **> 0**. The sign comes from `kind` |
| `method` | `cash, credit_card, bank_transfer, bit, check, other` |
| `document_number` | unique receipt / credit-note number, optional |
| `refund_of_payment_id` | required for refunds, null for receipts. Composite FK keeps the refund on the receipt's order and currency |
| `reason` | required for refunds |
| `recorded_by_employee_id` | → employees |
| `occurred_at` | timestamp |

Triggers: a refund must reference a **receipt**, total refunds of a receipt ≤ the receipt, rows are
append-only. View **`order_payment_summary`**: received, refunded, net paid, and balance due per order.
Python API: `app.repositories.finance.record_receipt / record_refund / order_balance`.

### equipment_items — reusable tables and serving utensils
`name` unique (case-insensitive) · `category` ∈ `table, serving_utensil` · `description` ·
`replacement_cost_minor` · `is_active` · timestamps.

### equipment_movements
`equipment_item_id` · `movement_type` · `quantity` > 0 · `order_id` (required exactly for
dispatch / return / lost_at_event) · `delivery_id` (composite FK → deliveries of the same order) ·
`employee_id` · `occurred_at` · `notes` (required for losses, write-offs, adjustments).

| Type | On hand | Out at events |
|---|---|---|
| `purchase` | +q | |
| `dispatch` | −q | +q |
| `return` | +q | −q |
| `lost_at_event` | | −q |
| `write_off` | −q | |
| `adjustment_in` / `adjustment_out` | ±q | |

Triggers: on hand never goes negative. An order cannot return or lose more than was dispatched to it.
Append-only. Views: **`equipment_stock`** (on hand, out at events) and **`equipment_out_by_order`**.

### ingredients
`name` unique (case-insensitive) · `base_unit` ∈ `g, ml, unit` · `reorder_level` (base units) ·
`is_active` · timestamps.

### ingredient_batches
`ingredient_id` · `lot_code` (unique per ingredient) · `supplier_name` · `received_on` ·
`expires_on` (null = non-perishable, ≥ `received_on`) · `total_cost_minor` · `currency`.
Quantity is not stored here. It is the sum of the batch's movements.
After movements exist, ingredient units and the batch's ingredient, receipt date and expiry date
cannot be changed; this prevents relabeling historical stock. Corrections need new batch records
and explicit adjustment movements.

### ingredient_movements
`batch_id` · `movement_type` ∈ `receipt, consumption, waste, expired_disposal, return_to_supplier,
adjustment_in, adjustment_out` · `quantity` > 0 (base units) · `order_id` (consumption/waste only) ·
`employee_id` · `occurred_at` · `notes` (required for waste and adjustments).
Triggers: a batch never goes negative. No movement before the batch's `received_on`. **No consumption
after `expires_on`** (disposal is allowed). Append-only.
Views: **`ingredient_batch_stock`** (on hand per batch) and **`ingredient_stock`** (usable vs. expired
on hand per ingredient, judged against today's UTC date).
Python API: `app.repositories.inventory.consume_ingredient` draws first-expired-first-out across
usable batches, all or nothing. `expiring_batches(conn, on_or_before)` lists batches to use or discard.

## Customer quotations (migration 0003)

- `dishes`: menu metadata, integer price in agorot, quantity step in thousandths.
- `delivery_zones`: city and fee in agorot. Seed values preserve the UI demonstration menu/rates.
- `order_items`: ordered dish, name/unit snapshot, quantity in thousandths and frozen prices.
- `order_submissions`: unique hash of the private retrieval/retry credential, order reference,
  and validated original payload for historical contact/event details and retry comparison.
  The original local date and full time slot are retained. `orders.requested_at` is the start
  of that slot converted from Asia/Jerusalem to UTC.

The submission transaction creates customer, optional delivery address, event, order, items and
receipt together. It does not identify returning customers by phone/name, reserve inventory,
record income or create a dispatch: a quotation is still awaiting business approval.
Existing rows remain unchanged. The migration adds four tables and seeds only menu/rate data.

## Planned tables (not migrated yet)

The remaining normalized catalog and AI tables from the draft are still planned. They will
follow the conventions above (money in `*_minor`, enums as CHECK lists, JSON as `TEXT` checked with
`json_valid`):

- `dish_categories`, `dish_dietary`, `allergens`, `dish_allergens` (missing row = unknown,
  never "free")
- `time_slots`, `blocked_dates`; business confirmation of delivery rates (**[OPEN #19]**)
- `ai_conversations`, `ai_messages`, `ai_change_proposals` (`base_order_version` must equal
  `orders.version` at execution, `executed_at` set once for idempotency)
- `quantity_rules` once formulas are known (**[OPEN #3]**)
- A recipe link between dishes and ingredients, so consumption can be planned from orders
