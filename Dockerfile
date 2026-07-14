# 用 Python 3.11+ 运行时
FROM python:3.11-slim

WORKDIR /app

# 复制项目文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt || true

# 缓存破坏层：每次构建强制复制最新文件
# 每次构建唯一值，强制刷新缓存
ARG BUILD_COMMIT=1784004831dd6_1784004498
RUN echo "Build: $BUILD_COMMIT"

COPY . .

# 数据目录
RUN mkdir -p /app/data

EXPOSE 5000
CMD ["python", "app.py"]
