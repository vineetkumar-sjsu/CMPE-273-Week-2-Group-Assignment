import os
import json
import time
import logging
import threading

import pika
from flask import Flask, request, jsonify

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common.ids import generate_order_id, generate_event_id

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("order_service")

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))

orders_db = {}


def get_rabbit_connection():
    """Try connecting to RabbitMQ with retries."""
    for attempt in range(15):
        try:
            params = pika.ConnectionParameters(
                host=RABBITMQ_HOST, port=RABBITMQ_PORT,
                heartbeat=600,
                connection_attempts=3, retry_delay=2,
            )
            return pika.BlockingConnection(params)
        except pika.exceptions.AMQPConnectionError:
            logger.warning(f"rabbitmq not ready, retrying ({attempt+1}/15)...")
            time.sleep(2)
    raise RuntimeError("could not connect to rabbitmq")


def publish_order_placed(order_id, item, qty):
    conn = get_rabbit_connection()
    ch = conn.channel()
    ch.exchange_declare(exchange="orders", exchange_type="fanout", durable=True)

    event = {
        "event_id": generate_event_id(),
        "event_type": "OrderPlaced",
        "order_id": order_id,
        "item": item,
        "qty": qty,
        "timestamp": time.time(),
    }
    ch.basic_publish(
        exchange="orders",
        routing_key="",
        body=json.dumps(event),
        properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
    )
    logger.info(f"[{order_id}] published OrderPlaced (event_id={event['event_id']})")
    conn.close()


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "order_service"})


@app.route("/order", methods=["POST"])
def create_order():
    data = request.get_json(force=True)
    item = data.get("item", "unknown_item")
    qty = data.get("qty", 1)

    order_id = generate_order_id()
    orders_db[order_id] = {"status": "pending", "item": item, "qty": qty}
    logger.info(f"[{order_id}] stored locally, publishing event...")

    try:
        publish_order_placed(order_id, item, qty)
    except Exception as e:
        logger.error(f"[{order_id}] failed to publish: {e}")
        orders_db[order_id]["status"] = "publish_failed"
        return jsonify({"order_id": order_id, "status": "publish_failed"}), 500

    return jsonify({"order_id": order_id, "status": "pending"}), 202


@app.route("/orders", methods=["GET"])
def list_orders():
    return jsonify(orders_db)


# background listener for status updates from inventory
def listen_for_status_updates():
    time.sleep(5)  # let rabbitmq boot
    conn = get_rabbit_connection()
    ch = conn.channel()
    ch.exchange_declare(exchange="inventory_events", exchange_type="fanout", durable=True)
    result = ch.queue_declare(queue="order_status_updates", durable=True)
    ch.queue_bind(exchange="inventory_events", queue="order_status_updates")

    def callback(ch, method, properties, body):
        try:
            event = json.loads(body)
            oid = event.get("order_id", "")
            etype = event.get("event_type", "")
            if oid in orders_db:
                if etype == "InventoryReserved":
                    orders_db[oid]["status"] = "confirmed"
                elif etype == "InventoryFailed":
                    orders_db[oid]["status"] = "failed"
                    orders_db[oid]["reason"] = event.get("reason", "unknown")
                logger.info(f"[{oid}] status updated to {orders_db[oid]['status']}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logger.error(f"status update error: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    ch.basic_consume(queue="order_status_updates", on_message_callback=callback)
    logger.info("listening for inventory status updates...")
    ch.start_consuming()


if __name__ == "__main__":
    t = threading.Thread(target=listen_for_status_updates, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5000)
