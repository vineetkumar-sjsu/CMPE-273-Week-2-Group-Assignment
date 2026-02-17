FROM python:3.11-slim
WORKDIR /app
COPY sync-rest/inventory_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY sync-rest/inventory_service/app.py .
EXPOSE 5001
CMD ["python", "app.py"]
