FROM python:3.11-slim
WORKDIR /app
ARG CACHEBUST=$(date +%s)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt 2>/dev/null || true
COPY . .
EXPOSE 5000
CMD ["python", "app.py"]
