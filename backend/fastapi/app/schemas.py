from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class MessageResponse(BaseModel):
    success: bool
    message: str


class IdentityOut(BaseModel):
    name: str
    avatar: str
    mobile: str | None = None
    sex: int
    sexName: str
    born: str | None = None
    province: str | None = None
    city: str | None = None
    area: str | None = None
    level: str | None = None
    vip: int


class UserOut(BaseModel):
    id: int
    externalUserId: int | None = None
    username: str
    email: str | None = None
    displayName: str
    avatarUrl: str
    phone: str | None = None
    role: str
    vip: int
    vipLevel: int
    userRuleId: int
    authSource: str
    createdAt: str
    updatedAt: str
    lastLoginAt: str | None
    aqcRoleKey: str = "aqc_sales"
    aqcRoleName: str = "销售员"
    shopId: int | None = None
    shopIds: list[int] = Field(default_factory=list)
    shopName: str = ""
    shopNames: list[str] = Field(default_factory=list)
    employmentDate: str | None = None
    dataScope: str = "shop"
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    identity: IdentityOut


class UserOptionOut(BaseModel):
    id: int
    username: str
    displayName: str
    aqcRoleKey: str = "aqc_sales"
    aqcRoleName: str = "销售员"


class UserOptionListResponse(BaseModel):
    success: bool
    options: list[UserOptionOut]


class AccountProfileUpdateRequest(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    phone: str | None = Field(default=None, max_length=20)
    displayName: str = Field(min_length=1, max_length=80)


class AccountPasswordChangeRequest(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class LoginResponse(MessageResponse):
    user: UserOut | None = None
    token: str | None = None
    tokenType: str | None = None
    expiresAt: str | None = None
    sessionId: int | None = None
    redirectTo: str | None = None


class SymuseExchangeRequest(BaseModel):
    code: str = Field(min_length=16, max_length=200)
    state: str | None = Field(default=None, min_length=8, max_length=400)


class SymuseQrSessionRequest(BaseModel):
    sessionToken: str = Field(min_length=16, max_length=256)


class SymuseQrSessionApproveRequest(SymuseQrSessionRequest):
    loginOnceOnly: bool = True


class SymuseQrSessionInspectResponse(MessageResponse):
    status: str = "pending"
    expiresAt: str | None = None
    serviceLabel: str = ""
    deviceLabel: str = ""
    scannedAt: str | None = None
    approvedAt: str | None = None
    isExpired: bool = False


class SymuseStatePrepareRequest(BaseModel):
    redirectUri: str | None = Field(default=None, max_length=500)
    returnPath: str | None = Field(default=None, max_length=500)


class SymuseStatePrepareResponse(MessageResponse):
    state: str | None = None
    expiresAt: str | None = None
    authPage: str | None = None
    authUrl: str | None = None


class LocalLoginRequest(BaseModel):
    account: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=128)


class AuthCheckResponse(BaseModel):
    success: bool
    isAuthenticated: bool
    user: UserOut | None = None
    session: SessionOut | None = None


class MeResponse(BaseModel):
    success: bool
    user: UserOut


class IdentityUpdateRequest(BaseModel):
    displayName: str | None = Field(default=None, max_length=80)
    avatarUrl: str | None = Field(default=None, max_length=500)
    mobile: str | None = Field(default=None, max_length=20)
    sex: int | None = Field(default=None, ge=0, le=2)
    born: str | None = Field(default=None, max_length=50)
    province: str | None = Field(default=None, max_length=100)
    city: str | None = Field(default=None, max_length=100)
    area: str | None = Field(default=None, max_length=100)
    level: str | None = Field(default=None, max_length=50)
    vip: int | None = Field(default=None, ge=0, le=10)
    vipLevel: int | None = Field(default=None, ge=0, le=100)
    userRuleId: int | None = Field(default=None, ge=0, le=1000)


class GroupCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=2000)
    inviteUserIds: list[int] = Field(default_factory=list)


class GroupUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=2000)
    isActive: bool | None = None


class GroupMemberAddRequest(BaseModel):
    userId: int = Field(gt=0)
    memberRole: Literal["owner", "admin", "member"] = "member"


class GroupInviteRequest(BaseModel):
    userIds: list[int] = Field(default_factory=list)


class GroupOut(BaseModel):
    id: int
    name: str
    description: str
    isActive: bool
    createdBy: int | None
    createdAt: str
    updatedAt: str
    memberRole: str | None = None
    isDefault: bool = False


class GroupListResponse(BaseModel):
    success: bool
    groups: list[GroupOut]


class GroupMemberOut(BaseModel):
    userId: int
    username: str
    displayName: str
    avatarUrl: str
    role: str
    vip: int
    memberRole: str
    joinedAt: str


class GroupMembersResponse(BaseModel):
    success: bool
    group: GroupOut
    members: list[GroupMemberOut]


class GroupCreateResponse(MessageResponse):
    group: GroupOut | None = None
    invitedUserIds: list[int] = Field(default_factory=list)


class MyGroupsResponse(BaseModel):
    success: bool
    groups: list[GroupOut]


class NotificationRespondRequest(BaseModel):
    accepted: bool


class NotificationOut(BaseModel):
    id: int
    notificationType: str
    title: str
    content: str
    status: str
    isPersistent: bool = False
    isRead: bool = False
    relatedType: str
    relatedId: int | None = None
    createdBy: int | None = None
    createdByName: str = ""
    createdAt: str
    readAt: str | None = None
    handledAt: str | None = None
    dismissedAt: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class NotificationListResponse(BaseModel):
    success: bool
    total: int = 0
    unreadCount: int = 0
    notifications: list[NotificationOut] = Field(default_factory=list)


class LegacyGetUserIdRequest(BaseModel):
    token: str | None = None


class SessionOut(BaseModel):
    id: int
    userAgent: str
    ipAddress: str
    createdAt: str
    lastUsedAt: str
    expiresAt: str
    revokedAt: str | None = None
    isCurrent: bool
    sessionCount: int = 1


class SessionListResponse(BaseModel):
    success: bool
    sessions: list[SessionOut]
    currentSessionId: int | None = None


class PermissionOut(BaseModel):
    id: int
    code: str
    name: str
    description: str


class RoleOut(BaseModel):
    id: int
    name: str
    slug: str
    description: str
    isSystem: bool
    permissions: list[str] = Field(default_factory=list)
    userCount: int = 0


class RoleListResponse(BaseModel):
    success: bool
    roles: list[RoleOut]


class PermissionListResponse(BaseModel):
    success: bool
    permissions: list[PermissionOut]


