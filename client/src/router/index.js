import { createRouter, createWebHistory } from 'vue-router'

import AccountAdminView from '../views/AccountAdminView.vue'
import AccountSettingsView from '../views/AccountSettingsView.vue'
import DashboardView from '../views/DashboardView.vue'
import GoodsManageView from '../views/GoodsManageView.vue'
import LoginView from '../views/LoginView.vue'
import LogCenterView from '../views/LogCenterView.vue'
import MainLayout from '../layouts/MainLayout.vue'
import OrderManageView from '../views/OrderManageView.vue'
import ReportCenterView from '../views/ReportCenterView.vue'
import SalesEntryView from '../views/SalesEntryView.vue'
import SalesRecordsView from '../views/SalesRecordsView.vue'
import ShopManageView from '../views/ShopManageView.vue'
import ShopScheduleView from '../views/ShopScheduleView.vue'
import ShopTargetView from '../views/ShopTargetView.vue'
import SsoLogoutView from '../views/SsoLogoutView.vue'
import UserCenterView from '../views/UserCenterView.vue'
import WorkOrderManageView from '../views/WorkOrderManageView.vue'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: { public: true },
    },
    {
      path: '/sso-logout',
      name: 'sso-logout',
      component: SsoLogoutView,
      meta: { public: true },
    },
    {
      path: '/',
      component: MainLayout,
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          name: 'dashboard',
          component: DashboardView,
        },
        {
          path: 'reports',
          name: 'reports',
          component: ReportCenterView,
          meta: {
            permission: 'sales.read',
            headerTitle: '报告中心',
            headerSubtitle: '查看最新报告与历史报告推送',
          },
        },
        {
          path: 'sales/entry',
          name: 'sales-entry',
          component: SalesEntryView,
          meta: { permission: 'sales.write' },
        },
        {
          path: 'sales/repair-entry',
          name: 'repair-sales-entry',
          component: SalesEntryView,
          meta: { permission: 'sales.write' },
        },
        {
          path: 'sales/records',
          name: 'sales-records',
          component: SalesRecordsView,
          meta: { permission: 'sales.read' },
        },
        {
          path: 'sales/repair-records',
          name: 'repair-sales-records',
          component: SalesRecordsView,
          meta: { permission: 'sales.read' },
        },
        {
          path: 'work-orders',
          name: 'work-orders',
          component: WorkOrderManageView,
          meta: { permission: 'workorders.read' },
        },
        {
          path: 'orders',
          name: 'orders',
          component: OrderManageView,
          meta: { permission: 'orders.read' },
        },
        {
          path: 'goods',
          name: 'goods-manage',
          component: GoodsManageView,
          meta: { permission: 'goods.read' },
        },
        {
          path: 'shops',
          name: 'shops-manage',
          component: ShopManageView,
          meta: { permission: 'shops.read' },
        },
        {
          path: 'shops/:shopId/schedule',
          name: 'shop-schedule',
          component: ShopScheduleView,
          meta: { permission: 'shops.read' },
        },
        {
          path: 'shops/:shopId/target',
          name: 'shop-target',
          component: ShopTargetView,
          meta: { permission: 'shops.read' },
        },
        {
          path: 'logs',
          name: 'log-center',
          component: LogCenterView,
        },
        {
          path: 'update-logs',
          redirect: { name: 'log-center', query: { type: 'update' } },
        },
        {
          path: 'accounts',
          name: 'accounts',
          component: UserCenterView,
        },
        {
          path: 'accounts/settings',
          name: 'account-settings',
          component: AccountSettingsView,
        },
        {
          path: 'admin-settings',
          name: 'admin-settings',
          component: AccountAdminView,
          meta: { permission: 'admin.manage_users' },
        },
        {
          path: 'module/:moduleKey',
          redirect: { name: 'dashboard' },
        },
        {
          path: 'user-center',
          name: 'user-center',
          redirect: { name: 'accounts' },
        },
      ],
    },
  ],
})

router.beforeEach(async (to) => {
  const authStore = useAuthStore()
  if (authStore.loading) {
    await authStore.bootstrap()
  }

  const isPublicRoute = Boolean(to.meta?.public)
  const forceLogin = String(to.query.force_login || '').trim() === '1'
  const hasCallbackCode = String(to.query.code || '').trim().length > 0

  if (!isPublicRoute && !authStore.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (to.name === 'login' && authStore.isAuthenticated && !forceLogin && !hasCallbackCode) {
    return { name: 'dashboard' }
  }

  const requiredPermission = String(to.meta?.permission || '').trim()
  if (requiredPermission && !authStore.can(requiredPermission)) {
    return { name: 'accounts' }
  }

  if (authStore.aqcRoleKey === 'aqc_engineer') {
    if (to.name === 'sales-entry') {
      return { name: 'repair-sales-entry', query: to.query }
    }
    if (to.name === 'sales-records') {
      return { name: 'repair-sales-records', query: to.query }
    }
  }

  return true
})

export default router
