import os

class Config:
    # Baza de date
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://scd:scd@db:5432/clinica')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Keycloak
    KEYCLOAK_URL = os.getenv('KEYCLOAK_URL', 'http://keycloak:8080')
    KEYCLOAK_REALM = os.getenv('KEYCLOAK_REALM', 'medical-clinica')

    # RabbitMQ
    RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'rabbitmq')
    RABBITMQ_QUEUE = 'appointments_queue'

    JWT_ALGORITHM = 'RS256'

    PROPAGATE_EXCEPTIONS = True