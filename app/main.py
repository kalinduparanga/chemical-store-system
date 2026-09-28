"""
Chemical Store Management System - FastAPI Application Entrypoint.
Desktop-First Responsive Web Application with Persistent SQLite Relational Database,
ACID compliant transactions, real Excel & PDF exports, and RBAC security.
"""

import os
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import (
    auth_router,
    inventory_router,
    receiving_router,
    usage_router,
    ammonia_router,
    physical_stock_router,
    reports_router,
    export_router,
    settings_router
)

app = FastAPI(
    title="Chemical Store Management System",
    description="Professional desktop-first chemical store inventory management system for industrial manufacturing & compounding plants.",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth_router.router)
app.include_router(inventory_router.router)
app.include_router(receiving_router.router)
app.include_router(usage_router.router)
app.include_router(ammonia_router.router)
app.include_router(physical_stock_router.router)
app.include_router(reports_router.router)
app.include_router(export_router.router)
app.include_router(settings_router.router)

# Static files directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")

if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h2>Chemical Store Management System API is running. UI not found in /static.</h2>")

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "Chemical Store Management System", "version": "1.0.0"}
