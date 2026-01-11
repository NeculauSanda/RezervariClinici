import os

class Config:
    # BD
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://scd:scd@db:5432/clinica')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Keycloak
    KEYCLOAK_URL = os.getenv('KEYCLOAK_URL', 'http://keycloak:8080')
    KEYCLOAK_REALM = os.getenv('KEYCLOAK_REALM', 'medical-clinica')

    # SMTP
    SMTP_HOST = os.getenv('SMTP_HOST', 'mailhog')
    SMTP_PORT = int(os.getenv('SMTP_PORT', 1025))
    SMTP_FROM = os.getenv('SMTP_FROM', 'noreply@clinica.com') 

    # MinIO
    MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT', 'minio:9000')
    MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
    MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY', 'minioadmin')
    MINIO_BUCKET = 'confirmations'