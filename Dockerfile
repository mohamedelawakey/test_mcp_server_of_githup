FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the code
COPY . .

# Variables (passed as secrets from the platform)
# ENV LOG_LEVEL=INFO
# ENV LOG_FILE=/var/log/mcp.log

# Run as an SSE server
EXPOSE 8000

RUN ln -sf /usr/local/bin/python3 /usr/local/bin/python
# If you modified the code above
CMD ["python", "server_github.py"]
# Or use the CLI instead of the previous line:
# CMD ["fastmcp", "run", "server_github.py:mcp", "--transport", "sse", "--host", "0.0.0.0", "--port", "8000", "--path", "/mcp"]
