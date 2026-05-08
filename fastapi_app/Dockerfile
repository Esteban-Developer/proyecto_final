FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app/fastapi_app

# Copia el repositorio completo para mantener acceso a assets estáticos en /app
COPY . /app

RUN pip install --no-cache-dir -r /app/fastapi_app/requirements.txt

EXPOSE 8000

