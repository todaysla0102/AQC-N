from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.utcnow()


class AqcUser(Base):
    __tablename__ = "aqc_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_user_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True, nullable=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str] = mapped_column(String(80), default="", server_default="")
    avatar_url: Mapped[str] = mapped_column(String(500), default="", server_default="")
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="user", server_default="user")
    aqc_role_key: Mapped[str] = mapped_column(String(40), default="aqc_sales", server_default="aqc_sales", index=True)
    shop_id: Mapped[int | None] = mapped_column(ForeignKey("aqc_shops.id", ondelete="SET NULL"), nullable=True, index=True)
    shop_ids: Mapped[str] = mapped_column(String(2000), default="[]", server_default="[]")
    employment_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    vip: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    vip_level: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    user_rule_id: Mapped[int] = mapped_column(Integer, default=5, server_default="5")
    auth_source: Mapped[str] = mapped_column(String(30), default="symuse_account", server_default="symuse_account")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    identity: Mapped[AqcUserIdentity | None] = relationship(back_populates="user", uselist=False, cascade="all,delete-orphan")
    sessions: Mapped[list[AqcAuthSession]] = relationship(back_populates="user", cascade="all,delete-orphan")
    group_memberships: Mapped[list[AqcGroupMember]] = relationship(back_populates="user", cascade="all,delete-orphan")
    assigned_shop: Mapped[AqcShop | None] = relationship(
        back_populates="assigned_users",
        foreign_keys=[shop_id],
    )
    role_links: Mapped[list[AqcUserRole]] = relationship(
        back_populates="user",
        cascade="all,delete-orphan",
        foreign_keys="AqcUserRole.user_id",
    )
    sale_records: Mapped[list[AqcSaleRecord]] = relationship(back_populates="creator")
    created_shops: Mapped[list[AqcShop]] = relationship(
        back_populates="creator",
        foreign_keys="AqcShop.created_by",
    )
    created_goods_items: Mapped[list[AqcGoodsItem]] = relationship(back_populates="creator")
    created_work_orders: Mapped[list[AqcWorkOrder]] = relationship(
        back_populates="applicant",
        foreign_keys="AqcWorkOrder.applicant_id",
    )
    assigned_work_orders: Mapped[list[AqcWorkOrder]] = relationship(
        back_populates="approver",
        foreign_keys="AqcWorkOrder.approver_id",
    )
    shared_work_orders: Mapped[list[AqcWorkOrder]] = relationship(
        back_populates="shared_by_user",
        foreign_keys="AqcWorkOrder.shared_by_id",
    )
    work_order_actions: Mapped[list[AqcWorkOrderAction]] = relationship(back_populates="actor")
    notifications: Mapped[list[AqcNotification]] = relationship(
        back_populates="user",
        foreign_keys="AqcNotification.user_id",
        cascade="all,delete-orphan",
    )
    sent_notifications: Mapped[list[AqcNotification]] = relationship(
        back_populates="creator",
        foreign_keys="AqcNotification.created_by",
    )


class AqcUserIdentity(Base):
    __tablename__ = "aqc_user_identity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("aqc_users.id", ondelete="CASCADE"), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80), default="", server_default="")
    avatar: Mapped[str] = mapped_column(String(500), default="", server_default="")
    mobile: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sex: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    born: Mapped[str | None] = mapped_column(String(50), nullable=True)
    province: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    area: Mapped[str | None] = mapped_column(String(100), nullable=True)
    level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    vip: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    user: Mapped[AqcUser] = relationship(back_populates="identity")


