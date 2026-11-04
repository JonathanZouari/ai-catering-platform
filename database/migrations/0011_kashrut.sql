-- Kashrut (OPEN_DECISIONS #9, decided 2026-11-04): the kitchen is kosher with a certificate and
-- serves meat and pareve dishes only (no dairy), so meat and dairy can never meet in an order.
-- Every dish has a known kashrut class; unmarked dishes are pareve.

-- Dishes without a dietary row get one (pareve, everything else unknown).
insert into dish_dietary (dish_id, kashrut_class)
select d.id, 'pareve' from dishes d
where not exists (select 1 from dish_dietary dd where dd.dish_id = d.id);

update dish_dietary set kashrut_class = 'pareve'
where kashrut_class is null or kashrut_class = 'dairy';

alter table dish_dietary
  alter column kashrut_class set default 'pareve',
  alter column kashrut_class set not null,
  add constraint dish_dietary_meat_or_pareve check (kashrut_class in ('meat', 'pareve'));
-- The enum type keeps 'dairy' (Postgres can't drop an enum value); the check keeps it out.

-- Who certifies the kitchen, shown to customers; null = not shown.
alter table business_settings
  add column kashrut_certificate text check (char_length(kashrut_certificate) <= 200);
