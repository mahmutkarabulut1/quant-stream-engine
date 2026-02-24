FROM python:3.11-slim
WORKDIR /app
# Sadece requirements kopyala ve kur (Kod değişse bile bu katman cache'ten gelir)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Kodları en son kopyala
COPY . . 
EXPOSE 8501
