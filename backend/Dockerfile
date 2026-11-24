FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu && pip install -r requirements.txt
COPY . .
RUN useradd -m allocate && mkdir -p /private/uploads /models && chown -R allocate:allocate /app /private /models
USER allocate
CMD ["sh", "-c", "alembic upgrade head && python -m uvicorn app.server:app --host 0.0.0.0 --port 8000"]
