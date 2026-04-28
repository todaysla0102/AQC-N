from __future__ import annotations

import json
import re
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import and_, create_engine, inspect, or_, select, text
from sqlalchemy.orm import Session, sessionmaker

from .config import settings
from .goods_attributes import GOODS_ATTRIBUTE_NONE, GOODS_ATTRIBUTE_VALUES, compose_goods_name, normalize_goods_attribute, split_model_attribute
from .models import (
    AqcGoodsItem,
    AqcPermission,
    AqcReportSetting,
    AqcRole,
    AqcRolePermission,
    AqcSaleRecord,
    AqcShop,
    AqcUser,
    AqcUserIdentity,
    AqcUserRole,
    AqcWorkOrderSchedule,
    AqcWorkOrderSetting,
    Base,
)
from .security import hash_password


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=settings.db_pool_recycle,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_pool_max_overflow,
    pool_timeout=settings.db_pool_timeout,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
INIT_DB_LOCK_NAME = "aqc_n_init_db"
SALE_ORDER_NUM_PATTERN = re.compile(r"单号:([^;\s]+)")
SALE_GUIDE_PATTERN = re.compile(r"导购:([^;]+)")
SHOP_TYPE_OTHER_WAREHOUSE = 2
DEFAULT_OTHER_WAREHOUSE_NAMES = [
    "卡西欧中国",
    "兴达公司",
    "丽声",
    "恩施汤刚",
    "上海美吉莱",
    "新宇代销",
    "swatch公司",
]
DEFAULT_WORK_ORDER_TYPES = [
    "transfer",
    "purchase",
    "return",
    "damage",
    "sale",
    "sale_return",
    "sale_exchange",
]
DEFAULT_TRANSFER_APPROVER_DISPLAY_NAMES = ["柏云"]


DEFAULT_PERMISSION_SEEDS = [
    ("*", "所有权限", "系统超级权限"),
    ("sales.read", "查看销售", "查看销售记录与统计"),
    ("sales.write", "录入销售", "录入和编辑销售数据"),
    ("sales.manage", "管理销售", "删除销售记录和管理销售模块"),
    ("orders.read", "查看订单", "查看 AQC-O 迁移订单与上传记录"),
    ("orders.upload", "上传订单", "按 AQC-O 兼容方式上传订单"),
    ("orders.manage", "管理订单", "管理订单上传状态与订单模块"),
    ("goods.read", "查看商品", "查看商品数据与详情"),
    ("goods.write", "编辑商品", "新增与编辑商品信息"),
    ("goods.manage", "管理商品", "删除商品与管理商品模块"),
    ("workorders.read", "查看工单", "查看工单列表、草稿和审批记录"),
    ("workorders.write", "填写工单", "创建、编辑、提交工单"),
    ("workorders.approve", "审批工单", "审核工单并执行库存变更"),
    ("shops.read", "查看店铺", "查看店铺数据与详情"),
    ("shops.write", "编辑店铺", "新增与编辑店铺信息"),
    ("shops.manage", "管理店铺", "删除店铺与管理店铺模块"),
    ("admin.manage_users", "管理用户", "创建、更新 AQC 后台账号"),
    ("admin.manage_roles", "管理角色", "管理角色和权限关系"),
    ("admin.import_legacy", "导入旧后台账号", "导入 AQC-O 后台账户与权限"),
]


DEFAULT_ROLE_SEEDS = [
    {
        "name": "超级管理员",
        "slug": "administrator",
        "description": "AQC 后台超级管理员",
        "is_system": True,
        "permissions": ["*"],
    },
    {
        "name": "管理员",
        "slug": "admin",
        "description": "AQC 后台管理员",
        "is_system": True,
        "permissions": [
            "sales.read",
            "sales.write",
            "sales.manage",
            "orders.read",
            "orders.upload",
            "orders.manage",
            "goods.read",
            "goods.write",
            "goods.manage",
            "workorders.read",
            "workorders.write",
            "workorders.approve",
            "shops.read",
            "shops.write",
            "shops.manage",
            "admin.manage_users",
            "admin.manage_roles",
            "admin.import_legacy",
        ],
    },
    {
        "name": "销售主管",
        "slug": "sales-manager",
        "description": "可管理销售录入与销售查看",
        "is_system": True,
        "permissions": [
            "sales.read",
            "sales.write",
            "sales.manage",
            "orders.read",
            "orders.upload",
            "orders.manage",
            "goods.read",
            "workorders.read",
            "workorders.write",
            "shops.read",
        ],
    },
    {
        "name": "销售录入",
        "slug": "sales-entry",
        "description": "仅录入和查看销售数据",
        "is_system": True,
        "permissions": ["sales.read", "sales.write", "orders.read", "goods.read", "workorders.read", "workorders.write", "shops.read"],
    },
    {
        "name": "销售查看",
        "slug": "sales-viewer",
        "description": "仅可查看销售数据",
        "is_system": True,
        "permissions": ["sales.read", "orders.read", "goods.read", "workorders.read", "shops.read"],
    },
    {
        "name": "商品运营",
        "slug": "goods-manager",
        "description": "管理商品与查看店铺",
        "is_system": True,
        "permissions": ["goods.read", "goods.write", "goods.manage", "orders.read", "workorders.read", "workorders.write", "shops.read"],
    },
    {
        "name": "店铺运营",
        "slug": "shop-manager",
        "description": "管理店铺与查看商品",
        "is_system": True,
        "permissions": ["shops.read", "shops.write", "shops.manage", "orders.read", "orders.upload", "goods.read", "workorders.read", "workorders.write"],
    },
]

