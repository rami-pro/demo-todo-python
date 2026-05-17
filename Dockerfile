FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VENV_IN_PROJECT=false

WORKDIR /app

# System deps for psycopg2 and Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry==2.3.2

# Dependency layer (cached unless pyproject.toml changes)
COPY pyproject.toml ./
RUN poetry install --only main --no-root

COPY . .

# Collect static files (fails gracefully if DATABASE_URL is not set yet)
RUN DJANGO_SETTINGS_MODULE=config.settings.production \
    SECRET_KEY=build-time-dummy \
    DATABASE_URL=sqlite:///dummy.db \
    poetry run python manage.py collectstatic --noinput || true

EXPOSE 8000

CMD ["poetry", "run", "gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "60"]
