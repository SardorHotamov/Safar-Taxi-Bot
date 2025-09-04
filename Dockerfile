FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render uchun default portni belgilash
ENV PORT=10000
CMD ["python3", "main.py"]