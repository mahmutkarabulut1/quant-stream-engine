FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY analyzer.py .
COPY dashboard.py .
# Default command (can be overridden by K8s)
CMD ["python", "analyzer.py"]
