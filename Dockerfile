FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instalar SOLO procps (necesario para que app.py pueda controlar procesos)
RUN apt-get update && apt-get install -y \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Directorio de trabajo
WORKDIR /app

# Instalar dependencias python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir flask flask-socketio eventlet

# Copiar código
COPY . .

# Crear carpeta de datos
RUN mkdir -p /app/datos

# Puerto
EXPOSE 5000

# Comando
CMD ["python3", "app.py"]
