FROM python:3.11-slim
WORKDIR /app
COPY requirements-runtime.txt ./
RUN apt-get update && apt-get install -y \
    build-essential \
    fonts-nanum \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    zlib1g-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements-runtime.txt
COPY app ./app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