class AdminUserItem(BaseModel):
    id: int
    externalUserId: int | None = None
    username: str
    email: str | None = None
    displayName: str
    phone: str | None = None
    role: str
    vip: int
    vipLevel: int
    userRuleId: int
    authSource: str
    isActive: bool
    createdAt: str
    updatedAt: str
    lastLoginAt: str | None = None
    aqcRoleKey: str = "aqc_sales"
    aqcRoleName: str = "销售员"
    shopId: int | None = None
    shopName: str | None = None
    shopIds: list[int] = Field(default_factory=list)
    shopNames: list[str] = Field(default_factory=list)
    employmentDate: str | None = None
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)


class AdminUserListResponse(BaseModel):
    success: bool
    users: list[AdminUserItem]


class AdminUserCreateRequest(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    email: str | None = Field(default=None, max_length=120)
    displayName: str | None = Field(default=None, max_length=80)
    phone: str | None = Field(default=None, max_length=20)
    externalUserId: int | None = Field(default=None, ge=1)
    authSource: str = Field(default="local", max_length=30)
    vip: int = Field(default=0, ge=0, le=10)
    vipLevel: int = Field(default=0, ge=0, le=100)
    userRuleId: int = Field(default=5, ge=0, le=1000)
    isActive: bool = True
    aqcRoleKey: Literal["aqc_admin", "aqc_manager", "aqc_sales", "aqc_engineer", "aqc_departed"] = "aqc_sales"
    shopId: int | None = Field(default=None, ge=1)
    shopIds: list[int] = Field(default_factory=list)
    employmentDate: str | None = Field(default=None, max_length=10)
    roleIds: list[int] = Field(default_factory=list)


class AdminUserUpdateRequest(BaseModel):
    username: str | None = Field(default=None, min_length=2, max_length=50)
    email: str | None = Field(default=None, max_length=120)
    displayName: str | None = Field(default=None, max_length=80)
    phone: str | None = Field(default=None, max_length=20)
    externalUserId: int | None = Field(default=None, ge=1)
    vip: int | None = Field(default=None, ge=0, le=10)
    vipLevel: int | None = Field(default=None, ge=0, le=100)
    userRuleId: int | None = Field(default=None, ge=0, le=1000)
    isActive: bool | None = None
    aqcRoleKey: Literal["aqc_admin", "aqc_manager", "aqc_sales", "aqc_engineer", "aqc_departed"] | None = None
    shopId: int | None = Field(default=None, ge=1)
    shopIds: list[int] | None = None
    employmentDate: str | None = Field(default=None, max_length=10)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    roleIds: list[int] | None = None


class AdminSetUserRolesRequest(BaseModel):
    roleIds: list[int] = Field(default_factory=list)


class AdminRoleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    slug: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=255)
    permissionCodes: list[str] = Field(default_factory=list)


class AdminRoleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    slug: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=255)
    permissionCodes: list[str] | None = None


class AdminImportAqcORequest(BaseModel):
    sqlPath: str | None = Field(default=None, max_length=2000)


class AdminImportAqcOResponse(MessageResponse):
    stats: dict[str, Any] | None = None


class SalesFilterOptionOut(BaseModel):
    value: str
    label: str
    count: int


class SalesIndexOptionOut(BaseModel):
    key: str
    count: int


class SalesRecommendedPeriodOptionOut(BaseModel):
    key: Literal["today", "yesterday", "this_week", "last_week", "this_month", "last_month", "this_year", "last_year"]
    label: str
    count: int
    dateFrom: str
    dateTo: str
    recommended: bool = False


class SaleRecordCreateRequest(BaseModel):
    saleKind: Literal["goods", "repair"] = "goods"
    soldAt: str | None = Field(default=None, max_length=30)
    orderNum: str | None = Field(default=None, max_length=32)
    goodsId: int | None = Field(default=None, ge=1)
    goodsCode: str | None = Field(default=None, max_length=64)
    goodsBrand: str | None = Field(default=None, max_length=120)
    goodsSeries: str | None = Field(default=None, max_length=120)
    goodsModel: str | None = Field(default=None, max_length=191)
    goodsBarcode: str | None = Field(default=None, max_length=64)
    unitPrice: float | None = Field(default=None, ge=0, le=999999999)
    receivableAmount: float | None = Field(default=None, ge=0, le=999999999)
    receivedAmount: float | None = Field(default=None, ge=0, le=999999999)
    couponAmount: float | None = Field(default=0, ge=0, le=999999999)
    discountRate: float | None = Field(default=None, ge=0, le=99.99)
    amount: float | None = Field(default=None, ge=0, le=999999999)
    quantity: int = Field(default=1, ge=1, le=1000000)
    channel: str | None = Field(default=None, max_length=50)
    shopId: int | None = Field(default=None, ge=1)
    shopName: str | None = Field(default=None, max_length=255)
    shipShopId: int | None = Field(default=None, ge=1)
    shipShopName: str | None = Field(default=None, max_length=255)
    salesperson: str | None = Field(default=None, max_length=80)
    customerName: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=5000)


class SaleRecordOut(BaseModel):
    id: int
    soldAt: str
    saleKind: Literal["goods", "repair"] = "goods"
    saleKindLabel: str = ""
    orderNum: str
    goodsId: int | None = None
    goodsCode: str
    goodsBrand: str
    goodsSeries: str
    goodsModel: str
    goodsBarcode: str
    indexKey: str
    goodsDisplayName: str
    unitPrice: float
    receivableAmount: float
    receivedAmount: float
    couponAmount: float
    discountRate: float
    discountDisplay: str
    amount: float
    quantity: int
    channel: str
    saleStatus: str = "normal"
    saleStatusLabel: str = ""
    sourceSaleRecordId: int | None = None
    relatedWorkOrderId: int | None = None
    shopId: int | None = None
    shopName: str = ""
    shipShopId: int | None = None
    shipShopName: str = ""
    salesperson: str = ""
    customerName: str
    note: str
    createdBy: int | None = None
    createdByName: str | None = None
    createdAt: str
    updatedAt: str


class SaleRecordListResponse(BaseModel):
    success: bool
    total: int
    records: list[SaleRecordOut]


class SaleRecordMetaResponse(BaseModel):
    success: bool
    totalItems: int
    brandOptions: list[SalesFilterOptionOut]
    seriesOptions: list[SalesFilterOptionOut]
    shopOptions: list[SalesFilterOptionOut]
    salespersonOptions: list[SalesFilterOptionOut]
    indexOptions: list[SalesIndexOptionOut]
    recommendedPeriodOptions: list[SalesRecommendedPeriodOptionOut]


class SalesTemplateImportResponse(MessageResponse):
    stats: dict[str, Any] = Field(default_factory=dict)


class SalesMetricOut(BaseModel):
    key: Literal["day", "week", "month", "ytd", "range"]
    label: str
    sales: float
    uplift: float


class SalesPointOut(BaseModel):
    x: str
    y: float
    segmentSales: float = 0
    quantity: int = 0


class SalesChampionOut(BaseModel):
    name: str = ""
    amount: float = 0
    quantity: int = 0