class AqcAuthSession(Base):
    __tablename__ = "aqc_auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("aqc_users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_agent: Mapped[str] = mapped_column(String(255), default="", server_default="")
    ip_address: Mapped[str] = mapped_column(String(45), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_used_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[AqcUser] = relationship(back_populates="sessions")


class AqcSymuseState(Base):
    __tablename__ = "aqc_symuse_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    state_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    redirect_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    return_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    user_agent: Mapped[str] = mapped_column(String(255), default="", server_default="")
    ip_address: Mapped[str] = mapped_column(String(45), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    consumed_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)


class AqcGroup(Base):
    __tablename__ = "aqc_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    # MySQL 8 does not allow DEFAULT on TEXT columns.
    description: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("aqc_users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    memberships: Mapped[list[AqcGroupMember]] = relationship(back_populates="group", cascade="all,delete-orphan")
    shared_work_orders: Mapped[list[AqcWorkOrder]] = relationship(back_populates="shared_group")


class AqcGroupMember(Base):
    __tablename__ = "aqc_group_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("aqc_groups.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("aqc_users.id", ondelete="CASCADE"), index=True)
    member_role: Mapped[str] = mapped_column(String(20), default="member", server_default="member")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    group: Mapped[AqcGroup] = relationship(back_populates="memberships")
    user: Mapped[AqcUser] = relationship(back_populates="group_memberships")

    __table_args__ = (UniqueConstraint("group_id", "user_id", name="uq_aqc_group_user"),)


class AqcRole(Base):
    __tablename__ = "aqc_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(255), default="", server_default="")
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    permission_links: Mapped[list[AqcRolePermission]] = relationship(back_populates="role", cascade="all,delete-orphan")
    user_links: Mapped[list[AqcUserRole]] = relationship(back_populates="role", cascade="all,delete-orphan")


class AqcPermission(Base):
    __tablename__ = "aqc_permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(255), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    role_links: Mapped[list[AqcRolePermission]] = relationship(back_populates="permission", cascade="all,delete-orphan")


class AqcRolePermission(Base):
    __tablename__ = "aqc_role_permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("aqc_roles.id", ondelete="CASCADE"), index=True)
    permission_id: Mapped[int] = mapped_column(ForeignKey("aqc_permissions.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    role: Mapped[AqcRole] = relationship(back_populates="permission_links")
    permission: Mapped[AqcPermission] = relationship(back_populates="role_links")

    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uq_aqc_role_permission"),)


class AqcUserRole(Base):
    __tablename__ = "aqc_user_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("aqc_users.id", ondelete="CASCADE"), index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("aqc_roles.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    assigned_by: Mapped[int | None] = mapped_column(ForeignKey("aqc_users.id", ondelete="SET NULL"), nullable=True)

    user: Mapped[AqcUser] = relationship(back_populates="role_links", foreign_keys=[user_id])
    role: Mapped[AqcRole] = relationship(back_populates="user_links")

    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_aqc_user_role"),)


class AqcSaleRecord(Base):
    __tablename__ = "aqc_sale_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sold_at: Mapped[datetime] = mapped_column(DateTime, index=True, default=utcnow)
    sale_kind: Mapped[str] = mapped_column(String(20), default="goods", server_default="goods", index=True)
    order_num: Mapped[str] = mapped_column(String(32), default="", server_default="", index=True)
    goods_id: Mapped[int | None] = mapped_column(ForeignKey("aqc_goods_items.id", ondelete="SET NULL"), nullable=True, index=True)
    goods_code: Mapped[str] = mapped_column(String(64), default="", server_default="", index=True)
    goods_brand: Mapped[str] = mapped_column(String(120), default="", server_default="", index=True)
    goods_series: Mapped[str] = mapped_column(String(120), default="", server_default="", index=True)
    goods_model: Mapped[str] = mapped_column(String(191), default="", server_default="", index=True)
    goods_barcode: Mapped[str] = mapped_column(String(64), default="", server_default="", index=True)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), server_default="0.00")
    receivable_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), server_default="0.00")
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), server_default="0.00")
    coupon_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), server_default="0.00")
    discount_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("10.00"), server_default="10.00")
    quantity: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    channel: Mapped[str] = mapped_column(String(50), default="", server_default="")
    shop_id: Mapped[int | None] = mapped_column(ForeignKey("aqc_shops.id", ondelete="SET NULL"), nullable=True, index=True)
    shop_name: Mapped[str] = mapped_column(String(255), default="", server_default="")
    ship_shop_id: Mapped[int | None] = mapped_column(ForeignKey("aqc_shops.id", ondelete="SET NULL"), nullable=True, index=True)
    ship_shop_name: Mapped[str] = mapped_column(String(255), default="", server_default="")
    salesperson: Mapped[str] = mapped_column(String(80), default="", server_default="", index=True)
    index_key: Mapped[str] = mapped_column(String(8), default="", server_default="", index=True)
    sale_status: Mapped[str] = mapped_column(String(20), default="normal", server_default="normal", index=True)
    source_sale_record_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    related_work_order_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    customer_name: Mapped[str] = mapped_column(String(120), default="", server_default="")
    note: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("aqc_users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    goods: Mapped[AqcGoodsItem | None] = relationship(back_populates="sale_records")
    creator: Mapped[AqcUser | None] = relationship(back_populates="sale_records")


class AqcShop(Base):
    __tablename__ = "aqc_shops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    legacy_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    image: Mapped[str] = mapped_column(String(500), default="", server_default="")
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    address: Mapped[str] = mapped_column(String(255), default="", server_default="")
    province: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    district: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latitude: Mapped[str | None] = mapped_column(String(50), nullable=True)
    longitude: Mapped[str | None] = mapped_column(String(50), nullable=True)
    business_hours: Mapped[str | None] = mapped_column(String(100), nullable=True)
    brand_ids: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    shop_type: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    channel: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    schedule_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    target_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    report_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    manager_user_id: Mapped[int | None] = mapped_column(ForeignKey("aqc_users.id", ondelete="SET NULL"), nullable=True)
    manager_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    division: Mapped[str | None] = mapped_column(String(120), nullable=True)
    share_code: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("aqc_users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    creator: Mapped[AqcUser | None] = relationship(
        back_populates="created_shops",
        foreign_keys=[created_by],
    )
    manager_user: Mapped[AqcUser | None] = relationship(
        foreign_keys=[manager_user_id],
    )
    goods_items: Mapped[list[AqcGoodsItem]] = relationship(back_populates="shop")
    inventory_entries: Mapped[list[AqcGoodsInventory]] = relationship(back_populates="shop", cascade="all,delete-orphan")
    assigned_users: Mapped[list[AqcUser]] = relationship(
        back_populates="assigned_shop",
        foreign_keys="AqcUser.shop_id",
    )


class AqcGoodsItem(Base):
    __tablename__ = "aqc_goods_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    legacy_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(191), index=True)
    product_code: Mapped[str] = mapped_column(String(64), default="", server_default="", index=True)
    brand: Mapped[str] = mapped_column(String(120), default="", server_default="", index=True)
    series_name: Mapped[str] = mapped_column(String(120), default="", server_default="", index=True)
    model_name: Mapped[str] = mapped_column(String(191), default="", server_default="", index=True)
    model_attribute: Mapped[str] = mapped_column(String(8), default="-", server_default="-", index=True)
    barcode: Mapped[str] = mapped_column(String(64), default="", server_default="", index=True)
    index_key: Mapped[str] = mapped_column(String(8), default="", server_default="", index=True)
    category_id: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cover_image: Mapped[str] = mapped_column(String(500), default="", server_default="")
    image_list: Mapped[str] = mapped_column(Text, default="[]")
    description: Mapped[str] = mapped_column(Text, default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), server_default="0.00")
    original_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), server_default="0.00")
    sale_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), server_default="0.00")
    score: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    stock: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    sale_num: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    sort: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    putaway: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    status: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    goods_type: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    remark: Mapped[str] = mapped_column(String(255), default="", server_default="")
    goodspec: Mapped[str | None] = mapped_column(String(255), nullable=True)
    score_rule: Mapped[str] = mapped_column(Text, default="")
    legacy_admin_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shop_id: Mapped[int | None] = mapped_column(ForeignKey("aqc_shops.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("aqc_users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    shop: Mapped[AqcShop | None] = relationship(back_populates="goods_items")
    creator: Mapped[AqcUser | None] = relationship(back_populates="created_goods_items")
    sale_records: Mapped[list[AqcSaleRecord]] = relationship(back_populates="goods")
    inventory_entries: Mapped[list[AqcGoodsInventory]] = relationship(back_populates="goods_item", cascade="all,delete-orphan")
    work_order_items: Mapped[list[AqcWorkOrderItem]] = relationship(back_populates="goods_item")


class AqcGoodsInventory(Base):
    __tablename__ = "aqc_goods_inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goods_item_id: Mapped[int] = mapped_column(ForeignKey("aqc_goods_items.id", ondelete="CASCADE"), index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("aqc_shops.id", ondelete="CASCADE"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    goods_item: Mapped[AqcGoodsItem] = relationship(back_populates="inventory_entries")
    shop: Mapped[AqcShop] = relationship(back_populates="inventory_entries")

    __table_args__ = (UniqueConstraint("goods_item_id", "shop_id", name="uq_aqc_goods_inventory_goods_shop"),)


class AqcInventoryLog(Base):
    __tablename__ = "aqc_inventory_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goods_item_id: Mapped[int | None] = mapped_column(ForeignKey("aqc_goods_items.id", ondelete="SET NULL"), nullable=True, index=True)
    goods_name: Mapped[str] = mapped_column(String(191), default="", server_default="")
    goods_model: Mapped[str] = mapped_column(String(191), default="", server_default="", index=True)
    shop_id: Mapped[int | None] = mapped_column(ForeignKey("aqc_shops.id", ondelete="SET NULL"), nullable=True, index=True)
    shop_name: Mapped[str] = mapped_column(String(255), default="", server_default="")
    change_content: Mapped[str] = mapped_column(String(255), default="", server_default="")
    quantity_before: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    quantity_after: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("aqc_users.id", ondelete="SET NULL"), nullable=True, index=True)
    operator_name: Mapped[str] = mapped_column(String(80), default="", server_default="")
    related_type: Mapped[str] = mapped_column(String(40), default="", server_default="", index=True)
    related_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class AqcWorkOrder(Base):
    __tablename__ = "aqc_work_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_num: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    order_type: Mapped[str] = mapped_column(String(20), index=True, default="transfer", server_default="transfer")
    status: Mapped[str] = mapped_column(String(20), index=True, default="draft", server_default="draft")
    reason: Mapped[str] = mapped_column(String(255), default="", server_default="")
    form_date: Mapped[datetime] = mapped_column(DateTime, index=True, default=utcnow)
    source_shop_id: Mapped[int | None] = mapped_column(ForeignKey("aqc_shops.id", ondelete="SET NULL"), nullable=True, index=True)
    source_shop_name: Mapped[str] = mapped_column(String(255), default="", server_default="")
    target_shop_id: Mapped[int | None] = mapped_column(ForeignKey("aqc_shops.id", ondelete="SET NULL"), nullable=True, index=True)
    target_shop_name: Mapped[str] = mapped_column(String(255), default="", server_default="")
    supplier_name: Mapped[str] = mapped_column(String(255), default="", server_default="")
    partner_name: Mapped[str] = mapped_column(String(255), default="", server_default="")
    applicant_id: Mapped[int] = mapped_column(ForeignKey("aqc_users.id", ondelete="CASCADE"), index=True)
    applicant_name: Mapped[str] = mapped_column(String(80), default="", server_default="")
    approver_id: Mapped[int | None] = mapped_column(ForeignKey("aqc_users.id", ondelete="SET NULL"), nullable=True, index=True)
    approver_name: Mapped[str] = mapped_column(String(80), default="", server_default="")
    shared_group_id: Mapped[int | None] = mapped_column(ForeignKey("aqc_groups.id", ondelete="SET NULL"), nullable=True, index=True)
    shared_group_name: Mapped[str] = mapped_column(String(80), default="", server_default="")
    shared_by_id: Mapped[int | None] = mapped_column(ForeignKey("aqc_users.id", ondelete="SET NULL"), nullable=True, index=True)
    shared_by_name: Mapped[str] = mapped_column(String(80), default="", server_default="")
    approval_comment: Mapped[str] = mapped_column(String(1000), default="", server_default="")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sale_affects_inventory: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    stock_applied: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    applicant: Mapped[AqcUser] = relationship(back_populates="created_work_orders", foreign_keys=[applicant_id])
    approver: Mapped[AqcUser | None] = relationship(back_populates="assigned_work_orders", foreign_keys=[approver_id])
    shared_by_user: Mapped[AqcUser | None] = relationship(back_populates="shared_work_orders", foreign_keys=[shared_by_id])
    shared_group: Mapped[AqcGroup | None] = relationship(back_populates="shared_work_orders", foreign_keys=[shared_group_id])
    source_shop: Mapped[AqcShop | None] = relationship(foreign_keys=[source_shop_id])
    target_shop: Mapped[AqcShop | None] = relationship(foreign_keys=[target_shop_id])
    items: Mapped[list[AqcWorkOrderItem]] = relationship(back_populates="work_order", cascade="all,delete-orphan")
    actions: Mapped[list[AqcWorkOrderAction]] = relationship(back_populates="work_order", cascade="all,delete-orphan")
    allocation_draft: Mapped[AqcWorkOrderAllocationDraft | None] = relationship(
        back_populates="work_order",
        uselist=False,
        cascade="all,delete-orphan",
    )


class AqcWorkOrderItem(Base):
    __tablename__ = "aqc_work_order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("aqc_work_orders.id", ondelete="CASCADE"), index=True)
    sort_index: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    goods_id: Mapped[int | None] = mapped_column(ForeignKey("aqc_goods_items.id", ondelete="SET NULL"), nullable=True, index=True)
    goods_name: Mapped[str] = mapped_column(String(191), default="", server_default="")
    product_code: Mapped[str] = mapped_column(String(64), default="", server_default="")
    source_order_num: Mapped[str] = mapped_column(String(64), default="", server_default="", index=True)
    salesperson: Mapped[str] = mapped_column(String(80), default="", server_default="")
    sale_record_id: Mapped[int | None] = mapped_column(ForeignKey("aqc_sale_records.id", ondelete="SET NULL"), nullable=True, index=True)
    line_type: Mapped[str] = mapped_column(String(20), default="default", server_default="default", index=True)
    sale_shop_id: Mapped[int | None] = mapped_column(ForeignKey("aqc_shops.id", ondelete="SET NULL"), nullable=True, index=True)
    sale_shop_name: Mapped[str] = mapped_column(String(255), default="", server_default="")
    receive_shop_id: Mapped[int | None] = mapped_column(ForeignKey("aqc_shops.id", ondelete="SET NULL"), nullable=True, index=True)
    receive_shop_name: Mapped[str] = mapped_column(String(255), default="", server_default="")
    ship_shop_id: Mapped[int | None] = mapped_column(ForeignKey("aqc_shops.id", ondelete="SET NULL"), nullable=True, index=True)
    ship_shop_name: Mapped[str] = mapped_column(String(255), default="", server_default="")
    brand: Mapped[str] = mapped_column(String(120), default="", server_default="")
    series_name: Mapped[str] = mapped_column(String(120), default="", server_default="")
    barcode: Mapped[str] = mapped_column(String(64), default="", server_default="")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), server_default="0.00")
    received_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), server_default="0.00")
    receivable_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), server_default="0.00")
    coupon_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), server_default="0.00")
    discount_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("10.00"), server_default="10.00")
    quantity: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), server_default="0.00")
    channel: Mapped[str] = mapped_column(String(50), default="", server_default="")
    customer_name: Mapped[str] = mapped_column(String(120), default="", server_default="")
    remark: Mapped[str] = mapped_column(String(255), default="", server_default="")
    is_new_goods: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    work_order: Mapped[AqcWorkOrder] = relationship(back_populates="items")
    goods_item: Mapped[AqcGoodsItem | None] = relationship(back_populates="work_order_items")


