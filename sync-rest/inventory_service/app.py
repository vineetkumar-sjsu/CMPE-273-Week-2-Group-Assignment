import os
import time
import logging

from flask import Flask, request, jsonify

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("inventory_service")

SIMULATED_DELAY = float(os.getenv("SIMULATED_DELAY", "0"))
FORCE_FAILURE = os.getenv("FORCE_FAILURE", "false").lower() == "true"

# simple in-memory stock
stock = {
    "burger": 100,
    "pizza": 100,
    "soda": 200,
    "fries": 150,
    "salad": 80,
}


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "inventory_service",
                    "delay": SIMULATED_DELAY, "force_failure": FORCE_FAILURE})


@app.route("/reserve", methods=["POST"])
def reserve():
    if FORCE_FAILURE:
        logger.warning("forced failure mode is ON")
        return jsonify({"reserved": False, "reason": "service_error"}), 500

    if SIMULATED_DELAY > 0:
        logger.info(f"sleeping {SIMULATED_DELAY}s (simulated delay)")
        time.sleep(SIMULATED_DELAY)

    data = request.get_json(force=True)
    order_id = data.get("order_id", "n/a")
    item = data.get("item", "")
    qty = data.get("qty", 1)

    if item not in stock:
        logger.warning(f"[{order_id}] item '{item}' not found")
        return jsonify({"reserved": False, "reason": "item_not_found"}), 404

    if stock[item] < qty:
        logger.warning(f"[{order_id}] not enough stock for '{item}' (have={stock[item]}, want={qty})")
        return jsonify({"reserved": False, "reason": "insufficient_stock"}), 409

    stock[item] -= qty
    logger.info(f"[{order_id}] reserved {qty}x {item}, remaining={stock[item]}")
    return jsonify({"reserved": True, "order_id": order_id, "item": item,
                    "qty": qty, "remaining": stock[item]}), 200


@app.route("/stock", methods=["GET"])
def get_stock():
    return jsonify(stock)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
