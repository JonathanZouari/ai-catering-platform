update order_items oi set snapshot_name = d.name, snapshot_pricing_unit = d.pricing_unit,
  snapshot_unit_price = d.unit_price, snapshot_line_total = round(oi.quantity * d.unit_price)
from dishes d, orders o
where d.id = oi.dish_id and o.id = oi.order_id and o.status <> 'draft' and oi.snapshot_name is null;

update orders o set
  subtotal = (select sum(snapshot_line_total) from order_items where order_id = o.id),
  delivery_fee = coalesce((select fee from delivery_zones where id = o.delivery_zone_id), 0),
  total = (select sum(snapshot_line_total) from order_items where order_id = o.id)
          + coalesce((select fee from delivery_zones where id = o.delivery_zone_id), 0)
where o.status <> 'draft' and o.total is null;