DEFAULT_SCHEDULE_ENABLED_SHOP_NAMES = [
    "武汉新佳丽Casio专卖店",
    "武商世贸Casio专柜",
    "宜昌国贸Casio专卖店",
    "武商梦时代Casio专卖店",
    "十堰武商Casio专柜",
]

DEFAULT_TARGET_ENABLED_SHOP_NAMES = [
    "武汉新佳丽Casio专卖店",
    "武商世贸Casio专柜",
    "宜昌国贸Casio专卖店",
    "武商梦时代Casio专卖店",
    "十堰武商Casio专柜",
]

DEFAULT_REPORT_SETTING_SEEDS = [
    {
        "period_key": "day",
        "enabled": True,
        "recipient_role_keys": ["aqc_admin", "aqc_manager", "aqc_sales"],
        "push_hour": 7,
        "push_minute": 0,
        "push_weekday": 0,
        "push_day_of_month": 1,
        "cleanup_hour": 23,
        "cleanup_minute": 59,
        "cleanup_weekday": 0,
        "cleanup_day_of_month": 1,
        "retention_days": 35,
    },
    {
        "period_key": "week",
        "enabled": True,
        "recipient_role_keys": ["aqc_admin", "aqc_manager", "aqc_sales"],
        "push_hour": 7,
        "push_minute": 0,
        "push_weekday": 0,
        "push_day_of_month": 1,
        "cleanup_hour": 23,
        "cleanup_minute": 59,
        "cleanup_weekday": 0,
        "cleanup_day_of_month": 1,
        "retention_days": 35,
    },
    {
        "period_key": "month",
        "enabled": True,
        "recipient_role_keys": ["aqc_admin", "aqc_manager", "aqc_sales"],
        "push_hour": 7,
        "push_minute": 0,
        "push_weekday": 0,
        "push_day_of_month": 1,
        "cleanup_hour": 23,
        "cleanup_minute": 59,
        "cleanup_weekday": 0,
        "cleanup_day_of_month": 1,
        "retention_days": 0,
    },
]


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_admin_user(db: Session) -> None:
    stmt = select(AqcUser).where(AqcUser.username == settings.admin_username).limit(1)
    admin = db.execute(stmt).scalars().first()

    if admin is None:
        admin = AqcUser(
            username=settings.admin_username,
            email=settings.admin_email,
            password_hash=hash_password(settings.admin_password),
            display_name=settings.admin_username,
            role="admin",
            vip=2,
            vip_level=0,
            user_rule_id=5,
            auth_source="local",
            is_active=True,
        )
        db.add(admin)
        db.flush()

        db.add(
            AqcUserIdentity(
                user_id=admin.id,
                name=admin.display_name,
                avatar=admin.avatar_url,
                mobile=admin.phone,
                sex=0,
                vip=admin.vip,
            )
        )
        return

    admin.role = "admin"
    admin.vip = 2
    admin.is_active = True
    admin.auth_source = admin.auth_source or "local"
    admin.password_hash = hash_password(settings.admin_password)
    if not admin.email:
        admin.email = settings.admin_email


def _ensure_permissions_and_roles(db: Session, admin: AqcUser) -> None:
    permission_map: dict[str, AqcPermission] = {}
    for code, name, description in DEFAULT_PERMISSION_SEEDS:
        permission = db.execute(select(AqcPermission).where(AqcPermission.code == code).limit(1)).scalars().first()
        if permission is None:
            permission = AqcPermission(code=code, name=name, description=description)
            db.add(permission)
            db.flush()
        else:
            permission.name = name
            permission.description = description
        permission_map[code] = permission

    role_map: dict[str, AqcRole] = {}
    for role_seed in DEFAULT_ROLE_SEEDS:
        role = db.execute(select(AqcRole).where(AqcRole.slug == role_seed["slug"]).limit(1)).scalars().first()
        if role is None:
            role = AqcRole(
                name=role_seed["name"],
                slug=role_seed["slug"],
                description=role_seed["description"],
                is_system=bool(role_seed["is_system"]),
            )
            db.add(role)
            db.flush()
        else:
            role.name = role_seed["name"]
            role.description = role_seed["description"]
            role.is_system = bool(role_seed["is_system"])

        role_map[role.slug] = role

        for code in role_seed["permissions"]:
            permission = permission_map.get(code)
            if permission is None:
                continue
            exists = db.execute(
                select(AqcRolePermission.id).where(
                    AqcRolePermission.role_id == role.id,
                    AqcRolePermission.permission_id == permission.id,
                )
            ).scalar()
            if exists is None:
                db.add(AqcRolePermission(role_id=role.id, permission_id=permission.id))

    administrator_role = role_map.get("administrator")
    if administrator_role is not None:
        user_role_exists = db.execute(
            select(AqcUserRole.id).where(
                AqcUserRole.user_id == admin.id,
                AqcUserRole.role_id == administrator_role.id,
            )
        ).scalar()
        if user_role_exists is None:
            db.add(AqcUserRole(user_id=admin.id, role_id=administrator_role.id, assigned_by=admin.id))


