import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select

from app import models  # noqa: F401  (registers models with metadata for create_db_and_tables)
from app.api import (
    auth_router,
    branch_router,
    customer_router,
    document_type_router,
    leave_credit_router,
    notification_router,
    project_router,
    role_router,
    system_option_router,
    task_type_router,
    timelog_router,
    user201_router,
    user_router,
)
from app.database import create_db_and_tables, get_async_session_context
from app.models.document_types import DocumentType
from app.models.roles import DEFAULT_ROLES, Role
from app.models.system_options import SystemOption
from app.models.task_types import TaskType
from app.models.users import User

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------
TASK_TYPE_SEEDS = [
    ("training", "Training tasks", "other"),
    ("hr task", "Human resources related tasks", "other"),
    ("it task", "IT related tasks", "other"),
    ("admin task", "Administrative tasks", "other"),
    ("delivery assurance", "Delivery assurance tasks", "other"),
    ("sick leave", "Sick leave", "leave"),
    ("holidays", "Holidays", "leave"),
    ("vacation leave", "Vacation leave", "leave"),
    ("absent without office leave", "Absent without office leave", "leave"),
]

DOCUMENT_TYPE_SEEDS = [
    ("PSA", "PSA Birth Certificate", "pre-employment", True),
    ("NBI", "NBI Clearance for Local Employment", "pre-employment", True),
    ("POLICE", "Police Clearance", "pre-employment", True),
    ("MEDCERT", "Medical Certificate (Fit to Work)", "pre-employment", True),
    ("TOR_SO", "Transcript of Records with SO number", "pre-employment", True),
    ("MARR_CERT", "Marriage Certificate (if legally married)", "pre-employment", False),
    ("GOTYME_CERT", "GoTyme Bank Certificate", "payroll", True),
    ("ATM_CARD", "GoTyme ATM Card", "payroll", True),
    ("TIN", "TIN", "government", True),
    ("SSS", "SSS", "government", True),
    ("PHILHEALTH", "PhilHealth", "government", True),
    ("PAGIBIG", "Pag-IBIG", "government", True),
]

SYSTEM_OPTION_DEFAULTS = {
    "Department": ["Admin", "Delivery"],
    "Salutation": ["Mr", "Ms", "Dr"],
    "Job Level": ["Career Level I", "Career Level II", "Career Level III", "Career Level IV"],
}


async def seed_roles(session):
    result = await session.execute(select(Role.role_name))
    existing = {row[0] for row in result.all()}
    missing = [name for name in DEFAULT_ROLES if name not in existing]
    if missing:
        session.add_all(Role(role_name=name) for name in missing)
        await session.commit()
        logger.info(f"✅ Seeded roles: {missing}")


async def backfill_user_role_ids(session):
    result = await session.execute(select(User).where(User.role_id.is_(None)))
    updated = 0
    for user in result.scalars().all():
        role_value = (user.role or "").strip().lower()
        if not role_value:
            continue
        role_res = await session.execute(
            select(Role).where(func.lower(Role.role_name) == role_value)
        )
        role = role_res.scalars().first()
        if role:
            user.role_id = role.id
            session.add(user)
            updated += 1
    if updated:
        await session.commit()
        logger.info(f"✅ Backfilled role_ids for {updated} users")


async def seed_task_types(session):
    count = (await session.execute(select(func.count(TaskType.id)))).scalar_one()
    if count == 0:
        session.add_all(
            TaskType(name=name, description=desc, category=category)
            for name, desc, category in TASK_TYPE_SEEDS
        )
        await session.commit()
        logger.info("✅ Seeded default task types")


async def seed_document_types(session):
    result = await session.execute(select(DocumentType.code))
    existing = {row[0] for row in result.all()}
    to_add = [d for d in DOCUMENT_TYPE_SEEDS if d[0] not in existing]
    if to_add:
        session.add_all(
            DocumentType(code=code, name=name, category=category, required=required)
            for code, name, category, required in to_add
        )
        await session.commit()
        logger.info(f"✅ Seeded {len(to_add)} document types")


async def seed_system_options(session):
    result = await session.execute(select(SystemOption))
    existing = {(o.category, o.value) for o in result.scalars().all()}
    to_add = [
        SystemOption(category=category, value=value)
        for category, values in SYSTEM_OPTION_DEFAULTS.items()
        for value in values
        if (category, value) not in existing
    ]
    if to_add:
        session.add_all(to_add)
        await session.commit()
        logger.info(f"✅ Seeded {len(to_add)} system options")


async def run_step(name, fn, session):
    """Run one seeding step; a failure is logged and doesn't block the others."""
    try:
        await fn(session)
    except Exception as e:
        await session.rollback()
        logger.warning(f"⚠️ Error in {name}: {e}")


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await create_db_and_tables()
        async with get_async_session_context() as session:
            await run_step("seed_roles", seed_roles, session)
            await run_step("backfill_user_role_ids", backfill_user_role_ids, session)
            await run_step("seed_task_types", seed_task_types, session)
            await run_step("seed_document_types", seed_document_types, session)
            await run_step("seed_system_options", seed_system_options, session)
    except Exception as e:
        logger.exception(f"Startup initialization error: {e}")
    yield


app = FastAPI(
    title="FastAPI and Svelte",
    description="This is a simple API for a FastAPI and Svelte application",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "auth", "description": "Operations with user authentication."},
        {"name": "users", "description": "Operations with users."},
    ],
    swagger_ui_oauth2_redirect_url="/docs/oauth2-redirect",
    swagger_ui_init_oauth={
        "usePkceWithAuthorizationCodeGrant": True,
        "clientId": "your-client-id",
        "scopes": "openid profile email",
    },
)

# Static files
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


# CORS — CORS_ORIGIN may be a list or a comma-separated string
def _parse_origins(value) -> list[str]:
    if isinstance(value, str):
        return [o.strip() for o in value.split(",") if o.strip()]
    return [o.strip() for o in value if o and o.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def read_root():
    return {"status": "ok", "message": "FastAPI server is running"}


@app.get("/schema/status")
async def schema_status():
    return {"status": "ok", "driver": "mysql", "version": 1}


app.include_router(user_router, tags=["Users"])
app.include_router(auth_router, tags=["Auth"])
app.include_router(project_router, tags=["Projects"])
app.include_router(branch_router, tags=["Branches"])
app.include_router(timelog_router, tags=["Timelogs"])
app.include_router(task_type_router, tags=["TaskTypes"])
app.include_router(user201_router, tags=["User201Files"])
app.include_router(document_type_router, tags=["DocumentTypes"])
app.include_router(role_router, tags=["Roles"])
app.include_router(notification_router, tags=["Notifications"])
app.include_router(leave_credit_router, tags=["LeaveCredits"])
app.include_router(customer_router, tags=["Customers"])
app.include_router(system_option_router, tags=["SystemOptions"])