import { DEMO_TOKEN, isDemoMode } from './demoMode'

const nowIso = () => new Date().toISOString()
const today = () => new Date().toISOString().slice(0, 10)

const demoShops = [
  { id: 1, name: '武昌万象城Casio专卖店', shortName: '武昌万象城', shopType: 0, managerName: '林溪', staffCount: 8, isActive: true },
  { id: 2, name: '武汉新佳丽广场Casio专卖店', shortName: '新佳丽', shopType: 0, managerName: '周然', staffCount: 6, isActive: true },
  { id: 3, name: '武商梦时代Casio专卖店', shortName: '梦时代', shopType: 0, managerName: '宋乔', staffCount: 7, isActive: true },
  { id: 9, name: '孝感保利仓库', shortName: '孝感保利', shopType: 1, managerName: '陈舟', staffCount: 3, isActive: true },
]

const demoUsers = [
  { id: 1, username: 'demo-admin', phone: '13800000001', email: 'demo-admin@aqc.symuse.local', displayName: '演示管理员', role: 'admin', aqcRoleKey: 'aqc_admin', aqcRoleName: '管理员', shopId: 1, shopIds: [1, 2, 3], shopName: '武昌万象城Casio专卖店', shopNames: ['武昌万象城Casio专卖店', '武汉新佳丽广场Casio专卖店', '武商梦时代Casio专卖店'], employmentDate: '2024-03-01', isActive: true, permissions: ['*'], roles: ['administrator'], lastLoginAt: nowIso(), createdAt: '2024-03-01T09:00:00' },
  { id: 2, username: 'sales-lin', phone: '13800000002', email: 'sales-lin@aqc.symuse.local', displayName: '林溪', role: 'user', aqcRoleKey: 'aqc_manager', aqcRoleName: '店长', shopId: 1, shopIds: [1], shopName: '武昌万象城Casio专卖店', shopNames: ['武昌万象城Casio专卖店'], employmentDate: '2024-07-12', isActive: true, permissions: ['sales.read', 'sales.write', 'goods.read', 'workorders.read', 'workorders.write', 'shops.read'], roles: ['manager'], lastLoginAt: nowIso(), createdAt: '2024-07-12T09:00:00' },
  { id: 3, username: 'engineer-chen', phone: '13800000003', email: 'engineer-chen@aqc.symuse.local', displayName: '陈舟', role: 'user', aqcRoleKey: 'aqc_engineer', aqcRoleName: '工程师', shopId: 9, shopIds: [9], shopName: '孝感保利仓库', shopNames: ['孝感保利仓库'], employmentDate: '2025-01-09', isActive: true, permissions: ['sales.read', 'sales.write', 'workorders.read', 'workorders.write'], roles: ['engineer'], lastLoginAt: nowIso(), createdAt: '2025-01-09T09:00:00' },
]

const demoGoods = [
  { id: 101, brand: 'CASIO', series: 'G-SHOCK', model: 'GM-2100-1A', name: 'GM-2100-1A', barcode: 'DEMO-GM2100', price: 1490, originalPrice: 1490, status: 1, putaway: true, coverImage: '/aqc-dw5000.png', images: ['/aqc-dw5000.png'] },
  { id: 102, brand: 'CASIO', series: 'BABY-G', model: 'BA-110X-7A', name: 'BA-110X-7A', barcode: 'DEMO-BA110', price: 990, originalPrice: 990, status: 1, putaway: true, coverImage: '/uploads/goods/legacy/32/0032-01-e5a3641a80fe941cc73dd413c945aab9.png', images: ['/uploads/goods/legacy/32/0032-01-e5a3641a80fe941cc73dd413c945aab9.png'] },
  { id: 103, brand: 'CASIO', series: 'EDIFICE', model: 'ECB-2000DC-1A', name: 'ECB-2000DC-1A', barcode: 'DEMO-ECB2000', price: 1890, originalPrice: 1890, status: 1, putaway: true, coverImage: '/uploads/goods/legacy/35/0035-01-92c8cffdd305fb2aa094e062ffbf2eeb.png', images: ['/uploads/goods/legacy/35/0035-01-92c8cffdd305fb2aa094e062ffbf2eeb.png'] },
  { id: 104, brand: 'CASIO', series: 'OCEANUS', model: 'OCW-T200S-1A', name: 'OCW-T200S-1A', barcode: 'DEMO-OCWT200', price: 3990, originalPrice: 3990, status: 1, putaway: true, coverImage: '/uploads/goods/legacy/34/0034-01-d1cf257f6699eade823fd0d697edf9eb.png', images: ['/uploads/goods/legacy/34/0034-01-d1cf257f6699eade823fd0d697edf9eb.png'] },
]

