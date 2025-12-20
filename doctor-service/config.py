import os
from datetime import timedelta

class Config:

    # Conectare la aceeasi BD
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'postgresql://scd:scd@db:5432/clinica'
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Setari Keycloak
    KEYCLOAK_URL = os.getenv('KEYCLOAK_URL', 'http://keycloak:8080')
    KEYCLOAK_REALM = os.getenv('KEYCLOAK_REALM', 'medical-clinica')
    KEYCLOAK_CLIENT_ID = os.getenv('KEYCLOAK_CLIENT_ID', 'medical-app')

    # JWT algoritmul de criptare
    JWT_ALGORITHM = 'RS256'

    PROPAGATE_EXCEPTIONS = True