# Imagen oficial que ya incluye Python 3.11 + Node.js 20 — sin instalación manual
FROM nikolaik/python-nodejs:python3.11-nodejs20

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
