# 用 Python 3.11+ 运行时
FROM python:3.11-slim

WORKDIR /app

# 复制项目文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt || true

COPY . .

# 数据目录
RUN mkdir -p /app/data

EXPOSE 5000
CMD ["python", "app.py"]
