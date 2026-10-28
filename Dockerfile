FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libusb-1.0-0 \
    libhidapi-libusb0 \
    curl \
    gcc \
    libc6-dev \
    make \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=UTC

WORKDIR /app
# "energy-cost" is a named build context; docker-compose.yml points it at ../energy-cost.
COPY --from=energy-cost pyproject.toml /opt/energy-cost/pyproject.toml
COPY --from=energy-cost src /opt/energy-cost/src
COPY pyproject.toml /app/pyproject.toml
COPY src /app/src
RUN pip install --no-cache-dir /opt/energy-cost ".[device]"

VOLUME ["/data"]
EXPOSE 5000
CMD ["python", "-m", "psu_meter.main"]
