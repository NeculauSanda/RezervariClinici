import os
from datetime import timedelta

class Config:
    # Configurari pentru FLASK - baza de date - Keycloak - JWT

    # BD
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'postgresql://scd:scd@db:5432/clinica'
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # setari Keycloak 
    KEYCLOAK_URL = os.getenv('KEYCLOAK_URL', 'http://keycloak:8080')
    KEYCLOAK_REALM = os.getenv('KEYCLOAK_REALM', 'master')
    KEYCLOAK_CLIENT_ID = os.getenv('KEYCLOAK_CLIENT_ID', 'admin-cli')
    KEYCLOAK_CLIENT_SECRET = os.getenv('KEYCLOAK_CLIENT_SECRET', '')

    # JWT - algoritmul de criptare pt token-urile userilor + durata de viata a lui
    JWT_ALGORITHM = 'RS256'
    JWT_EXPIRATION = timedelta(minutes=60)

    PROPAGATE_EXCEPTIONS = True # pentru debug ca erorile sa se vada si sa fie propagate