def _ensure_report_settings(db: Session, admin: AqcUser | None) -> None:
    default_actor_id = int(admin.id) if admin is not None else None
    for seed in DEFAULT_REPORT_SETTING_SEEDS:
        period_key = str(seed["period_key"]).strip()
        setting = db.execute(select(AqcReportSetting).where(AqcReportSetting.period_key == period_key).limit(1)).scalars().first()
        if setting is None:
            setting = AqcReportSetting(
                period_key=period_key,
                enabled=bool(seed.get("enabled", True)),
                recipient_role_keys_json=json.dumps(seed.get("recipient_role_keys") or [], ensure_ascii=True),
                recipient_user_ids_json="[]",
                push_hour=int(seed.get("push_hour", 7)),
                push_minute=int(seed.get("push_minute", 0)),
                push_weekday=int(seed.get("push_weekday", 0)),
                push_day_of_month=int(seed.get("push_day_of_month", 1)),
                cleanup_hour=int(seed.get("cleanup_hour", 23)),
                cleanup_minute=int(seed.get("cleanup_minute", 59)),
                cleanup_weekday=int(seed.get("cleanup_weekday", 0)),
                cleanup_day_of_month=int(seed.get("cleanup_day_of_month", 1)),
                retention_days=int(seed.get("retention_days", 35)),
                created_by=default_actor_id,
                updated_by=default_actor_id,
            )
            db.add(setting)
            continue

        if not str(setting.recipient_role_keys_json or "").strip():
            setting.recipient_role_keys_json = json.dumps(seed.get("recipient_role_keys") or [], ensure_ascii=True)
        if not str(setting.recipient_user_ids_json or "").strip():
            setting.recipient_user_ids_json = "[]"
        if int(getattr(setting, "push_hour", 7) or 7) < 0 or int(getattr(setting, "push_hour", 7) or 7) > 23:
            setting.push_hour = int(seed.get("push_hour", 7))
        if int(getattr(setting, "push_minute", 0) or 0) < 0 or int(getattr(setting, "push_minute", 0) or 0) > 59:
            setting.push_minute = int(seed.get("push_minute", 0))
        if int(getattr(setting, "push_weekday", 0) or 0) < 0 or int(getattr(setting, "push_weekday", 0) or 0) > 6:
            setting.push_weekday = int(seed.get("push_weekday", 0))
        if int(getattr(setting, "push_day_of_month", 1) or 1) < 1 or int(getattr(setting, "push_day_of_month", 1) or 1) > 31:
            setting.push_day_of_month = int(seed.get("push_day_of_month", 1))
        if int(getattr(setting, "cleanup_hour", 23) or 23) < 0 or int(getattr(setting, "cleanup_hour", 23) or 23) > 23:
            setting.cleanup_hour = int(seed.get("cleanup_hour", 23))
        if int(getattr(setting, "cleanup_minute", 59) or 59) < 0 or int(getattr(setting, "cleanup_minute", 59) or 59) > 59:
            setting.cleanup_minute = int(seed.get("cleanup_minute", 59))
        if int(getattr(setting, "cleanup_weekday", 0) or 0) < 0 or int(getattr(setting, "cleanup_weekday", 0) or 0) > 6:
            setting.cleanup_weekday = int(seed.get("cleanup_weekday", 0))
        if int(getattr(setting, "cleanup_day_of_month", 1) or 1) < 1 or int(getattr(setting, "cleanup_day_of_month", 1) or 1) > 31:
            setting.cleanup_day_of_month = int(seed.get("cleanup_day_of_month", 1))
        if int(getattr(setting, "retention_days", seed.get("retention_days", 35)) or 0) < 0:
            setting.retention_days = int(seed.get("retention_days", 35))
        if setting.updated_by is None and default_actor_id is not None:
            setting.updated_by = default_actor_id


