FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    libusb-1.0-0 \
    libhidapi-libusb0 \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN pip install flask hidapi

COPY app.py /app.py

CMD ["python", "/app/app.py"]
