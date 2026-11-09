-- init_schema — core Yummai schema for Supabase (Postgres 17). Postgres port of database/migrations/0001_init_sqlite.sql.
-- Postgres port of 0001_init_sqlite.sql: same tables, columns and rules, with native types.
-- Conventions:
--   * ids are uuid (gen_random_uuid()); money is integer agorot (1 ILS = 100); times are timestamptz.
--   * nullable booleans: NULL means UNKNOWN and must never be shown as "no" / "free".
--   * RLS is enabled on every table with no policies: only the backend's privileged role
--     (postgres / service_role) can read or write. The anon key sees nothing.
-- Idempotent: safe to run on an existing database.

-- ---------------------------------------------------------------- enums
DO $$
BEGIN
    IF to_regtype('public.pricing_unit') IS NULL THEN
        CREATE TYPE public.pricing_unit AS ENUM ('per_guest', 'per_tray', 'per_weight', 'per_item');
    END IF;
    IF to_regtype('public.kashrut_class') IS NULL THEN
        CREATE TYPE public.kashrut_class AS ENUM ('meat', 'dairy', 'pareve');
    END IF;
    IF to_regtype('public.fulfillment_type') IS NULL THEN
        CREATE TYPE public.fulfillment_type AS ENUM ('pickup', 'delivery');
    END IF;
    IF to_regtype('public.order_status') IS NULL THEN
        CREATE TYPE public.order_status AS ENUM
            ('draft', 'pending_approval', 'approved', 'rejected', 'cancelled');
    END IF;
    IF to_regtype('public.allergen_status') IS NULL THEN
        CREATE TYPE public.allergen_status AS ENUM ('contains', 'free', 'unknown');
    END IF;
    IF to_regtype('public.proposal_status') IS NULL THEN
        CREATE TYPE public.proposal_status AS ENUM
            ('pending', 'approved', 'rejected', 'expired', 'failed');
    END IF;
END
$$;

