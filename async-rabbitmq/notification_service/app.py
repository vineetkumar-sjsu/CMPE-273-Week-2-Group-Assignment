import os
import json
import time
import logging

import pika

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("notification_service")

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))


def get_rabbit_connection():
    for attempt in range(20):
        try:
            params = pika.ConnectionParameters(
                host=RABBITMQ_HOST, port=RABBITMQ_PORT,
                heartbeat=600,
                connection_attempts=3, retry_delay=2,
            )
            return pika.BlockingConnection(params)
        except pika.exceptions.AMQPConnectionError:
            logger.warning(f"rabbitmq not ready, retrying ({attempt+1}/20)...")
            time.sleep(3)
    raise RuntimeError("could not connect to rabbitmq")


notifications_sent = []


def on_inventory_event(ch, method, properties, body):
    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        logger.error(f"malformed event, ignoring: {body[:200]}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    event_type = event.get("event_type", "")
    order_id = event.get("order_id", "unknown")

    if event_type == "InventoryReserved":
        item = event.get("item", "")
        qty = event.get("qty", 0)
        msg = f"Order {order_id} confirmed: {qty}x {item} reserved."
        logger.info(f"NOTIFICATION >> {msg}")
        notifications_sent.append({"order_id": order_id, "message": msg, "time": time.time()})
    elif event_type == "InventoryFailed":
        reason = event.get("reason", "unknown")
        msg = f"Order {order_id} failed: {reason}."
        logger.info(f"NOTIFICATION >> {msg}")
        notifications_sent.append({"order_id": order_id, "message": msg, "time": time.time()})
    else:
        logger.debug(f"ignoring event type: {event_type}")

    ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    conn = get_rabbit_connection()
    ch = conn.channel()

    ch.exchange_declare(exchange="inventory_events", exchange_type="fanout", durable=True)
    ch.queue_declare(queue="notification_events", durable=True)
    ch.queue_bind(exchange="inventory_events", queue="notification_events")

    ch.basic_qos(prefetch_count=1)
    ch.basic_consume(queue="notification_events", on_message_callback=on_inventory_event)

    logger.info("notification_service listening for inventory events...")
    ch.start_consuming()


if __name__ == "__main__":
    main()
