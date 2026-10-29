# ADR 0001 — FastAPI modular monolith serving a static frontend

Status: Accepted (Phase 0) · Date: 2026-10-29

## Context
Mandated stack: Python 3.12+, FastAPI, plain HTML/CSS/JS, Railway. One business, modest traffic.

## Decision
One FastAPI app exposes the REST API and serves `frontend/` as static files. Internal layers: `api → services → repositories → models`, plus isolated `agents/`.

## Consequences
+ One Railway service, one deploy, same origin (no CORS).
+ Clear module boundaries allow splitting later.
− Static assets are served by Python; acceptable at this scale (can move to a CDN later).
