-- Delivery to any Israeli locality (OPEN_DECISIONS #19, extended 2026-11-08).
-- Cities in a delivery zone keep the zone's fee; any other locality on the CBS list
-- (frontend/data/cities.json) costs this fee. null = deliver only to zone cities.
alter table business_settings
  add column default_delivery_fee numeric(10, 2)
    check (default_delivery_fee is null or default_delivery_fee between 0 and 10000);
