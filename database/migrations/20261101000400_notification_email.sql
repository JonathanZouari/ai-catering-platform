-- Where a caterer hears about new orders. Null means no email is sent (OPEN_DECISIONS #13).
alter table caterers add column notification_email text;
