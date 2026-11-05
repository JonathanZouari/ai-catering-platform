-- Demo seed data: placeholder dishes and prices, not business rules.
insert into public.dish_categories (name, sort_order) values
  ('Starters', 1), ('Mains', 2), ('Desserts', 3);

insert into public.dishes (category_id, name, description, pricing_unit, unit_price)
select c.id, d.name, d.description, d.unit::public.pricing_unit, d.price
from (values
  ('Starters', 'Hummus platter', 'Creamy hummus with warm pita', 'per_tray', 120.00),
  ('Starters', 'Green salad', 'Seasonal greens, house dressing', 'per_guest', 18.00),
  ('Mains', 'Roast chicken', 'Herb roasted, serves 8 per tray', 'per_tray', 240.00),
  ('Mains', 'Green eggs and ham', 'The house signature', 'per_guest', 42.00),
  ('Desserts', 'Chocolate cake', 'Whole cake, 12 slices', 'per_item', 95.00)
) as d (cat, name, description, unit, price)
join public.dish_categories c on c.name = d.cat;
