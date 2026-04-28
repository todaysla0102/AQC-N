from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import init_db
from .routers.reports import start_report_schedule_runner, stop_report_schedule_runner
from .routers import admin, auth, goods, groups, legacy, legacy_scaffold, notifications, orders, reports, sales, shop_schedules, shop_targets, shops, users, work_orders


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="AQC-N 后端服务（账户接入 + AQC 独立用户集 + 分组系统）",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event() -> None:
    init_db()
    start_report_schedule_runner()


@app.on_event("shutdown")
def shutdown_event() -> None:
    stop_report_schedule_runner()


@app.get("/")
def root():
    return {
        "success": True,
        "message": "AQC-N API is running",
        "apiPrefix": settings.api_prefix,
    }


@app.get(f"{settings.api_prefix}/health")
def health():
    return {"success": True, "message": "ok"}


app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(users.router, prefix=settings.api_prefix)
app.include_router(groups.router, prefix=settings.api_prefix)
app.include_router(notifications.router, prefix=settings.api_prefix)
app.include_router(reports.router, prefix=settings.api_prefix)
app.include_router(sales.router, prefix=settings.api_prefix)
app.include_router(orders.router, prefix=settings.api_prefix)
app.include_router(shops.router, prefix=settings.api_prefix)
app.include_router(shop_schedules.router, prefix=settings.api_prefix)
app.include_router(shop_targets.router, prefix=settings.api_prefix)
app.include_router(goods.router, prefix=settings.api_prefix)
app.include_router(work_orders.router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)
app.include_router(legacy.router, prefix=settings.api_prefix)
app.include_router(legacy_scaffold.router, prefix=settings.api_prefix)
