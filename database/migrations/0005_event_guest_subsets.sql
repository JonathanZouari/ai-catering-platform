-- Dietary guest groups are subsets of adults + children (OPEN_DECISIONS #4, decided 2026-11-02).
-- Whether vegan guests also count as vegetarian is still open, so only the total bound is enforced.

alter table events
  add constraint events_dietary_subsets check (
    vegetarian_guests <= adults + children
    and vegan_guests <= adults + children
    and restricted_guests <= adults + children
  );
