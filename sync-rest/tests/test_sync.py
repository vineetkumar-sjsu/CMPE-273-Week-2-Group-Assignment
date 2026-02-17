"""
Test suite for Part A – Synchronous REST.

Run from the sync-rest/ directory:
    pip install requests
    python tests/test_sync.py

Expects services via: docker compose up -d
  order-service   -> localhost:6000
  inventory       -> localhost:6001
  notification    -> localhost:6002

For delay/failure injection tests the script will automatically
restart inventory-service with the right environment variables.
"""

import os
import sys
import time
import json
import statistics
import subprocess
import requests

ORDER_URL = "http://localhost:6000"
INVENTORY_URL = "http://localhost:6001"

ITEMS = ["burger", "pizza", "soda", "fries", "salad"]
COMPOSE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def place_order(item="burger", qty=1):
    start = time.time()
    try:
        r = requests.post(f"{ORDER_URL}/order", json={"item": item, "qty": qty}, timeout=10)
        elapsed_ms = (time.time() - start) * 1000
        return r.status_code, r.json(), elapsed_ms
    except requests.exceptions.Timeout:
        elapsed_ms = (time.time() - start) * 1000
        return 0, {"error": "timeout"}, elapsed_ms
    except requests.exceptions.ConnectionError:
        elapsed_ms = (time.time() - start) * 1000
        return 0, {"error": "connection_refused"}, elapsed_ms


def run_compose(*args):
    result = subprocess.run(
        ["docker", "compose"] + list(args),
        cwd=COMPOSE_DIR, capture_output=True, text=True, timeout=60
    )
    return result


