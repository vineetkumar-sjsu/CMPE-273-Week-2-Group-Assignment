"""
Test suite for Part C – Kafka Streaming.

Run from the streaming-kafka/ directory:
    pip install requests kafka-python-ng
    python tests/test_streaming.py

Expects services via: docker compose up -d
  producer-order     -> localhost:6000
  kafka (external)   -> localhost:29092
"""

import os
import time
import json
import subprocess
import requests
from kafka import KafkaConsumer, KafkaAdminClient
from kafka.errors import NoBrokersAvailable

PRODUCER_URL = "http://localhost:6000"
KAFKA_BOOTSTRAP = "localhost:29092"
COMPOSE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
METRICS_DIR = os.path.join(COMPOSE_DIR, "metrics")


def run_compose(*args, timeout=60):
    return subprocess.run(
        ["docker", "compose"] + list(args),
        cwd=COMPOSE_DIR, capture_output=True, text=True, timeout=timeout
    )


def wait_for_services(timeout=90):
    print("  Waiting for producer service...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"{PRODUCER_URL}/health", timeout=3)
            if r.status_code == 200:
                print("  Producer is ready.")
                return True
        except Exception:
            pass
        time.sleep(3)
    print("  WARN: producer not ready after timeout")
    return False


def test_produce_10k():
    print(f"\n{'='*60}")
    print("TEST 1: Produce 10,000 events")
    print(f"{'='*60}")

    start = time.time()
    r = requests.post(f"{PRODUCER_URL}/bulk",
                      json={"count": 10000, "fail_rate": 0.1}, timeout=180)
    elapsed = time.time() - start
    body = r.json()
    print(f"  Published: {body.get('published', 0)} events in {elapsed:.1f}s")
    print(f"  Fail rate injected: {body.get('fail_rate', 0)*100:.0f}%")
    return body


def test_consumer_lag():
    print(f"\n{'='*60}")
    print("TEST 2: Consumer lag")
    print(f"{'='*60}")

    result = run_compose(
        "exec", "kafka",
        "kafka-consumer-groups", "--bootstrap-server", "kafka:9092",
        "--describe", "--group", "inventory-group"
    )
    print("  inventory-group lag:")
    for line in result.stdout.strip().split("\n"):
        print(f"    {line}")

    result2 = run_compose(
        "exec", "kafka",
        "kafka-consumer-groups", "--bootstrap-server", "kafka:9092",
        "--describe", "--group", "analytics-group"
    )
    print("\n  analytics-group lag:")
    for line in result2.stdout.strip().split("\n"):
        print(f"    {line}")


def test_replay():
    print(f"\n{'='*60}")
    print("TEST 3: Replay – new consumer group reads from beginning")
    print(f"{'='*60}")

    metrics_file = os.path.join(METRICS_DIR, "metrics_output.json")

    # read existing metrics if present
    before = None
    try:
        with open(metrics_file) as f:
            before = json.load(f)
        print("  BEFORE replay (live metrics):")
        for k, v in before.items():
            if not isinstance(v, dict):
                print(f"    {k}: {v}")
    except FileNotFoundError:
        print("  No existing metrics file (analytics consumer may still be processing).")

    # run replay: exec into the analytics-consumer and run with --replay flag
    print("\n  Running replay (new consumer group, offset=earliest)...")
    result = run_compose(
        "exec", "analytics-consumer",
        "python", "app.py", "--replay",
        timeout=120
    )

    # show last lines of output
    lines = result.stdout.strip().split("\n") if result.stdout else []
    if lines:
        print("  Replay output (last 15 lines):")
        for line in lines[-15:]:
            print(f"    {line}")
    if result.stderr:
        err_lines = result.stderr.strip().split("\n")
        for line in err_lines[-5:]:
            if "ERROR" in line or "error" in line:
                print(f"    [stderr] {line}")

    # read replayed metrics
    after = None
    try:
        with open(metrics_file) as f:
            after = json.load(f)
        print("\n  AFTER replay (recomputed metrics):")
        for k, v in after.items():
            if not isinstance(v, dict):
                print(f"    {k}: {v}")
    except FileNotFoundError:
        print("  No metrics file produced after replay.")

    if before and after:
        print("\n  Comparison (before vs after replay):")
        print(f"    total_orders:   {before.get('total_orders_seen'):>6}  |  {after.get('total_orders_seen'):>6}")
        print(f"    total_reserved: {before.get('total_reserved'):>6}  |  {after.get('total_reserved'):>6}")
        print(f"    total_failed:   {before.get('total_failed'):>6}  |  {after.get('total_failed'):>6}")
        print(f"    failure_rate:   {before.get('failure_rate_percent'):>5.1f}%  |  {after.get('failure_rate_percent'):>5.1f}%")

        if (before.get('total_orders_seen') == after.get('total_orders_seen') and
                before.get('total_failed') == after.get('total_failed')):
            print("    ==> Replay produced CONSISTENT metrics.")
        else:
            print("    ==> Metrics differ slightly. This can happen if the live consumer")
            print("        had not fully consumed all events before the first snapshot.")


if __name__ == "__main__":
    print("=" * 60)
    print(" Part C – Kafka Streaming Test Suite")
    print("=" * 60)

    wait_for_services()
    test_produce_10k()

    print("\n  Waiting 20s for consumers to process...")
    time.sleep(20)

    test_consumer_lag()
    test_replay()

    print(f"\n{'='*60}")
    print(" All Part C tests completed.")
    print(f"{'='*60}")
