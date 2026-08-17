from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from fastapi import FastAPI, APIRouter, Request, Response
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from datetime import datetime, timezone

from routes.auth import router as auth_router
from routes.companies import router as companies_router
from routes.employees import router as employees_router
from routes.attendance import router as attendance_router
from routes.gps import router as gps_router
from routes.tasks import router as tasks_router
from routes.leaves import router as leaves_router
from routes.admin import router as admin_router
from routes.shifts import router as shifts_router
from routes.shift_comments import router as shift_comments_router
from routes.overtime import router as overtime_router
from routes.payroll import router as payroll_router
from routes.notifications import router as notifications_router
from routes.settings import router as settings_router
from routes.office_locations import router as office_locations_router
from routes.reports import router as reports_router
from routes.dispatch import router as dispatch_router
from utils.auth import hash_password, verify_password
from utils.storage import init_storage

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="OfficeFlow API", version="1.0.0")
api_router = APIRouter(prefix="/api")

app.state.db = db

async def seed_admin():
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com")
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    
    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        hashed = hash_password(admin_password)
        await db.users.insert_one({
            "email": admin_email,
            "password_hash": hashed,
            "name": "Super Admin",
            "role": "super_admin",
            "status": "active",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        })
        logger.info(f"Admin user created: {admin_email}")
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one(
            {"email": admin_email},
            {"$set": {"password_hash": hash_password(admin_password), "updated_at": datetime.now(timezone.utc)}}
        )
        logger.info(f"Admin password updated: {admin_email}")
    
    credentials_content = f"""# OfficeFlow Test Credentials

## Admin Account
- Email: {admin_email}
- Password: {admin_password}
- Role: super_admin

## Auth Endpoints
- POST /api/auth/register - Register new user
- POST /api/auth/login - Login
- POST /api/auth/logout - Logout
- GET /api/auth/me - Get current user
- POST /api/auth/refresh - Refresh access token
- POST /api/auth/forgot-password - Request password reset
- POST /api/auth/reset-password - Reset password with token

## Test User Account (Create via register endpoint)
- Email: test@officeflow.com
- Password: Test@123
- Role: employee
"""
    
    with open("/app/memory/test_credentials.md", "w") as f:
        f.write(credentials_content)
    
    logger.info("Test credentials file updated")

@app.on_event("startup")
async def startup():
    try:
        await db.users.create_index("email", unique=True)
        await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)
        await db.login_attempts.create_index("identifier")
        # Dispatch indexes
        await db.dispatch_clients.create_index("name")
        await db.dispatch_vendors.create_index("name")
        await db.dispatch_officers.create_index("name")
        await db.dispatch_officers.create_index("vendor_id")
        await db.dispatch_post_sites.create_index("post_pin", unique=True)
        await db.dispatch_post_sites.create_index("client_id")
        await db.dispatch_post_sites.create_index("vendor_id")
        await db.dispatch_schedules.create_index([("date", -1), ("officer_id", 1)])
        await db.dispatch_schedules.create_index("post_site_id")
        await db.dispatch_schedules.create_index("client_id")
        await db.dispatch_schedules.create_index("vendor_id")
        await db.dispatch_confirmation_history.create_index("schedule_id")
        logger.info("Database indexes created")
        
        await seed_admin()
        
        try:
            init_storage()
            logger.info("Storage initialized")
        except Exception as e:
            logger.warning(f"Storage initialization failed: {e}")
    except Exception as e:
        logger.error(f"Startup error: {e}")

@app.on_event("shutdown")
async def shutdown():
    client.close()

@api_router.get("/")
async def root():
    return {"message": "OfficeFlow API v1.0.0", "status": "running"}

@api_router.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

api_router.include_router(auth_router)
api_router.include_router(companies_router)
api_router.include_router(employees_router)
api_router.include_router(attendance_router)
api_router.include_router(gps_router)
api_router.include_router(tasks_router)
api_router.include_router(leaves_router)
api_router.include_router(admin_router)
api_router.include_router(shifts_router)
api_router.include_router(shift_comments_router)
api_router.include_router(overtime_router)
api_router.include_router(payroll_router)
api_router.include_router(notifications_router)
api_router.include_router(settings_router)
api_router.include_router(office_locations_router)
api_router.include_router(reports_router)
api_router.include_router(dispatch_router)

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[
        os.environ.get("FRONTEND_URL", "http://localhost:3000"),
        "http://localhost:3000",
    ],
    allow_origin_regex=r"https://.*\.preview\.emergentagent\.com",
    allow_methods=["*"],
    allow_headers=["*"],
)
