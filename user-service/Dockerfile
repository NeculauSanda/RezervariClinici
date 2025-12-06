FROM python:3.11-slim

WORKDIR /app

# instaleza tot ce e nevoie pt sistem
RUN apt-get update && apt-get install -y gcc postgresql-client && rm -rf /var/lib/apt/lists/*

# instaleza toate pachetele
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copiaza codul
COPY . .

# port + comada de pornire 
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "app:create_app()"]