FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-chi-sim && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt || true
COPY . .
RUN mkdir -p /app/data
EXPOSE 5000
CMD ["python", "app.py"]
