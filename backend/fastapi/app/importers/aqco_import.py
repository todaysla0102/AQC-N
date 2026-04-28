from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..models import (
    AqcGoodsItem,
    AqcPermission,
    AqcRole,
    AqcRolePermission,
    AqcSaleRecord,
    AqcShop,
    AqcUser,
    AqcUserIdentity,
    AqcUserRole,
)
from ..security import normalize_username


INSERT_PATTERN = re.compile(r"^INSERT INTO `(?P<table>[^`]+)` VALUES (?P<values>.+);$")
CREATE_TABLE_PATTERN = re.compile(r"^CREATE TABLE `(?P<table>[^`]+)`", re.IGNORECASE)
ESSENTIAL_MIRROR_TABLES = {"shopping_order", "goods_item", "user_item"}
LEGACY_PHONE_PATTERN = re.compile(r"^1\d{10}$")


def _split_value_groups(raw: str) -> list[str]:
    groups: list[str] = []
    in_quote = False
    escaped = False
    depth = 0
    start = -1

    for index, ch in enumerate(raw):
        if in_quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == "'":
                in_quote = False
            continue

        if ch == "'":
            in_quote = True
            continue

        if ch == "(":
            if depth == 0:
                start = index
            depth += 1
            continue

        if ch == ")":
            depth -= 1
            if depth == 0 and start >= 0:
                groups.append(raw[start + 1 : index])
                start = -1
            continue

    return groups


def _split_fields(group_raw: str) -> list[str]:
    fields: list[str] = []
    in_quote = False
    escaped = False
    token: list[str] = []

    for ch in group_raw:
        if in_quote:
            token.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == "'":
                in_quote = False
            continue

        if ch == "'":
            in_quote = True
            token.append(ch)
            continue

        if ch == ",":
            fields.append("".join(token).strip())
            token = []
            continue

        token.append(ch)

    fields.append("".join(token).strip())
    return fields


def _decode_mysql_string(raw: str) -> str:
    value = raw
    value = value.replace("\\'", "'")
    value = value.replace('\\"', '"')
    value = value.replace("\\r", "\r")
    value = value.replace("\\n", "\n")
    value = value.replace("\\t", "\t")
    value = value.replace("\\0", "\0")
    value = value.replace("\\\\", "\\")
    return value


def _parse_field(token: str):
    upper = token.upper()
    if upper == "NULL":
        return None

    if token.startswith("'") and token.endswith("'"):
        return _decode_mysql_string(token[1:-1])

    if re.fullmatch(r"-?\d+", token):
        try:
            return int(token)
        except Exception:
            return token

    if re.fullmatch(r"-?\d+\.\d+", token):
        try:
            return float(token)
        except Exception:
            return token

    return token