def wait_for_service(url, label, timeout=30):
    for _ in range(timeout // 2):
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(2)
    print(f"  WARN: {label} not ready after {timeout}s")
    return False


def test_baseline_latency(n=20):
    print(f"\n{'='*60}")
    print(f"TEST 1: Baseline latency ({n} requests, no injected delay)")
    print(f"{'='*60}")
    latencies = []
    for i in range(n):
        code, body, ms = place_order(item=ITEMS[i % len(ITEMS)], qty=1)
        latencies.append(ms)
        status = body.get("status", "error")
        print(f"  req {i+1:3d}  | {code} | {status:10s} | {ms:7.1f} ms")

    print(f"\n  --- Summary ---")
    print(f"  min    = {min(latencies):7.1f} ms")
    print(f"  max    = {max(latencies):7.1f} ms")
    print(f"  mean   = {statistics.mean(latencies):7.1f} ms")
    print(f"  median = {statistics.median(latencies):7.1f} ms")
    if len(latencies) > 1:
        print(f"  stdev  = {statistics.stdev(latencies):7.1f} ms")
    return latencies


def test_delay_injection(n=10):
    print(f"\n{'='*60}")
    print("TEST 2: 2s delay injected into Inventory Service")
    print(f"{'='*60}")

    # set env var and recreate only the inventory service
    os.environ["SIMULATED_DELAY"] = "2"
    print("  Recreating inventory-service with SIMULATED_DELAY=2 ...")
    run_compose("up", "-d", "--no-deps", "--force-recreate",
                "-e", "SIMULATED_DELAY=2", "inventory-service")
    # the -e flag doesn't work with up, so we write a temp override
    override = os.path.join(COMPOSE_DIR, "docker-compose.override.yml")
    with open(override, "w") as f:
        f.write("""services:
  inventory-service:
    environment:
      - SIMULATED_DELAY=2
      - FORCE_FAILURE=false
""")
    run_compose("up", "-d", "--no-deps", "--force-recreate", "inventory-service")
    time.sleep(4)
    wait_for_service(f"{INVENTORY_URL}/health", "inventory (delayed)")

    latencies = []
    for i in range(n):
        code, body, ms = place_order(item="burger", qty=1)
        latencies.append(ms)
        status = body.get("status", "error")
        print(f"  req {i+1:3d}  | {code} | {status:10s} | {ms:7.1f} ms")

    print(f"\n  --- Summary (with 2s delay) ---")
    print(f"  min    = {min(latencies):7.1f} ms")
    print(f"  max    = {max(latencies):7.1f} ms")
    print(f"  mean   = {statistics.mean(latencies):7.1f} ms")
    print(f"  median = {statistics.median(latencies):7.1f} ms")

    # restore normal inventory
    os.remove(override)
    run_compose("up", "-d", "--no-deps", "--force-recreate", "inventory-service")
    time.sleep(3)
    wait_for_service(f"{INVENTORY_URL}/health", "inventory (restored)")

    return latencies


def test_failure_injection(n=5):
    print(f"\n{'='*60}")
    print("TEST 3: Inventory forced failure (FORCE_FAILURE=true)")
    print(f"{'='*60}")

    override = os.path.join(COMPOSE_DIR, "docker-compose.override.yml")
    with open(override, "w") as f:
        f.write("""services:
  inventory-service:
    environment:
      - SIMULATED_DELAY=0
      - FORCE_FAILURE=true
""")
    run_compose("up", "-d", "--no-deps", "--force-recreate", "inventory-service")
    time.sleep(4)
    wait_for_service(f"{INVENTORY_URL}/health", "inventory (failing)")

    for i in range(n):
        code, body, ms = place_order(item="burger", qty=1)
        status = body.get("status", body.get("error", "unknown"))
        reason = body.get("reason", "")
        print(f"  req {i+1:3d}  | HTTP {code} | {status:10s} | reason={reason} | {ms:7.1f} ms")

    # restore
    os.remove(override)
    run_compose("up", "-d", "--no-deps", "--force-recreate", "inventory-service")
    time.sleep(3)
    wait_for_service(f"{INVENTORY_URL}/health", "inventory (restored)")


def test_inventory_down(n=3):
    print(f"\n{'='*60}")
    print("TEST 4: Inventory service completely down (timeout + error)")
    print(f"{'='*60}")

    print("  Stopping inventory-service ...")
    run_compose("stop", "inventory-service")
    time.sleep(2)

    for i in range(n):
        code, body, ms = place_order(item="burger", qty=1)
        status = body.get("status", body.get("error", "unknown"))
        reason = body.get("reason", "")
        print(f"  req {i+1:3d}  | HTTP {code} | {status:10s} | reason={reason} | {ms:7.1f} ms")

    # restore
    print("  Restarting inventory-service ...")
    run_compose("start", "inventory-service")
    time.sleep(3)


if __name__ == "__main__":
    print("=" * 60)
    print(" Part A – Synchronous REST Test Suite")
    print("=" * 60)

    print("\nWaiting for services to be ready...")
    wait_for_service(f"{ORDER_URL}/health", "order-service")
    wait_for_service(f"{INVENTORY_URL}/health", "inventory-service")

    baseline = test_baseline_latency(20)
    delayed = test_delay_injection(10)
    test_failure_injection(5)
    test_inventory_down(3)

    print(f"\n{'='*60}")
    print("LATENCY COMPARISON TABLE")
    print(f"{'='*60}")
    print(f"  {'Scenario':<30s} | {'Mean (ms)':>10s} | {'Median (ms)':>12s}")
    print(f"  {'-'*30} | {'-'*10} | {'-'*12}")
    print(f"  {'Baseline (no delay)':<30s} | {statistics.mean(baseline):>10.1f} | {statistics.median(baseline):>12.1f}")
    print(f"  {'2s inventory delay':<30s} | {statistics.mean(delayed):>10.1f} | {statistics.median(delayed):>12.1f}")
    print(f"\n  Δ mean = {statistics.mean(delayed) - statistics.mean(baseline):.1f} ms")
    print(f"  The ~2000 ms increase matches the injected delay because")
    print(f"  the synchronous call blocks the entire request pipeline.")
    print(f"  OrderService cannot return until Inventory responds.\n")

    # cleanup override file if it exists
    override = os.path.join(COMPOSE_DIR, "docker-compose.override.yml")
    if os.path.exists(override):
        os.remove(override)
