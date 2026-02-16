FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY analyzer.py .
COPY dashboard.py .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh
EXPOSE 8501
CMD ["/bin/bash", "entrypoint.sh"]