def _normalize_slug(raw: str, fallback: str) -> str:
    value = (raw or "").strip().lower()
    if not value:
        value = fallback
    value = re.sub(r"[^a-z0-9._\-*]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or fallback


def _parse_datetime(raw: str | None) -> datetime | None:
    value = (raw or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except Exception:
            continue
    return None


def _to_decimal(value) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0.00")


def _to_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _load_rows_by_table(sql_path: Path, tables: set[str]) -> dict[str, list[list]]:
    rows_by_table: dict[str, list[list]] = {table: [] for table in tables}

    with sql_path.open("r", encoding="utf-8", errors="ignore") as fp:
        for raw_line in fp:
            line = raw_line.strip()
            if not line.startswith("INSERT INTO `"):
                continue
            match = INSERT_PATTERN.match(line)
            if match is None:
                continue

            table_name = match.group("table")
            if table_name not in tables:
                continue

            value_raw = match.group("values")
            for group in _split_value_groups(value_raw):
                tokens = _split_fields(group)
                rows_by_table[table_name].append([_parse_field(item) for item in tokens])

    return rows_by_table


def _strip_sql_comments(raw_sql: str) -> str:
    without_block = re.sub(r"/\*.*?\*/", "", raw_sql, flags=re.DOTALL)
    without_line = re.sub(r"(?m)^\s*--.*?$", "", without_block)
    return without_line


def _split_sql_statements(raw_sql: str) -> list[str]:
    statements: list[str] = []
    in_quote = False
    escaped = False
    token: list[str] = []

    for ch in raw_sql:
        token.append(ch)
        if in_quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == "'":
                in_quote = False
            continue

        if ch == "'":
            in_quote = True
            continue

        if ch == ";":
            statement = "".join(token).strip().rstrip(";").strip()
            token = []
            if statement:
                statements.append(statement)

    tail = "".join(token).strip()
    if tail:
        statements.append(tail)
    return statements


def _extract_sql_row_counts(sql_path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    with sql_path.open("r", encoding="utf-8", errors="ignore") as fp:
        for raw_line in fp:
            line = raw_line.strip()
            if not line.startswith("INSERT INTO `"):
                continue
            match = INSERT_PATTERN.match(line)
            if match is None:
                continue
            table_name = match.group("table")
            value_raw = match.group("values")
            row_count = len(_split_value_groups(value_raw))
            counts[table_name] = counts.get(table_name, 0) + row_count
    return counts


def _extract_source_tables(statements: list[str]) -> set[str]:
    tables: set[str] = set()
    for statement in statements:
        create_match = CREATE_TABLE_PATTERN.match(statement)
        if create_match is not None:
            tables.add(create_match.group("table"))
            continue
        insert_match = INSERT_PATTERN.match(statement + ";")
        if insert_match is not None:
            tables.add(insert_match.group("table"))
    return tables


def _mirror_statement(statement: str, rename_map: dict[str, str]) -> str:
    mirrored = statement
    for source_table, mirror_table in rename_map.items():
        mirrored = mirrored.replace(f"`{source_table}`", f"`{mirror_table}`")
    if CREATE_TABLE_PATTERN.match(mirrored) and "ROW_FORMAT" not in mirrored.upper():
        mirrored = f"{mirrored} ROW_FORMAT=DYNAMIC"
    return mirrored


def _value_at(row: list, index: int):
    if index < 0:
        index = len(row) + index
    if index < 0 or index >= len(row):
        return None
    return row[index]


def _ensure_essential_mirror_schema(db: Session, table_prefix: str) -> None:
    prefix = (table_prefix or "aqco_").strip() or "aqco_"
    ddl_statements = [
        f"""
        CREATE TABLE IF NOT EXISTS `{prefix}shopping_order` (
            `id` BIGINT NOT NULL,
            `user_id` BIGINT NOT NULL,
            `admin_id` BIGINT NULL,
            `user_pickup_id` BIGINT NULL,
            `community_leader_id` BIGINT NULL,
            `address_id` BIGINT NULL,
            `logistics_id` VARCHAR(50) NULL,
            `logistics_type` TINYINT NULL DEFAULT 1,
            `logistics_num` VARCHAR(191) NULL,
            `logistics_name` VARCHAR(191) NULL,
            `logistics_address` VARCHAR(255) NULL,
            `logistics_phone` VARCHAR(40) NULL,
            `total` DECIMAL(10, 2) NULL,
            `total_fee` DECIMAL(10, 2) NULL,
            `pocket` DECIMAL(10, 2) NULL,
            `score` INT NULL DEFAULT 0,
            `pay_type` INT NULL DEFAULT 0,
            `status` TINYINT NOT NULL DEFAULT 0,
            `is_import` TINYINT NULL DEFAULT 0,
            `order_num` VARCHAR(191) NOT NULL,
            `remark` VARCHAR(255) NULL,
            `created_at` DATETIME NULL,
            `updated_at` DATETIME NULL,
            PRIMARY KEY (`id`),
            KEY `idx_{prefix}shopping_order_num` (`order_num`),
            KEY `idx_{prefix}shopping_order_status` (`status`, `is_import`),
            KEY `idx_{prefix}shopping_order_created` (`created_at`),
            KEY `idx_{prefix}shopping_order_user` (`user_id`),
            KEY `idx_{prefix}shopping_order_admin` (`admin_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci ROW_FORMAT=DYNAMIC
        """,
        f"""
        CREATE TABLE IF NOT EXISTS `{prefix}goods_item` (
            `id` BIGINT NOT NULL,
            `name_ch` VARCHAR(191) NULL,
            `weight` INT NULL DEFAULT 0,
            `goodspec` VARCHAR(255) NULL,
            `status` INT NOT NULL DEFAULT 3,
            `putaway` TINYINT NULL DEFAULT 0,
            `admin_id` BIGINT NULL,
            `shop_id` BIGINT NULL,
            `created_at` DATETIME NULL,
            `updated_at` DATETIME NULL,
            `deleted_at` DATETIME NULL,
            PRIMARY KEY (`id`),
            KEY `idx_{prefix}goods_item_status` (`status`, `putaway`),
            KEY `idx_{prefix}goods_item_admin` (`admin_id`),
            KEY `idx_{prefix}goods_item_shop` (`shop_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci ROW_FORMAT=DYNAMIC
        """,
        f"""
        CREATE TABLE IF NOT EXISTS `{prefix}user_item` (
            `id` BIGINT NOT NULL,
            `name` VARCHAR(191) NULL,
            `mobile` VARCHAR(40) NULL,
            `user_pickup_id` BIGINT NULL,
            `guide_id` BIGINT NULL,
            `vip` TINYINT NULL DEFAULT 0,
            `user_rule_id` INT NULL DEFAULT 0,
            `created_at` DATETIME NULL,
            `updated_at` DATETIME NULL,
            PRIMARY KEY (`id`),
            KEY `idx_{prefix}user_item_mobile` (`mobile`),
            KEY `idx_{prefix}user_item_pickup` (`user_pickup_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci ROW_FORMAT=DYNAMIC
        """,
    ]

    bind = db.get_bind()
    with bind.begin() as conn:
        for ddl in ddl_statements:
            conn.exec_driver_sql(ddl)


def _upsert_essential_mirror_rows(db: Session, sql_path: Path, table_prefix: str) -> dict[str, int]:
    prefix = (table_prefix or "aqco_").strip() or "aqco_"
    rows = _load_rows_by_table(sql_path, ESSENTIAL_MIRROR_TABLES)
    stats = {
        "essentialRowsOrders": 0,
        "essentialRowsGoods": 0,
        "essentialRowsUsers": 0,
    }

    order_sql = text(
        f"""
        INSERT INTO `{prefix}shopping_order` (
            id, user_id, admin_id, user_pickup_id, community_leader_id, address_id,
            logistics_id, logistics_type, logistics_num, logistics_name, logistics_address,
            logistics_phone, total, total_fee, pocket, score, pay_type, status,
            is_import, order_num, remark, created_at, updated_at
        ) VALUES (
            :id, :user_id, :admin_id, :user_pickup_id, :community_leader_id, :address_id,
            :logistics_id, :logistics_type, :logistics_num, :logistics_name, :logistics_address,
            :logistics_phone, :total, :total_fee, :pocket, :score, :pay_type, :status,
            :is_import, :order_num, :remark, :created_at, :updated_at
        )
        ON DUPLICATE KEY UPDATE
            user_id = VALUES(user_id),
            admin_id = VALUES(admin_id),
            user_pickup_id = VALUES(user_pickup_id),
            community_leader_id = VALUES(community_leader_id),
            address_id = VALUES(address_id),
            logistics_id = VALUES(logistics_id),
            logistics_type = VALUES(logistics_type),
            logistics_num = VALUES(logistics_num),
            logistics_name = VALUES(logistics_name),
            logistics_address = VALUES(logistics_address),
            logistics_phone = VALUES(logistics_phone),
            total = VALUES(total),
            total_fee = VALUES(total_fee),
            pocket = VALUES(pocket),
            score = VALUES(score),
            pay_type = VALUES(pay_type),
            status = VALUES(status),
            is_import = VALUES(is_import),
            order_num = VALUES(order_num),
            remark = VALUES(remark),
            created_at = VALUES(created_at),
            updated_at = VALUES(updated_at)
        """
    )
    for row in rows["shopping_order"]:
        order_id = _to_int(_value_at(row, 0), 0)
        if order_id <= 0:
            continue
        db.execute(
            order_sql,
            {
                "id": order_id,
                "user_id": _to_int(_value_at(row, 1), 0),
                "admin_id": _to_int(_value_at(row, 46), 0) or None,
                "user_pickup_id": _to_int(_value_at(row, 47), 0) or None,
                "community_leader_id": _to_int(_value_at(row, 48), 0) or None,
                "address_id": _to_int(_value_at(row, 6), 0) or None,
                "logistics_id": str(_value_at(row, 5) or "").strip() or None,
                "logistics_type": _to_int(_value_at(row, 7), 1),
                "logistics_num": str(_value_at(row, 9) or "").strip() or None,
                "logistics_name": str(_value_at(row, 11) or "").strip() or None,
                "logistics_address": str(_value_at(row, 12) or "").strip() or None,
                "logistics_phone": str(_value_at(row, 13) or "").strip() or None,
                "total": _to_decimal(_value_at(row, 19)),
                "total_fee": _to_decimal(_value_at(row, 20)),
                "pocket": _to_decimal(_value_at(row, 21)),
                "score": _to_int(_value_at(row, 34), 0),
                "pay_type": _to_int(_value_at(row, 37), 0),
                "status": _to_int(_value_at(row, 24), 0),
                "is_import": _to_int(_value_at(row, 40), 0),
                "order_num": str(_value_at(row, 29) or "").strip() or f"legacy-order-{order_id}",
                "remark": str(_value_at(row, 39) or "").strip() or None,
                "created_at": _parse_datetime(str(_value_at(row, 44) or "")),
                "updated_at": _parse_datetime(str(_value_at(row, 45) or "")),
            },
        )
        stats["essentialRowsOrders"] += 1

    goods_sql = text(
        f"""
        INSERT INTO `{prefix}goods_item` (
            id, name_ch, weight, goodspec, status, putaway,
            admin_id, shop_id, created_at, updated_at, deleted_at
        ) VALUES (
            :id, :name_ch, :weight, :goodspec, :status, :putaway,
            :admin_id, :shop_id, :created_at, :updated_at, :deleted_at
        )
        ON DUPLICATE KEY UPDATE
            name_ch = VALUES(name_ch),
            weight = VALUES(weight),
            goodspec = VALUES(goodspec),
            status = VALUES(status),
            putaway = VALUES(putaway),
            admin_id = VALUES(admin_id),
            shop_id = VALUES(shop_id),
            created_at = VALUES(created_at),
            updated_at = VALUES(updated_at),
            deleted_at = VALUES(deleted_at)
        """
    )
    for row in rows["goods_item"]:
        goods_id = _to_int(_value_at(row, 0), 0)
        if goods_id <= 0:
            continue
        db.execute(
            goods_sql,
            {
                "id": goods_id,
                "name_ch": str(_value_at(row, 1) or "").strip() or None,
                "weight": _to_int(_value_at(row, 8), 0),
                "goodspec": str(_value_at(row, 51) or "").strip() or None,
                "status": _to_int(_value_at(row, 45), 3),
                "putaway": _to_int(_value_at(row, 44), 0),
                "admin_id": _to_int(_value_at(row, 33), 0) or None,
                "shop_id": _to_int(_value_at(row, 34), 0) or None,
                "created_at": _parse_datetime(str(_value_at(row, 53) or "")),
                "updated_at": _parse_datetime(str(_value_at(row, 54) or "")),
                "deleted_at": _parse_datetime(str(_value_at(row, 55) or "")),
            },
        )
        stats["essentialRowsGoods"] += 1

    user_sql = text(
        f"""
        INSERT INTO `{prefix}user_item` (
            id, name, mobile, user_pickup_id, guide_id, vip, user_rule_id, created_at, updated_at
        ) VALUES (
            :id, :name, :mobile, :user_pickup_id, :guide_id, :vip, :user_rule_id, :created_at, :updated_at
        )
        ON DUPLICATE KEY UPDATE
            name = VALUES(name),
            mobile = VALUES(mobile),
            user_pickup_id = VALUES(user_pickup_id),
            guide_id = VALUES(guide_id),
            vip = VALUES(vip),
            user_rule_id = VALUES(user_rule_id),
            created_at = VALUES(created_at),
            updated_at = VALUES(updated_at)
        """
    )
    for row in rows["user_item"]:
        user_id = _to_int(_value_at(row, 0), 0)
        if user_id <= 0:
            continue
        db.execute(
            user_sql,
            {
                "id": user_id,
                "name": str(_value_at(row, 1) or "").strip() or None,
                "mobile": str(_value_at(row, 12) or "").strip() or None,
                "user_pickup_id": _to_int(_value_at(row, 8), 0) or None,
                "guide_id": _to_int(_value_at(row, 9), 0) or None,
                "vip": _to_int(_value_at(row, 42), 0),
                "user_rule_id": _to_int(_value_at(row, 44), 0),
                "created_at": _parse_datetime(str(_value_at(row, -3) or "")),
                "updated_at": _parse_datetime(str(_value_at(row, -2) or "")),
            },
        )
        stats["essentialRowsUsers"] += 1

    db.commit()
    return stats


def import_aqco_admin_data(db: Session, sql_path: str, assigned_by: int | None = None) -> dict[str, int]:
    source = Path(sql_path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"SQL 文件不存在: {source}")

    required_tables = {
        "admin_users",
        "admin_roles",
        "admin_permissions",
        "admin_role_users",
        "admin_role_permissions",
    }
    rows = _load_rows_by_table(source, required_tables)

    stats = {
        "rolesCreated": 0,
        "rolesUpdated": 0,
        "permissionsCreated": 0,
        "permissionsUpdated": 0,
        "usersCreated": 0,
        "usersUpdated": 0,
        "rolePermissionLinked": 0,
        "userRoleLinked": 0,
        "rowsUsers": len(rows["admin_users"]),
        "rowsRoles": len(rows["admin_roles"]),
        "rowsPermissions": len(rows["admin_permissions"]),
        "rowsRoleUsers": len(rows["admin_role_users"]),
        "rowsRolePermissions": len(rows["admin_role_permissions"]),
    }

    permission_map: dict[int, AqcPermission] = {}
    for row in rows["admin_permissions"]:
        if len(row) < 3:
            continue
        legacy_id = int(row[0])
        name = str(row[1] or f"权限{legacy_id}")[:120]
        slug = _normalize_slug(str(row[2] or ""), f"legacy.permission.{legacy_id}")
        description = str((row[4] or row[3] or ""))[:255]

        permission = db.execute(select(AqcPermission).where(AqcPermission.code == slug).limit(1)).scalars().first()
        if permission is None:
            permission = AqcPermission(code=slug, name=name, description=description)
            db.add(permission)
            db.flush()
            stats["permissionsCreated"] += 1
        else:
            permission.name = name
            permission.description = description
            stats["permissionsUpdated"] += 1
        permission_map[legacy_id] = permission

    role_map: dict[int, AqcRole] = {}
    for row in rows["admin_roles"]:
        if len(row) < 3:
            continue
        legacy_id = int(row[0])
        name = str(row[1] or f"角色{legacy_id}")[:80]
        slug = _normalize_slug(str(row[2] or ""), f"legacy-role-{legacy_id}")

        role = db.execute(select(AqcRole).where(AqcRole.slug == slug).limit(1)).scalars().first()
        if role is None:
            role = AqcRole(name=name, slug=slug, description=f"从 AQC-O 导入: {name}", is_system=False)
            db.add(role)
            db.flush()
            stats["rolesCreated"] += 1
        else:
            role.name = name
            stats["rolesUpdated"] += 1
        role_map[legacy_id] = role

    for row in rows["admin_role_permissions"]:
        if len(row) < 2:
            continue
        legacy_role_id = int(row[0])
        legacy_permission_id = int(row[1])
        role = role_map.get(legacy_role_id)
        permission = permission_map.get(legacy_permission_id)
        if role is None or permission is None:
            continue

        exists = db.execute(
            select(AqcRolePermission.id).where(
                AqcRolePermission.role_id == role.id,
                AqcRolePermission.permission_id == permission.id,
            )
        ).scalar()
        if exists is None:
            db.add(AqcRolePermission(role_id=role.id, permission_id=permission.id))
            stats["rolePermissionLinked"] += 1

    user_map: dict[int, AqcUser] = {}
    for row in rows["admin_users"]:
        if len(row) < 4:
            continue
        legacy_id = int(row[0])
        username = normalize_username(str(row[1] or f"legacy_{legacy_id}"))[:50]
        legacy_phone = username if LEGACY_PHONE_PATTERN.fullmatch(username) else None
        password_hash = str(row[2] or "").strip() or None
        display_name = str(row[3] or username).strip()[:80]
        avatar_url = str(row[4] or "").strip()[:500]

        user = db.execute(select(AqcUser).where(AqcUser.username == username).limit(1)).scalars().first()
        if user is None:
            user = AqcUser(
                username=username,
                email=None,
                password_hash=password_hash,
                display_name=display_name,
                avatar_url=avatar_url,
                phone=legacy_phone,
                role="user",
                vip=0,
                vip_level=0,
                user_rule_id=5,
                auth_source="aqc_o_legacy",
                is_active=True,
            )
            db.add(user)
            db.flush()
            stats["usersCreated"] += 1
        else:
            if password_hash:
                user.password_hash = password_hash
            user.display_name = display_name
            user.avatar_url = avatar_url
            if legacy_phone:
                user.phone = legacy_phone
            user.is_active = True
            if not user.auth_source:
                user.auth_source = "aqc_o_legacy"
            stats["usersUpdated"] += 1

        if user.identity is None:
            db.add(
                AqcUserIdentity(
                    user_id=user.id,
                    name=user.display_name,
                    avatar=user.avatar_url,
                    mobile=user.phone,
                    sex=0,
                    vip=user.vip,
                )
            )
        else:
            user.identity.name = user.display_name or user.identity.name
            user.identity.avatar = user.avatar_url or user.identity.avatar
            user.identity.mobile = user.phone or user.identity.mobile
            user.identity.vip = user.vip

        user_map[legacy_id] = user

    for row in rows["admin_role_users"]:
        if len(row) < 2:
            continue
        legacy_role_id = int(row[0])
        legacy_user_id = int(row[1])
        role = role_map.get(legacy_role_id)
        user = user_map.get(legacy_user_id)
        if role is None or user is None:
            continue

        exists = db.execute(
            select(AqcUserRole.id).where(
                AqcUserRole.user_id == user.id,
                AqcUserRole.role_id == role.id,
            )
        ).scalar()
        if exists is None:
            db.add(AqcUserRole(user_id=user.id, role_id=role.id, assigned_by=assigned_by))
            stats["userRoleLinked"] += 1

        if role.slug in {"administrator", "admin"}:
            user.role = "admin"
            user.vip = max(user.vip or 0, 2)

    return stats


def import_aqco_goods_shop_data(db: Session, sql_path: str, assigned_by: int | None = None) -> dict[str, int]:
    source = Path(sql_path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"SQL 文件不存在: {source}")

    required_tables = {
        "user_pickup",
        "goods_item",
    }
    rows = _load_rows_by_table(source, required_tables)

    stats = {
        "shopsCreated": 0,
        "shopsUpdated": 0,
        "goodsCreated": 0,
        "goodsUpdated": 0,
        "goodsLegacyDeleted": 0,
        "rowsShops": len(rows["user_pickup"]),
        "rowsGoods": len(rows["goods_item"]),
    }

    shop_map: dict[int, AqcShop] = {}
    for row in rows["user_pickup"]:
        if len(row) < 28:
            continue

        legacy_id = _to_int(row[0], 0)
        if legacy_id <= 0:
            continue

        shop = db.execute(select(AqcShop).where(AqcShop.legacy_id == legacy_id).limit(1)).scalars().first()
        if shop is None:
            shop = AqcShop(
                legacy_id=legacy_id,
                name=str(row[4] or f"店铺{legacy_id}")[:255],
            )
            db.add(shop)
            db.flush()
            stats["shopsCreated"] += 1
        else:
            stats["shopsUpdated"] += 1

        shop.name = str(row[4] or f"店铺{legacy_id}")[:255]
        shop.image = str(row[5] or "")[:500]
        shop.phone = str(row[6] or "").strip()[:40] or None
        shop.address = str(row[7] or "")[:255]
        shop.province = str(row[8] or "").strip()[:100] or None
        shop.city = str(row[10] or "").strip()[:100] or None
        shop.district = str(row[12] or "").strip()[:100] or None
        shop.latitude = str(row[14] or "").strip()[:50] or None
        shop.longitude = str(row[15] or "").strip()[:50] or None
        shop.business_hours = str(row[17] or "").strip()[:100] or None
        shop.brand_ids = str(row[3] or "")
        shop.status = _to_int(row[19], 1)
        shop.shop_type = _to_int(row[20], 0)
        shop.division = str(row[21] or "").strip()[:120] or None
        shop.channel = _to_int(row[22], 1)
        shop.manager_name = str(row[21] or "").strip()[:120] or None
        shop.share_code = str(row[24] or "").strip()[:255] or None
        shop.is_enabled = _to_int(row[25], 1) == 1
        if assigned_by is not None:
            shop.created_by = assigned_by

        created_at = _parse_datetime(str(row[26] or ""))
        if created_at is not None:
            shop.created_at = created_at
        updated_at = _parse_datetime(str(row[27] or ""))
        if updated_at is not None:
            shop.updated_at = updated_at

        shop_map[legacy_id] = shop

    for row in rows["goods_item"]:
        if len(row) < 56:
            continue

        deleted_at = _parse_datetime(str(row[55] or ""))
        if deleted_at is not None:
            stats["goodsLegacyDeleted"] += 1

        legacy_id = _to_int(row[0], 0)
        if legacy_id <= 0:
            continue

        goods_item = db.execute(select(AqcGoodsItem).where(AqcGoodsItem.legacy_id == legacy_id).limit(1)).scalars().first()
        if goods_item is None:
            goods_item = AqcGoodsItem(
                legacy_id=legacy_id,
                name=str(row[1] or f"商品{legacy_id}")[:191],
            )
            db.add(goods_item)
            db.flush()
            stats["goodsCreated"] += 1
        else:
            stats["goodsUpdated"] += 1

        legacy_shop_id = _to_int(row[34], 0)
        mapped_shop = shop_map.get(legacy_shop_id) if legacy_shop_id > 0 else None

        goods_item.name = str(row[1] or f"商品{legacy_id}")[:191]
        goods_item.original_price = _to_decimal(row[2])
        goods_item.price = _to_decimal(row[3])
        goods_item.sale_price = _to_decimal(row[4])
        goods_item.score = _to_int(row[5], 0)
        goods_item.description = str(row[6] or "")
        goods_item.stock = _to_int(row[7], 0)
        goods_item.cover_image = str(row[12] or "")[:500]
        goods_item.image_list = str(row[13] or "[]")
        goods_item.category_id = _to_int(row[29], 0)
        goods_item.legacy_admin_id = _to_int(row[33], 0) or None
        goods_item.shop_id = mapped_shop.id if mapped_shop is not None else None
        goods_item.detail = str(row[36] or "")
        goods_item.sale_num = _to_int(row[37], 0)
        goods_item.sort = _to_int(row[42], 0)
        goods_item.putaway = _to_int(row[43], 0)
        goods_item.status = _to_int(row[44], 3)
        goods_item.goods_type = _to_int(row[49], 0)
        goods_item.remark = str(row[50] or "")[:255]
        goods_item.goodspec = str(row[51] or "").strip()[:255] or None
        goods_item.score_rule = str(row[52] or "")
        if assigned_by is not None:
            goods_item.created_by = assigned_by

        created_at = _parse_datetime(str(row[53] or ""))
        if created_at is not None:
            goods_item.created_at = created_at
        updated_at = _parse_datetime(str(row[54] or ""))
        if updated_at is not None:
            goods_item.updated_at = updated_at

    return stats


def import_aqco_sales_data(db: Session, sql_path: str, assigned_by: int | None = None) -> dict[str, int]:
    source = Path(sql_path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"SQL 文件不存在: {source}")

    required_tables = {
        "shopping_order_clock",
        "shopping_order_clock_item",
        "admin_users",
        "user_pickup",
    }
    rows = _load_rows_by_table(source, required_tables)

    stats = {
        "recordsCreated": 0,
        "recordsSkippedDuplicate": 0,
        "recordsSkippedInvalid": 0,
        "rowsOrders": len(rows["shopping_order_clock"]),
        "rowsOrderItems": len(rows["shopping_order_clock_item"]),
        "rowsAdmins": len(rows["admin_users"]),
        "rowsShops": len(rows["user_pickup"]),
    }

    admin_username_by_legacy_id: dict[int, str] = {}
    admin_name_by_legacy_id: dict[int, str] = {}
    for row in rows["admin_users"]:
        if len(row) < 4:
            continue
        legacy_id = _to_int(row[0], 0)
        if legacy_id <= 0:
            continue
        admin_username_by_legacy_id[legacy_id] = normalize_username(str(row[1] or ""))
        admin_name_by_legacy_id[legacy_id] = str(row[3] or row[1] or "")

    local_user_id_by_username = {
        item.username: item.id
        for item in db.execute(select(AqcUser).where(AqcUser.username.is_not(None))).scalars().all()
    }

    shop_name_by_legacy_id: dict[int, str] = {}
    for row in rows["user_pickup"]:
        if len(row) < 5:
            continue
        legacy_id = _to_int(row[0], 0)
        if legacy_id <= 0:
            continue
        shop_name_by_legacy_id[legacy_id] = str(row[4] or f"店铺{legacy_id}").strip()

    quantity_by_order_id: dict[int, int] = {}
    for row in rows["shopping_order_clock_item"]:
        if len(row) < 23:
            continue
        order_id = _to_int(row[1], 0)
        if order_id <= 0:
            continue
        item_status = _to_int(row[22], 1)
        if item_status != 1:
            continue
        quantity = _to_int(row[7], 0)
        if quantity <= 0:
            quantity = 1
        quantity_by_order_id[order_id] = quantity_by_order_id.get(order_id, 0) + quantity

    channel_map = {
        1: "门店收银",
        2: "商场收银",
    }

    existing_order_ids: set[int] = set()
    note_rows = db.execute(select(AqcSaleRecord.note).where(AqcSaleRecord.note.like("AQC-O#order:%"))).scalars().all()
    for note in note_rows:
        text = str(note or "")
        match = re.search(r"AQC-O#order:(\d+)", text)
        if match:
            existing_order_ids.add(int(match.group(1)))

    for row in rows["shopping_order_clock"]:
        if len(row) < 17:
            stats["recordsSkippedInvalid"] += 1
            continue

        order_id = _to_int(row[0], 0)
        if order_id <= 0:
            stats["recordsSkippedInvalid"] += 1
            continue

        if order_id in existing_order_ids:
            stats["recordsSkippedDuplicate"] += 1
            continue

        status = _to_int(row[13], 1)
        if status != 1:
            stats["recordsSkippedInvalid"] += 1
            continue

        amount = _to_decimal(row[10])
        if amount <= Decimal("0.00"):
            amount = _to_decimal(row[6])
        if amount <= Decimal("0.00"):
            amount = _to_decimal(row[5])
        if amount <= Decimal("0.00"):
            stats["recordsSkippedInvalid"] += 1
            continue

        sold_at = _parse_datetime(str(row[16] or "")) or datetime.utcnow()
        order_num = str(row[1] or "").strip()
        legacy_admin_id = _to_int(row[11], 0)
        legacy_shop_id = _to_int(row[12], 0)
        channel = _to_int(row[14], 0)

        username = admin_username_by_legacy_id.get(legacy_admin_id, "")
        admin_name = admin_name_by_legacy_id.get(legacy_admin_id, username or "")
        local_user_id = local_user_id_by_username.get(username) if username else None

        shop_name = shop_name_by_legacy_id.get(legacy_shop_id, "")
        channel_name = channel_map.get(channel, f"渠道{channel}" if channel > 0 else "未知渠道")
        if shop_name:
            channel_name = f"{channel_name} / {shop_name}"

        note = f"AQC-O#order:{order_id};单号:{order_num};导购:{admin_name}"

        db.add(
            AqcSaleRecord(
                sold_at=sold_at,
                order_num=order_num[:32],
                amount=amount,
                receivable_amount=amount,
                coupon_amount=Decimal("0.00"),
                discount_rate=Decimal("10.00"),
                quantity=max(1, quantity_by_order_id.get(order_id, 1)),
                channel=channel_name[:50],
                shop_name=shop_name[:255],
                salesperson=admin_name[:80],
                index_key="#",
                customer_name=shop_name[:120],
                note=note,
                created_by=local_user_id if local_user_id is not None else assigned_by,
            )
        )
        existing_order_ids.add(order_id)
        stats["recordsCreated"] += 1

    return stats


def import_aqco_full_mirror_data(
    db: Session,
    sql_path: str,
    table_prefix: str = "aqco_",
) -> dict[str, int | str]:
    source = Path(sql_path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"SQL 文件不存在: {source}")

    raw_sql = source.read_text(encoding="utf-8", errors="ignore")
    statements = _split_sql_statements(_strip_sql_comments(raw_sql))
    if not statements:
        return {
            "mirrorStatements": 0,
            "mirrorTables": 0,
            "mirrorRowsSource": 0,
            "mirrorRowsTarget": 0,
            "mirrorTablesMismatch": 0,
            "mirrorTablePrefix": table_prefix,
        }

    source_tables = _extract_source_tables(statements)
    insert_counts = _extract_sql_row_counts(source)
    if not source_tables:
        source_tables = set(insert_counts.keys())

    normalized_prefix = (table_prefix or "aqco_").strip()
    if not normalized_prefix:
        normalized_prefix = "aqco_"

    rename_map = {table_name: f"{normalized_prefix}{table_name}" for table_name in sorted(source_tables)}
    bind = db.get_bind()

    executed = 0
    failed = 0
    with bind.begin() as conn:
        conn.exec_driver_sql("SET FOREIGN_KEY_CHECKS = 0")
        for statement in statements:
            clean = statement.strip()
            if not clean:
                continue
            upper = clean.upper()
            if upper.startswith("SET NAMES"):
                try:
                    conn.exec_driver_sql(clean)
                    executed += 1
                except Exception:
                    failed += 1
                continue

            mirrored = _mirror_statement(clean, rename_map)
            # Escape '%' for DBAPI string interpolation while keeping literal '%' semantics.
            # This avoids failures on legacy payloads like "%(null)s" in inserted text fields.
            try:
                conn.exec_driver_sql(mirrored.replace("%", "%%"))
                executed += 1
            except Exception:
                failed += 1
        conn.exec_driver_sql("SET FOREIGN_KEY_CHECKS = 1")

    target_rows_total = 0
    mismatch_count = 0
    missing_table_count = 0
    for source_table in sorted(source_tables):
        mirror_table = rename_map[source_table]
        source_rows = int(insert_counts.get(source_table, 0))
        try:
            target_rows = int(db.execute(text(f"SELECT COUNT(*) FROM `{mirror_table}`")).scalar() or 0)
        except Exception:
            target_rows = 0
            missing_table_count += 1
        target_rows_total += target_rows
        if target_rows != source_rows:
            mismatch_count += 1

    source_rows_total = sum(int(value) for value in insert_counts.values())

    essential_stats = {"essentialRowsOrders": 0, "essentialRowsGoods": 0, "essentialRowsUsers": 0}
    if any(name in insert_counts for name in ESSENTIAL_MIRROR_TABLES):
        _ensure_essential_mirror_schema(db, normalized_prefix)
        essential_stats = _upsert_essential_mirror_rows(db, source, normalized_prefix)
        target_rows_total = 0
        mismatch_count = 0
        missing_table_count = 0
        for source_table in sorted(source_tables):
            mirror_table = rename_map[source_table]
            source_rows = int(insert_counts.get(source_table, 0))
            try:
                target_rows = int(db.execute(text(f"SELECT COUNT(*) FROM `{mirror_table}`")).scalar() or 0)
            except Exception:
                target_rows = 0
                missing_table_count += 1
            target_rows_total += target_rows
            if target_rows != source_rows:
                mismatch_count += 1

    return {
        "mirrorStatements": executed,
        "mirrorStatementsFailed": failed,
        "mirrorTables": len(source_tables),
        "mirrorRowsSource": int(source_rows_total),
        "mirrorRowsTarget": int(target_rows_total),
        "mirrorTablesMismatch": int(mismatch_count),
        "mirrorTablesMissing": int(missing_table_count),
        "mirrorTablePrefix": normalized_prefix,
        **essential_stats,
    }


def check_aqco_full_mirror_data(
    db: Session,
    sql_path: str,
    table_prefix: str = "aqco_",
) -> dict[str, int | str]:
    source = Path(sql_path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"SQL 文件不存在: {source}")

    insert_counts = _extract_sql_row_counts(source)
    source_tables = sorted(insert_counts.keys())
    normalized_prefix = (table_prefix or "aqco_").strip() or "aqco_"

    source_rows_total = 0
    target_rows_total = 0
    mismatch_count = 0
    missing_table_count = 0

    for source_table in source_tables:
        mirror_table = f"{normalized_prefix}{source_table}"
        source_rows = int(insert_counts.get(source_table, 0))
        source_rows_total += source_rows
        try:
            target_rows = int(db.execute(text(f"SELECT COUNT(*) FROM `{mirror_table}`")).scalar() or 0)
        except Exception:
            target_rows = 0
            missing_table_count += 1
        target_rows_total += target_rows
        if target_rows != source_rows:
            mismatch_count += 1

    return {
        "checkTables": len(source_tables),
        "checkRowsSource": int(source_rows_total),
        "checkRowsTarget": int(target_rows_total),
        "checkTablesMismatch": int(mismatch_count),
        "checkTablesMissing": int(missing_table_count),
        "mirrorTablePrefix": normalized_prefix,
    }