const inventories = {
  101: [{ shopId: 1, shopName: demoShops[0].name, shopType: 0, quantity: 6 }, { shopId: 2, shopName: demoShops[1].name, shopType: 0, quantity: 2 }, { shopId: 9, shopName: demoShops[3].name, shopType: 1, quantity: 12 }],
  102: [{ shopId: 1, shopName: demoShops[0].name, shopType: 0, quantity: 4 }, { shopId: 3, shopName: demoShops[2].name, shopType: 0, quantity: 5 }],
  103: [{ shopId: 1, shopName: demoShops[0].name, shopType: 0, quantity: 1 }, { shopId: 9, shopName: demoShops[3].name, shopType: 1, quantity: 9 }],
  104: [{ shopId: 3, shopName: demoShops[2].name, shopType: 0, quantity: 2 }, { shopId: 9, shopName: demoShops[3].name, shopType: 1, quantity: 4 }],
}

let saleId = 9004
let workOrderId = 99003
const demoSales = [
  saleRow({ id: 9001, goodsId: 101, quantity: 1, receivedAmount: 1490, salesperson: '林溪', shopId: 1, channel: '门店' }),
  saleRow({ id: 9002, goodsId: 102, quantity: 2, receivedAmount: 1880, salesperson: '宋乔', shopId: 3, channel: '私域' }),
  saleRow({ id: 9003, goodsId: 103, quantity: 1, receivedAmount: 1790, salesperson: '林溪', shopId: 1, channel: '企业微信' }),
]
const demoWorkOrders = [
  workOrderRow({ id: 99001, orderNum: 'DEMO-DB-001', orderType: 'transfer', reason: '演示调拨：热门款补货', status: 'pending' }),
  workOrderRow({ id: 99002, orderNum: 'DEMO-SJ-002', orderType: 'purchase', reason: '演示进货：新品到店', status: 'draft' }),
]

function withGoodsComputed(item) {
  const rows = inventories[item.id] || []
  const quantity = rows.reduce((sum, row) => sum + Number(row.quantity || 0), 0)
  return { ...item, quantity, stockQuantity: quantity, inventoryQuantity: quantity }
}

function saleRow(input) {
  const goods = demoGoods.find((item) => Number(item.id) === Number(input.goodsId)) || demoGoods[0]
  const shop = demoShops.find((item) => Number(item.id) === Number(input.shopId)) || demoShops[0]
  return {
    id: input.id,
    saleKind: 'goods',
    orderNum: `DEMO-SALE-${input.id}`,
    soldAt: input.soldAt || `${today()}T10:30:00`,
    goodsId: goods.id,
    goodsCode: goods.model,
    goodsBrand: goods.brand,
    goodsSeries: goods.series,
    goodsModel: goods.model,
    goodsBarcode: goods.barcode,
    coverImage: goods.coverImage,
    unitPrice: goods.price,
    quantity: Number(input.quantity || 1),
    receivableAmount: Number(input.receivedAmount || goods.price),
    receivedAmount: Number(input.receivedAmount || goods.price),
    couponAmount: 0,
    discountRate: 10,
    channel: input.channel || '门店',
    shopId: shop.id,
    shopName: shop.name,
    shipShopId: shop.id,
    shipShopName: shop.name,
    salesperson: input.salesperson || '林溪',
    customerName: input.customerName || '演示顾客',
    note: input.note || '仅供演示',
    createdAt: nowIso(),
  }
}

