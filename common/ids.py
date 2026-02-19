"""
Shared ID generators used by all three communication models (sync REST,
async RabbitMQ, and streaming Kafka).

generate_order_id()  - Produces a timestamped order ID (e.g. ORD-1707000000000-a1b2c3d4)
                       that is roughly time-sortable and globally unique.
generate_event_id()  - Produces a hex UUID suitable for message deduplication
                       and distributed tracing.

Each service copies or mounts this module to keep ID formats consistent
across every implementation.
"""

import uuid
import time


def generate_order_id():
    """Generate a unique order ID using timestamp prefix + uuid suffix."""
    ts = int(time.time() * 1000)
    short_uuid = uuid.uuid4().hex[:8]
    return f"ORD-{ts}-{short_uuid}"


def generate_event_id():
    """Generate a unique event/message ID."""
    return uuid.uuid4().hex


if __name__ == "__main__":
    print("Sample order ID:", generate_order_id())
    print("Sample event ID:", generate_event_id())
