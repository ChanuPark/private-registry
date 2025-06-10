FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN apt-get update && \
    apt-get install -y apache2-utils && \
    pip install --no-cache-dir -r requirements.txt && \
    rm -rf /var/lib/apt/lists/*

COPY . .

CMD ["python", "app.py"]