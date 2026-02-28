# Library Management System API - Project Proposal

## Task Scope and Expectations

Your task is to build a Library Management System API using modern Python technologies.

You need to write an API for a library application where members can borrow books from different library branches.

### Technology Stack
- **Language**: Python 3.11+
- **Framework**: FastAPI
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy 2.0+
- **Migrations**: Alembic
- **Testing**: Pytest
- **Containerization**: Docker & Docker Compose
- **Version Control**: GitHub
- **Logging**: Python logging module with structured logging

### User Authentication
- Users must be able to create an account and log in using the API
- Each user can have only one account (identified by email)
- Authentication should use JWT tokens
- All endpoints (except registration and login) should require authentication
- **Logging**: Log all authentication attempts (success and failure)

## User Roles and Permissions

Implement 3 roles with different permission levels:

### Member (Regular User)
- Can view all library branches
- Can view available books across all branches
- Can borrow books from any branch
- Can view their borrowing history
- **Logging**: Log all book borrowing and return actions

### Librarian
- Can CRUD (Create, Read, Update, Delete) library branches
- Can CRUD books in the system
- Can manage book inventory (add/remove copies)
- Can view all active loans
- Can process book returns
- **Logging**: Log all CRUD operations on branches and books

### Administrator
- Full system access
- Can CRUD users (of any role)
- Can CRUD library branches
- Can CRUD books
- Can change all user/branch/book information, including blocking users
- Can view system-wide statistics and reports
- **Logging**: Log all administrative actions

**Important**: The application should include one built-in admin account that cannot be deleted.

## Data Models

### LibraryBranch
A library branch should have:
- Name
- Address
- Description
- Phone number
- Email
- Is active (boolean)
- Created at timestamp
- Updated at timestamp

### Book
A book should have:
- Title
- Author
- ISBN (unique)
- Description
- Genre/Category
- Publication year
- Total copies available
- Available copies (calculated field)
- Associated library branch
- Created at timestamp
- Updated at timestamp

### Loan (Borrowing Record)
A loan includes:
- Reference to the member (user)
- Reference to the book
- Reference to the library branch
- Borrow date
- Due date (typically 14 days from borrow date)
- Return date (nullable)
- Status
- Late fee amount (calculated if overdue)
- Notes (optional)
- Created at timestamp
- Updated at timestamp

**Important**: A loan is for a single book from a single branch, but a member can have multiple active loans.

**Note**: There is no need to handle actual payment of late fees, just calculate and display them.

## Loan Status Flow

Members and librarians can change the loan status respecting the flow and permissions below:

1. **Requested**: Once a member requests to borrow a book
2. **Canceled**: If the member cancels before approval, or librarian rejects
3. **Approved**: Once the librarian approves the loan request
4. **Borrowed**: Once the member picks up the book (librarian confirms)
5. **Overdue**: Automatically set if the book is not returned by due date
6. **Returned**: Once the member returns the book and librarian confirms
7. **Lost**: If the book is reported as lost

### Status Change Permissions
- **Member**: Can request loans (Requested), cancel before approval (Canceled)
- **Librarian**: Can approve (Approved), mark as borrowed (Borrowed), mark as returned (Returned), mark as lost (Lost)
- **System**: Automatically marks as overdue (Overdue) via scheduled job

### Loan History
- Loans should maintain a history of status changes with timestamps
- Members should be able to browse their loan history
- Members should be able to view current loan status and due dates
- Librarians should be able to see all loans for their branch
- Administrators should be able to see all loans system-wide
- **Logging**: Log all status changes with user who made the change

## API Requirements

### REST API
Make it possible to perform all user and admin actions via the API, including authentication.

The API should follow RESTful principles:
- Proper HTTP methods (GET, POST, PUT, PATCH, DELETE)
- Appropriate status codes
- JSON request/response format
- Pagination for list endpoints
- Filtering and sorting capabilities
- API documentation via FastAPI's automatic OpenAPI/Swagger UI

### Required Endpoints (Examples)

