FROM python:3.12-slim

WORKDIR /app

ARG BUILD_ID=2025-10-27-01
ENV BUILD_ID=$BUILD_ID

# Install dependencies
COPY requirements.txt .
RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose port
EXPOSE 8000

# Set environment variables for host binding
ENV HOST=0.0.0.0
ENV PORT=8000

# Health check - just check if port is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('localhost', 8000)); s.close()" || exit 1

# Run the server directly with python (no fastmcp CLI needed)
# server_github.py
CMD ["python", "/app/server_github.py"]
