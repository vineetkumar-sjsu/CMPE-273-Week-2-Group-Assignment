# Broker Configuration

The RabbitMQ broker is configured via the `docker-compose.yml` in the parent directory. It uses the official `rabbitmq:3.12-management` image with default credentials (`guest/guest`).

Key configuration:

- **AMQP port:** 5672 (mapped to host)
- **Management UI:** 15672 (mapped to host, accessible at http://localhost:15672)
- **Exchanges:**
  - `orders` (fanout, durable) – carries OrderPlaced events
  - `inventory_events` (fanout, durable) – carries InventoryReserved / InventoryFailed events
  - `orders_dlx` (fanout, durable) – dead-letter exchange for poison messages
- **Queues:**
  - `inventory_orders` – bound to `orders` exchange, with DLX configured
  - `notification_events` – bound to `inventory_events` exchange
  - `order_status_updates` – bound to `inventory_events` exchange
  - `orders_dlq` – bound to `orders_dlx` for dead-letter messages