def _ensure_runtime_indexes() -> None:
    inspector = inspect(engine)
    dialect = engine.dialect.name.lower()

    index_specs = {
        "aqc_goods_items": [
            ("idx_goods_filter", "putaway, status, shop_id, updated_at, id"),
            ("idx_goods_sort_updated", "sort, updated_at, id"),
            ("idx_goods_status_updated", "status, updated_at, id"),
            ("idx_goods_code_lookup", "product_code, id"),
            ("idx_goods_barcode_lookup", "barcode, id"),
            ("idx_goods_brand_series_model", "brand, series_name, model_name, id"),
            ("idx_goods_attribute_model", "model_attribute, model_name, id"),
            ("idx_goods_index_brand", "index_key, brand, product_code, id"),
        ],
        "aqc_shops": [
            ("idx_shops_status_updated", "status, updated_at, id"),
            ("idx_shops_enabled_updated", "is_enabled, updated_at, id"),
            ("idx_shops_report_enabled", "report_enabled, shop_type, updated_at, id"),
        ],
        "aqc_sale_records": [
            ("idx_sales_kind_time", "sale_kind, sold_at, id"),
            ("idx_sales_sold_time", "sold_at, id"),
            ("idx_sales_order_num", "order_num, sold_at, id"),
            ("idx_sales_goods_time", "goods_barcode, sold_at, id"),
            ("idx_sales_code_time", "goods_code, sold_at, id"),
            ("idx_sales_shop_time", "shop_id, sold_at, id"),
            ("idx_sales_salesperson_time", "salesperson, sold_at, id"),
            ("idx_sales_index_time", "index_key, sold_at, id"),
            ("idx_sales_brand_series_model", "goods_brand, goods_series, goods_model, id"),
            ("idx_sales_status_time", "sale_status, sold_at, id"),
            ("idx_sales_source_sale", "source_sale_record_id, id"),
        ],
        "aqc_order_upload_logs": [
            ("idx_order_upload_order_time", "legacy_order_id, uploaded_at, id"),
            ("idx_order_upload_success_time", "success, uploaded_at, id"),
        ],
        "aqc_users": [
            ("idx_users_role_shop", "aqc_role_key, shop_id, is_active, id"),
        ],
        "aqc_goods_inventory": [
            ("idx_goods_inventory_goods", "goods_item_id, quantity, shop_id"),
            ("idx_goods_inventory_shop", "shop_id, quantity, goods_item_id"),
        ],
        "aqc_inventory_logs": [
            ("idx_inventory_logs_goods_time", "goods_item_id, created_at, id"),
            ("idx_inventory_logs_shop_time", "shop_id, created_at, id"),
            ("idx_inventory_logs_operator_time", "operator_id, created_at, id"),
            ("idx_inventory_logs_related", "related_type, related_id, created_at, id"),
        ],
        "aqc_work_orders": [
            ("idx_work_orders_status_date", "status, form_date, id"),
            ("idx_work_orders_type_status", "order_type, status, id"),
            ("idx_work_orders_applicant_status", "applicant_id, status, id"),
            ("idx_work_orders_approver_status", "approver_id, status, id"),
            ("idx_work_orders_group_status", "shared_group_id, status, id"),
        ],
        "aqc_work_order_items": [
            ("idx_work_order_items_order_sort", "work_order_id, sort_index, id"),
            ("idx_work_order_items_goods", "goods_id, work_order_id, id"),
            ("idx_work_order_items_sale_shop", "sale_shop_id, work_order_id, id"),
            ("idx_work_order_items_receive_shop", "receive_shop_id, work_order_id, id"),
        ],
        "aqc_group_members": [
            ("idx_group_members_user_default", "user_id, is_default, id"),
        ],
        "aqc_work_order_actions": [
            ("idx_work_order_actions_order_time", "work_order_id, created_at, id"),
            ("idx_work_order_actions_actor_time", "actor_id, created_at, id"),
        ],
        "aqc_work_order_allocation_drafts": [
            ("idx_work_order_allocation_source", "source_shop_id, updated_at, id"),
            ("idx_work_order_allocation_approver", "approver_id, updated_at, id"),
            ("idx_work_order_allocation_group", "shared_group_id, updated_at, id"),
        ],
        "aqc_work_order_schedules": [
            ("idx_work_order_schedules_enabled_period", "enabled, period_key, id"),
            ("idx_work_order_schedules_type_period", "order_type, period_key, id"),
            ("idx_work_order_schedules_applicant", "applicant_id, enabled, id"),
        ],
        "aqc_work_order_settings": [
            ("idx_work_order_settings_type", "order_type, id"),
            ("idx_work_order_settings_approver", "approver_id, updated_at, id"),
        ],
        "aqc_notifications": [
            ("idx_notifications_user_status", "user_id, status, created_at, id"),
            ("idx_notifications_related", "related_type, related_id, created_at, id"),
            ("idx_notifications_creator", "created_by, created_at, id"),
            ("idx_notifications_persistent", "user_id, is_persistent, dismissed_at, read_at, created_at, id"),
        ],
        "aqc_report_settings": [
            ("idx_report_settings_enabled_period", "enabled, period_key, id"),
            ("idx_report_settings_last_period", "last_period_key, last_run_at, id"),
        ],
        "aqc_report_logs": [
            ("idx_report_logs_period_scope", "period_key, period_token, scope_type, primary_shop_id, created_at, id"),
            ("idx_report_logs_scope_user", "scope_user_id, created_at, id"),
            ("idx_report_logs_scope_key", "scope_shop_ids_key, created_at, id"),
        ],
        "aqc_shop_target_months": [
            ("idx_shop_target_months_shop_year", "shop_id, year, month_key, id"),
        ],
        "aqc_shop_target_logs": [
            ("idx_shop_target_logs_shop_year", "shop_id, year, created_at, id"),
        ],
        "aqc_shop_target_presets": [
            ("idx_shop_target_presets_shop_updated", "shop_id, updated_at, id"),
        ],
    }

    with engine.begin() as conn:
        for table_name, table_indexes in index_specs.items():
            if not inspector.has_table(table_name):
                continue
            if dialect == "mysql":
                existing_indexes = {
                    row["Key_name"]
                    for row in conn.execute(text(f"SHOW INDEX FROM {table_name}")).mappings().all()
                }
            else:
                existing_indexes = {
                    row["name"]
                    for row in inspector.get_indexes(table_name)
                }
            for index_name, columns in table_indexes:
                if index_name in existing_indexes:
                    continue
                if dialect == "mysql":
                    conn.execute(text(f"CREATE INDEX {index_name} ON {table_name} ({columns})"))
                else:
                    conn.execute(text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns})"))


