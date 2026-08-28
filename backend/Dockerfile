# Production Dockerfile for EventLens AI Backend
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

WORKDIR /app

# Install minimal OS dependencies for OpenCV headless and networking
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install CPU-optimized Python dependencies
COPY requirements.txt requirements-cpu.txt /app/
RUN pip install --no-cache-dir -U pip setuptools wheel && \
    pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Pre-download and cache FaceNet (VGGFace2) weights into the Docker layer
RUN python -c "from facenet_pytorch import InceptionResnetV1; InceptionResnetV1(pretrained='vggface2').eval()"

# Copy backend application source code
COPY . /app/

# Ensure storage directories exist
RUN mkdir -p /app/storage_data/raw /app/storage_data/thumbnails

EXPOSE 8000

# Run with dynamic PORT support for Render, Railway, Fly.io, or VPS
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
