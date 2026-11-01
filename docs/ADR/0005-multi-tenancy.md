# ADR 0005 — Multi-tenancy with a shared schema and caterer scope

Status: Accepted (Phase 2) · Date: 2026-11-01

## Context
The product changed from one business to many caterers. Any cross-caterer leak exposes one business's customers and prices to a competitor. ADR 0002 has the backend connect with a privileged role, so Postgres RLS can't be the main barrier. Pilot caterers are onboarded by hand, so the number of tenants stays small during the MVP.

## Decision
- One database and one schema. Every business table carries a non-null `caterer_id`, directly or through a parent that is itself scoped.
- Repository functions take the caterer scope as a required argument, so an unscoped query can't be written by accident.
- Composite foreign keys tie child rows to the same caterer where it matters (for example, an order item's dish must belong to the order's caterer).
- The scope is resolved server-side from the login, private link, or URL slug, and is never accepted from a request body or from model output.
- A resource belonging to another caterer returns `404`.
- Cross-caterer tests are required for every endpoint.

## Consequences
+ One deploy and one migration path for all caterers.
+ Isolation can be tested without a live LLM or real Supabase project.
− Isolation depends on discipline in repositories, so the test requirement is not optional.
− Noisy-neighbor risk on shared resources, accepted at pilot scale.
− A database per caterer would give stronger isolation, but its operating cost isn't justified now.
