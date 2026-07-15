FROM python:3.11-slim

# 避免 pip 交互 + 缓存
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 先复制依赖文件（利用 Docker 缓存层）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 再复制代码（排除 .git 等，由 .dockerignore 控制）
COPY . .

# 健康检查（Railway 会定期调用）
HEALTHCHECK --interval=30s --timeout=5s --start-period=8s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-5000}/api/health', timeout=3)" || exit 1

EXPOSE 5000

CMD ["python", "app.py"]
