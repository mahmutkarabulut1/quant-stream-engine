FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY streamer.py .
COPY dashboard.py .
COPY prediction-engine/ ./prediction-engine/
EXPOSE 8501
