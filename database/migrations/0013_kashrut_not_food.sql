-- Non-food catalog items (disposables, OPEN_DECISIONS #10) carry no kashrut badge.
-- kashrut_class null = not food; food dishes stay meat or pareve (the check passes on null).

alter table dish_dietary alter column kashrut_class drop not null;
