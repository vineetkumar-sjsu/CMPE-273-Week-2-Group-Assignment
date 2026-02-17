FROM python:3.11-slim
WORKDIR /app
COPY streaming-kafka/producer_order/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY common/ ./common/
COPY streaming-kafka/producer_order/app.py .
EXPOSE 5000
CMD ["python", "app.py"]
