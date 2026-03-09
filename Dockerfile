# Étape 1 : Construction (Builder)
FROM python:3.12.4-slim as builder

RUN pip install poetry==2.3.2

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Copie uniquement les fichiers de dépendances pour profiter du cache Docker
COPY pyproject.toml poetry.lock ./

RUN poetry install --no-root --without dev

# Étape 2 : Runtime
FROM python:3.12.4-slim as runtime

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /app

# On récupère l'environnement virtuel de l'étape précédente
COPY --from=builder /app/.venv /app/.venv
COPY . .

# Exposition du port FastAPI
EXPOSE 8000

# Commande de lancement
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]