class SalesSummaryResponse(BaseModel):
    success: bool
    period: Literal["day", "week", "month", "ytd", "range"]
    title: str
    sales: float
    uplift: float
    receivableTotal: float = 0
    receivedTotal: float = 0
    couponTotal: float = 0
    discountAmountTotal: float = 0
    averageTicketValue: float = 0
    quantityTotal: int = 0
    orderCount: int = 0
    topSalespersonLabel: str = ""
    topShopLabel: str = ""
    topSalespersonName: str = ""
    topShopName: str = ""
    topSalesperson: SalesChampionOut = Field(default_factory=SalesChampionOut)
    topShop: SalesChampionOut = Field(default_factory=SalesChampionOut)
    metrics: list[SalesMetricOut]
    points: list[SalesPointOut]
    xTicks: list[str]
    yTicks: list[float]


class AccountPerformanceRankItemOut(BaseModel):
    rank: int = 0
    name: str = ""
    shopName: str = ""
    amount: float = 0
    quantity: int = 0


class AccountPerformanceResponse(BaseModel):
    success: bool
    period: str = "this_month"
    periodLabel: str = ""
    rangeLabel: str = ""
    commissionPeriod: str = "this_month"
    commissionPeriodLabel: str = ""
    commissionRangeLabel: str = ""
    rankingPeriod: str = "this_month"
    rankingPeriodLabel: str = ""
    rankingRangeLabel: str = ""
    dateFrom: str = ""
    dateTo: str = ""
    employmentDate: str | None = None
    joinedDays: int | None = None
    commissionRate: float = 0.02
    salesAmount: float = 0
    commissionAmount: float = 0
    formulaText: str = ""
    rankScope: Literal["shop", "company"] = "shop"
    rankScopeLabel: str = ""
    shopName: str = ""
    currentRank: int = 0
    rankingCount: int = 0
    currentEntry: AccountPerformanceRankItemOut = Field(default_factory=AccountPerformanceRankItemOut)
    previousEntry: AccountPerformanceRankItemOut | None = None
    nextEntry: AccountPerformanceRankItemOut | None = None
    rankings: list[AccountPerformanceRankItemOut] = Field(default_factory=list)


class SalesCalendarPersonEntryOut(BaseModel):
    label: str
    amount: float = 0
    meta: str = ""


class SalesCalendarDrilldownItemOut(BaseModel):
    label: str
    amount: float = 0
    quantity: int = 0
    averageTicketValue: float = 0
    orderCount: int = 0
    entries: list[SalesCalendarPersonEntryOut] = Field(default_factory=list)


class SalesCalendarBreakdownOut(BaseModel):
    label: str
    amount: float = 0
    quantity: int = 0
    averageTicketValue: float = 0
    orderCount: int = 0
    drilldownTitle: str = ""
    drilldowns: list[SalesCalendarDrilldownItemOut] = Field(default_factory=list)


class SalesCalendarDayOut(BaseModel):
    date: str
    day: int
    amount: float = 0
    quantity: int = 0
    averageTicketValue: float = 0
    isCurrentMonth: bool = True
    isToday: bool = False
    breakdownMode: str = ""
    breakdownTitle: str = ""
    breakdowns: list[SalesCalendarBreakdownOut] = Field(default_factory=list)


class SalesCalendarResponse(BaseModel):
    success: bool
    month: str
    monthLabel: str
    totalAmount: float = 0
    totalQuantity: int = 0
    activeDays: int = 0
    days: list[SalesCalendarDayOut]


class ShopCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    image: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=255)
    province: str | None = Field(default=None, max_length=100)
    city: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    latitude: str | None = Field(default=None, max_length=50)
    longitude: str | None = Field(default=None, max_length=50)
    businessHours: str | None = Field(default=None, max_length=100)
    brandIds: str | None = Field(default=None, max_length=5000)
    shopType: int = Field(default=0, ge=0, le=20)
    channel: int = Field(default=1, ge=0, le=20)
    managerUserId: int | None = Field(default=None, ge=1)
    managerName: str | None = Field(default=None, max_length=120)
    scheduleEnabled: bool = False
    targetEnabled: bool = False
    reportEnabled: bool = True
    salespersonIds: list[int] = Field(default_factory=list)
    division: str | None = Field(default=None, max_length=120)
    shareCode: str | None = Field(default=None, max_length=255)


class ShopUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    image: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=255)
    province: str | None = Field(default=None, max_length=100)
    city: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    latitude: str | None = Field(default=None, max_length=50)
    longitude: str | None = Field(default=None, max_length=50)
    businessHours: str | None = Field(default=None, max_length=100)
    brandIds: str | None = Field(default=None, max_length=5000)
    shopType: int | None = Field(default=None, ge=0, le=20)
    channel: int | None = Field(default=None, ge=0, le=20)
    managerUserId: int | None = Field(default=None, ge=1)
    managerName: str | None = Field(default=None, max_length=120)
    scheduleEnabled: bool | None = None
    targetEnabled: bool | None = None
    reportEnabled: bool | None = None
    salespersonIds: list[int] | None = None
    division: str | None = Field(default=None, max_length=120)
    shareCode: str | None = Field(default=None, max_length=255)


class ShopOut(BaseModel):
    id: int
    legacyId: int | None = None
    name: str
    image: str
    phone: str | None = None
    address: str
    province: str | None = None
    city: str | None = None
    district: str | None = None
    latitude: str | None = None
    longitude: str | None = None
    businessHours: str | None = None
    brandIds: str
    shopType: int
    channel: int
    managerUserId: int | None = None
    managerName: str | None = None
    scheduleEnabled: bool = False
    targetEnabled: bool = False
    reportEnabled: bool = False
    scheduleMemberCount: int = 0
    salespersonIds: list[int] = Field(default_factory=list)
    division: str | None = None
    shareCode: str | None = None
    createdBy: int | None = None
    createdByName: str | None = None
    salespeople: str = ""
    goodsQuantity: int = 0
    createdAt: str
    updatedAt: str


class ShopListResponse(BaseModel):
    success: bool
    total: int
    shops: list[ShopOut]


class ShopOptionOut(BaseModel):
    id: int
    name: str
    shopType: int = 0


class ShopOptionListResponse(BaseModel):
    success: bool
    options: list[ShopOptionOut]


class ShopScheduleShopOut(BaseModel):
    id: int
    name: str
    managerName: str | None = None
    staffCount: int = 0


class ShopScheduleStaffOut(BaseModel):
    id: int
    username: str = ""
    displayName: str
    roleName: str = ""
    isManager: bool = False
    isActive: bool = True
    isAssigned: bool = True


class ShopScheduleAssignmentOut(BaseModel):
    userId: int
    displayName: str
    username: str = ""
    roleName: str = ""
    isManager: bool = False
    isActive: bool = True
    isAssigned: bool = True


