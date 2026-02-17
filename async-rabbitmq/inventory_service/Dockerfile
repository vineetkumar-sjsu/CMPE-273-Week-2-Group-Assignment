FROM python:3.11-slim
WORKDIR /app
COPY async-rabbitmq/inventory_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY common/ ./common/
COPY async-rabbitmq/inventory_service/app.py .
CMD ["python", "app.py"]
