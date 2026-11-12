-- orders had both city (FK -> zone_cities) and delivery_zone_id (FK -> delivery_zones),
-- so an order could name a city in one zone and point at another. The zone is fully
-- determined by the city: orders.city -> zone_cities.zone_id. The money that depends
-- on the zone is already frozen in delivery_fee_agorot at submission, so moving a city
-- to another zone later never changes a submitted order's price.
alter table orders drop column delivery_zone_id;  -- also drops ix_orders_zone