class ShopScheduleShiftSlotOut(BaseModel):
    key: Literal["morning", "extra", "night"]
    label: str
    assignments: list[ShopScheduleAssignmentOut] = Field(default_factory=list)


class ShopScheduleDayOut(BaseModel):
    date: str
    day: int
    weekday: int
    isCurrentMonth: bool = True
    isToday: bool = False
    isIncomplete: bool = False
    shiftSlots: list[ShopScheduleShiftSlotOut] = Field(default_factory=list)


class ShopScheduleStaffStatOut(BaseModel):
    userId: int
    displayName: str
    username: str = ""
    roleName: str = ""
    isManager: bool = False
    isActive: bool = True
    isAssigned: bool = True
    shiftCount: int = 0
    doubleShiftDays: int = 0
    workDays: int = 0
    restDays: int = 0


class ShopScheduleStaffGroupOut(BaseModel):
    shopId: int
    shopName: str
    isCurrentShop: bool = False
    staff: list[ShopScheduleStaffOut] = Field(default_factory=list)


class ShopScheduleStatEntryOut(BaseModel):
    shopId: int
    shopName: str = ""
    userId: int
    date: str
    shiftKey: Literal["morning", "extra", "night"]


class ShopScheduleLogItemOut(BaseModel):
    id: int
    operatorName: str = ""
    createdAt: str = ""
    summary: str = ""
    highlights: list[str] = Field(default_factory=list)


class ShopScheduleLogListResponse(BaseModel):
    success: bool
    total: int = 0
    logs: list[ShopScheduleLogItemOut] = Field(default_factory=list)


class ShopSchedulePageResponse(BaseModel):
    success: bool
    canEdit: bool = False
    month: str
    monthLabel: str
    shop: ShopScheduleShopOut
    staff: list[ShopScheduleStaffOut] = Field(default_factory=list)
    staffGroups: list[ShopScheduleStaffGroupOut] = Field(default_factory=list)
    staffStats: list[ShopScheduleStaffStatOut] = Field(default_factory=list)
    staffStatEntries: list[ShopScheduleStatEntryOut] = Field(default_factory=list)
    days: list[ShopScheduleDayOut] = Field(default_factory=list)
    incompleteDays: list[str] = Field(default_factory=list)
    logs: list[ShopScheduleLogItemOut] = Field(default_factory=list)


class ShopScheduleDaySaveInput(BaseModel):
    date: str = Field(min_length=10, max_length=10)
    morning: list[int] = Field(default_factory=list)
    extra: list[int] = Field(default_factory=list)
    night: list[int] = Field(default_factory=list)

    @field_validator("morning", "extra", "night", mode="before")
    @classmethod
    def normalize_member_ids(cls, value: Any) -> list[int]:
        values = value if isinstance(value, list) else []
        result: list[int] = []
        seen: set[int] = set()
        for item in values:
            try:
                user_id = int(item)
            except (TypeError, ValueError):
                continue
            if user_id <= 0 or user_id in seen:
                continue
            seen.add(user_id)
            result.append(user_id)
        return result


class ShopScheduleSaveRequest(BaseModel):
    month: str = Field(min_length=7, max_length=7)
    confirmIncomplete: bool = False
    confirmConflicts: bool = False
    days: list[ShopScheduleDaySaveInput] = Field(default_factory=list)


class ShopScheduleConflictWarningOut(BaseModel):
    userId: int
    displayName: str
    roleName: str = ""
    date: str
    shiftKey: Literal["morning", "extra", "night"]
    shiftLabel: str
    shopId: int
    shopName: str


class ShopScheduleSaveResponse(MessageResponse):
    needsConfirm: bool = False
    incompleteDays: list[str] = Field(default_factory=list)
    changedDays: int = 0
    logId: int | None = None
    conflictWarnings: list[ShopScheduleConflictWarningOut] = Field(default_factory=list)


class MyScheduleTomorrowShiftOut(BaseModel):
    shopId: int
    shopName: str
    shiftType: Literal["morning", "extra", "night"]
    shiftLabel: str


class MyScheduleSummaryResponse(BaseModel):
    success: bool
    period: str
    periodLabel: str
    dateFrom: str
    dateTo: str
    shiftCount: int = 0
    workDays: int = 0
    tomorrowShifts: list[MyScheduleTomorrowShiftOut] = Field(default_factory=list)


class ShopTargetStageInput(BaseModel):
    targetAmount: float = Field(default=0, ge=0, le=999999999)
    rewardAmount: float = Field(default=0, ge=0, le=999999999)


class ShopTargetModelGoalInput(BaseModel):
    goodsId: int | None = Field(default=None, ge=1)
    name: str | None = Field(default=None, max_length=120)
    modelDisplay: str | None = Field(default=None, max_length=120)
    brand: str | None = Field(default=None, max_length=120)
    series: str | None = Field(default=None, max_length=120)
    barcode: str | None = Field(default=None, max_length=120)
    models: list[str] = Field(default_factory=list)
    targetQuantity: int = Field(default=0, ge=0, le=999999999)
    rewardAmount: float = Field(default=0, ge=0, le=999999999)


class ShopTargetPresetCreateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    models: list[str] = Field(default_factory=list)


class ShopTargetPresetOut(BaseModel):
    id: int
    name: str
    models: list[str] = Field(default_factory=list)
    createdAt: str = ""
    updatedAt: str = ""


class ShopTargetContributionOut(BaseModel):
    label: str
    amount: float = 0
    ratio: float = 0


class ShopTargetStageOut(BaseModel):
    level: int
    targetAmount: float = 0
    rewardAmount: float = 0
    achieved: bool = False


class ShopTargetModelGoalOut(BaseModel):
    goodsId: int | None = None
    name: str
    modelDisplay: str = ""
    brand: str = ""
    series: str = ""
    barcode: str = ""
    models: list[str] = Field(default_factory=list)
    targetQuantity: int = 0
    completedQuantity: int = 0
    rewardAmount: float = 0
    achieved: bool = False


class ShopTargetModelSaleOut(BaseModel):
    label: str
    quantity: int = 0


class ShopTargetMonthOut(BaseModel):
    month: str
    monthLabel: str
    targetAmount: float = 0
    actualAmount: float = 0
    completionRatio: float = 0
    currentStageLevel: int = 0
    currentStageLabel: str = ""
    currentStageTargetAmount: float = 0
    currentStageRewardAmount: float = 0
    totalStageReward: float = 0
    totalModelReward: float = 0
    stages: list[ShopTargetStageOut] = Field(default_factory=list)
    modelGoals: list[ShopTargetModelGoalOut] = Field(default_factory=list)
    contributions: list[ShopTargetContributionOut] = Field(default_factory=list)
    modelSales: list[ShopTargetModelSaleOut] = Field(default_factory=list)


class ShopTargetLogItemOut(BaseModel):
    id: int
    operatorName: str = ""
    createdAt: str = ""
    summary: str = ""
    highlights: list[str] = Field(default_factory=list)


