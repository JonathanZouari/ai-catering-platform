-- SAMPLE DATA, not real zones, fees or hours (OPEN #19, OPEN #5).
-- Same values as frontend/js/customer/mock-backend.js.
-- No blocked dates: the mock computes them from today's date, and fixed dates would go stale.

INSERT INTO delivery_zones (name, fee, definition) VALUES
  ('תל אביב-יפו', 60.00, '{"cities": ["תל אביב-יפו"]}'),
  ('רמת גן', 60.00, '{"cities": ["רמת גן"]}'),
  ('גבעתיים', 60.00, '{"cities": ["גבעתיים"]}'),
  ('הרצליה', 90.00, '{"cities": ["הרצליה"]}'),
  ('פתח תקווה', 100.00, '{"cities": ["פתח תקווה"]}'),
  ('ראשון לציון', 110.00, '{"cities": ["ראשון לציון"]}');

INSERT INTO time_slots (fulfillment_type, start_time, end_time) VALUES
  ('pickup', '10:00', '12:00'),
  ('pickup', '12:00', '14:00'),
  ('pickup', '15:00', '17:00'),
  ('delivery', '09:00', '11:00'),
  ('delivery', '11:00', '13:00'),
  ('delivery', '14:00', '16:00');
