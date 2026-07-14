FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt || true

# 复制所有项目文件（无缓存）
COPY . .

# 确保数据目录
RUN mkdir -p /app/data

# 构建版本标记
RUN echo "Deploy version: 2026-07-14 06:38:05 UTC"

EXPOSE 5000
CMD ["python", "app.py"]