class ShopTargetPageResponse(BaseModel):
    success: bool
    shop: ShopScheduleShopOut
    year: int
    yearLabel: str
    canEdit: bool = False
    months: list[ShopTargetMonthOut] = Field(default_factory=list)
    presets: list[ShopTargetPresetOut] = Field(default_factory=list)
    logs: list[ShopTargetLogItemOut] = Field(default_factory=list)


class ShopTargetSaveMonthInput(BaseModel):
    month: str = Field(min_length=7, max_length=7)
    targetAmount: float = Field(default=0, ge=0, le=999999999)
    stages: list[ShopTargetStageInput] = Field(default_factory=list)
    modelGoals: list[ShopTargetModelGoalInput] = Field(default_factory=list)


class ShopTargetSaveRequest(BaseModel):
    year: int = Field(ge=2000, le=2100)
    months: list[ShopTargetSaveMonthInput] = Field(default_factory=list)


class ShopTargetSaveResponse(MessageResponse):
    logs: list[ShopTargetLogItemOut] = Field(default_factory=list)


class ShopTargetPresetListResponse(BaseModel):
    success: bool
    presets: list[ShopTargetPresetOut] = Field(default_factory=list)


class ShopTargetLogListResponse(BaseModel):
    success: bool
    total: int = 0
    logs: list[ShopTargetLogItemOut] = Field(default_factory=list)


class GoodsInventoryQuantityInput(BaseModel):
    shopId: int = Field(gt=0)
    quantity: int = Field(default=0, ge=-1000000000, le=1000000000)


class GoodsItemCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=191)
    productCode: str | None = Field(default=None, max_length=64)
    brand: str | None = Field(default=None, max_length=120)
    series: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=191)
    modelAttribute: str | None = Field(default=None, max_length=8)
    barcode: str | None = Field(default=None, max_length=64)
    indexKey: str | None = Field(default=None, max_length=8)
    categoryId: int = Field(default=0, ge=0, le=100000000)
    coverImage: str | None = Field(default=None, max_length=500)
    imageList: str | None = Field(default=None, max_length=20000)
    description: str | None = Field(default=None, max_length=5000)
    detail: str | None = Field(default=None, max_length=200000)
    price: float = Field(default=0, ge=0, le=999999999)
    originalPrice: float = Field(default=0, ge=0, le=999999999)
    salePrice: float = Field(default=0, ge=0, le=999999999)
    score: int = Field(default=0, ge=0, le=100000000)
    stock: int = Field(default=0, ge=-1000000000, le=1000000000)
    saleNum: int = Field(default=0, ge=0, le=1000000000)
    sort: int = Field(default=0, ge=0, le=1000000000)
    putaway: int = Field(default=0, ge=0, le=20)
    status: int = Field(default=3, ge=0, le=20)
    goodsType: int = Field(default=0, ge=0, le=20)
    remark: str | None = Field(default=None, max_length=255)
    goodspec: str | None = Field(default=None, max_length=255)
    scoreRule: str | None = Field(default=None, max_length=5000)
    legacyAdminId: int | None = Field(default=None, ge=0)
    shopId: int | None = Field(default=None, ge=1)
    quantities: list[GoodsInventoryQuantityInput] = Field(default_factory=list)


class GoodsInventoryUpdateRequest(BaseModel):
    quantities: list[GoodsInventoryQuantityInput] = Field(default_factory=list)


class GoodsItemUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=191)
    productCode: str | None = Field(default=None, max_length=64)
    brand: str | None = Field(default=None, max_length=120)
    series: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=191)
    modelAttribute: str | None = Field(default=None, max_length=8)
    barcode: str | None = Field(default=None, max_length=64)
    indexKey: str | None = Field(default=None, max_length=8)
    categoryId: int | None = Field(default=None, ge=0, le=100000000)
    coverImage: str | None = Field(default=None, max_length=500)
    imageList: str | None = Field(default=None, max_length=20000)
    description: str | None = Field(default=None, max_length=5000)
    detail: str | None = Field(default=None, max_length=200000)
    price: float | None = Field(default=None, ge=0, le=999999999)
    originalPrice: float | None = Field(default=None, ge=0, le=999999999)
    salePrice: float | None = Field(default=None, ge=0, le=999999999)
    score: int | None = Field(default=None, ge=0, le=100000000)
    stock: int | None = Field(default=None, ge=-1000000000, le=1000000000)
    saleNum: int | None = Field(default=None, ge=0, le=1000000000)
    sort: int | None = Field(default=None, ge=0, le=1000000000)
    putaway: int | None = Field(default=None, ge=0, le=20)
    status: int | None = Field(default=None, ge=0, le=20)
    goodsType: int | None = Field(default=None, ge=0, le=20)
    remark: str | None = Field(default=None, max_length=255)
    goodspec: str | None = Field(default=None, max_length=255)
    scoreRule: str | None = Field(default=None, max_length=5000)
    legacyAdminId: int | None = Field(default=None, ge=0)
    shopId: int | None = Field(default=None, ge=1)


class GoodsItemOut(BaseModel):
    id: int
    legacyId: int | None = None
    name: str
    productCode: str
    brand: str
    series: str
    model: str
    modelAttribute: str = "-"
    barcode: str
    indexKey: str
    categoryId: int
    coverImage: str
    imageList: str
    description: str
    detail: str
    price: float
    originalPrice: float
    salePrice: float
    score: int
    stock: int
    shopQuantity: int = 0
    compareQuantities: dict[str, int] = Field(default_factory=dict)
    salesCount: int = 0
    compareSalesCounts: dict[str, int] = Field(default_factory=dict)
    saleNum: int
    sort: int
    putaway: int
    status: int
    goodsType: int
    remark: str
    goodspec: str | None = None
    scoreRule: str
    legacyAdminId: int | None = None
    shopId: int | None = None
    shopName: str | None = None
    createdBy: int | None = None
    createdByName: str | None = None
    createdAt: str
    updatedAt: str


class GoodsItemSummaryOut(BaseModel):
    id: int
    legacyId: int | None = None
    name: str
    productCode: str
    brand: str
    series: str
    model: str
    modelAttribute: str = "-"
    barcode: str
    indexKey: str
    categoryId: int
    coverImage: str
    price: float
    originalPrice: float
    salePrice: float
    score: int
    stock: int
    shopQuantity: int = 0
    compareQuantities: dict[str, int] = Field(default_factory=dict)
    salesCount: int = 0
    compareSalesCounts: dict[str, int] = Field(default_factory=dict)
    saleNum: int
    sort: int
    putaway: int
    status: int
    goodsType: int
    remark: str
    goodspec: str | None = None
    legacyAdminId: int | None = None
    shopId: int | None = None
    shopName: str | None = None
    createdBy: int | None = None
    createdByName: str | None = None
    createdAt: str
    updatedAt: str


