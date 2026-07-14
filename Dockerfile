FROM python:3.11-slim as builder
RUN echo "fresh-build-1784013837"
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt 2>/dev/null || true
COPY . .
EXPOSE 5000
CMD ["python", "app.py"]
