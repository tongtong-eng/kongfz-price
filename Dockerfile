FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 60 -r requirements.txt 2>/dev/null || true
COPY . .
EXPOSE 5000
CMD ["python", "app.py"]