class GoodsItemListResponse(BaseModel):
    success: bool
    total: int
    items: list[GoodsItemSummaryOut]
    shopQuantityTotal: int = 0
    shopAmountTotal: float = 0
    stockTotal: int = 0
    salesTotal: int = 0


class GoodsInventoryOut(BaseModel):
    shopId: int
    shopName: str
    shopShortName: str
    shopType: int
    quantity: int


class GoodsInventoryResponse(BaseModel):
    success: bool
    message: str | None = None
    item: GoodsItemSummaryOut | None = None
    inventories: list[GoodsInventoryOut] = Field(default_factory=list)
    totalStock: int = 0


class GoodsFilterOptionOut(BaseModel):
    value: str
    label: str
    count: int


class GoodsIndexOptionOut(BaseModel):
    key: str
    count: int


class GoodsCatalogMetaResponse(BaseModel):
    success: bool
    totalItems: int
    brandCount: int
    seriesCount: int
    priceMin: float
    priceMax: float
    nextProductCode: str = ""
    brandOptions: list[GoodsFilterOptionOut]
    seriesOptions: list[GoodsFilterOptionOut]
    attributeOptions: list[GoodsFilterOptionOut]
    indexOptions: list[GoodsIndexOptionOut]


class GoodsCatalogImportResponse(MessageResponse):
    stats: dict[str, Any] = Field(default_factory=dict)


class InventoryLogOut(BaseModel):
    id: int
    goodsId: int | None = None
    goodsName: str = ""
    goodsModel: str = ""
    shopId: int | None = None
    shopName: str = ""
    changeContent: str = ""
    quantityBefore: int = 0
    quantityAfter: int = 0
    totalQuantityAfter: int = 0
    operatorId: int | None = None
    operatorName: str = ""
    relatedType: str = ""
    relatedId: int | None = None
    createdAt: str = ""


class InventoryLogListResponse(BaseModel):
    success: bool
    total: int = 0
    currentQuantityTotal: int = 0
    logs: list[InventoryLogOut] = Field(default_factory=list)


class WorkOrderTypeOptionOut(BaseModel):
    value: str
    label: str
    prefix: str
    category: str = "goods"
    categoryLabel: str = ""


class WorkOrderDefaultApproverSettingOut(BaseModel):
    orderType: str
    orderTypeLabel: str = ""
    approverId: int | None = None
    approverName: str = ""


class WorkOrderCategoryOptionOut(BaseModel):
    value: str
    label: str


class WorkOrderScheduleOut(BaseModel):
    id: int
    orderType: str
    orderTypeLabel: str
    periodKey: str
    periodLabel: str
    shopIds: list[int] = Field(default_factory=list)
    shopNames: list[str] = Field(default_factory=list)
    applicantId: int
    applicantName: str
    approverId: int | None = None
    approverName: str = ""
    groupId: int | None = None
    groupName: str = ""
    enabled: bool = True
    lastPeriodKey: str = ""
    lastRunAt: str | None = None
    createdAt: str = ""
    updatedAt: str = ""


class WorkOrderScheduleSaveRequest(BaseModel):
    orderType: Literal["sale"] = "sale"
    periodKey: Literal["day", "week", "month"] = "day"
    shopIds: list[int] = Field(default_factory=list, min_length=1)
    applicantId: int = Field(ge=1)
    approverId: int = Field(ge=1)
    groupId: int | None = Field(default=None, ge=1)
    enabled: bool = True


class WorkOrderScheduleListResponse(BaseModel):
    success: bool
    schedules: list[WorkOrderScheduleOut] = Field(default_factory=list)


class WorkOrderSettingsSaveItem(BaseModel):
    orderType: str
    approverId: int | None = Field(default=None, ge=1)


class WorkOrderSettingsSaveRequest(BaseModel):
    settings: list[WorkOrderSettingsSaveItem] = Field(default_factory=list)


class WorkOrderSettingsResponse(BaseModel):
    success: bool
    settings: list[WorkOrderDefaultApproverSettingOut] = Field(default_factory=list)


class WorkOrderStatusOptionOut(BaseModel):
    value: str
    label: str


class WorkOrderShopOptionOut(BaseModel):
    id: int
    name: str
    shortName: str = ""
    shopType: int
    salespersonIds: list[int] = Field(default_factory=list)


class WorkOrderApproverOptionOut(BaseModel):
    id: int
    username: str
    displayName: str
    aqcRoleKey: str = "aqc_admin"


class WorkOrderUserOptionOut(BaseModel):
    id: int
    username: str
    displayName: str
    aqcRoleKey: str = ""


class WorkOrderGroupOptionOut(BaseModel):
    id: int
    name: str
    description: str = ""
    memberRole: str | None = None
    memberCount: int = 0
    isDefault: bool = False


class WorkOrderItemInput(BaseModel):
    goodsId: int | None = Field(default=None, ge=1)
    saleRecordId: int | None = Field(default=None, ge=1)
    lineType: str | None = Field(default=None, max_length=20)
    orderNum: str | None = Field(default=None, max_length=64)
    salesperson: str | None = Field(default=None, max_length=80)
    saleShopId: int | None = Field(default=None, ge=1)
    saleShopName: str | None = Field(default=None, max_length=255)
    receiveShopId: int | None = Field(default=None, ge=1)
    receiveShopName: str | None = Field(default=None, max_length=255)
    shipShopId: int | None = Field(default=None, ge=1)
    shipShopName: str | None = Field(default=None, max_length=255)
    goodsName: str = Field(default="", max_length=191)
    productCode: str | None = Field(default=None, max_length=64)
    brand: str | None = Field(default=None, max_length=120)
    series: str | None = Field(default=None, max_length=120)
    barcode: str | None = Field(default=None, max_length=64)
    unitPrice: float = Field(default=0, ge=0, le=999999999)
    receivedAmount: float | None = Field(default=None, ge=-999999999999, le=999999999999)
    receivableAmount: float | None = Field(default=None, ge=-999999999999, le=999999999999)
    couponAmount: float | None = Field(default=0, ge=-999999999999, le=999999999999)
    discountRate: float | None = Field(default=None, ge=0, le=99.99)
    quantity: int = Field(default=1, ge=0, le=1000000000)
    totalAmount: float | None = Field(default=None, ge=0, le=999999999999)
    channel: str | None = Field(default=None, max_length=50)
    customerName: str | None = Field(default=None, max_length=120)
    remark: str | None = Field(default=None, max_length=255)
    isNewGoods: bool = False

    @staticmethod
    def _normalize_optional_int(value: Any) -> int | None:
        if value in (None, "", "null", "undefined"):
            return None
        if isinstance(value, dict):
            value = value.get("id")
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    @staticmethod
    def _normalize_decimal(value: Any, *, default: float = 0) -> float:
        if value in (None, "", "null", "undefined"):
            return default
        if isinstance(value, dict):
            value = value.get("value")
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return default
        if not math.isfinite(parsed):
            return default
        return parsed

    @staticmethod
    def _normalize_text(value: Any) -> str:
        if value in (None, "", "null", "undefined"):
            return ""
        if isinstance(value, dict):
            for key in ("displayName", "username", "name", "label", "value"):
                candidate = value.get(key)
                if candidate not in (None, ""):
                    return str(candidate)
            return ""
        return str(value)

    @field_validator("goodsId", "saleRecordId", "saleShopId", "receiveShopId", "shipShopId", mode="before")
    @classmethod
    def _validate_optional_ids(cls, value: Any) -> int | None:
        return cls._normalize_optional_int(value)

    @field_validator(
        "unitPrice",
        "receivedAmount",
        "receivableAmount",
        "couponAmount",
        "discountRate",
        "totalAmount",
        mode="before",
    )
    @classmethod
    def _validate_numeric_fields(cls, value: Any, info) -> float:
        default = 10 if info.field_name == "discountRate" else 0
        return cls._normalize_decimal(value, default=default)

    @field_validator("quantity", mode="before")
    @classmethod
    def _validate_quantity(cls, value: Any) -> int:
        if value in (None, "", "null", "undefined"):
            return 1
        if isinstance(value, dict):
            value = value.get("value")
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return 1
        if not math.isfinite(parsed):
            return 1
        return max(int(parsed), 0)

    @field_validator(
        "lineType",
        "orderNum",
        "salesperson",
        "saleShopName",
        "receiveShopName",
        "shipShopName",
        "goodsName",
        "productCode",
        "brand",
        "series",
        "barcode",
        "channel",
        "customerName",
        "remark",
        mode="before",
    )
    @classmethod
    def _validate_text_fields(cls, value: Any) -> str:
        return cls._normalize_text(value)