function workOrderRow(input) {
  const source = demoShops[0]
  const target = demoShops[2]
  return {
    id: input.id,
    orderNum: input.orderNum,
    orderType: input.orderType,
    orderTypeName: input.orderType === 'purchase' ? '商品进货单' : '商品调拨单',
    category: 'goods',
    categoryName: '商品类工单',
    reason: input.reason,
    status: input.status,
    statusName: input.status === 'pending' ? '待审批' : '草稿',
    day: today(),
    applicantId: 1,
    applicantName: '演示管理员',
    approverId: 1,
    approverName: '演示管理员',
    sourceShopId: source.id,
    sourceShopName: source.name,
    targetShopId: target.id,
    targetShopName: target.name,
    groupId: 1,
    groupName: '演示协作组',
    items: [{ id: 1, goodsId: 101, goodsBrand: 'CASIO', goodsSeries: 'G-SHOCK', goodsModel: 'GM-2100-1A', goodsName: 'GM-2100-1A', barcode: 'DEMO-GM2100', quantity: 1, unitPrice: 1490 }],
    logs: [{ id: 1, operatorName: '演示管理员', actionName: '创建工单', createdAt: nowIso(), detail: 'demo 数据，不写入服务器' }],
    createdAt: nowIso(),
    updatedAt: nowIso(),
  }
}

function filterRows(rows, query = {}, fields = []) {
  const keyword = String(query.q || query.keyword || '').trim().toLowerCase()
  if (!keyword) {
    return rows
  }
  return rows.filter((row) => fields.some((field) => String(row[field] || '').toLowerCase().includes(keyword)))
}

function paginate(rows, query = {}) {
  const page = Math.max(Number(query.page || 1), 1)
  const pageSize = Math.max(Number(query.page_size || query.pageSize || 20), 1)
  return rows.slice((page - 1) * pageSize, page * pageSize)
}

function demoUser() {
  const user = demoUsers[0]
  return {
    ...user,
    avatarUrl: '',
    vip: 2,
    vipLevel: 2,
    userRuleId: 5,
    authSource: 'demo',
    updatedAt: nowIso(),
    dataScope: 'all',
    identity: { name: user.displayName, avatar: '', mobile: user.phone, sex: 0, sexName: '未知', vip: 2 },
  }
}

function catalogMeta() {
  return {
    success: true,
    brands: [...new Set(demoGoods.map((item) => item.brand))],
    series: [...new Set(demoGoods.map((item) => item.series))],
    indexes: [...new Set(demoGoods.map((item) => item.model.slice(0, 1)))],
    brandOptions: [...new Set(demoGoods.map((item) => item.brand))],
    seriesOptions: [...new Set(demoGoods.map((item) => item.series))],
    indexOptions: [...new Set(demoGoods.map((item) => item.model.slice(0, 1)))],
  }
}

function salesSummary(query = {}) {
  const rows = filterRows(demoSales, query, ['goodsModel', 'goodsBrand', 'goodsSeries', 'salesperson', 'shopName', 'channel'])
  const receivedTotal = rows.reduce((sum, row) => sum + Number(row.receivedAmount || 0), 0)
  const quantityTotal = rows.reduce((sum, row) => sum + Number(row.quantity || 0), 0)
  return { success: true, sales: receivedTotal, receivedTotal, receivableTotal: receivedTotal, quantityTotal, orderCount: rows.length, topSalespersonName: rows[0]?.salesperson || '林溪', topShopName: rows[0]?.shopName || demoShops[0].name }
}