def _ensure_runtime_columns() -> None:
    inspector = inspect(engine)

    column_specs = {
        "aqc_symuse_states": {
            "return_path": "VARCHAR(500) NULL",
        },
        "aqc_goods_items": {
            "product_code": "VARCHAR(64) NOT NULL DEFAULT ''",
            "brand": "VARCHAR(120) NOT NULL DEFAULT ''",
            "series_name": "VARCHAR(120) NOT NULL DEFAULT ''",
            "model_name": "VARCHAR(191) NOT NULL DEFAULT ''",
            "model_attribute": "VARCHAR(8) NOT NULL DEFAULT '-'",
            "barcode": "VARCHAR(64) NOT NULL DEFAULT ''",
            "index_key": "VARCHAR(8) NOT NULL DEFAULT ''",
        },
        "aqc_users": {
            "aqc_role_key": "VARCHAR(40) NOT NULL DEFAULT 'aqc_sales'",
            "shop_id": "INTEGER NULL",
            "shop_ids": "VARCHAR(2000) NOT NULL DEFAULT '[]'",
            "employment_date": "VARCHAR(10) NULL",
        },
        "aqc_shops": {
            "manager_user_id": "INTEGER NULL",
            "schedule_enabled": "BOOLEAN NOT NULL DEFAULT 0",
            "target_enabled": "BOOLEAN NOT NULL DEFAULT 0",
            "report_enabled": "BOOLEAN NOT NULL DEFAULT 0",
        },
        "aqc_sale_records": {
            "sale_kind": "VARCHAR(20) NOT NULL DEFAULT 'goods'",
            "order_num": "VARCHAR(32) NOT NULL DEFAULT ''",
            "goods_id": "INTEGER NULL",
            "goods_code": "VARCHAR(64) NOT NULL DEFAULT ''",
            "goods_brand": "VARCHAR(120) NOT NULL DEFAULT ''",
            "goods_series": "VARCHAR(120) NOT NULL DEFAULT ''",
            "goods_model": "VARCHAR(191) NOT NULL DEFAULT ''",
            "goods_barcode": "VARCHAR(64) NOT NULL DEFAULT ''",
            "unit_price": "NUMERIC(12, 2) NOT NULL DEFAULT 0.00",
            "receivable_amount": "NUMERIC(12, 2) NOT NULL DEFAULT 0.00",
            "coupon_amount": "NUMERIC(12, 2) NOT NULL DEFAULT 0.00",
            "discount_rate": "NUMERIC(5, 2) NOT NULL DEFAULT 10.00",
            "shop_id": "INTEGER NULL",
            "shop_name": "VARCHAR(255) NOT NULL DEFAULT ''",
            "ship_shop_id": "INTEGER NULL",
            "ship_shop_name": "VARCHAR(255) NOT NULL DEFAULT ''",
            "salesperson": "VARCHAR(80) NOT NULL DEFAULT ''",
            "index_key": "VARCHAR(8) NOT NULL DEFAULT ''",
            "sale_status": "VARCHAR(20) NOT NULL DEFAULT 'normal'",
            "source_sale_record_id": "INTEGER NULL",
            "related_work_order_id": "INTEGER NULL",
            "returned_at": "DATETIME NULL",
        },
        "aqc_work_orders": {
            "shared_group_id": "INTEGER NULL",
            "shared_group_name": "VARCHAR(80) NOT NULL DEFAULT ''",
            "shared_by_id": "INTEGER NULL",
            "shared_by_name": "VARCHAR(80) NOT NULL DEFAULT ''",
            "sale_affects_inventory": "BOOLEAN NOT NULL DEFAULT 0",
        },
        "aqc_work_order_items": {
            "source_order_num": "VARCHAR(64) NOT NULL DEFAULT ''",
            "salesperson": "VARCHAR(80) NOT NULL DEFAULT ''",
            "sale_record_id": "INTEGER NULL",
            "line_type": "VARCHAR(20) NOT NULL DEFAULT 'default'",
            "sale_shop_id": "INTEGER NULL",
            "sale_shop_name": "VARCHAR(255) NOT NULL DEFAULT ''",
            "receive_shop_id": "INTEGER NULL",
            "receive_shop_name": "VARCHAR(255) NOT NULL DEFAULT ''",
            "ship_shop_id": "INTEGER NULL",
            "ship_shop_name": "VARCHAR(255) NOT NULL DEFAULT ''",
            "received_amount": "NUMERIC(12, 2) NOT NULL DEFAULT 0.00",
            "receivable_amount": "NUMERIC(12, 2) NOT NULL DEFAULT 0.00",
            "coupon_amount": "NUMERIC(12, 2) NOT NULL DEFAULT 0.00",
            "discount_rate": "NUMERIC(5, 2) NOT NULL DEFAULT 10.00",
            "channel": "VARCHAR(50) NOT NULL DEFAULT ''",
            "customer_name": "VARCHAR(120) NOT NULL DEFAULT ''",
        },
        "aqc_group_members": {
            "is_default": "BOOLEAN NOT NULL DEFAULT 0",
        },
        "aqc_notifications": {
            "is_persistent": "BOOLEAN NOT NULL DEFAULT 0",
            "is_read": "BOOLEAN NOT NULL DEFAULT 0",
            "read_at": "DATETIME NULL",
            "dismissed_at": "DATETIME NULL",
        },
        "aqc_report_settings": {
            "push_hour": "INTEGER NOT NULL DEFAULT 7",
            "push_minute": "INTEGER NOT NULL DEFAULT 0",
            "push_weekday": "INTEGER NOT NULL DEFAULT 0",
            "push_day_of_month": "INTEGER NOT NULL DEFAULT 1",
            "cleanup_hour": "INTEGER NOT NULL DEFAULT 23",
            "cleanup_minute": "INTEGER NOT NULL DEFAULT 59",
            "cleanup_weekday": "INTEGER NOT NULL DEFAULT 0",
            "cleanup_day_of_month": "INTEGER NOT NULL DEFAULT 1",
            "retention_days": "INTEGER NOT NULL DEFAULT 35",
            "last_cleanup_date": "VARCHAR(10) NOT NULL DEFAULT ''",
        },
    }

    added_schedule_enabled_column = False
    added_target_enabled_column = False
    added_report_enabled_column = False

    with engine.begin() as conn:
        live_inspector = inspect(conn)
        for table_name, columns in column_specs.items():
            if not inspector.has_table(table_name):
                continue
            existing_columns = {row["name"] for row in live_inspector.get_columns(table_name)}
            for column_name, ddl in columns.items():
                if column_name in existing_columns:
                    continue
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}"))
                existing_columns.add(column_name)
                if table_name == "aqc_shops" and column_name == "schedule_enabled":
                    added_schedule_enabled_column = True
                if table_name == "aqc_shops" and column_name == "target_enabled":
                    added_target_enabled_column = True
                if table_name == "aqc_shops" and column_name == "report_enabled":
                    added_report_enabled_column = True

        if added_schedule_enabled_column and DEFAULT_SCHEDULE_ENABLED_SHOP_NAMES:
            quoted_names = ", ".join(
                "'" + name.replace("'", "''") + "'"
                for name in DEFAULT_SCHEDULE_ENABLED_SHOP_NAMES
            )
            conn.execute(
                text(
                    "UPDATE aqc_shops "
                    "SET schedule_enabled = 1 "
                    "WHERE name IN (" + quoted_names + ") "
                    "AND (legacy_id IS NOT NULL OR shop_type IS NULL OR shop_type = 0)"
                )
            )

        if added_target_enabled_column and DEFAULT_TARGET_ENABLED_SHOP_NAMES:
            quoted_names = ", ".join(
                "'" + name.replace("'", "''") + "'"
                for name in DEFAULT_TARGET_ENABLED_SHOP_NAMES
            )
            conn.execute(
                text(
                    "UPDATE aqc_shops "
                    "SET target_enabled = 1 "
                    "WHERE name IN (" + quoted_names + ") "
                    "AND (legacy_id IS NOT NULL OR shop_type IS NULL OR shop_type = 0)"
                )
            )

        if added_report_enabled_column:
            conn.execute(
                text(
                    "UPDATE aqc_shops "
                    "SET report_enabled = 1 "
                    "WHERE name <> 'AQC Flow' "
                    "AND (legacy_id IS NOT NULL OR shop_type IS NULL OR shop_type = 0)"
                )
            )
            conn.execute(
                text(
                    "UPDATE aqc_shops "
                    "SET report_enabled = 0 "
                    "WHERE name = 'AQC Flow' OR (legacy_id IS NULL AND shop_type IN (1, 2, 3))"
                )
            )

        if inspector.has_table("aqc_users"):
            user_columns = {row["name"] for row in live_inspector.get_columns("aqc_users")}
            if "aqc_role_key" in user_columns:
                conn.execute(
                    text(
                        "UPDATE aqc_users SET aqc_role_key = CASE "
                        "WHEN aqc_role_key IN ('aqc_super_admin', 'aqc_admin') THEN 'aqc_admin' "
                        "WHEN aqc_role_key = 'aqc_operator' THEN 'aqc_manager' "
                        "WHEN aqc_role_key = 'aqc_engineer' THEN 'aqc_engineer' "
                        "WHEN aqc_role_key = 'aqc_viewer' THEN 'aqc_departed' "
                        "WHEN aqc_role_key = '' OR aqc_role_key IS NULL THEN 'aqc_sales' "
                        "ELSE aqc_role_key END"
                    )
                )


