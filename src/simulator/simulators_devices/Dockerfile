FROM python:3.11-slim-bookworm

# Update base packages
RUN apt-get update && apt-get upgrade -y && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy the app code and pyproject info
COPY src/simulator /app/src/simulator
COPY pyproject.toml /app/
COPY poetry.lock /app/

# Install poetry and use it to install project deps
RUN pip install --no-cache-dir poetry
ENV POETRY_VIRTUALENVS_CREATE=false
RUN poetry install --no-root

# Environment variables
ENV PYTHONPATH=/app
ENV PYTHONPATH=/app/src
ENV TLS_CA_CERT=/certs/ca.crt

# Default fallback (compose file should override this)
CMD ["python", "src/simulator/simulators_devices/lock-01/run_device.py"]