class AqcWorkOrderAction(Base):
    __tablename__ = "aqc_work_order_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("aqc_work_orders.id", ondelete="CASCADE"), index=True)
    action_type: Mapped[str] = mapped_column(String(20), default="saved", server_default="saved")
    status_from: Mapped[str] = mapped_column(String(20), default="", server_default="")
    status_to: Mapped[str] = mapped_column(String(20), default="", server_default="")
    comment: Mapped[str] = mapped_column(String(1000), default="", server_default="")
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("aqc_users.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_name: Mapped[str] = mapped_column(String(80), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    work_order: Mapped[AqcWorkOrder] = relationship(back_populates="actions")
    actor: Mapped[AqcUser | None] = relationship(back_populates="work_order_actions")


class AqcWorkOrderAllocationDraft(Base):
    __tablename__ = "aqc_work_order_allocation_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("aqc_work_orders.id", ondelete="CASCADE"), unique=True, index=True)
    source_shop_id: Mapped[int | None] = mapped_column(ForeignKey("aqc_shops.id", ondelete="SET NULL"), nullable=True, index=True)
    source_shop_name: Mapped[str] = mapped_column(String(255), default="", server_default="")
    approver_id: Mapped[int | None] = mapped_column(ForeignKey("aqc_users.id", ondelete="SET NULL"), nullable=True, index=True)
    approver_name: Mapped[str] = mapped_column(String(80), default="", server_default="")
    shared_group_id: Mapped[int | None] = mapped_column(ForeignKey("aqc_groups.id", ondelete="SET NULL"), nullable=True, index=True)
    shared_group_name: Mapped[str] = mapped_column(String(80), default="", server_default="")
    target_shop_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    allocations_json: Mapped[str] = mapped_column(Text, default="[]")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("aqc_users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_name: Mapped[str] = mapped_column(String(80), default="", server_default="")
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("aqc_users.id", ondelete="SET NULL"), nullable=True, index=True)
    updated_by_name: Mapped[str] = mapped_column(String(80), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    work_order: Mapped[AqcWorkOrder] = relationship(back_populates="allocation_draft")
    source_shop: Mapped[AqcShop | None] = relationship(foreign_keys=[source_shop_id])
    approver: Mapped[AqcUser | None] = relationship(foreign_keys=[approver_id])
    shared_group: Mapped[AqcGroup | None] = relationship(foreign_keys=[shared_group_id])
    creator: Mapped[AqcUser | None] = relationship(foreign_keys=[created_by])
    updater: Mapped[AqcUser | None] = relationship(foreign_keys=[updated_by])


class AqcWorkOrderSchedule(Base):
    __tablename__ = "aqc_work_order_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_type: Mapped[str] = mapped_column(String(20), default="sale", server_default="sale", index=True)
    period_key: Mapped[str] = mapped_column(String(20), default="day", server_default="day", index=True)
    shop_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    shop_names_json: Mapped[str] = mapped_column(Text, default="[]")
    applicant_id: Mapped[int] = mapped_column(ForeignKey("aqc_users.id", ondelete="CASCADE"), index=True)
    applicant_name: Mapped[str] = mapped_column(String(80), default="", server_default="")
    approver_id: Mapped[int | None] = mapped_column(ForeignKey("aqc_users.id", ondelete="SET NULL"), nullable=True, index=True)
    approver_name: Mapped[str] = mapped_column(String(80), default="", server_default="")
    shared_group_id: Mapped[int | None] = mapped_column(ForeignKey("aqc_groups.id", ondelete="SET NULL"), nullable=True, index=True)
    shared_group_name: Mapped[str] = mapped_column(String(80), default="", server_default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", index=True)
    last_period_key: Mapped[str] = mapped_column(String(32), default="", server_default="", index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("aqc_users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    applicant: Mapped[AqcUser] = relationship(foreign_keys=[applicant_id])
    approver: Mapped[AqcUser | None] = relationship(foreign_keys=[approver_id])
    creator: Mapped[AqcUser | None] = relationship(foreign_keys=[created_by])
    shared_group: Mapped[AqcGroup | None] = relationship(foreign_keys=[shared_group_id])


class AqcWorkOrderSetting(Base):
    __tablename__ = "aqc_work_order_settings"
    __table_args__ = (
        UniqueConstraint("order_type", name="uq_aqc_work_order_settings_order_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_type: Mapped[str] = mapped_column(String(20), default="transfer", server_default="transfer", index=True)
    approver_id: Mapped[int | None] = mapped_column(ForeignKey("aqc_users.id", ondelete="SET NULL"), nullable=True, index=True)
    approver_name: Mapped[str] = mapped_column(String(80), default="", server_default="")
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("aqc_users.id", ondelete="SET NULL"), nullable=True, index=True)
    updated_by_name: Mapped[str] = mapped_column(String(80), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    approver: Mapped[AqcUser | None] = relationship(foreign_keys=[approver_id])
    updater: Mapped[AqcUser | None] = relationship(foreign_keys=[updated_by])


class AqcOrderUploadLog(Base):
    __tablename__ = "aqc_order_upload_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    legacy_order_id: Mapped[int] = mapped_column(BigInteger, index=True)
    legacy_order_num: Mapped[str] = mapped_column(String(80), default="", server_default="", index=True)
    legacy_order_item_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    generated_order_num: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    cargo_name: Mapped[str] = mapped_column(String(255), default="", server_default="")
    request_payload: Mapped[str] = mapped_column(Text, default="")
    response_payload: Mapped[str] = mapped_column(Text, default="")
    success: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("aqc_users.id", ondelete="SET NULL"), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    creator: Mapped[AqcUser | None] = relationship()


class AqcNotification(Base):
    __tablename__ = "aqc_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("aqc_users.id", ondelete="CASCADE"), index=True)
    notification_type: Mapped[str] = mapped_column(String(40), default="", server_default="", index=True)
    title: Mapped[str] = mapped_column(String(120), default="", server_default="")
    content: Mapped[str] = mapped_column(String(500), default="", server_default="")
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending", index=True)
    is_persistent: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    related_type: Mapped[str] = mapped_column(String(40), default="", server_default="", index=True)
    related_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    payload_json: Mapped[str] = mapped_column(Text().with_variant(LONGTEXT(), "mysql"), default="{}")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("aqc_users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_name: Mapped[str] = mapped_column(String(80), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    handled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)

    user: Mapped[AqcUser] = relationship(back_populates="notifications", foreign_keys=[user_id])
    creator: Mapped[AqcUser | None] = relationship(back_populates="sent_notifications", foreign_keys=[created_by])


class AqcReportSetting(Base):
    __tablename__ = "aqc_report_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    period_key: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", index=True)
    recipient_role_keys_json: Mapped[str] = mapped_column(Text, default="[]")
    recipient_user_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    push_hour: Mapped[int] = mapped_column(Integer, default=7, server_default="7")
    push_minute: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    push_weekday: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    push_day_of_month: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    cleanup_hour: Mapped[int] = mapped_column(Integer, default=23, server_default="23")
    cleanup_minute: Mapped[int] = mapped_column(Integer, default=59, server_default="59")
    cleanup_weekday: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cleanup_day_of_month: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    retention_days: Mapped[int] = mapped_column(Integer, default=35, server_default="35")
    last_period_key: Mapped[str] = mapped_column(String(32), default="", server_default="", index=True)
    last_cleanup_date: Mapped[str] = mapped_column(String(10), default="", server_default="", index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("aqc_users.id", ondelete="SET NULL"), nullable=True, index=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("aqc_users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    creator: Mapped[AqcUser | None] = relationship(foreign_keys=[created_by])
    updater: Mapped[AqcUser | None] = relationship(foreign_keys=[updated_by])


class AqcReportLog(Base):
    __tablename__ = "aqc_report_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    period_key: Mapped[str] = mapped_column(String(20), default="", server_default="", index=True)
    period_token: Mapped[str] = mapped_column(String(32), default="", server_default="", index=True)
    period_label: Mapped[str] = mapped_column(String(40), default="", server_default="")
    range_label: Mapped[str] = mapped_column(String(120), default="", server_default="")
    scope_type: Mapped[str] = mapped_column(String(20), default="", server_default="", index=True)
    scope_label: Mapped[str] = mapped_column(String(255), default="", server_default="")
    scope_shop_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    scope_shop_ids_key: Mapped[str] = mapped_column(String(500), default="", server_default="", index=True)
    primary_shop_id: Mapped[int | None] = mapped_column(ForeignKey("aqc_shops.id", ondelete="SET NULL"), nullable=True, index=True)
    scope_user_id: Mapped[int | None] = mapped_column(ForeignKey("aqc_users.id", ondelete="SET NULL"), nullable=True, index=True)
    scope_user_name: Mapped[str] = mapped_column(String(80), default="", server_default="")
    report_title: Mapped[str] = mapped_column(String(160), default="", server_default="", index=True)
    window_start: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    window_end: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    highlights_json: Mapped[str] = mapped_column(Text, default="[]")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    generated_by: Mapped[int | None] = mapped_column(ForeignKey("aqc_users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    primary_shop: Mapped[AqcShop | None] = relationship(foreign_keys=[primary_shop_id])
    scope_user: Mapped[AqcUser | None] = relationship(foreign_keys=[scope_user_id])
    generator: Mapped[AqcUser | None] = relationship(foreign_keys=[generated_by])


class AqcShopScheduleEntry(Base):
    __tablename__ = "aqc_shop_schedule_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("aqc_shops.id", ondelete="CASCADE"), index=True)
    work_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    month_key: Mapped[str] = mapped_column(String(7), default="", server_default="", index=True)
    shift_type: Mapped[str] = mapped_column(String(20), default="morning", server_default="morning", index=True)
    salesperson_id: Mapped[int] = mapped_column(ForeignKey("aqc_users.id", ondelete="CASCADE"), index=True)
    salesperson_name: Mapped[str] = mapped_column(String(80), default="", server_default="")
    salesperson_username: Mapped[str] = mapped_column(String(50), default="", server_default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("aqc_users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    shop: Mapped[AqcShop] = relationship(foreign_keys=[shop_id])
    salesperson: Mapped[AqcUser] = relationship(foreign_keys=[salesperson_id])
    creator: Mapped[AqcUser | None] = relationship(foreign_keys=[created_by])

    __table_args__ = (
        UniqueConstraint("shop_id", "work_date", "shift_type", "salesperson_id", name="uq_aqc_shop_schedule_entry"),
    )


class AqcShopScheduleLog(Base):
    __tablename__ = "aqc_shop_schedule_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("aqc_shops.id", ondelete="CASCADE"), index=True)
    month_key: Mapped[str] = mapped_column(String(7), default="", server_default="", index=True)
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("aqc_users.id", ondelete="SET NULL"), nullable=True, index=True)
    operator_name: Mapped[str] = mapped_column(String(80), default="", server_default="")
    summary: Mapped[str] = mapped_column(String(255), default="", server_default="")
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    shop: Mapped[AqcShop] = relationship(foreign_keys=[shop_id])
    operator: Mapped[AqcUser | None] = relationship(foreign_keys=[operator_id])


class AqcShopTargetMonth(Base):
    __tablename__ = "aqc_shop_target_months"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("aqc_shops.id", ondelete="CASCADE"), index=True)
    year: Mapped[int] = mapped_column(Integer, default=0, server_default="0", index=True)
    month_key: Mapped[str] = mapped_column(String(7), default="", server_default="", index=True)
    target_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), server_default="0.00")
    stages_json: Mapped[str] = mapped_column(Text, default="[]")
    model_goals_json: Mapped[str] = mapped_column(Text, default="[]")
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("aqc_users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    shop: Mapped[AqcShop] = relationship(foreign_keys=[shop_id])
    updater: Mapped[AqcUser | None] = relationship(foreign_keys=[updated_by])

    __table_args__ = (
        UniqueConstraint("shop_id", "month_key", name="uq_aqc_shop_target_month"),
    )


class AqcShopTargetPreset(Base):
    __tablename__ = "aqc_shop_target_presets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("aqc_shops.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120), default="", server_default="")
    models_json: Mapped[str] = mapped_column(Text, default="[]")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("aqc_users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    shop: Mapped[AqcShop] = relationship(foreign_keys=[shop_id])
    creator: Mapped[AqcUser | None] = relationship(foreign_keys=[created_by])


class AqcShopTargetLog(Base):
    __tablename__ = "aqc_shop_target_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("aqc_shops.id", ondelete="CASCADE"), index=True)
    year: Mapped[int] = mapped_column(Integer, default=0, server_default="0", index=True)
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("aqc_users.id", ondelete="SET NULL"), nullable=True, index=True)
    operator_name: Mapped[str] = mapped_column(String(80), default="", server_default="")
    summary: Mapped[str] = mapped_column(String(255), default="", server_default="")
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    shop: Mapped[AqcShop] = relationship(foreign_keys=[shop_id])
    operator: Mapped[AqcUser | None] = relationship(foreign_keys=[operator_id])
