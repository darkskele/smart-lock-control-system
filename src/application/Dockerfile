FROM python:3.11-slim-bookworm

WORKDIR /app

# Copy just the application CLI code
COPY src/application /app/src/application

# Poetry dependencies
COPY pyproject.toml poetry.lock /app/

# Install dependencies
RUN pip install --no-cache-dir poetry
ENV POETRY_VIRTUALENVS_CREATE=false
RUN poetry install --no-root

ENV PYTHONPATH=/app/src

# Run main
CMD ["python", "src/application/main.py"]
