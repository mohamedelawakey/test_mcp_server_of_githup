FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python3","/app/server_github.py"]