-- ---------------------------------------------------------------- tables
CREATE TABLE IF NOT EXISTS public.customers (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name   text NOT NULL CHECK (length(trim(full_name)) > 0),
    email       text UNIQUE CHECK (email IS NULL OR (email = lower(email) AND email LIKE '%_@_%')),
    phone       text,
    notes       text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.events (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id        uuid NOT NULL REFERENCES public.customers (id),
    event_type         text NOT NULL,
    event_date         date NOT NULL,
    adults             integer NOT NULL DEFAULT 0 CHECK (adults >= 0),
    children           integer NOT NULL DEFAULT 0 CHECK (children >= 0),
    vegetarian_guests  integer NOT NULL DEFAULT 0 CHECK (vegetarian_guests >= 0),
    vegan_guests       integer NOT NULL DEFAULT 0 CHECK (vegan_guests >= 0),
    restricted_guests  integer NOT NULL DEFAULT 0 CHECK (restricted_guests >= 0),
    dietary_notes      text,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    CHECK (adults + children > 0)
);
CREATE INDEX IF NOT EXISTS ix_events_customer ON public.events (customer_id);
CREATE INDEX IF NOT EXISTS ix_events_date ON public.events (event_date);

CREATE TABLE IF NOT EXISTS public.dish_categories (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text NOT NULL UNIQUE,
    sort_order  integer NOT NULL DEFAULT 0,
    is_active   boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.dishes (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id        uuid NOT NULL REFERENCES public.dish_categories (id),
    name               text NOT NULL,
    description        text,
    image_path         text,
    pricing_unit       public.pricing_unit NOT NULL,
    unit_price_agorot  integer NOT NULL CHECK (unit_price_agorot >= 0),
    unit_label         text,
    currency           char(3) NOT NULL DEFAULT 'ILS' CHECK (length(currency) = 3),
    min_quantity       numeric(10, 2) CHECK (min_quantity IS NULL OR min_quantity > 0),
    quantity_step      numeric(10, 2) CHECK (quantity_step IS NULL OR quantity_step > 0),
    per_guest_ratio    numeric(10, 3) CHECK (per_guest_ratio IS NULL OR per_guest_ratio > 0),
    kashrut_class      public.kashrut_class,
    is_vegetarian      boolean,
    is_vegan           boolean,
    sort_order         integer NOT NULL DEFAULT 0,
    is_available       boolean NOT NULL DEFAULT true,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    CHECK (is_vegan IS NOT TRUE OR is_vegetarian IS NOT FALSE)
);
CREATE INDEX IF NOT EXISTS ix_dishes_category ON public.dishes (category_id);

CREATE TABLE IF NOT EXISTS public.allergens (
    id    smallint PRIMARY KEY,
    name  text NOT NULL UNIQUE
);

-- A missing (dish, allergen) row means UNKNOWN, never "free".
CREATE TABLE IF NOT EXISTS public.dish_allergens (
    dish_id      uuid NOT NULL REFERENCES public.dishes (id) ON DELETE CASCADE,
    allergen_id  smallint NOT NULL REFERENCES public.allergens (id),
    status       public.allergen_status NOT NULL,
    PRIMARY KEY (dish_id, allergen_id)
);
CREATE INDEX IF NOT EXISTS ix_dish_allergens_allergen ON public.dish_allergens (allergen_id);

-- Logistics (admin-managed): delivery zones, pickup/delivery time slots, blocked dates.
CREATE TABLE IF NOT EXISTS public.delivery_zones (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text NOT NULL UNIQUE,
    fee_agorot  integer NOT NULL CHECK (fee_agorot >= 0),
    -- Shape depends on OPEN #19 (city list, radius, polygon...).
    definition  jsonb NOT NULL DEFAULT '{}'::jsonb,
    is_active   boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.time_slots (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fulfillment_type  public.fulfillment_type NOT NULL,
    weekday           smallint CHECK (weekday BETWEEN 0 AND 6),  -- NULL = every day
    start_time        time NOT NULL,
    end_time          time NOT NULL,
    capacity          integer CHECK (capacity IS NULL OR capacity > 0),  -- OPEN #5
    is_active         boolean NOT NULL DEFAULT true,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    CHECK (end_time > start_time)
);

CREATE TABLE IF NOT EXISTS public.blocked_dates (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    date        date NOT NULL UNIQUE,
    reason      text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.orders (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Human-friendly order numbers (1001, 1002, ...); replaces the SQLite trigger.
    order_number         integer GENERATED BY DEFAULT AS IDENTITY (START WITH 1001) UNIQUE,
    customer_id          uuid NOT NULL REFERENCES public.customers (id),
    event_id             uuid NOT NULL UNIQUE REFERENCES public.events (id),
    status               public.order_status NOT NULL DEFAULT 'draft',
    version              integer NOT NULL DEFAULT 1 CHECK (version >= 1),
    fulfillment_type     public.fulfillment_type NOT NULL,
    requested_date       date,
    requested_slot       text,
    delivery_city        text,
    delivery_address     text,
    delivery_zone_id     uuid REFERENCES public.delivery_zones (id),
    subtotal_agorot     integer CHECK (subtotal_agorot >= 0),
    delivery_fee_agorot  integer CHECK (delivery_fee_agorot >= 0),
    total_agorot         integer CHECK (total_agorot >= 0),
    customer_notes       text,
    decision_note        text,
    submitted_at         timestamptz,
    decided_at           timestamptz,
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now(),
    CHECK (fulfillment_type <> 'delivery'
           OR (delivery_address IS NOT NULL AND length(trim(delivery_address)) > 0))
);
CREATE INDEX IF NOT EXISTS ix_orders_status ON public.orders (status);
CREATE INDEX IF NOT EXISTS ix_orders_customer ON public.orders (customer_id);

CREATE TABLE IF NOT EXISTS public.order_items (
    id                          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id                    uuid NOT NULL REFERENCES public.orders (id) ON DELETE CASCADE,
    dish_id                     uuid NOT NULL REFERENCES public.dishes (id),
    quantity                    numeric(10, 2) NOT NULL CHECK (quantity > 0),
    -- Price snapshot: filled on submission; authoritative once the order leaves 'draft'.
    snapshot_name               text,
    snapshot_pricing_unit       public.pricing_unit,
    snapshot_unit_price_agorot  integer CHECK (snapshot_unit_price_agorot >= 0),
    snapshot_line_total_agorot  integer CHECK (snapshot_line_total_agorot >= 0),
    created_at                  timestamptz NOT NULL DEFAULT now(),
    updated_at                  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (order_id, dish_id)
);
CREATE INDEX IF NOT EXISTS ix_order_items_dish ON public.order_items (dish_id);

CREATE TABLE IF NOT EXISTS public.order_status_history (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id     uuid NOT NULL REFERENCES public.orders (id) ON DELETE CASCADE,
    from_status  public.order_status,
    to_status    public.order_status NOT NULL,
    changed_by   text NOT NULL CHECK (changed_by IN ('customer', 'owner', 'system')),
    note         text,
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_status_history_order ON public.order_status_history (order_id);

-- AI assistant (scoped to one order). The AI only creates proposals; the customer approves them.
CREATE TABLE IF NOT EXISTS public.ai_conversations (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id    uuid NOT NULL REFERENCES public.orders (id) ON DELETE CASCADE,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_ai_conversations_order ON public.ai_conversations (order_id);

CREATE TABLE IF NOT EXISTS public.ai_messages (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id  uuid NOT NULL REFERENCES public.ai_conversations (id) ON DELETE CASCADE,
    role             text NOT NULL CHECK (role IN ('user', 'assistant', 'tool')),
    content          jsonb NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_ai_messages_conversation ON public.ai_messages (conversation_id, created_at);

CREATE TABLE IF NOT EXISTS public.ai_change_proposals (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id             uuid NOT NULL REFERENCES public.orders (id) ON DELETE CASCADE,
    conversation_id      uuid REFERENCES public.ai_conversations (id) ON DELETE SET NULL,
    base_order_version   integer NOT NULL CHECK (base_order_version >= 1),  -- must equal orders.version
    changes              jsonb NOT NULL,  -- validated list of typed operations
    rationale            text,
    price_before_agorot  integer NOT NULL CHECK (price_before_agorot >= 0),
    price_after_agorot   integer NOT NULL CHECK (price_after_agorot >= 0),
    status               public.proposal_status NOT NULL DEFAULT 'pending',
    created_at           timestamptz NOT NULL DEFAULT now(),
    decided_at           timestamptz,
    executed_at          timestamptz,  -- set once -> idempotent execution
    CHECK (executed_at IS NULL OR status = 'approved')
);
CREATE INDEX IF NOT EXISTS ix_ai_proposals_order ON public.ai_change_proposals (order_id);
CREATE INDEX IF NOT EXISTS ix_ai_proposals_conversation ON public.ai_change_proposals (conversation_id);
-- At most one pending proposal per order (simplifies the UI).
CREATE UNIQUE INDEX IF NOT EXISTS ux_ai_proposals_one_pending
    ON public.ai_change_proposals (order_id) WHERE status = 'pending';

-- ---------------------------------------------------------------- triggers
-- Keep updated_at current, unless the UPDATE already set it explicitly.
CREATE OR REPLACE FUNCTION public.set_updated_at() RETURNS trigger
LANGUAGE plpgsql SET search_path = '' AS $$
BEGIN
    IF NEW.updated_at IS NOT DISTINCT FROM OLD.updated_at THEN
        NEW.updated_at := now();
    END IF;
    RETURN NEW;
END
$$;

CREATE OR REPLACE TRIGGER trg_customers_updated BEFORE UPDATE ON public.customers
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE OR REPLACE TRIGGER trg_events_updated BEFORE UPDATE ON public.events
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE OR REPLACE TRIGGER trg_dish_categories_updated BEFORE UPDATE ON public.dish_categories
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE OR REPLACE TRIGGER trg_dishes_updated BEFORE UPDATE ON public.dishes
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE OR REPLACE TRIGGER trg_delivery_zones_updated BEFORE UPDATE ON public.delivery_zones
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE OR REPLACE TRIGGER trg_time_slots_updated BEFORE UPDATE ON public.time_slots
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE OR REPLACE TRIGGER trg_orders_updated BEFORE UPDATE ON public.orders
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE OR REPLACE TRIGGER trg_order_items_updated BEFORE UPDATE ON public.order_items
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- Audit trail: record every status change automatically.
CREATE OR REPLACE FUNCTION public.log_order_status_change() RETURNS trigger
LANGUAGE plpgsql SET search_path = '' AS $$
BEGIN
    INSERT INTO public.order_status_history (order_id, from_status, to_status, changed_by)
    VALUES (NEW.id, OLD.status, NEW.status, 'system');
    RETURN NULL;
END
$$;

CREATE OR REPLACE TRIGGER trg_orders_status_history AFTER UPDATE OF status ON public.orders
    FOR EACH ROW WHEN (NEW.status IS DISTINCT FROM OLD.status)
    EXECUTE FUNCTION public.log_order_status_change();

-- ---------------------------------------------------------------- row level security
ALTER TABLE public.customers            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.events               ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dish_categories      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dishes               ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.allergens            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dish_allergens       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.orders               ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.order_items          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.order_status_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.delivery_zones       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.time_slots           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.blocked_dates        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_conversations     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_messages          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_change_proposals  ENABLE ROW LEVEL SECURITY;
CREATE INDEX IF NOT EXISTS ix_orders_delivery_zone ON public.orders (delivery_zone_id);
