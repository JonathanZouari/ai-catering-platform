-- SAMPLE DATA, not real zones, fees or hours (OPEN #19, OPEN #5).
-- Same values as frontend/js/customer/mock-backend.js.
-- No blocked dates: the mock computes them from today's date, and fixed dates would go stale.

INSERT INTO delivery_zones (id, name, fee_minor, definition) VALUES
  (1, 'תל אביב-יפו', 6000, '{"cities": ["תל אביב-יפו"]}'),
  (2, 'רמת גן', 6000, '{"cities": ["רמת גן"]}'),
  (3, 'גבעתיים', 6000, '{"cities": ["גבעתיים"]}'),
  (4, 'הרצליה', 9000, '{"cities": ["הרצליה"]}'),
  (5, 'פתח תקווה', 10000, '{"cities": ["פתח תקווה"]}'),
  (6, 'ראשון לציון', 11000, '{"cities": ["ראשון לציון"]}');

INSERT INTO time_slots (fulfillment_type, start_time, end_time) VALUES
  ('pickup', '10:00', '12:00'),
  ('pickup', '12:00', '14:00'),
  ('pickup', '15:00', '17:00'),
  ('delivery', '09:00', '11:00'),
  ('delivery', '11:00', '13:00'),
  ('delivery', '14:00', '16:00');
