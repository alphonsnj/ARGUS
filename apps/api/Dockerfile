FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install --no-install-recommends -y poppler-utils tesseract-ocr \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system argus \
    && adduser --system --ingroup argus argus
COPY pyproject.toml ./
COPY requirements.lock ./
RUN pip install --upgrade pip "setuptools>=78.1.1" \
    && pip install --require-hashes -r requirements.lock
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./
RUN pip install --no-deps . && chown -R argus:argus /app
USER argus
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
