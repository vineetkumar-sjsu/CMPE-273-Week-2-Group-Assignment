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
