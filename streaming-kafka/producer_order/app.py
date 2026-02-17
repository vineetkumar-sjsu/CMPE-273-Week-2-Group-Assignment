import os
import json
import time
import logging
import random

from flask import Flask, request, jsonify
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common.ids import generate_order_id, generate_event_id

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("producer_order")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
ORDER_TOPIC = "OrderEvents"

ITEMS = ["burger", "pizza", "soda", "fries", "salad"]

producer = None


def get_producer():
    global producer
    if producer is not None:
        return producer
    for attempt in range(20):
        try:
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                acks="all",
                retries=3,
            )
            logger.info("kafka producer connected")
            return producer
        except NoBrokersAvailable:
            logger.warning(f"kafka not ready, retrying ({attempt+1}/20)...")
            time.sleep(3)
    raise RuntimeError("could not connect to kafka")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "producer_order"})


@app.route("/order", methods=["POST"])
def create_order():
    data = request.get_json(force=True)
    item = data.get("item", random.choice(ITEMS))
    qty = data.get("qty", 1)
    # allow tests to inject failures
    force_fail = data.get("force_fail", False)

    order_id = generate_order_id()
    event = {
        "event_id": generate_event_id(),
        "event_type": "OrderPlaced",
        "order_id": order_id,
        "item": item,
        "qty": qty,
        "force_fail": force_fail,
        "timestamp": time.time(),
    }

    p = get_producer()
    future = p.send(ORDER_TOPIC, value=event)
    future.get(timeout=10)  # block until ack
    logger.info(f"[{order_id}] published OrderPlaced to {ORDER_TOPIC}")

    return jsonify({"order_id": order_id, "status": "published"}), 202


@app.route("/bulk", methods=["POST"])
def bulk_orders():
    """Publish many orders at once for load testing."""
    data = request.get_json(force=True)
    count = data.get("count", 100)
    fail_rate = data.get("fail_rate", 0.1)  # 10% failure injection

    p = get_producer()
    published = 0
    for i in range(count):
        item = random.choice(ITEMS)
        force_fail = random.random() < fail_rate
        event = {
            "event_id": generate_event_id(),
            "event_type": "OrderPlaced",
            "order_id": generate_order_id(),
            "item": item,
            "qty": random.randint(1, 3),
            "force_fail": force_fail,
            "timestamp": time.time(),
        }
        p.send(ORDER_TOPIC, value=event)
        published += 1

    p.flush()
    logger.info(f"bulk published {published} events")
    return jsonify({"published": published, "fail_rate": fail_rate}), 202


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