**Authentication**
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login and receive JWT token
- `POST /api/v1/auth/logout` - Logout (invalidate token)

**Users** (Admin only)
- `GET /api/v1/users` - List all users
- `GET /api/v1/users/{id}` - Get user details
- `PUT /api/v1/users/{id}` - Update user
- `DELETE /api/v1/users/{id}` - Delete user (except built-in admin)

**Library Branches**
- `GET /api/v1/branches` - List all branches (all authenticated users)
- `POST /api/v1/branches` - Create branch (Librarian/Admin)
- `GET /api/v1/branches/{id}` - Get branch details
- `PUT /api/v1/branches/{id}` - Update branch (Librarian/Admin)
- `DELETE /api/v1/branches/{id}` - Delete branch (Admin only)

**Books**
- `GET /api/v1/books` - List all books with filters
- `POST /api/v1/books` - Create book (Librarian/Admin)
- `GET /api/v1/books/{id}` - Get book details
- `PUT /api/v1/books/{id}` - Update book (Librarian/Admin)
- `DELETE /api/v1/books/{id}` - Delete book (Admin only)

**Loans**
- `GET /api/v1/loans` - List loans (filtered by role)
- `POST /api/v1/loans` - Request a loan (Member)
- `GET /api/v1/loans/{id}` - Get loan details
- `PATCH /api/v1/loans/{id}/status` - Update loan status
- `GET /api/v1/loans/my-history` - Get current user's loan history

## Testing Requirements

### Unit Tests (Optional)
- Test all business logic and utility functions
- Test database models and relationships
- Test authentication and authorization logic
- Aim for >80% code coverage
- **Logging**: Tests should verify that appropriate log messages are generated

### Integration Tests (Optional)
- Test API endpoints with different user roles
- Test authentication flows
- Test permission enforcement
- Test database transactions and rollbacks
- Test error handling and validation

### Functional Tests (Required)
Use Pytest with FastAPI TestClient to create comprehensive functional tests:
- Test complete user workflows (registration → login → borrow book → return book)
- Test role-based access control
- Test loan status transitions
- Test edge cases (overdue books, unavailable books, etc.)
- Test pagination, filtering, and sorting
- **Logging**: Verify logs are generated for critical operations

### API Testing Tools (Required)
Be prepared to demonstrate the API using:
- **Swagger UI** (built-in with FastAPI at `/docs`)
- **ReDoc** (built-in with FastAPI at `/redoc`)
- **Postman** or **Insomnia** (Required)
- **cURL** commands
- **HTTPie**

## Docker Requirements

### Docker Compose Setup
Create a `docker-compose.yml` that includes:
- **API Service**: FastAPI application
- **Database Service**: PostgreSQL 15+
- **PgAdmin** (optional): For database management UI

### Dockerfile
- Use multi-stage builds for optimization (optional)
- Use Python 3.11+ slim image
- Install dependencies via pip (requirements.txt)
- Set up proper environment variables
- Configure health checks

### Environment Configuration
- Use `.env` file for configuration
- Separate configs for development, testing, and production
- Database connection strings
- JWT secret keys
- Log levels and formats

## Database Requirements

### PostgreSQL Setup
- Use PostgreSQL 15 or higher
- Proper indexing on frequently queried fields (email, ISBN, status)
- Foreign key constraints
- Check constraints for data validation
- Timestamps on all tables (created_at, updated_at)

### SQLAlchemy Models
- Use SQLAlchemy 2.0+ declarative style
- Define proper relationships (one-to-many, many-to-one)
- Implement model validators
- Use Enums for status fields
- Implement soft deletes where appropriate

### Alembic Migrations
- Initialize Alembic for migration management
- Create initial migration for all tables
- Document migration steps
- Support both upgrade and downgrade
- **Logging**: Log migration execution

## Logging Requirements

### Logging Strategy
Implement comprehensive logging throughout the application:

#### Log Levels
- **DEBUG**: Detailed diagnostic information
- **INFO**: General informational messages (successful operations)
- **WARNING**: Warning messages (deprecated features, unusual situations)
- **ERROR**: Error messages (handled exceptions)
- **CRITICAL**: Critical issues (system failures)

#### What to Log
- **Authentication**: All login attempts, token generation, logout
- **Authorization**: Permission checks, access denials
- **CRUD Operations**: All create, update, delete operations with user context
- **Loan Operations**: Borrow requests, approvals, returns, status changes
- **Errors**: All exceptions with stack traces
- **Performance**: Slow queries (>1s), API response times
- **Security**: Failed authentication, suspicious activities

#### Log Format
Use structured logging (JSON format) with:
- Timestamp (ISO 8601)
- Log level
- Logger name
- Message
- User ID (if authenticated)
- Request ID (for tracing)
- Additional context (operation type, resource ID, etc.)

Example log entry:
```json
{
  "timestamp": "2025-12-01T10:30:45.123Z",
  "level": "INFO",
  "logger": "api.loans",
  "message": "Loan request created successfully",
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "request_id": "req_abc123",
  "loan_id": "loan_xyz789",
  "book_id": "book_456",
  "branch_id": "branch_789"
}
```

#### Log Storage
- Console output for development
- File rotation for production (daily rotation, keep 30 days) (optional)
- Consider integration with log aggregation tools (ELK stack, CloudWatch, etc.) (optional)

## GitHub Requirements

### Repository Structure
```
library-management-api/
├── alembic/
│   ├── versions/           # Migration files
│   └── env.py
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/  # API route handlers
│   │       └── dependencies.py
│   ├── core/
│   │   ├── config.py       # Configuration
│   │   ├── security.py     # Auth utilities
│   │   └── logging.py      # Logging setup
│   ├── db/
│   │   ├── models.py       # SQLAlchemy models
│   │   └── session.py      # Database session
│   ├── schemas/            # Pydantic schemas
│   ├── services/           # Business logic
│   └── main.py             # FastAPI app
├── tests/
│   ├── unit/
│   ├── integration/
│   └── functional/
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── pytest.ini
├── alembic.ini
└── README.md
```

### README.md
Include comprehensive documentation: (optional)
- Project overview
- Technology stack
- Setup instructions (local and Docker)
- API documentation link
- Testing instructions
- Environment variables
- Contributing guidelines

## Additional Features

### Data Validation
- Use Pydantic models for request/response validation
- Validate email formats, ISBN formats
- Validate date ranges (due date must be after borrow date)
- Validate business rules (can't borrow if already have 5 active loans)

### Error Handling
- Custom exception classes
- Proper HTTP status codes
- Detailed error messages in development
- Generic error messages in production
- **Logging**: Log all errors with context

### Performance Considerations
- Database query optimization
- Use of database indexes
- Pagination for large result sets
- Caching for frequently accessed data (optional)
- Connection pooling

### Security
- Password hashing (bcrypt)
- JWT token authentication
- Role-based access control (RBAC)
- Input sanitization
- SQL injection prevention (via SQLAlchemy)
- Rate limiting (optional)
- CORS configuration

## Deliverables

1. **Source Code**: Complete, well-organized codebase on GitHub
2. **Database**: PostgreSQL schema with migrations
3. **Tests**: Comprehensive test suite with >80% coverage (optional)
4. **Docker**: Working Docker Compose setup
5. **Documentation**: README with setup and usage instructions
6. **API Docs**: Interactive API documentation (Swagger/ReDoc)
7. **Logs**: Properly configured logging throughout the application

## Evaluation Criteria

You will be evaluated on:
- **Functionality**: All features work as specified
- **Code Quality**: Clean, readable, well-organized code
- **Testing**: Comprehensive tests with good coverage
- **API Design**: RESTful principles, proper status codes
- **Database Design**: Normalized schema, proper relationships
- **Security**: Proper authentication and authorization
- **Logging**: Comprehensive, structured logging
- **Docker**: Working containerized setup
- **Documentation**: Clear, complete documentation
- **Git Practices**: Meaningful commits, proper branching




