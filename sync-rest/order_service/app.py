import os
import time
import logging

import requests
from flask import Flask, request, jsonify

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common.ids import generate_order_id

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("order_service")

INVENTORY_URL = os.getenv("INVENTORY_URL", "http://inventory-service:5001")
NOTIFICATION_URL = os.getenv("NOTIFICATION_URL", "http://notification-service:5002")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "5"))

orders_db = {}


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "order_service"})


@app.route("/order", methods=["POST"])
def create_order():
    data = request.get_json(force=True)
    item = data.get("item", "unknown_item")
    qty = data.get("qty", 1)

    order_id = generate_order_id()
    start = time.time()
    logger.info(f"[{order_id}] received order: item={item} qty={qty}")

    # step 1 – call inventory synchronously
    try:
        inv_resp = requests.post(
            f"{INVENTORY_URL}/reserve",
            json={"order_id": order_id, "item": item, "qty": qty},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.Timeout:
        elapsed = time.time() - start
        logger.error(f"[{order_id}] inventory timed out after {elapsed:.2f}s")
        orders_db[order_id] = {"status": "failed", "reason": "inventory_timeout"}
        return jsonify({"order_id": order_id, "status": "failed",
                        "reason": "inventory_timeout", "latency_ms": int(elapsed * 1000)}), 504
    except requests.exceptions.ConnectionError:
        elapsed = time.time() - start
        logger.error(f"[{order_id}] inventory connection failed")
        orders_db[order_id] = {"status": "failed", "reason": "inventory_unavailable"}
        return jsonify({"order_id": order_id, "status": "failed",
                        "reason": "inventory_unavailable", "latency_ms": int(elapsed * 1000)}), 503

    if inv_resp.status_code != 200:
        elapsed = time.time() - start
        reason = inv_resp.json().get("reason", "reserve_failed")
        logger.warning(f"[{order_id}] inventory reserve failed: {reason}")
        orders_db[order_id] = {"status": "failed", "reason": reason}
        return jsonify({"order_id": order_id, "status": "failed",
                        "reason": reason, "latency_ms": int(elapsed * 1000)}), 422

    # step 2 – notify
    try:
        notif_resp = requests.post(
            f"{NOTIFICATION_URL}/send",
            json={"order_id": order_id, "item": item, "qty": qty, "message": "order confirmed"},
            timeout=REQUEST_TIMEOUT,
        )
        logger.info(f"[{order_id}] notification sent, status={notif_resp.status_code}")
    except Exception as e:
        logger.warning(f"[{order_id}] notification failed ({e}), order still confirmed")

    elapsed = time.time() - start
    orders_db[order_id] = {"status": "confirmed", "item": item, "qty": qty}
    logger.info(f"[{order_id}] confirmed in {elapsed:.2f}s")

    return jsonify({"order_id": order_id, "status": "confirmed",
                    "latency_ms": int(elapsed * 1000)}), 201


@app.route("/orders", methods=["GET"])
def list_orders():
    return jsonify(orders_db)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