class WorkOrderSaveRequest(BaseModel):
    orderType: Literal["transfer", "purchase", "return", "damage", "sale", "sale_return", "sale_exchange"]
    status: Literal["draft", "pending"] = "draft"
    saleAffectsInventory: bool = False
    reason: str | None = Field(default=None, max_length=255)
    formDate: str | None = Field(default=None, max_length=40)
    sourceShopId: int | None = Field(default=None, ge=1)
    targetShopId: int | None = Field(default=None, ge=1)
    supplierName: str | None = Field(default=None, max_length=255)
    partnerName: str | None = Field(default=None, max_length=255)
    approverId: int | None = Field(default=None, ge=1)
    groupId: int | None = Field(default=None, ge=1)
    items: list[WorkOrderItemInput] = Field(default_factory=list)

    @field_validator("sourceShopId", "targetShopId", "approverId", "groupId", mode="before")
    @classmethod
    def _validate_root_optional_ids(cls, value: Any) -> int | None:
        return WorkOrderItemInput._normalize_optional_int(value)

    @field_validator("reason", "formDate", "supplierName", "partnerName", mode="before")
    @classmethod
    def _validate_root_text_fields(cls, value: Any) -> str | None:
        normalized = WorkOrderItemInput._normalize_text(value)
        return normalized or None


class WorkOrderReviewRequest(BaseModel):
    approved: bool
    comment: str | None = Field(default=None, max_length=1000)


class WorkOrderItemOut(BaseModel):
    id: int
    sortIndex: int = 0
    goodsId: int | None = None
    saleRecordId: int | None = None
    lineType: str = "default"
    orderNum: str = ""
    salesperson: str = ""
    saleShopId: int | None = None
    saleShopName: str = ""
    receiveShopId: int | None = None
    receiveShopName: str = ""
    shipShopId: int | None = None
    shipShopName: str = ""
    goodsName: str
    productCode: str
    brand: str
    series: str
    barcode: str
    unitPrice: float
    receivedAmount: float = 0
    receivableAmount: float = 0
    couponAmount: float = 0
    discountRate: float = 10
    quantity: int
    totalAmount: float
    channel: str = ""
    customerName: str = ""
    remark: str
    sourceStock: int = 0
    targetStock: int = 0
    isNewGoods: bool = False


class WorkOrderActionOut(BaseModel):
    id: int
    actionType: str
    actionLabel: str
    statusFrom: str
    statusFromLabel: str
    statusTo: str
    statusToLabel: str
    comment: str
    actorId: int | None = None
    actorName: str
    createdAt: str


class WorkOrderLogOut(BaseModel):
    id: int
    workOrderId: int
    orderNum: str
    orderCategory: str = "goods"
    orderCategoryLabel: str = ""
    orderType: str
    orderTypeLabel: str
    reason: str
    applicantName: str
    approverName: str
    actionType: str
    actionLabel: str
    statusFrom: str
    statusFromLabel: str
    statusTo: str
    statusToLabel: str
    actorId: int | None = None
    actorName: str
    comment: str
    createdAt: str


class WorkOrderSummaryOut(BaseModel):
    id: int
    orderNum: str
    orderCategory: str = "goods"
    orderCategoryLabel: str = ""
    orderType: str
    orderTypeLabel: str
    reason: str
    status: str
    statusLabel: str
    formDate: str
    applicantId: int
    applicantName: str
    approverId: int | None = None
    approverName: str
    groupId: int | None = None
    groupName: str = ""
    sharedById: int | None = None
    sharedByName: str = ""
    itemCount: int = 0
    totalQuantity: int = 0
    totalAmount: float = 0
    createdAt: str
    updatedAt: str


class WorkOrderDetailOut(WorkOrderSummaryOut):
    sourceShopId: int | None = None
    sourceShopName: str = ""
    targetShopId: int | None = None
    targetShopName: str = ""
    supplierName: str = ""
    partnerName: str = ""
    saleAffectsInventory: bool = False
    submittedAt: str | None = None
    approvedAt: str | None = None
    approvalComment: str = ""
    stockApplied: bool = False
    canEdit: bool = False
    canReview: bool = False
    canResubmit: bool = False
    items: list[WorkOrderItemOut] = Field(default_factory=list)
    actions: list[WorkOrderActionOut] = Field(default_factory=list)


class WorkOrderMetaResponse(BaseModel):
    success: bool
    categories: list[WorkOrderCategoryOptionOut] = Field(default_factory=list)
    types: list[WorkOrderTypeOptionOut]
    defaultApproverSettings: list[WorkOrderDefaultApproverSettingOut] = Field(default_factory=list)
    statuses: list[WorkOrderStatusOptionOut]
    shopOptions: list[WorkOrderShopOptionOut]
    storeOptions: list[WorkOrderShopOptionOut]
    warehouseOptions: list[WorkOrderShopOptionOut]
    otherWarehouseOptions: list[WorkOrderShopOptionOut]
    applicantOptions: list[WorkOrderUserOptionOut]
    approverOptions: list[WorkOrderApproverOptionOut]
    groups: list[WorkOrderGroupOptionOut] = Field(default_factory=list)
    nextProductCode: str = ""
    canApprove: bool = False


