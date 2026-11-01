# ADR 0006 — Customers access orders through a private link

Status: Accepted (Phase 2) · Date: 2026-11-01

## Context
Event orders are one-off, so customer accounts add friction with little return. Customers still need to return to a draft or quote. SMS verification would add a provider and a per-message cost.

## Decision
- No customer account. A customer gives a name and phone when creating an order. The phone is contact information only and is not verified.
- Creating an order generates a random token of at least 256 bits. Only its SHA-256 hash is stored, in `orders.access_token_hash`.
- The private link is `/c/{slug}/#order={order_id}.{token}`. Browsers never send the URL fragment to the server, and API calls carry the token in the `X-Order-Token` header, so it stays out of access logs and referrers.
- Token access covers that one order, its chat, and its proposals. The caterer scope comes from the order.
- Customers are per caterer. The same phone at two caterers is two unrelated customer records.

## Consequences
+ Low friction and no SMS cost.
− Anyone holding the link can see and edit the draft, including name, phone, and address. Customers must be told to keep it private.
− A lost link can't be recovered by the customer in the MVP; the caterer can see the order but can't reissue the link. Recovery depends on the notifications decision.
− The WhatsApp share action puts the link in a `wa.me` URL when the customer clicks it, so that one action knowingly gives the token to WhatsApp. It's optional and the page warns to keep the link private.
− Pages holding a token must load no third-party scripts, and application logs must never record the `X-Order-Token` header.