export function getDemoApiResponse(path, options = {}) {
  if (!isDemoMode()) {
    return null
  }
  const method = String(options.method || 'GET').toUpperCase()
  const query = options.query || {}
  const body = options.body || {}
  const cleanPath = String(path || '').split('?')[0]

  if (cleanPath === '/auth/check') {
    return { success: true, isAuthenticated: true, token: DEMO_TOKEN, user: demoUser(), session: { id: 1, createdAt: nowIso(), clientLabel: 'Demo' } }
  }
  if (cleanPath === '/auth/local-login' || cleanPath === '/auth/symuse/exchange') {
    return { success: true, message: '已进入演示模式', token: DEMO_TOKEN, user: demoUser(), rememberLogin: false }
  }
  if (cleanPath.startsWith('/auth/') || cleanPath.startsWith('/notifications')) {
    return { success: true, message: '演示模式已处理', notifications: [] }
  }
  if (cleanPath === '/shops/options') {
    return { success: true, options: demoShops }
  }
  if (cleanPath === '/shops') {
    const rows = filterRows(demoShops, query, ['name', 'shortName', 'managerName'])
    return { success: true, shops: paginate(rows, query), total: rows.length }
  }
  if (cleanPath === '/shop-schedules/me/summary') {
    return {
      success: true,
      summary: {
        shiftCount: 18,
        dateRangeLabel: '本月',
        periodLabel: '本月',
        tomorrowShifts: [{ shopId: 1, shopName: demoShops[0].name, shiftKey: 'morning', shiftText: '早班' }],
      },
    }
  }
  if (cleanPath === '/users/options') {
    return { success: true, options: demoUsers.map((item) => ({ id: item.id, username: item.username, displayName: item.displayName, aqcRoleKey: item.aqcRoleKey, aqcRoleName: item.aqcRoleName })) }
  }
  if (cleanPath === '/admin/users') {
    return { success: true, users: demoUsers }
  }
  if (cleanPath === '/goods/catalog/meta') {
    return catalogMeta()
  }
  if (cleanPath === '/goods/items') {
    const rows = filterRows(demoGoods.map(withGoodsComputed), query, ['brand', 'series', 'model', 'barcode', 'name'])
    return { success: true, items: paginate(rows, query), total: rows.length, ...catalogMeta() }
  }
  const barcodeMatch = cleanPath.match(/^\/goods\/barcode\/(.+)$/)
  if (barcodeMatch) {
    const barcode = decodeURIComponent(barcodeMatch[1] || '')
    const item = demoGoods.find((row) => row.barcode.toLowerCase() === barcode.toLowerCase())
    return item ? { success: true, item: withGoodsComputed(item) } : { success: false, message: '演示商品未匹配' }
  }
  const goodsInventoryMatch = cleanPath.match(/^\/goods\/items\/(-?\d+)\/inventory$/)
  if (goodsInventoryMatch) {
    const goodsId = Number(goodsInventoryMatch[1])
    const rows = inventories[goodsId] || []
    const totalStock = rows.reduce((sum, row) => sum + Number(row.quantity || 0), 0)
    return { success: true, inventories: rows, totalStock, totalQuantity: totalStock }
  }
  const goodsMatch = cleanPath.match(/^\/goods\/items\/(-?\d+)$/)
  if (goodsMatch) {
    const item = demoGoods.find((row) => Number(row.id) === Number(goodsMatch[1]))
    return item ? { success: true, item: withGoodsComputed(item) } : { success: false, message: '演示商品不存在' }
  }
  if (cleanPath === '/sales/meta') {
    return { success: true, channels: ['门店', '小程序', '企业微信', '私域', '团购', '其他'], salespersonOptions: demoUsers.map((item) => item.displayName), shopOptions: demoShops }
  }
  if (cleanPath === '/sales/summary') {
    return salesSummary(query)
  }
  if (cleanPath === '/sales/calendar') {
    return { success: true, days: [{ date: today(), amount: salesSummary(query).receivedTotal, count: demoSales.length }] }
  }
  if (cleanPath === '/sales/records' && method === 'POST') {
    const created = saleRow({ ...body, id: saleId += 1, goodsId: body.goodsId || 101, receivedAmount: body.receivedAmount, shopId: body.shopId || 1, salesperson: body.salesperson || '演示管理员', channel: body.channel || '门店', soldAt: body.soldAt || nowIso() })
    demoSales.unshift(created)
    return { success: true, message: '演示销售录入成功，数据仅保存在当前浏览器会话', record: created }
  }
  if (cleanPath === '/sales/records') {
    const rows = filterRows(demoSales, query, ['goodsModel', 'goodsBrand', 'goodsSeries', 'goodsBarcode', 'salesperson', 'shopName', 'customerName'])
    return { success: true, records: paginate(rows, query), total: rows.length, summary: salesSummary(query) }
  }
  if (cleanPath === '/sales/account-performance') {
    return { success: true, summary: salesSummary(query), records: demoSales }
  }
  if (cleanPath === '/work-orders/meta') {
    return { success: true, categories: [{ value: 'goods', label: '商品类工单' }, { value: 'sales', label: '销售类工单' }], types: [{ value: 'transfer', label: '商品调拨单', prefix: 'DB', category: 'goods' }, { value: 'purchase', label: '商品进货单', prefix: 'SJ', category: 'goods' }, { value: 'sale', label: '销售单', prefix: 'XS', category: 'sales' }], shopOptions: demoShops, storeOptions: demoShops.filter((item) => item.shopType === 0), warehouseOptions: demoShops.filter((item) => item.shopType === 1), users: demoUsers, groups: [{ id: 1, name: '演示协作组', memberRole: 'owner', memberCount: 3, isDefault: true }], approvalSettings: [] }
  }
  if (cleanPath === '/work-orders/dashboard') {
    return { success: true, dashboard: { draftCount: demoWorkOrders.filter((item) => item.status === 'draft').length, pendingCount: demoWorkOrders.filter((item) => item.status === 'pending').length, approvalCount: 1, mineCount: demoWorkOrders.length, recentMine: demoWorkOrders, pendingApprovals: demoWorkOrders.filter((item) => item.status === 'pending') } }
  }
  if (cleanPath === '/work-orders/settings') {
    return { success: true, settings: [] }
  }
  if (cleanPath === '/work-orders' && method === 'POST') {
    const created = workOrderRow({ id: workOrderId += 1, orderNum: `DEMO-WO-${workOrderId}`, orderType: body.orderType || 'transfer', reason: body.reason || '演示新建工单', status: body.status || 'draft' })
    demoWorkOrders.unshift(created)
    return { success: true, message: '演示工单创建成功，未上传服务器', order: created }
  }
  if (cleanPath === '/work-orders') {
    const rows = filterRows(demoWorkOrders, query, ['orderNum', 'reason', 'applicantName', 'sourceShopName', 'targetShopName'])
    return { success: true, orders: paginate(rows, query), total: rows.length }
  }
  const workOrderMatch = cleanPath.match(/^\/work-orders\/(\d+)$/)
  if (workOrderMatch) {
    const order = demoWorkOrders.find((item) => Number(item.id) === Number(workOrderMatch[1]))
    return order ? { success: true, order } : { success: false, message: '演示工单不存在' }
  }
  if (cleanPath === '/orders') {
    return { success: true, orders: [{ id: 7001, orderNum: 'DEMO-ORDER-001', status: 10, statusName: '待发货', userName: '演示顾客', goodsName: 'GM-2100-1A', amount: 1490, imported: false, createdAt: nowIso() }], total: 1 }
  }
  if (cleanPath.startsWith('/reports')) {
    return { success: true, message: '演示报告数据已生成', report: { id: 1, title: '演示报告', createdAt: nowIso(), modules: {} }, settings: [], logs: [], total: 0 }
  }
  if (cleanPath.includes('/logs') || cleanPath.endsWith('/inventory-logs')) {
    return { success: true, logs: [], total: 0 }
  }
  if (method !== 'GET') {
    return { success: true, message: '演示模式已保存，数据不会上传服务器' }
  }
  return { success: true }
}