class WorkOrderListResponse(BaseModel):
    success: bool
    total: int
    orders: list[WorkOrderSummaryOut]


class WorkOrderLogListResponse(BaseModel):
    success: bool
    total: int
    logs: list[WorkOrderLogOut]


class WorkOrderDetailResponse(BaseModel):
    success: bool
    message: str | None = None
    order: WorkOrderDetailOut | None = None


class WorkOrderDashboardResponse(BaseModel):
    success: bool
    draftCount: int = 0
    pendingCount: int = 0
    approvalCount: int = 0
    recentMine: list[WorkOrderSummaryOut] = Field(default_factory=list)
    pendingApprovals: list[WorkOrderSummaryOut] = Field(default_factory=list)


class WorkOrderAllocationTargetOut(BaseModel):
    shopId: int
    shopName: str
    shortName: str = ""
    shopType: int = 0
    currentStock: int = 0
    quantity: int = 0


class WorkOrderAllocationRowOut(BaseModel):
    workOrderItemId: int
    goodsId: int | None = None
    goodsName: str
    productCode: str = ""
    brand: str = ""
    series: str = ""
    barcode: str = ""
    plannedQuantity: int = 0
    sourceStock: int = 0
    unitPrice: float = 0
    lineAmount: float = 0
    allocatedQuantity: int = 0
    targets: list[WorkOrderAllocationTargetOut] = Field(default_factory=list)


class WorkOrderAllocationDraftOut(BaseModel):
    orderId: int
    orderNum: str = ""
    orderType: str = ""
    sourceShopId: int | None = None
    sourceShopName: str = ""
    approverId: int | None = None
    approverName: str = ""
    groupId: int | None = None
    groupName: str = ""
    targetShopIds: list[int] = Field(default_factory=list)
    itemCount: int = 0
    rows: list[WorkOrderAllocationRowOut] = Field(default_factory=list)
    updatedAt: str | None = None


class WorkOrderAllocationDraftTargetInput(BaseModel):
    shopId: int = Field(ge=1)
    quantity: int = Field(default=0, ge=0, le=1000000000)


class WorkOrderAllocationDraftRowInput(BaseModel):
    workOrderItemId: int = Field(ge=1)
    targets: list[WorkOrderAllocationDraftTargetInput] = Field(default_factory=list)


class WorkOrderAllocationDraftSaveRequest(BaseModel):
    approverId: int | None = Field(default=None, ge=1)
    targetShopIds: list[int] = Field(default_factory=list)
    rows: list[WorkOrderAllocationDraftRowInput] = Field(default_factory=list)


class WorkOrderAllocationDraftResponse(BaseModel):
    success: bool
    message: str | None = None
    order: WorkOrderDetailOut | None = None
    draft: WorkOrderAllocationDraftOut | None = None
    targetOptions: list[WorkOrderShopOptionOut] = Field(default_factory=list)
    approverOptions: list[WorkOrderApproverOptionOut] = Field(default_factory=list)


class WorkOrderAllocationConfirmResponse(BaseModel):
    success: bool
    message: str | None = None
    createdCount: int = 0
    orderIds: list[int] = Field(default_factory=list)


class GoodsItemDetailResponse(BaseModel):
    success: bool
    item: GoodsItemOut | None = None


class GoodsBarcodeLookupResponse(BaseModel):
    success: bool
    item: GoodsItemOut | None = None
    message: str | None = None


class AccountAqcUserOut(BaseModel):
    userId: int
    username: str
    email: str | None = None
    displayName: str
    aqcRoleKey: str
    aqcRoleName: str
    isEnabled: bool
    lastLoginAt: str | None = None
    updatedAt: str
    localUserId: int | None = None
    localDisplayName: str | None = None
    localRoles: list[str] = Field(default_factory=list)
    localIsActive: bool | None = None


class AccountAqcUserListResponse(BaseModel):
    success: bool
    message: str | None = None
    users: list[AccountAqcUserOut]


class AccountAqcUserUpsertRequest(BaseModel):
    userId: int = Field(gt=0)
    roleKey: Literal[
        "aqc_super_admin",
        "aqc_admin",
        "aqc_operator",
        "aqc_manager",
        "aqc_sales",
        "aqc_engineer",
        "aqc_viewer",
        "aqc_departed",
    ] = "aqc_departed"
    isEnabled: bool = True


class AccountAqcUserRemoveRequest(BaseModel):
    userId: int = Field(gt=0)


class OrderItemOut(BaseModel):
    id: int
    goodsItemId: int | None = None
    goodsName: str
    goodsSpecId: int | None = None
    goodsSpecName: str | None = None
    goodspec: str | None = None
    quantity: int
    price: float
    totalAmount: float
    score: int
    weightKg: float | None = None


class OrderUploadLogOut(BaseModel):
    id: int
    legacyOrderId: int
    legacyOrderNum: str
    legacyOrderItemId: int | None = None
    generatedOrderNum: str
    cargoName: str
    success: bool
    errorMessage: str | None = None
    responseMessage: str | None = None
    createdBy: int | None = None
    createdByName: str | None = None
    uploadedAt: str


class OrderSummaryOut(BaseModel):
    id: int
    orderNum: str
    userName: str | None = None
    adminName: str | None = None
    recipientName: str
    recipientPhone: str
    recipientAddress: str
    goodsSummary: str
    itemCount: int
    quantityTotal: int
    total: float
    totalFee: float
    pocket: float
    score: int
    payType: int
    payTypeLabel: str
    status: int
    statusLabel: str
    isImported: bool
    uploadCount: int
    lastUploadedAt: str | None = None
    logisticsNum: str | None = None
    remark: str
    createdAt: str


class OrderDetailOut(OrderSummaryOut):
    addressId: int | None = None
    logisticsType: int | None = None
    logisticsCompanyId: int | None = None
    items: list[OrderItemOut] = Field(default_factory=list)
    uploads: list[OrderUploadLogOut] = Field(default_factory=list)
    canUpload: bool = False


class OrderListResponse(BaseModel):
    success: bool
    message: str | None = None
    total: int
    orders: list[OrderSummaryOut]


class OrderDetailResponse(BaseModel):
    success: bool
    message: str | None = None
    order: OrderDetailOut | None = None


class OrderUploadLogListResponse(BaseModel):
    success: bool
    total: int = 0
    successCount: int = 0
    failedCount: int = 0
    uploads: list[OrderUploadLogOut] = Field(default_factory=list)


class OrderUploadResponse(MessageResponse):
    uploadedCount: int = 0
    failedCount: int = 0
    generatedOrderNums: list[str] = Field(default_factory=list)
    uploads: list[OrderUploadLogOut] = Field(default_factory=list)
