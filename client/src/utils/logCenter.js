export const LOG_CENTER_TYPE_META = {
  update: {
    label: '更新日志',
    shortLabel: '更新',
  },
  work_order: {
    label: '工单日志',
    shortLabel: '工单',
    permission: 'workorders.read',
  },
  goods_inventory: {
    label: '商品库存日志',
    shortLabel: '商品库存',
    permission: 'goods.read',
    requiresSubject: true,
  },
  shop_inventory: {
    label: '库存日志',
    shortLabel: '库存',
    permission: 'shops.read',
    requiresSubject: true,
  },
  shop_schedule: {
    label: '排班日志',
    shortLabel: '排班',
    permission: 'shops.read',
    requiresSubject: true,
  },
  shop_target: {
    label: '目标日志',
    shortLabel: '目标',
    permission: 'shops.read',
    requiresSubject: true,
  },
  order_upload: {
    label: '订单上传日志',
    shortLabel: '上传',
    permission: 'orders.read',
  },
  report: {
    label: '报告日志',
    shortLabel: '报告',
    permission: 'sales.read',
  },
}

const DEFAULT_TYPE = 'update'

export function normalizeLogCenterType(value) {
  const clean = String(value || '').trim().toLowerCase()
  return LOG_CENTER_TYPE_META[clean] ? clean : DEFAULT_TYPE
}

export function sanitizeLogBackPath(value, fallback = '') {
  const clean = String(value || '').trim()
  if (clean.startsWith('/')) {
    return clean
  }
  return fallback
}

export function buildLogCenterQuery(payload = {}) {
  return Object.fromEntries(
    Object.entries(payload).filter(([, value]) => value !== undefined && value !== null && value !== ''),
  )
}
