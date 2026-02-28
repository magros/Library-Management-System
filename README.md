# 📚 Library Management System API

A full-featured RESTful API for managing a library system, built with modern Python technologies. Members can borrow books from different library branches, librarians manage inventory and loans, and administrators have full system control.

## 📋 Table of Contents

- [Technology Stack](#technology-stack)
- [Features](#features)
- [Project Structure](#project-structure)
- [Setup Instructions](#setup-instructions)
  - [Docker Setup (Recommended)](#docker-setup-recommended)
  - [Local Setup](#local-setup)
- [Environment Variables](#environment-variables)
- [Database Migrations](#database-migrations)
- [API Documentation](#api-documentation)
- [API Endpoints](#api-endpoints)
- [User Roles & Permissions](#user-roles--permissions)
- [Loan Status Flow](#loan-status-flow)
- [Testing](#testing)
- [Logging](#logging)
- [Built-in Admin Account](#built-in-admin-account)
- [Contributing](#contributing)
- [License](#license)

## 🛠 Technology Stack

| Technology       | Version / Details               |
|------------------|---------------------------------|
| **Language**     | Python 3.11+                    |
| **Framework**    | FastAPI 0.115                   |
| **Database**     | PostgreSQL 15+                  |
| **ORM**          | SQLAlchemy 2.0+ (async)        |
| **Migrations**   | Alembic 1.13                    |
| **Auth**         | JWT (python-jose) + bcrypt      |
| **Validation**   | Pydantic v2 + email-validator   |
| **Testing**      | Pytest + httpx + pytest-asyncio |
| **Containerization** | Docker & Docker Compose     |
| **Logging**      | Python logging (structured/JSON)|

## ✨ Features

- **JWT Authentication** – Register, login, and logout with Bearer token authentication
- **Role-Based Access Control (RBAC)** – Three roles: Member, Librarian, Administrator
- **Library Branch Management** – CRUD operations for physical branch locations
- **Book Catalog** – Full book management with search, filtering, and pagination
- **Loan Workflow** – Complete borrow/return lifecycle with status tracking
- **Overdue Detection** – Automatic background job to mark overdue loans and calculate late fees
- **Structured Logging** – JSON-formatted logs with request tracing
- **API Documentation** – Interactive Swagger UI and ReDoc
- **Dockerized** – Full Docker Compose setup with PostgreSQL and optional PgAdmin

## 📁 Project Structure

```
library-management-api/
├── alembic/                    # Database migrations
│   ├── versions/               # Migration files
│   └── env.py
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/      # API route handlers
│   │       │   ├── auth.py     # Authentication endpoints
│   │       │   ├── users.py    # User management endpoints
│   │       │   ├── branches.py # Branch management endpoints
│   │       │   ├── books.py    # Book catalog endpoints
│   │       │   └── loans.py    # Loan workflow endpoints
│   │       └── dependencies.py # Shared dependencies (auth, DB session)
│   ├── core/
│   │   ├── config.py           # Application settings (pydantic-settings)
│   │   ├── security.py         # JWT & password hashing utilities
│   │   └── logging.py          # Structured logging setup
│   ├── db/
│   │   ├── models.py           # SQLAlchemy ORM models
│   │   └── session.py          # Async database session factory
│   ├── schemas/                # Pydantic request/response schemas
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── branch.py
│   │   ├── book.py
│   │   └── loan.py
│   ├── services/               # Business logic layer
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── book.py
│   │   ├── branch.py
│   │   ├── loan.py
│   │   └── overdue.py
│   └── main.py                 # FastAPI application entry point
├── tests/
│   ├── unit/                   # Unit tests
│   └── functional/             # Functional/integration tests
├── docs/
│   └── openapi.json            # Exported OpenAPI specification
├── scripts/
│   └── export_openapi.py       # Script to export OpenAPI spec
├── .env                        # Environment variables (not committed)
├── alembic.ini                 # Alembic configuration
├── docker-compose.yml          # Docker Compose services
├── Dockerfile                  # Application container image
├── pytest.ini                  # Pytest configuration
├── requirements.txt            # Python dependencies
└── README.md
```

## 🚀 Setup Instructions

### Docker Setup (Recommended)

1. **Clone the repository:**

   ```bash
   git clone git@github.com:magros/Library-Management-System.git
   cd Library-Management-System
   ```

2. **Create a `.env` file** (or copy from example):

   ```bash
   cp .env.example .env
   ```

   Adjust the values as needed (see [Environment Variables](#environment-variables)).

3. **Build and start the services:**

   ```bash
   docker compose up --build -d
   ```

   This starts:
   - **API** on `http://localhost:8000`
   - **PostgreSQL** on `localhost:5432`

4. **Run database migrations:**

   ```bash
   docker compose exec api alembic upgrade head
   ```

5. **(Optional) Start PgAdmin:**

   ```bash
   docker compose --profile tools up -d pgadmin
   ```

   Access PgAdmin at `http://localhost:5050` (login: `admin@admin.com` / `admin`).

6. **Verify the API is running:**

   ```bash
   curl http://localhost:8000/health
   ```

   Expected response:
   ```json
   {"status": "healthy", "version": "1.0.0"}
   ```

### Local Setup

1. **Prerequisites:**
   - Python 3.11+
   - PostgreSQL 15+ running locally

2. **Create a virtual environment:**

   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # venv\Scripts\activate   # Windows
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**

   Create a `.env` file in the project root:

   ```env
   DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/library_db
   JWT_SECRET_KEY=your-secret-key-here
   LOG_LEVEL=INFO
   ```

5. **Run database migrations:**

   ```bash
   alembic upgrade head
   ```

6. **Start the development server:**

   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

## ⚙️ Environment Variables

| Variable                         | Description                              | Default                                                        |
|----------------------------------|------------------------------------------|----------------------------------------------------------------|
| `DATABASE_URL`                   | PostgreSQL connection string (async)     | `postgresql+asyncpg://postgres:postgres@db:5432/library_db`    |
| `TEST_DATABASE_URL`              | Test database connection string          | `postgresql+asyncpg://postgres:postgres@db:5432/library_test_db` |
| `JWT_SECRET_KEY`                 | Secret key for JWT token signing         | `change-me-to-a-random-secret-key-in-production`               |
| `JWT_ALGORITHM`                  | JWT signing algorithm                    | `HS256`                                                        |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`| JWT token expiration time (minutes)      | `30`                                                           |
| `ADMIN_EMAIL`                    | Built-in admin account email             | `admin@library.com`                                            |
| `ADMIN_PASSWORD`                 | Built-in admin account password          | `admin123456`                                                  |
| `LOG_LEVEL`                      | Application log level                    | `INFO`                                                         |
| `OVERDUE_CHECK_INTERVAL`         | Overdue checker interval in seconds      | `86400` (24 hours)                                             |
| `DEBUG`                          | Enable debug mode                        | `False`                                                        |

> ⚠️ **Important**: Change `JWT_SECRET_KEY` and `ADMIN_PASSWORD` to strong, unique values in production.

## 🗄 Database Migrations

This project uses **Alembic** for database schema management.

```bash
# Apply all migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Generate a new migration after model changes
alembic revision --autogenerate -m "description of changes"

# View migration history
alembic history
```

When using Docker:
```bash
docker compose exec api alembic upgrade head
```

## 📖 API Documentation

Once the application is running, interactive API documentation is available at:

| Tool         | URL                              |
|--------------|----------------------------------|
| **Swagger UI** | http://localhost:8000/docs      |
| **ReDoc**      | http://localhost:8000/redoc     |
| **OpenAPI JSON** | http://localhost:8000/openapi.json |

The OpenAPI spec can be imported into **Postman** or **Insomnia** for manual API testing.

## 🔗 API Endpoints

### Authentication
| Method | Endpoint                    | Description             | Auth Required |
|--------|-----------------------------|-------------------------|:-------------:|
| POST   | `/api/v1/auth/register`     | Register a new user     | ❌            |
| POST   | `/api/v1/auth/login`        | Login and get JWT token | ❌            |
| POST   | `/api/v1/auth/logout`       | Logout (invalidate token)| ✅           |

### Users (Admin only)
| Method | Endpoint              | Description            | Auth Required |
|--------|-----------------------|------------------------|:-------------:|
| GET    | `/api/v1/users`       | List all users         | ✅ Admin      |
| GET    | `/api/v1/users/{id}`  | Get user details       | ✅ Admin      |
| PUT    | `/api/v1/users/{id}`  | Update user            | ✅ Admin      |
| DELETE | `/api/v1/users/{id}`  | Delete user            | ✅ Admin      |

### Library Branches
| Method | Endpoint                 | Description          | Auth Required          |
|--------|--------------------------|----------------------|:----------------------:|
| GET    | `/api/v1/branches`       | List all branches    | ✅ Any                 |
| POST   | `/api/v1/branches`       | Create branch        | ✅ Librarian/Admin     |
| GET    | `/api/v1/branches/{id}`  | Get branch details   | ✅ Any                 |
| PUT    | `/api/v1/branches/{id}`  | Update branch        | ✅ Librarian/Admin     |
| DELETE | `/api/v1/branches/{id}`  | Delete branch        | ✅ Admin               |

### Books
| Method | Endpoint              | Description                    | Auth Required          |
|--------|-----------------------|--------------------------------|:----------------------:|
| GET    | `/api/v1/books`       | List books (filter, paginate)  | ✅ Any                 |
| POST   | `/api/v1/books`       | Create book                    | ✅ Librarian/Admin     |
| GET    | `/api/v1/books/{id}`  | Get book details               | ✅ Any                 |
| PUT    | `/api/v1/books/{id}`  | Update book                    | ✅ Librarian/Admin     |
| DELETE | `/api/v1/books/{id}`  | Delete book                    | ✅ Admin               |

### Loans
| Method | Endpoint                       | Description                | Auth Required          |
|--------|--------------------------------|----------------------------|:----------------------:|
| GET    | `/api/v1/loans`                | List loans (by role)       | ✅ Any                 |
| POST   | `/api/v1/loans`                | Request a loan             | ✅ Member              |
| GET    | `/api/v1/loans/{id}`           | Get loan details           | ✅ Any                 |
| PATCH  | `/api/v1/loans/{id}/status`    | Update loan status         | ✅ Role-dependent      |
| GET    | `/api/v1/loans/my-history`     | Current user's loan history| ✅ Member              |

### Utility
| Method | Endpoint    | Description          | Auth Required |
|--------|-------------|----------------------|:-------------:|
| GET    | `/health`   | Health check         | ❌            |

## 👥 User Roles & Permissions

### Member (Default)
- View all library branches and available books
- Request book loans from any branch
- Cancel loan requests (before approval)
- View personal borrowing history and active loans

### Librarian
- All Member permissions, plus:
- Create, read, update, and delete library branches
- Create, read, update, and delete books
- Manage book inventory (add/remove copies)
- Approve/reject loan requests
- Mark loans as borrowed, returned, or lost
- View all active loans

### Administrator
- Full system access, plus:
- Create, read, update, and delete users of any role
- Block/unblock users
- Delete branches and books
- View system-wide statistics and reports

## 🔄 Loan Status Flow

```
┌───────────┐     ┌───────────┐     ┌──────────┐     ┌──────────┐
│ Requested │────▶│ Approved  │────▶│ Borrowed │────▶│ Returned │
└───────────┘     └───────────┘     └──────────┘     └──────────┘
      │                                    │
      ▼                                    ▼
┌───────────┐                       ┌──────────┐
│ Canceled  │                       │ Overdue  │────▶ Returned / Lost
└───────────┘                       └──────────┘
                                           │
                                           ▼
                                    ┌──────────┐
                                    │   Lost   │
                                    └──────────┘
```

| Transition              | Who Can Do It     |
|-------------------------|-------------------|
| → Requested             | Member            |
| Requested → Canceled    | Member / Librarian|
| Requested → Approved    | Librarian         |
| Approved → Borrowed     | Librarian         |
| Borrowed → Returned     | Librarian         |
| Borrowed → Lost         | Librarian         |
| Borrowed → Overdue      | System (automatic)|
| Overdue → Returned      | Librarian         |
| Overdue → Lost          | Librarian         |

- **Due date**: 14 days from borrow date
- **Late fees**: Automatically calculated for overdue loans (display only, no payment processing)
- **Overdue checker**: Background task runs every 24 hours (configurable via `OVERDUE_CHECK_INTERVAL`)

## 🧪 Testing

### Run All Tests

```bash
# Using Docker
docker compose exec api pytest

# Locally
pytest
```

### Run by Test Type

```bash
# Unit tests only
pytest tests/unit/

# Functional tests only
pytest tests/functional/
```

### Run with Verbose Output

```bash
pytest -v
```

### Run a Specific Test File

```bash
pytest tests/functional/test_full_loan_workflow.py
```

### Test Coverage

```bash
pytest --cov=app --cov-report=term-missing
```

### Test Categories

| Directory             | Description                                                          |
|-----------------------|----------------------------------------------------------------------|
| `tests/unit/`         | Unit tests for business logic, models, security, and configuration   |
| `tests/functional/`   | End-to-end workflow tests (registration, loans, RBAC, pagination)    |

## 📝 Logging

The application uses **structured JSON logging** for all operations.

### Log Levels

| Level      | Usage                                              |
|------------|----------------------------------------------------|
| `DEBUG`    | Detailed diagnostic information                    |
| `INFO`     | Successful operations, request tracking            |
| `WARNING`  | Unusual situations, deprecation warnings           |
| `ERROR`    | Handled exceptions                                 |
| `CRITICAL` | System failures                                    |

### What Gets Logged

- **Authentication**: Login attempts (success/failure), token generation, logout
- **Authorization**: Permission checks, access denials
- **CRUD Operations**: All create, update, delete operations with user context
- **Loan Operations**: Borrow requests, approvals, returns, status changes
- **Errors**: All exceptions with stack traces
- **Performance**: API response times per request
- **Request Tracing**: Every request gets a unique `X-Request-ID` header

### Example Log Entry

```json
{
  "timestamp": "2026-02-28T10:30:45.123Z",
  "level": "INFO",
  "logger": "app.main",
  "message": "POST /api/v1/loans -> 201 (0.045s)",
  "request_id": "a1b2c3d4"
}
```

Configure the log level via the `LOG_LEVEL` environment variable.

## 🔐 Built-in Admin Account

The application seeds a built-in administrator account on startup:

| Field    | Default Value       |
|----------|---------------------|
| Email    | `admin@library.com` |
| Password | `admin123456`       |
| Role     | `admin`             |

> ⚠️ **This account cannot be deleted.** Change the credentials via environment variables (`ADMIN_EMAIL`, `ADMIN_PASSWORD`) before deploying to production.

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style conventions
- Write tests for all new features
- Update documentation when adding new endpoints
- Use structured logging for all new operations
- Keep migrations up to date with model changes

## 📄 License

This project is licensed under the **MIT License**.