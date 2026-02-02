# Clinic appointment reservation system

A modern microservices based application for managing clinic appointments, doctor schedules, and user notifications.

## Overview

This is a distributed system built with Flask microservices, Docker, PostgreSQL, and Keycloak for authentication. It enables patients to book medical appointments, manage doctor schedules, and receive email notifications.

## Architecture

The application consists of four main microservices:

### 1. **User service** (`user-service/`)
- Manages user profiles and account information
- User registration and authentication support
- Integration with Keycloak for identity management

### 2. **Doctor service** (`doctor-service/`)
- Manages doctor profiles and specializations
- Doctor schedule management
- Availability tracking for appointments

### 3. **Appointment service** (`appointment-service/`)
- Core booking system for clinic appointments
- Appointment CRUD operations
- Appointment reminders through background workers
- Event-driven architecture

### 4. **Notification service** (`notification-service/`)
- Email notification handling
- PDF document generation
- MinIO integration for file storage
- Background task processing

## Technology stack

- **Backend framework**: Flask (Python)
- **Container orchestration**: Docker & Docker Swarm
- **Database**: PostgreSQL
- **Authentication**: Keycloak
- **Message queue**: Celery (for background tasks)
- **File storage**: MinIO
- **API communication**: RESTful APIs

## Prerequisites

- Docker and Docker compose
- Python 3.8+
- PostgreSQL (handled by Docker)
- Keycloak (handled by Docker)

## Getting started

### 1. Start the application

```bash
docker-compose up -d
```

This will:
- Initialize all microservices
- Set up the PostgreSQL database
- Configure Keycloak authentication
- Create Docker images (first run may take a few minutes)
- Start all services

### 2. Initialize the database

The database initialization scripts are located in `db/`:
- `0-init-keycloak.sh` - Keycloak setup
- `1-init-bd.sql` - Database schema creation

These run automatically on first startup.

### 3. Access the services

- **Keycloak (Authentication)**: http://localhost:8080
- **Appointment Service**: http://localhost:5000
- **Doctor Service**: http://localhost:5001
- **User Service**: http://localhost:5002
- **Notification Service**: http://localhost:5003

## Running tests

Run the automated test suite:

```bash
python3 test.py
```

### Test flow:

1. Docker initialization and image creation (may take a few moments)
2. Application startup - waiting for all services and database to be ready
3. Test execution begins after obtaining authentication tokens
4. Test results summary - passed/failed count
5. Manual cleanup required:
   - Stop the Docker Swarm stack
   - Exit Docker Swarm mode
   - Remove Docker images
   - Clean up volumes

## Configuration

Each service has a `config.py` file with environment-specific settings:

- `app.py` - Main Flask application
- `config.py` - Service configuration (database, authentication, etc.)
- `requirements.txt` - Python dependencies
- `Dockerfile` - Container configuration


## Deployment

### Docker compose (development)
```bash
docker-compose up -d
```

### Docker swarm (production)
```bash
docker-compose -f docker-compose.swarm.yml up -d
```


## Troubleshooting

**Check services?**
- Check Docker daemon is running
- Verify all required ports are available
- Check logs: `docker-compose logs [service-name]`


## Project structure

```
.
├── appointment-service/  # Appointment booking service
├── doctor-service/      # Doctor management service
├── user-service/        # User management service
├── notification-service/ # Email & notification service
├── keycloak/            # Authentication configuration
├── db/                  # Database initialization scripts
├── docker-compose.yml   # Development compose file
├── docker-compose.swarm.yml # Production compose file
├── test.py              # Test suite
└── test.sh              # Test script - run manual test
```
