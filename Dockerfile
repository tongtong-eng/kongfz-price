# 用 Python 3.11+ 运行时
FROM python:3.11-slim

WORKDIR /app

# 安装 Tesseract OCR（含中文语言包）
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    tesseract-ocr-chi-tra \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt || true

COPY . .

# 数据目录
RUN mkdir -p /app/data

EXPOSE 5000
CMD ["python", "app.py"]
