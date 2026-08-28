FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies needed for OpenCV, PyTorch, and general build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install PyTorch CPU first to leverage Docker cache
# We use the extra index url for CPU-only versions to keep the image small
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create models directory to pre-cache FaceNet weights
RUN mkdir -p /app/models
ENV TORCH_HOME=/app/models

# Pre-download the FaceNet model during build to save time on startup
RUN python -c "from facenet_pytorch import MTCNN, InceptionResnetV1; InceptionResnetV1(pretrained='vggface2').eval()"

# Copy application code
COPY . .

# Expose port (Render sets $PORT dynamically)
EXPOSE 8000

# Start server
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
