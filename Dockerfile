# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Instala dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia código
COPY . .

# Variável de ambiente para evitar buffering
ENV PYTHONUNBUFFERED=1

# Comando para rodar
CMD ["python", "main.py"]