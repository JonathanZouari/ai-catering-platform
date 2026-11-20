-- 0001 schema review fixes (Yonatan's review).
-- Upgrades a database created by init_db() (create_all never alters existing tables).
-- Safe to re-run. Run the read-only pre-checks first (see docs/DATABASE_SCHEMA.md, "Migrations").

BEGIN;

-- 1. orders.customer_id goes away; the customer is events.customer_id via orders.event_id.
DO $$
DECLARE mismatched bigint;
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'orders' AND column_name = 'customer_id'
    ) THEN
        EXECUTE 'SELECT count(*) FROM orders o JOIN events e ON e.id = o.event_id
                 WHERE o.customer_id IS DISTINCT FROM e.customer_id' INTO mismatched;
        IF mismatched > 0 THEN
            RAISE EXCEPTION 'orders.customer_id differs from events.customer_id for % order(s); fix the data first', mismatched;
        END IF;
    END IF;
END $$;

ALTER TABLE orders ALTER COLUMN event_id SET NOT NULL;
ALTER TABLE events ALTER COLUMN customer_id SET NOT NULL;
ALTER TABLE orders DROP COLUMN IF EXISTS customer_id;  -- also drops its FK and index

-- 2. json -> jsonb.
ALTER TABLE ai_messages ALTER COLUMN content TYPE jsonb USING content::jsonb;
ALTER TABLE ai_change_proposals ALTER COLUMN changes TYPE jsonb USING changes::jsonb;
ALTER TABLE delivery_zones ALTER COLUMN definition TYPE jsonb USING definition::jsonb;

-- 3a. DEFAULT gen_random_uuid() on every uuid id column.
ALTER TABLE customers ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE events ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE dish_categories ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE dishes ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE delivery_zones ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE time_slots ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE blocked_dates ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE orders ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE order_items ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE ai_conversations ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE ai_messages ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE ai_change_proposals ALTER COLUMN id SET DEFAULT gen_random_uuid();

-- 3b. Indexes on foreign keys not covered by a primary key or UNIQUE.
CREATE INDEX IF NOT EXISTS ix_events_customer_id ON events (customer_id);
CREATE INDEX IF NOT EXISTS ix_dish_allergens_allergen_id ON dish_allergens (allergen_id);
CREATE INDEX IF NOT EXISTS ix_orders_delivery_zone_id ON orders (delivery_zone_id);
CREATE INDEX IF NOT EXISTS ix_order_items_dish_id ON order_items (dish_id);

-- 4. time_slots.capacity is documentation only for now.
COMMENT ON COLUMN time_slots.capacity IS 'Not enforced: there is no reservations table yet (OPEN #5).';

-- 5. A proposal's conversation must belong to the same order.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'ai_conversations'::regclass AND conname = 'uq_ai_conversations_id_order'
    ) THEN
        ALTER TABLE ai_conversations
            ADD CONSTRAINT uq_ai_conversations_id_order UNIQUE (id, order_id);
    END IF;
END $$;

-- Drop the existing single-column FK on conversation_id by its real name (not assumed).
DO $$
DECLARE fk record;
BEGIN
    FOR fk IN
        SELECT c.conname
        FROM pg_constraint c
        WHERE c.conrelid = 'ai_change_proposals'::regclass
          AND c.contype = 'f'
          AND c.conkey = ARRAY[(
              SELECT a.attnum FROM pg_attribute a
              WHERE a.attrelid = c.conrelid AND a.attname = 'conversation_id'
          )]
    LOOP
        EXECUTE format('ALTER TABLE ai_change_proposals DROP CONSTRAINT %I', fk.conname);
    END LOOP;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'ai_change_proposals'::regclass
          AND conname = 'fk_proposal_conversation_same_order'
    ) THEN
        ALTER TABLE ai_change_proposals
            ADD CONSTRAINT fk_proposal_conversation_same_order
            FOREIGN KEY (conversation_id, order_id)
            REFERENCES ai_conversations (id, order_id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_ai_change_proposals_conversation_order
    ON ai_change_proposals (conversation_id, order_id);

COMMIT;