def _ensure_runtime_column_types() -> None:
    if engine.dialect.name.lower() != "mysql":
        return

    with engine.begin() as conn:
        inspector = inspect(conn)
        if not inspector.has_table("aqc_report_logs"):
            return
        column_rows = {
            str(row["Field"]): str(row["Type"]).lower()
            for row in conn.execute(text("SHOW COLUMNS FROM aqc_report_logs")).mappings().all()
        }
        payload_type = column_rows.get("payload_json", "")
        if payload_type == "text":
            conn.execute(text("ALTER TABLE aqc_report_logs MODIFY COLUMN payload_json LONGTEXT NOT NULL"))


def _quantize_sale_decimal(value: Decimal | int | float | str | None, default: str = "0.00") -> Decimal:
    return Decimal(str(value if value is not None else default)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _extract_sale_order_num(note: str | None) -> str:
    text = str(note or "").strip()
    match = SALE_ORDER_NUM_PATTERN.search(text)
    return match.group(1).strip()[:32] if match else ""


def _extract_sale_salesperson(note: str | None) -> str:
    text = str(note or "").strip()
    match = SALE_GUIDE_PATTERN.search(text)
    return match.group(1).strip()[:80] if match else ""


def _normalize_sale_index_key(series: str | None, brand: str | None, model: str | None) -> str:
    seed = f"{series or ''} {brand or ''} {model or ''}".strip()
    if not seed:
        return "#"
    for ch in seed:
        if ch.isascii() and ch.isalpha():
            return ch.upper()
        if ch.isdigit():
            return ch
    return "#"


def _backfill_sale_record_runtime_fields(db: Session) -> None:
    rows = (
        db.execute(
            select(AqcSaleRecord).where(
                or_(
                    AqcSaleRecord.sale_kind == "",
                    AqcSaleRecord.sale_kind.is_(None),
                    AqcSaleRecord.order_num == "",
                    AqcSaleRecord.receivable_amount == 0,
                    AqcSaleRecord.discount_rate == 0,
                    AqcSaleRecord.index_key == "",
                    AqcSaleRecord.shop_name == "",
                    AqcSaleRecord.ship_shop_name == "",
                    AqcSaleRecord.salesperson == "",
                    AqcSaleRecord.sale_status == "",
                    AqcSaleRecord.sale_status.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    changed = False
    for item in rows:
        item_changed = False

        if not (item.sale_kind or "").strip():
            item.sale_kind = "goods"
            item_changed = True

        if not (item.order_num or "").strip():
            extracted_order_num = _extract_sale_order_num(item.note)
            if extracted_order_num:
                item.order_num = extracted_order_num
            elif item.sold_at and item.id:
                item.order_num = f"Clo{item.sold_at.strftime('%Y%m%d')}{int(item.id):09d}"[:32]
            item_changed = True

        if not (item.shop_name or "").strip():
            fallback_shop_name = (item.customer_name or "").strip()
            if not fallback_shop_name and " / " in (item.channel or ""):
                fallback_shop_name = (item.channel or "").split(" / ", 1)[1].strip()
            if fallback_shop_name:
                item.shop_name = fallback_shop_name[:255]
                item_changed = True

        if item.ship_shop_id is None and item.shop_id is not None:
            item.ship_shop_id = int(item.shop_id)
            item_changed = True

        if not (item.ship_shop_name or "").strip():
            fallback_ship_shop_name = (item.shop_name or "").strip()
            if fallback_ship_shop_name:
                item.ship_shop_name = fallback_ship_shop_name[:255]
                item_changed = True

        if not (item.salesperson or "").strip():
            fallback_salesperson = _extract_sale_salesperson(item.note)
            if fallback_salesperson:
                item.salesperson = fallback_salesperson[:80]
                item_changed = True

        receivable_amount = _quantize_sale_decimal(item.receivable_amount or 0)
        if receivable_amount <= Decimal("0.00"):
            fallback_receivable = _quantize_sale_decimal(item.amount or 0)
            if fallback_receivable <= Decimal("0.00"):
                fallback_receivable = _quantize_sale_decimal((item.unit_price or 0) * max(int(item.quantity or 1), 1))
            item.receivable_amount = fallback_receivable
            receivable_amount = fallback_receivable
            item_changed = True

        if _quantize_sale_decimal(item.coupon_amount or 0) < Decimal("0.00"):
            item.coupon_amount = Decimal("0.00")
            item_changed = True

        discount_rate = _quantize_sale_decimal(item.discount_rate or 0)
        if discount_rate <= Decimal("0.00"):
            received_amount = _quantize_sale_decimal(item.amount or 0)
            if receivable_amount <= Decimal("0.00") or received_amount >= receivable_amount:
                item.discount_rate = Decimal("10.00")
            else:
                item.discount_rate = (received_amount / receivable_amount * Decimal("10")).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP,
                )
            item_changed = True

        if not (item.index_key or "").strip():
            item.index_key = _normalize_sale_index_key(item.goods_series, item.goods_brand, item.goods_model)
            item_changed = True

        if not (item.sale_status or "").strip():
            item.sale_status = "normal"
            item_changed = True

        changed = changed or item_changed

    if changed:
        db.commit()


def _backfill_goods_model_attributes(db: Session) -> None:
    rows = (
        db.execute(
            select(AqcGoodsItem).where(
                or_(
                    AqcGoodsItem.model_attribute.is_(None),
                    AqcGoodsItem.model_attribute == "",
                    ~AqcGoodsItem.model_attribute.in_(GOODS_ATTRIBUTE_VALUES),
                    AqcGoodsItem.model_name.like("%保"),
                    AqcGoodsItem.model_name.like("%畅"),
                )
            )
        )
        .scalars()
        .all()
    )
    changed = False

    for item in rows:
        clean_model, inferred_attribute = split_model_attribute(item.model_name, item.model_attribute)
        current_attribute = normalize_goods_attribute(item.model_attribute)
        next_attribute = inferred_attribute if current_attribute == GOODS_ATTRIBUTE_NONE else current_attribute
        next_name = compose_goods_name(item.brand, item.series_name, clean_model, item.name or "")

        if (item.model_name or "") != clean_model:
            item.model_name = clean_model
            changed = True
        if (item.model_attribute or GOODS_ATTRIBUTE_NONE) != next_attribute:
            item.model_attribute = next_attribute
            changed = True
        if (item.name or "") != next_name:
            item.name = next_name
            changed = True

    if changed:
        db.flush()


def _ensure_other_warehouses(db: Session, *, created_by: int | None = None) -> None:
    legacy_store_rows = db.execute(
        select(AqcShop).where(
            AqcShop.shop_type == SHOP_TYPE_OTHER_WAREHOUSE,
            or_(
                AqcShop.legacy_id.is_not(None),
                AqcShop.manager_user_id.is_not(None),
                and_(AqcShop.manager_name.is_not(None), AqcShop.manager_name != ""),
            ),
        )
    ).scalars().all()
    for item in legacy_store_rows:
        item.shop_type = 0

    existing_names = {
        str(name or "").strip()
        for name in db.execute(
            select(AqcShop.name).where(
                AqcShop.legacy_id.is_(None),
                AqcShop.shop_type == SHOP_TYPE_OTHER_WAREHOUSE,
            )
        ).scalars().all()
    }
    for name in DEFAULT_OTHER_WAREHOUSE_NAMES:
        clean_name = str(name or "").strip()[:255]
        if not clean_name or clean_name in existing_names:
            continue
        db.add(
            AqcShop(
                name=clean_name,
                shop_type=SHOP_TYPE_OTHER_WAREHOUSE,
                channel=1,
                status=1,
                is_enabled=True,
                created_by=created_by,
            )
        )
        existing_names.add(clean_name)
    db.flush()


def _acquire_init_lock():
    if engine.dialect.name.lower() != "mysql":
        return None

    conn = engine.connect()
    try:
        granted = conn.execute(
            text("SELECT GET_LOCK(:lock_name, :timeout_seconds)"),
            {"lock_name": INIT_DB_LOCK_NAME, "timeout_seconds": 60},
        ).scalar()
        if int(granted or 0) != 1:
            raise RuntimeError("数据库初始化锁获取失败")
        return conn
    except Exception:
        conn.close()
        raise


def _release_init_lock(lock_conn) -> None:
    if lock_conn is None:
        return
    try:
        lock_conn.execute(text("SELECT RELEASE_LOCK(:lock_name)"), {"lock_name": INIT_DB_LOCK_NAME})
    finally:
        lock_conn.close()


def _display_name(user: AqcUser | None) -> str:
    if user is None:
        return ""
    return (str(user.display_name or "").strip() or str(user.username or "").strip())[:80]


def _ensure_work_order_settings(db: Session) -> None:
    existing_rows = db.execute(select(AqcWorkOrderSetting)).scalars().all()
    existing_map = {str(item.order_type or "").strip(): item for item in existing_rows}
    transfer_approver = db.execute(
        select(AqcUser)
        .where(
            AqcUser.is_active.is_(True),
            AqcUser.aqc_role_key == "aqc_admin",
            or_(
                AqcUser.display_name.in_(DEFAULT_TRANSFER_APPROVER_DISPLAY_NAMES),
                AqcUser.username.in_(DEFAULT_TRANSFER_APPROVER_DISPLAY_NAMES),
            ),
        )
        .order_by(AqcUser.updated_at.desc(), AqcUser.id.asc())
        .limit(1)
    ).scalars().first()
    transfer_approver_name = _display_name(transfer_approver)
    for order_type in DEFAULT_WORK_ORDER_TYPES:
        row = existing_map.get(order_type)
        if row is None:
            row = AqcWorkOrderSetting(order_type=order_type)
            if order_type == "transfer" and transfer_approver is not None:
                row.approver_id = int(transfer_approver.id)
                row.approver_name = transfer_approver_name
            db.add(row)
            existing_map[order_type] = row
            continue
        if (
            order_type == "transfer"
            and transfer_approver is not None
            and not int(row.approver_id or 0)
        ):
            row.approver_id = int(transfer_approver.id)
            row.approver_name = transfer_approver_name


def init_db() -> None:
    lock_conn = _acquire_init_lock()
    db: Session | None = None
    try:
        Base.metadata.create_all(bind=engine)
        _ensure_runtime_columns()
        _ensure_runtime_column_types()
        _ensure_runtime_indexes()

        db = SessionLocal()
        _ensure_admin_user(db)
        admin = db.execute(select(AqcUser).where(AqcUser.username == settings.admin_username).limit(1)).scalars().first()
        if admin is not None:
            _ensure_permissions_and_roles(db, admin)
            _ensure_other_warehouses(db, created_by=admin.id)
            _ensure_report_settings(db, admin)
        else:
            _ensure_other_warehouses(db, created_by=None)
            _ensure_report_settings(db, None)
        _ensure_work_order_settings(db)
        _backfill_goods_model_attributes(db)
        _backfill_sale_record_runtime_fields(db)
        db.commit()
    except Exception:
        if db is not None:
            db.rollback()
        raise
    finally:
        if db is not None:
            db.close()
        _release_init_lock(lock_conn)
