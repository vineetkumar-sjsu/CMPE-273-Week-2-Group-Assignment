# Common Utilities

Shared helper functions used across all three communication models.

## ids.py

Provides two helpers:

- `generate_order_id()` – returns a string like `ORD-1707000000000-a1b2c3d4` combining a millisecond timestamp with a short random suffix. This makes IDs roughly sortable by creation time while staying globally unique.
- `generate_event_id()` – returns a plain hex UUID, used as a message/event identifier for idempotency checks and tracing.

## Usage

Each service copies or mounts this module so that order and event IDs stay consistent across the sync, async, and streaming implementations.
