export const permissionLabels = {
  '*': '全部权限',
  'sales.read': '查看销售',
  'sales.write': '录入销售',
  'sales.manage': '管理销售',
  'orders.read': '查看订单',
  'orders.upload': '上传订单',
  'orders.manage': '管理订单',
  'goods.read': '查看商品',
  'goods.write': '编辑商品',
  'goods.manage': '管理商品',
  'shops.read': '查看店铺/仓库',
  'shops.write': '编辑店铺/仓库',
  'shops.manage': '管理店铺/仓库',
  'admin.manage_users': '管理账户',
  'admin.manage_roles': '管理权限',
  'admin.import_legacy': '导入旧数据',
  'auth.login': '账号登录',
  'auth.setting': '账户设置',
  action: '通用操作',
  dashboard: '仪表盘',
  'activity-apply': '活动申请',
  'activity-detail': '活动详情',
  'activity-list': '活动列表',
  'click-item-detail': '点击项详情',
  'click-item-list': '点击项列表',
  'click-offline-create': '线下点击录入',
  'click-offline-detail': '线下点击详情',
  'click-offline-list': '线下点击列表',
  'clock-item-apply': '打卡申请',
  'orderclock-action-change': '钟表订单改签',
  'orderclock-action-refund': '钟表订单退款',
  'orderclock-delete': '删除钟表订单',
  'orderclock-detail': '钟表订单详情',
  'orderclock-list': '钟表订单列表',
  'orderrepair-delete': '删除维修单',
  'orderrepair-detail': '维修单详情',
  'orderrepair-edit': '编辑维修单',
  'orderrepair-list': '维修单列表',
  shopdetail: '门店详情',
  'showlist-detail': '陈列详情',
  statistics_repair: '维修统计',
  statistics_user: '用户统计',
  'user-item-detail': '会员详情',
  'user-item-edit': '编辑会员',
  'user-item-list': '会员列表',
  'user-pickup-detail': '取货详情',
  'user-pickup-edit': '编辑取货',
  'user-pickup-list': '取货列表',
  'user-pickup-month': '月度取货',
  'work-management': '工作台',
}

export const rolePermissionSummaries = {
  aqc_admin: '全部权限',
  aqc_manager: '查看销售、录入销售、查看订单、查看商品、查看店铺/仓库',
  aqc_sales: '查看销售、录入销售、查看订单、查看商品、查看店铺/仓库',
  aqc_engineer: '查看销售、录入销售、查看订单、查看商品、查看店铺/仓库',
  aqc_departed: '无系统权限',
}

export function formatPermissionSummaryFromUser(userLike) {
  if (rolePermissionSummaries[userLike?.aqcRoleKey]) {
    return rolePermissionSummaries[userLike.aqcRoleKey]
  }
  const permissions = userLike?.permissions || []
  if (!permissions.length) {
    return '无权限'
  }
  if (permissions.includes('*')) {
    return '全部权限'
  }
  const labels = [...new Set(permissions.map((item) => permissionLabels[item] || item))]
  return labels.join('、')
}
