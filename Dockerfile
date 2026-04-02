FROM python:3.11-slim

# Instalar Node.js 20 junto con Python
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Dependencias Node.js
COPY package.json .
RUN npm install

# Código fuente
COPY . .

CMD ["bash", "start.sh"]
