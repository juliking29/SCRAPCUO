# Base image con Python
FROM python:3.12-slim

# Evita preguntas durante instalaciones
ENV DEBIAN_FRONTEND=noninteractive

# Instala dependencias del sistema necesarias
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libnspr4 \
    libnss3 \
    libxss1 \
    libxcomposite1 \
    libxrandr2 \
    libu2f-udev \
    libvulkan1 \
    libgbm1 \
    libgtk-3-0 \
    libdrm2 \
    libx11-xcb1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Instala Google Chrome
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt-get update && apt-get install -y ./google-chrome-stable_current_amd64.deb && \
    rm google-chrome-stable_current_amd64.deb

# Instala ChromeDriver automáticamente usando webdriver-manager
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia tu app
COPY . /app
WORKDIR /app

# Expone el puerto
EXPOSE 8001

# Comando para lanzar el servidor
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
