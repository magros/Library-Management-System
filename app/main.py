import asyncio
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.core.config import settings
from app.core.logging import setup_logging, get_logger, request_id_ctx
from app.db.session import AsyncSessionLocal, engine
from app.db.models import Base, User, UserRole
from app.core.security import hash_password
from app.services.overdue import overdue_checker_loop

logger = get_logger("app.main")

# Background task reference
_overdue_task: asyncio.Task | None = None


async def seed_admin() -> None:
    """Create the built-in admin account if it doesn't exist."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == settings.ADMIN_EMAIL))
        admin = result.scalar_one_or_none()
        if not admin:
            admin = User(
                email=settings.ADMIN_EMAIL,
                hashed_password=hash_password(settings.ADMIN_PASSWORD),
                full_name="System Administrator",
                role=UserRole.ADMIN,
                is_built_in=True,
            )
            db.add(admin)
            await db.commit()
            logger.info(f"Built-in admin created: {settings.ADMIN_EMAIL}")
        else:
            logger.info(f"Built-in admin already exists: {settings.ADMIN_EMAIL}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    global _overdue_task

    # Startup
    setup_logging()
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # Create tables (in dev; in prod use alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await seed_admin()

    # Start background overdue checker
    _overdue_task = asyncio.create_task(overdue_checker_loop())
    logger.info("Background overdue checker started")

    yield

    # Shutdown
    if _overdue_task:
        _overdue_task.cancel()
        try:
            await _overdue_task
        except asyncio.CancelledError:
            pass
    logger.info("Application shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "## Library Management API\n\n"
        "A full-featured REST API for managing a library system including:\n\n"
        "- **Authentication** – Register, login (JWT Bearer), and logout\n"
        "- **Users** – Admin CRUD for user accounts\n"
        "- **Library Branches** – Manage physical branch locations\n"
        "- **Books** – Catalog management with search & filtering\n"
        "- **Loans** – Borrow/return workflow with status tracking\n\n"
        "### Authentication\n"
        "Most endpoints require a **Bearer JWT token**. "
        "Obtain one via `POST /api/v1/auth/login` (OAuth2 password flow) "
        "or `POST /api/v1/auth/register`.\n\n"
        "### Roles\n"
        "| Role | Description |\n"
        "|------|-------------|\n"
        "| `member` | Default role – can browse books and request loans |\n"
        "| `librarian` | Can manage books and branches, approve/reject loans |\n"
        "| `admin` | Full access including user management |\n"
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "Health",
            "description": "Application health checks",
        },
        {
            "name": "Authentication",
            "description": "Register, login (JWT), and logout endpoints",
        },
        {
            "name": "Users",
            "description": "User management (Admin only)",
        },
        {
            "name": "Library Branches",
            "description": "CRUD operations for library branches",
        },
        {
            "name": "Books",
            "description": "Book catalog management with search and filtering",
        },
        {
            "name": "Loans",
            "description": "Loan lifecycle – request, approve, borrow, return",
        },
    ],
    contact={
        "name": "Library API Support",
        "email": "support@library.com",
    },
    license_info={
        "name": "MIT",
    },
    servers=[
        {"url": "http://localhost:8000", "description": "Local development"},
    ],
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request ID and timing middleware
@app.middleware("http")
async def request_middleware(request: Request, call_next):
    req_id = str(uuid.uuid4())[:8]
    request_id_ctx.set(req_id)

    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    logger.info(
        f"{request.method} {request.url.path} -> {response.status_code} "
        f"({duration:.3f}s)"
    )

    response.headers["X-Request-ID"] = req_id
    return response


# Health check
@app.get("/health", tags=["Health"], summary="Health check", description="Returns the current health status and API version.")
async def health_check():
    return {"status": "healthy", "version": settings.APP_VERSION}


# OpenAPI spec download endpoint
@app.get(
    "/openapi.json",
    tags=["Health"],
    summary="Download OpenAPI spec",
    description="Download the OpenAPI 3.x JSON specification for import into Postman or other API tools.",
    include_in_schema=False,
)
async def get_openapi_spec():
    return JSONResponse(content=app.openapi())


# Include routers
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.users import router as users_router
from app.api.v1.endpoints.branches import router as branches_router
from app.api.v1.endpoints.books import router as books_router
from app.api.v1.endpoints.loans import router as loans_router

app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(branches_router, prefix="/api/v1")
app.include_router(books_router, prefix="/api/v1")
app.include_router(loans_router, prefix="/api/v1")

