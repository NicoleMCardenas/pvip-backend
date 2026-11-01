# KAIRO — Backend

**Customer Intelligence & Post-Sale Management API**

The KAIRO backend is a Python-based REST API built with FastAPI. It provides the business logic, data persistence, authentication, authorization, and analytical capabilities supporting KAIRO's customer intelligence and post-sale management platform.

The project focuses on connecting operational customer data with business-oriented insights, retention analysis, customer experience monitoring, and revenue recovery.

## Technology Stack

| Technology | Version | Purpose |
|---|---|---|
| Python | 3.12 | Backend programming language |
| FastAPI | 0.128.8 | REST API framework |
| PostgreSQL | 16 | Relational database |
| SQLAlchemy | 2.0.49 | Database ORM |
| Alembic | 1.16.5 | Database migrations |
| Pydantic | 2.13.3 | Data validation |
| Uvicorn | 0.39.0 | ASGI application server |
| Pytest | 8.4.2 | Automated testing |
| HTTPX | 0.28.1 | HTTP client and testing support |

## Architecture

The backend follows a modular structure organized around business responsibilities.

```text
app/
├── analytics/
├── auth/
├── businesses/
├── clients/
├── core/
├── db/
├── models/
├── retention/
├── revenue_recovery/
├── schemas/
├── services/
├── staff/
├── surveys/
└── visits/
```

### Core Modules

**Authentication (`auth`)**

Handles account authentication and related security workflows, including staff invitation functionality.

**Business Management (`businesses`, `staff`, `services`)**

Supports business records, staff management, and service-related operations.

**Customer Operations (`clients`, `visits`)**

Manages customer information and visit records used throughout the post-sale workflow.

**Customer Experience (`surveys`)**

Supports satisfaction surveys and notification processing.

**Business Intelligence (`analytics`, `retention`, `revenue_recovery`)**

Provides analytical functionality related to customer experience, retention, and revenue recovery.

**Data and Configuration (`core`, `db`, `models`, `schemas`)**

Contains application configuration, database integration, ORM models, and data schemas.

## API Entry Point

The FastAPI application is initialized in:

```text
app/main.py
```

The application registers routers for authentication, staff invitations, businesses, clients, services, staff, visits, surveys, analytics, retention, and revenue recovery.

The root endpoint is:

```http
GET /
```

It returns:

```json
{
  "message": "PVIP Backend is running"
}
```

### Interactive API Documentation

When the backend is running locally, FastAPI provides interactive documentation at:

- Swagger UI: `http://localhost:8001/docs`
- ReDoc: `http://localhost:8001/redoc`
- OpenAPI schema: `http://localhost:8001/openapi.json`

## Local Development with Docker

KAIRO uses Docker Compose to coordinate the frontend, backend, PostgreSQL database, and notification worker.

The expected local directory structure is:

```text
pvip/
├── compose.yaml
├── pvip-backend/
└── pvip-frontend/
```

The Compose configuration is located in the parent `pvip` directory.

### Environment Configuration

The backend loads environment variables from:

```text
pvip-backend/.env
```

The Docker Compose configuration also requires `POSTGRES_PASSWORD` to be available for variable substitution.

Environment variables may include database connection details, authentication settings, email-provider credentials, and other application configuration.

**Never commit actual credentials or private environment files to version control.**

### Start the Application

From the parent `pvip` directory:

```bash
docker compose up -d --build
```

The backend is accessible locally at:

```text
http://localhost:8001
```

The PostgreSQL service uses a persistent Docker volume named `postgres_data`.

### Notification Worker

The notification worker is a separate Docker Compose service that runs:

```bash
python -m app.surveys.run_notification_worker
```

The current Compose configuration invokes the worker in a loop with a 60-second interval.

## Database Migrations

Database schema migrations are managed with Alembic.

Migration files are maintained in:

```text
alembic/versions/
```

The project includes migrations related to staff invitations, user activation status, and relationships between staff and user accounts.

Migration execution should follow the project's configured database environment and deployment process.

## Authentication and Authorization

The backend includes functionality for:

- Account authentication
- Password recovery
- Role-based access restrictions
- Business-level access control
- Staff invitations and account activation

Staff invitations use a token-based workflow with validation and expiration controls.

Email delivery depends on the configured provider and verified sender permissions.

## Automated Testing

The backend contains automated tests for several functional areas, including:

- Authentication and password recovery
- Role-based permissions
- Customer and visit workflows
- Surveys and email notifications
- Customer segmentation and analytics
- Retention and revenue recovery
- Staff invitations and concurrency scenarios

Tests are maintained in files following the `test_*.py` naming convention.

The project uses Pytest, alongside other test scripts. Execution requirements may vary depending on the test and its database or service dependencies.


## Public Demo and Deployment

KAIRO includes a publicly accessible demonstration environment:

https://kairo-ten-tau.vercel.app/login

Visitors can select **Explorar demo** to access the application without registering or providing credentials.

The backend provides:

```http
POST /auth/demo
```

This endpoint issues an authenticated access token for the predefined fictional demo business.

The demonstration environment contains fictional customer, visit, survey, retention, and revenue recovery records.

### Demo Data Protection

The backend enforces read-only access for the demo business.

Authenticated requests using POST, PUT, PATCH, or DELETE are rejected with HTTP 403 when they attempt to modify demo business data.

Public survey submissions and staff invitation acceptance are also restricted for the demo business.

Regular business accounts retain their existing permissions and functionality.

### Production Infrastructure

The public demonstration uses:

- **Render:** FastAPI backend hosting.
- **Supabase:** Managed PostgreSQL database.
- **Vercel:** Next.js frontend hosting.

The local Docker Compose environment remains available for development and testing.

## Development Status

KAIRO's core backend modules are implemented, tested across multiple workflows, and deployed as part of a public portfolio demonstration.

The frontend and backend have successfully completed their latest deployment and build checks.

Staff invitation workflows have been implemented and technically tested. The complete real-email invitation activation flow remains pending external verification because email delivery depends on the configured provider and verified sender permissions.

The public demo uses fictional data and is intended for professional evaluation and product exploration.

## Project Purpose

KAIRO demonstrates backend engineering applied to practical business challenges.

Its main areas of focus are:

**Backend Architecture · REST APIs · Relational Databases · Authentication · Customer Intelligence · Customer Experience · Retention · Revenue Recovery**

The project connects technical implementation with the business processes that influence customer relationships and post-sale performance.