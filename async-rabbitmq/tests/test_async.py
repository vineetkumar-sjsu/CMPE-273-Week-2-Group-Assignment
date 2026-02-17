"""
Test suite for Part B – Async RabbitMQ.

Run from the async-rabbitmq/ directory:
    pip install requests pika
    python tests/test_async.py

Expects services via: docker compose up -d
  order-service   -> localhost:6000
  rabbitmq AMQP   -> localhost:5672
  rabbitmq mgmt   -> localhost:15672
"""

import os
import time
import json
import subprocess
import requests
import pika

ORDER_URL = "http://localhost:6000"
RABBITMQ_HOST = "localhost"
RABBITMQ_PORT = 5672
COMPOSE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def place_order(item="burger", qty=1):
    r = requests.post(f"{ORDER_URL}/order", json={"item": item, "qty": qty}, timeout=10)
    return r.status_code, r.json()


def get_queue_depth(queue_name):
    try:
        conn = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST, RABBITMQ_PORT))
        ch = conn.channel()
        q = ch.queue_declare(queue=queue_name, passive=True)
        depth = q.method.message_count
        conn.close()
        return depth
    except Exception as e:
        return f"error: {e}"


def run_compose(*args):
    return subprocess.run(
        ["docker", "compose"] + list(args),
        cwd=COMPOSE_DIR, capture_output=True, text=True, timeout=60
    )


def test_backlog_drain():
    print(f"\n{'='*60}")
    print("TEST 1: Kill inventory, publish orders, restart, observe drain")
    print(f"{'='*60}")

    # stop inventory
    print("\n  Stopping inventory-service...")
    run_compose("stop", "inventory-service")
    time.sleep(5)

    # publish orders while inventory is down
    num_orders = 15
    print(f"  Publishing {num_orders} orders while inventory is down...")
    order_ids = []
    for i in range(num_orders):
        code, body = place_order(item="pizza", qty=1)
        order_ids.append(body.get("order_id", ""))
        print(f"    order {i+1}: {code} -> {body.get('order_id','')}")
        time.sleep(0.1)

    # check queue depth
    time.sleep(2)
    depth = get_queue_depth("inventory_orders")
    print(f"\n  Queue depth (inventory_orders): {depth}")
    print(f"  Messages are queued in RabbitMQ waiting for a consumer.\n")

    # restart inventory
    print("  Restarting inventory-service...")
    run_compose("start", "inventory-service")

    # poll until drained
    print("  Watching backlog drain...")
    for tick in range(20):
        time.sleep(3)
        depth = get_queue_depth("inventory_orders")
        print(f"    t={tick*3:3d}s  queue depth = {depth}")
        if isinstance(depth, int) and depth == 0:
            print("  Backlog fully drained!")
            break

    # check order statuses
    time.sleep(3)
    r = requests.get(f"{ORDER_URL}/orders")
    orders = r.json()
    confirmed = sum(1 for o in orders.values() if o.get("status") == "confirmed")
    print(f"\n  Orders confirmed: {confirmed}/{num_orders}")


def test_idempotency():
    print(f"\n{'='*60}")
    print("TEST 2: Idempotency – duplicate event_id must not double-reserve")
    print(f"{'='*60}")

    conn = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST, RABBITMQ_PORT))
    ch = conn.channel()
    ch.exchange_declare(exchange="orders", exchange_type="fanout", durable=True)

    fixed_event_id = "idempotency-test-12345"
    event = {
        "event_id": fixed_event_id,
        "event_type": "OrderPlaced",
        "order_id": "ORD-IDEMP-001",
        "item": "soda",
        "qty": 5,
        "timestamp": time.time(),
    }

    for attempt in range(2):
        ch.basic_publish(
            exchange="orders", routing_key="",
            body=json.dumps(event),
            properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
        )
        print(f"  Published event (attempt {attempt+1}) with event_id={fixed_event_id}")

    conn.close()
    time.sleep(5)

    # verify from logs
    result = run_compose("logs", "--tail=30", "inventory-service")
    print("\n  Inventory service logs (last 30 lines):")
    for line in result.stdout.strip().split("\n"):
        if "IDEMP" in line or "idempotent" in line or "duplicate" in line or "reserved" in line.lower():
            print(f"    {line.strip()}")

    print("\n  If inventory only reserved 5 (not 10), idempotency is working.")
    print("  The second message with the same event_id was skipped.")


def test_dlq_poison_message():
    print(f"\n{'='*60}")
    print("TEST 3: DLQ – malformed message goes to dead-letter queue")
    print(f"{'='*60}")

    conn = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST, RABBITMQ_PORT))
    ch = conn.channel()
    ch.exchange_declare(exchange="orders", exchange_type="fanout", durable=True)

    # non-JSON garbage
    ch.basic_publish(
        exchange="orders", routing_key="",
        body=b"THIS IS NOT JSON {{{corrupted",
        properties=pika.BasicProperties(delivery_mode=2),
    )
    print("  Published malformed (non-JSON) message.")

    # JSON but missing required fields
    bad_event = {"event_id": "bad-001"}
    ch.basic_publish(
        exchange="orders", routing_key="",
        body=json.dumps(bad_event),
        properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
    )
    print("  Published JSON with missing required fields.")

    conn.close()
    time.sleep(5)

    dlq_depth = get_queue_depth("orders_dlq")
    print(f"\n  DLQ depth (orders_dlq): {dlq_depth}")
    print("  Both poison messages should be in the dead-letter queue.")

    # show relevant logs
    result = run_compose("logs", "--tail=20", "inventory-service")
    print("\n  Inventory logs (malformed handling):")
    for line in result.stdout.strip().split("\n"):
        if "malformed" in line.lower() or "dlq" in line.lower() or "nack" in line.lower() or "missing" in line.lower():
            print(f"    {line.strip()}")


if __name__ == "__main__":
    print("=" * 60)
    print(" Part B – Async RabbitMQ Test Suite")
    print("=" * 60)

    # wait for services
    print("\nWaiting for order-service...")
    for _ in range(20):
        try:
            r = requests.get(f"{ORDER_URL}/health", timeout=3)
            if r.status_code == 200:
                print("Order service is up.\n")
                break
        except Exception:
            pass
        time.sleep(3)

    test_backlog_drain()
    test_idempotency()
    test_dlq_poison_message()

    print(f"\n{'='*60}")
    print(" All Part B tests completed.")
    print(f"{'='*60}")
