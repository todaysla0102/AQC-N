<template>
  <section class="dashboard-page work-order-dashboard-page">
    <div class="dashboard-home-grid">
      <div class="dashboard-home-main">
        <template v-if="authStore.can('sales.read')">
          <div
            class="dashboard-card-viewport"
            @touchstart.passive="onDashboardTouchStart"
            @touchmove="onDashboardTouchMove"
            @touchend="onDashboardTouchEnd"
            @touchcancel="resetDashboardSwipe"
          >
            <div
              class="dashboard-card-track"
              :class="{
                'show-calendar': dashboardMainCard === 'calendar',
                'is-dragging': dashboardSwipeActive,
              }"
              :style="dashboardCardTrackStyle"
            >
              <div
                class="dashboard-card-slide"
                :class="{ active: dashboardMainCard === 'sales' }"
                :aria-hidden="dashboardMainCard !== 'sales'"
              >
                <SalesSummaryPanel
                  :key="`sales-${salesPanelKey}`"
                  panel-tag="主页"
                  :display-title="salesSummaryTitle"
                  :title-fallback="salesSummaryTitle"
                  :query="salesSummaryQuery"
                  :show-panel-tag="true"
                  :show-kpi="true"
                  :show-stats="false"
                  :minimal="true"
                  :default-period="salesPreferences.defaultPeriod"
                  :comparison-mode="salesPreferences.compareMode"
                  :compact-compare-amounts="true"
                  :compact-axis-labels="true"
                  :title-interactive="true"
                  :kpi-interactive="true"
                  :auto-refresh-ms="15000"
                  @loaded="onSalesSummaryLoaded"
                  @title-click="switchDashboardMainCard('calendar')"
                  @kpi-click="openSalesSettings"
                >
                  <template #panel-tag>
                    <label class="dashboard-sales-title-select" aria-label="切换销售范围">
                      <span class="panel-tag dashboard-sales-scope-label">{{ salesScopeDisplayLabel }}</span>
                      <select :value="activeSalesScopeValue" @change="onSalesScopeChange">
                        <option v-if="canSelectTotalSalesScope" value="all">总销售额</option>
                        <option
                          v-for="option in salesStoreOptions"
                          :key="option.id"
                          :value="String(option.id)"
                        >
                          {{ option.name }}
                        </option>
                      </select>
                    </label>
                  </template>
                </SalesSummaryPanel>
              </div>

              <div
                class="dashboard-card-slide"
                :class="{ active: dashboardMainCard === 'calendar' }"
                :aria-hidden="dashboardMainCard !== 'calendar'"
              >
                <SalesCalendarCard
                  class="dashboard-home-calendar-card"
                  title="日历"
                  title-interactive
                  :query="dashboardCalendarQuery"
                  :scope-value="activeSalesScopeValue === 'all' ? '' : activeSalesScopeValue"
                  :scope-label="salesScopeShortLabel"
                  :scope-options="dashboardCalendarScopeOptions"
                  :can-select-total-scope="canSelectTotalSalesScope"
                  motion-delay="0s"
                  @title-click="switchDashboardMainCard('sales')"
                  @scope-change="onDashboardCalendarScopeChange"
                />
              </div>
            </div>
          </div>
        </template>

        <article v-else class="card-surface profile-card motion-fade-slide">
          <header class="section-head">
            <h2>主页</h2>
            <p>当前身份暂无销售数据查看权限。</p>
          </header>
        </article>
      </div>

      <div v-if="showSideColumn" class="dashboard-home-side">
        <article v-if="showScheduleCard" class="card-surface profile-card motion-fade-slide dashboard-schedule-card">
          <div class="account-stat-card-head dashboard-schedule-head">
            <span class="account-stat-card-label">排班</span>
            <button type="button" class="account-period-trigger" @click="openScheduleRangeDialog">
              {{ scheduleSummary.periodLabel }}
            </button>
          </div>

          <button
            type="button"
            class="dashboard-schedule-main"
            @click="openOwnSchedule"
          >
            <span class="dashboard-schedule-caption">当前时间范围内排班数</span>
            <strong class="dashboard-schedule-value">{{ scheduleSummary.shiftCount }}</strong>
            <div class="dashboard-schedule-meta">
              <span>{{ scheduleSummary.dateRangeLabel }}</span>
            </div>
          </button>

          <div class="dashboard-schedule-tomorrow">
            <div class="dashboard-schedule-tomorrow-head">
              <span class="sales-filter-label">明日排班类型</span>
              <small>{{ tomorrowDateLabel }}</small>
            </div>

            <div v-if="tomorrowShiftRows.length" class="dashboard-schedule-shift-list">
              <article v-for="item in tomorrowShiftRows" :key="item.key" class="dashboard-schedule-shift-item">
                <strong>{{ item.shopName }}</strong>
                <span>{{ item.shiftText }}</span>
              </article>
            </div>
            <div v-else class="dashboard-schedule-empty">
              明日暂无排班
            </div>
          </div>

          <div class="work-order-dashboard-actions dashboard-schedule-actions">
            <el-button type="primary" :disabled="!authStore.can('sales.write')" @click="openSalesScanner">
              {{ salesEntryButtonLabel }}
            </el-button>
          </div>
        </article>

        <article v-if="authStore.can('workorders.read')" class="card-surface profile-card motion-fade-slide work-order-dashboard-card">
          <div class="work-order-summary-grid dashboard-summary-grid dashboard-summary-grid-compact">
            <button type="button" class="work-order-summary-card work-order-summary-card-compact" @click="goToScope('draft')">
              <span>草稿箱</span>
              <strong>{{ dashboard.draftCount }}</strong>
            </button>
            <button type="button" class="work-order-summary-card work-order-summary-card-compact" @click="goToScope('pending')">
              <span>待审批</span>
              <strong>{{ dashboard.pendingCount }}</strong>
            </button>
            <button
              type="button"
              class="work-order-summary-card work-order-summary-card-compact"
              :class="{ accent: authStore.can('workorders.approve') }"
              @click="goToScope(authStore.can('workorders.approve') ? 'approver' : 'mine')"
            >
              <span>{{ authStore.can('workorders.approve') ? '待我审核' : '我的工单' }}</span>
              <strong>{{ authStore.can('workorders.approve') ? dashboard.approvalCount : dashboard.mineCount }}</strong>
            </button>
          </div>

          <div class="work-order-dashboard-actions">
            <el-button v-if="authStore.can('workorders.write')" type="primary" @click="openCreateWorkOrder">新建工单</el-button>
            <el-button class="dashboard-secondary-action" @click="openWorkOrders">进入工单管理</el-button>
          </div>
        </article>
      </div>
    </div>

    <el-dialog
      v-model="scheduleRangeDialogVisible"
      title="排班时间范围"
      width="min(720px, 94vw)"
      append-to-body
      destroy-on-close
      align-center
      class="aqc-app-dialog account-range-dialog"
    >
      <div class="goods-editor-shell account-range-dialog-shell">
        <div class="goods-compare-presets goods-sales-range-presets">
          <button
            v-for="preset in periodPresetOptions"
            :key="preset.value"
            type="button"
            class="goods-compare-preset-chip"
            :class="{ active: scheduleDraftPreset === preset.value }"
            @click="applyDraftPreset(preset.value)"
          >
            <span>{{ preset.label }}</span>
          </button>
        </div>

        <div class="sales-filter-grid account-range-grid">
          <div class="sales-filter-field sales-filter-field-wide">
            <label class="sales-filter-label">自定义时间范围</label>
            <el-date-picker
              v-model="scheduleDraftRange"
              type="daterange"
              unlink-panels
              class="full-width"
              value-format="YYYY-MM-DD"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
            />
          </div>
        </div>
      </div>

      <template #footer>
        <div class="form-actions">
          <el-button @click="resetRangeToDefault">恢复本月</el-button>
          <el-button @click="scheduleRangeDialogVisible = false">关闭</el-button>
          <el-button type="primary" :loading="scheduleLoading" @click="confirmScheduleRange">应用</el-button>
        </div>
      </template>
    </el-dialog>

    <ResponsiveDialog
      v-model="salesSettingsVisible"
      title="销售额设置"
      width="min(720px, 94vw)"
      class="aqc-app-dialog dashboard-sales-settings-dialog"
      mobile-subtitle="首页图表"
      :initial-snap="0.66"
      :expanded-snap="0.94"
      :before-close="handleSalesSettingsBeforeClose"
    >
      <div class="dashboard-sales-settings-shell">
        <section class="header-floating-menu-section">
          <span class="header-floating-menu-label">销售额类目</span>
          <div class="header-panel-toggle dashboard-settings-toggle" role="tablist" aria-label="销售额类目">
            <button
              v-for="option in salesKindOptions"
              :key="option.value"
              type="button"
              class="header-panel-toggle-btn"
              :class="{ active: salesSettingsDraft.saleKind === option.value }"
              @click="salesSettingsDraft.saleKind = option.value"
            >
              {{ option.label }}
            </button>
          </div>
        </section>

        <section class="header-floating-menu-section">
          <span class="header-floating-menu-label">默认显示时间范围</span>
          <div class="header-theme-options dashboard-settings-options">
            <button
              v-for="option in salesPeriodOptions"
              :key="option.value"
              type="button"
              class="header-theme-option dashboard-settings-option"
              :class="{ active: salesSettingsDraft.defaultPeriod === option.value }"
              @click="salesSettingsDraft.defaultPeriod = option.value"
            >
              <span>{{ option.label }}</span>
            </button>
          </div>
        </section>

        <section class="header-floating-menu-section">
          <span class="header-floating-menu-label">默认数据对比</span>
          <div class="header-theme-options dashboard-settings-options">
            <button
              v-for="option in salesCompareOptions"
              :key="option.value"
              type="button"
              class="header-theme-option dashboard-settings-option"
              :class="{ active: salesSettingsDraft.compareMode === option.value }"
              @click="salesSettingsDraft.compareMode = option.value"
            >
              <span>{{ option.label }}</span>
            </button>
          </div>
        </section>

        <section class="header-floating-menu-section">
          <span class="header-floating-menu-label">默认显示点位</span>
          <div class="header-setting-switch-row dashboard-settings-select-row">
            <span>{{ defaultSalesScopeHint }}</span>
            <el-select
              v-model="salesSettingsDraft.defaultScope"
              filterable
              class="dashboard-settings-select"
              placeholder="选择默认点位"
            >
              <el-option v-if="canSelectTotalSalesScope" label="总销售额" value="all" />
              <el-option
                v-for="option in salesStoreOptions"
                :key="option.id"
                :label="option.name"
                :value="String(option.id)"
              />
            </el-select>
          </div>
        </section>
      </div>

      <template #footer>
        <div class="form-actions">
          <el-button @click="requestCloseSalesSettings">返回</el-button>
          <el-button type="primary" @click="saveSalesSettings">保存</el-button>
        </div>
      </template>
    </ResponsiveDialog>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import ResponsiveDialog from '../components/ResponsiveDialog.vue'
import SalesCalendarCard from '../components/SalesCalendarCard.vue'
import SalesSummaryPanel from '../components/SalesSummaryPanel.vue'
import { apiGet } from '../services/api'
import { useAuthStore } from '../stores/auth'
import { confirmAction } from '../utils/confirm'
import { simplifyShopName, SHOP_TYPE_STORE } from '../utils/shops'

const authStore = useAuthStore()
const router = useRouter()
const isEngineerRole = computed(() => authStore.aqcRoleKey === 'aqc_engineer')
const SALES_DASHBOARD_SETTINGS_KEY = 'aqc_n_dashboard_sales_settings_v1'

const salesPeriodOptions = [
  { value: 'day', label: '本日' },
  { value: 'week', label: '本周' },
  { value: 'month', label: '本月' },
  { value: 'ytd', label: '年累计' },
]
const salesKindOptions = [
  { value: 'goods', label: '门店销售额' },
  { value: 'repair', label: '维修中心销售额' },
]
const salesCompareOptions = [
  { value: 'period_total', label: '环比总额' },
  { value: 'period_elapsed', label: '环比同期' },
  { value: 'year_over_year', label: '同比' },
]

const dashboard = reactive({
  draftCount: 0,
  pendingCount: 0,
  approvalCount: 0,
  mineCount: 0,
})

const scheduleLoading = ref(false)
const scheduleRangeDialogVisible = ref(false)
const schedulePeriodPreset = ref('this_month')
const scheduleDateRange = ref([])
const scheduleDraftPreset = ref('this_month')
const scheduleDraftRange = ref([])
const scheduleSummary = reactive({
  period: 'this_month',
  periodLabel: '本月',
  dateFrom: '',
  dateTo: '',
  dateRangeLabel: '本月',
  shiftCount: 0,
  workDays: 0,
  tomorrowShifts: [],
})

const showScheduleCard = computed(() => authStore.can('shops.read'))
const showSideColumn = computed(() => showScheduleCard.value || authStore.can('workorders.read'))
const salesPanelKey = ref(0)
const dashboardMainCard = ref('sales')
const dashboardSwipeActive = ref(false)
const dashboardSwipeStart = reactive({
  x: 0,
  y: 0,
})
const dashboardSwipeDeltaX = ref(0)
const salesSettingsVisible = ref(false)
const salesActivePeriod = ref('month')
const salesStoreOptions = ref([])
const activeSalesScope = ref('all')
const salesPreferences = reactive({
  saleKind: 'goods',
  defaultPeriod: 'month',
  compareMode: 'period_total',
  defaultScope: 'all',
})
const salesSettingsDraft = reactive({
  saleKind: 'goods',
  defaultPeriod: 'month',
  compareMode: 'period_total',
  defaultScope: 'all',
})
const canSelectTotalSalesScope = computed(() => authStore.isAdmin)
const activeSalesScopeValue = computed(() => normalizeSalesScopeValue(activeSalesScope.value))
const salesActivePeriodLabel = computed(() => salesPeriodOptions.find((item) => item.value === salesActivePeriod.value)?.label || '本月')
const salesSummaryTitle = computed(() => '销售额')
const salesScopeShortLabel = computed(() => {
  const value = activeSalesScopeValue.value
  if (value === 'all') {
    return '总'
  }
  const option = salesStoreOptions.value.find((item) => String(item.id) === value)
  return simplifyShopName(option?.name || authStore.user?.shopName || '') || '当前店铺'
})
const salesScopeDisplayLabel = computed(() => `${salesScopeShortLabel.value} · ${salesActivePeriodLabel.value}`)
const salesSummaryQuery = computed(() => {
  const query = {
    sale_kind: salesPreferences.saleKind,
    compare_mode: salesPreferences.compareMode,
  }
  const scopeValue = activeSalesScopeValue.value
  if (scopeValue !== 'all') {
    query.shop_id = scopeValue
  }
  return query
})
const dashboardCalendarQuery = computed(() => {
  const query = {
    sale_kind: salesPreferences.saleKind,
  }
  const scopeValue = activeSalesScopeValue.value
  if (scopeValue !== 'all') {
    query.shop_id = scopeValue
  }
  return query
})
const dashboardCalendarScopeOptions = computed(() => salesStoreOptions.value.map((item) => ({
  label: item.name,
  value: String(item.id),
})))
const dashboardCardTrackStyle = computed(() => ({
  '--dashboard-swipe-offset': `${dashboardSwipeDeltaX.value}px`,
}))
const defaultSalesScopeHint = computed(() => (
  salesSettingsDraft.defaultScope === 'all'
    ? '总销售额'
    : salesStoreOptions.value.find((item) => String(item.id) === String(salesSettingsDraft.defaultScope))?.name || '当前店铺'
))
const salesEntryButtonLabel = computed(() => (isEngineerRole.value ? '录入维修销售' : '扫码录入销售'))
const salesSettingsDirty = computed(() => (
  JSON.stringify(normalizeSalesPreferences(salesSettingsDraft))
  !== JSON.stringify(normalizeSalesPreferences(salesPreferences))
))

const tomorrowDateLabel = computed(() => {
  const tomorrow = new Date()
  tomorrow.setDate(tomorrow.getDate() + 1)
  return `${tomorrow.getMonth() + 1} 月 ${tomorrow.getDate()} 日`
})

const tomorrowShiftRows = computed(() => {
  const grouped = new Map()
  for (const item of scheduleSummary.tomorrowShifts || []) {
    const shopName = String(item?.shopName || '当前店铺')
    if (!grouped.has(shopName)) {
      grouped.set(shopName, [])
    }
    const nextLabels = grouped.get(shopName)
    const label = String(item?.shiftLabel || '').trim()
    if (label && !nextLabels.includes(label)) {
      nextLabels.push(label)
    }
  }
  return [...grouped.entries()].map(([shopName, labels]) => ({
    key: `${shopName}-${labels.join('-')}`,
    shopName,
    shiftText: labels.join(' / '),
  }))
})

const periodPresetOptions = [
  { value: 'yesterday', label: '昨日' },
  { value: 'today', label: '今日' },
  { value: 'last_week', label: '上周' },
  { value: 'this_week', label: '本周' },
  { value: 'last_month', label: '上月' },
  { value: 'this_month', label: '本月' },
  { value: 'last_year', label: '去年' },
  { value: 'this_year', label: '本年' },
]

function formatDateValue(date) {
  const year = date.getFullYear()
  const month = `${date.getMonth() + 1}`.padStart(2, '0')
  const day = `${date.getDate()}`.padStart(2, '0')
  return `${year}-${month}-${day}`
}

function startOfWeek(date) {
  const next = new Date(date)
  const diff = next.getDay() === 0 ? -6 : 1 - next.getDay()
  next.setDate(next.getDate() + diff)
  next.setHours(0, 0, 0, 0)
  return next
}

function endOfWeek(date) {
  const next = startOfWeek(date)
  next.setDate(next.getDate() + 6)
  return next
}

function resolveRangeFromPreset(preset) {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  if (preset === 'today') {
    return [formatDateValue(today), formatDateValue(today)]
  }
  if (preset === 'yesterday') {
    const day = new Date(today)
    day.setDate(day.getDate() - 1)
    return [formatDateValue(day), formatDateValue(day)]
  }
  if (preset === 'this_week') {
    return [formatDateValue(startOfWeek(today)), formatDateValue(endOfWeek(today))]
  }
  if (preset === 'last_week') {
    const end = new Date(startOfWeek(today))
    end.setDate(end.getDate() - 1)
    const start = startOfWeek(end)
    return [formatDateValue(start), formatDateValue(end)]
  }
  if (preset === 'last_month') {
    const start = new Date(today.getFullYear(), today.getMonth() - 1, 1)
    const end = new Date(today.getFullYear(), today.getMonth(), 0)
    return [formatDateValue(start), formatDateValue(end)]
  }
  if (preset === 'this_year') {
    return [formatDateValue(new Date(today.getFullYear(), 0, 1)), formatDateValue(new Date(today.getFullYear(), 11, 31))]
  }
  if (preset === 'last_year') {
    return [formatDateValue(new Date(today.getFullYear() - 1, 0, 1)), formatDateValue(new Date(today.getFullYear() - 1, 11, 31))]
  }
  return [
    formatDateValue(new Date(today.getFullYear(), today.getMonth(), 1)),
    formatDateValue(new Date(today.getFullYear(), today.getMonth() + 1, 0)),
  ]
}

function getSalesSettingsStorageKey() {
  return `${SALES_DASHBOARD_SETTINGS_KEY}:${authStore.user?.id || 'anonymous'}`
}

function defaultSalesScopeValue() {
  if (authStore.isAdmin) {
    return 'all'
  }
  const userShopIds = Array.isArray(authStore.user?.shopIds) ? authStore.user.shopIds : []
  const primaryShopId = Number(userShopIds[0] || authStore.shopId || 0)
  return primaryShopId > 0 ? String(primaryShopId) : 'all'
}

function normalizeSalesScopeValue(value) {
  const raw = String(value || '').trim()
  if (canSelectTotalSalesScope.value && raw === 'all') {
    return 'all'
  }
  const numericValue = Number(raw)
  if (numericValue > 0) {
    return String(numericValue)
  }
  const fallback = defaultSalesScopeValue()
  return canSelectTotalSalesScope.value || fallback !== 'all' ? fallback : 'all'
}

function normalizeSalesPreferences(value = {}) {
  const saleKind = salesKindOptions.some((item) => item.value === value.saleKind) ? value.saleKind : (isEngineerRole.value ? 'repair' : 'goods')
  const defaultPeriod = salesPeriodOptions.some((item) => item.value === value.defaultPeriod) ? value.defaultPeriod : 'month'
  const compareMode = salesCompareOptions.some((item) => item.value === value.compareMode) ? value.compareMode : 'period_total'
  return {
    saleKind,
    defaultPeriod,
    compareMode,
    defaultScope: normalizeSalesScopeValue(value.defaultScope),
  }
}

function applySalesPreferences(value = {}) {
  const normalized = normalizeSalesPreferences(value)
  salesPreferences.saleKind = normalized.saleKind
  salesPreferences.defaultPeriod = normalized.defaultPeriod
  salesPreferences.compareMode = normalized.compareMode
  salesPreferences.defaultScope = normalized.defaultScope
  salesActivePeriod.value = normalized.defaultPeriod
  activeSalesScope.value = normalized.defaultScope
}

function copySalesPreferencesToDraft() {
  salesSettingsDraft.saleKind = salesPreferences.saleKind
  salesSettingsDraft.defaultPeriod = salesPreferences.defaultPeriod
  salesSettingsDraft.compareMode = salesPreferences.compareMode
  salesSettingsDraft.defaultScope = normalizeSalesScopeValue(salesPreferences.defaultScope)
}

function loadSalesPreferences() {
  const fallback = normalizeSalesPreferences({
    saleKind: isEngineerRole.value ? 'repair' : 'goods',
    defaultPeriod: 'month',
    compareMode: 'period_total',
    defaultScope: defaultSalesScopeValue(),
  })
  if (typeof window === 'undefined' || typeof window.localStorage === 'undefined') {
    applySalesPreferences(fallback)
    return
  }
  try {
    const raw = window.localStorage.getItem(getSalesSettingsStorageKey())
    const parsed = raw ? JSON.parse(raw) : {}
    applySalesPreferences({ ...fallback, ...(parsed && typeof parsed === 'object' ? parsed : {}) })
  } catch (error) {
    console.warn('Failed to read dashboard sales settings', error)
    applySalesPreferences(fallback)
  }
}

function persistSalesPreferences() {
  if (typeof window === 'undefined' || typeof window.localStorage === 'undefined') {
    return
  }
  try {
    window.localStorage.setItem(getSalesSettingsStorageKey(), JSON.stringify(normalizeSalesPreferences(salesPreferences)))
  } catch (error) {
    console.warn('Failed to persist dashboard sales settings', error)
  }
}

function ensureSalesScopeStillAvailable() {
  const storeIds = new Set(salesStoreOptions.value.map((item) => String(item.id)))
  const fallback = defaultSalesScopeValue()
  for (const target of [salesPreferences, salesSettingsDraft]) {
    if (target.defaultScope === 'all' && canSelectTotalSalesScope.value) {
      continue
    }
    if (!storeIds.has(String(target.defaultScope))) {
      target.defaultScope = storeIds.has(fallback) ? fallback : (canSelectTotalSalesScope.value ? 'all' : String(salesStoreOptions.value[0]?.id || fallback))
    }
  }
  if (activeSalesScope.value === 'all' && canSelectTotalSalesScope.value) {
    return
  }
  if (!storeIds.has(String(activeSalesScope.value))) {
    activeSalesScope.value = storeIds.has(String(salesPreferences.defaultScope)) ? String(salesPreferences.defaultScope) : String(salesStoreOptions.value[0]?.id || fallback)
  }
}

async function loadSalesStoreOptions() {
  if (!authStore.can('shops.read')) {
    return
  }
  const payload = await apiGet('/shops/options', {
    token: authStore.token,
    query: { limit: 300 },
  })
  if (!payload?.success) {
    return
  }
  salesStoreOptions.value = (payload.options || [])
    .filter((item) => Number(item.shopType ?? SHOP_TYPE_STORE) === SHOP_TYPE_STORE)
    .map((item) => ({
      id: Number(item.id),
      name: String(item.name || ''),
    }))
    .filter((item) => item.id > 0 && item.name)
  ensureSalesScopeStillAvailable()
}

function onSalesScopeChange(event) {
  activeSalesScope.value = normalizeSalesScopeValue(event?.target?.value)
}

function onDashboardCalendarScopeChange(value) {
  activeSalesScope.value = normalizeSalesScopeValue(value || 'all')
}

function switchDashboardMainCard(target) {
  const nextTarget = target === 'calendar' ? 'calendar' : 'sales'
  if (dashboardMainCard.value === nextTarget) {
    return
  }
  resetDashboardSwipe()
  dashboardMainCard.value = nextTarget
}

function resetDashboardSwipe() {
  dashboardSwipeActive.value = false
  dashboardSwipeDeltaX.value = 0
  dashboardSwipeStart.x = 0
  dashboardSwipeStart.y = 0
}

function onDashboardTouchStart(event) {
  const touch = event.touches?.[0]
  if (!touch) {
    return
  }
  dashboardSwipeActive.value = true
  dashboardSwipeDeltaX.value = 0
  dashboardSwipeStart.x = touch.clientX
  dashboardSwipeStart.y = touch.clientY
}

function onDashboardTouchMove(event) {
  if (!dashboardSwipeActive.value) {
    return
  }
  const touch = event.touches?.[0]
  if (!touch) {
    return
  }
  const deltaX = touch.clientX - dashboardSwipeStart.x
  const deltaY = touch.clientY - dashboardSwipeStart.y
  if (Math.abs(deltaX) < 10 || Math.abs(deltaX) < Math.abs(deltaY) * 1.18) {
    return
  }
  event.preventDefault?.()
  const canSwipeToCalendar = dashboardMainCard.value === 'sales' && deltaX < 0
  const canSwipeToSales = dashboardMainCard.value === 'calendar' && deltaX > 0
  if (!canSwipeToCalendar && !canSwipeToSales) {
    dashboardSwipeDeltaX.value = Math.max(-28, Math.min(28, deltaX * 0.18))
    return
  }
  dashboardSwipeDeltaX.value = Math.max(-140, Math.min(140, deltaX))
}

function onDashboardTouchEnd(event) {
  if (!dashboardSwipeActive.value) {
    return
  }
  const touch = event.changedTouches?.[0]
  const deltaX = touch ? touch.clientX - dashboardSwipeStart.x : dashboardSwipeDeltaX.value
  const deltaY = touch ? touch.clientY - dashboardSwipeStart.y : 0
  const isHorizontalSwipe = Math.abs(deltaX) >= 54 && Math.abs(deltaX) > Math.abs(deltaY) * 1.18
  const nextTarget = deltaX < 0 ? 'calendar' : 'sales'
  resetDashboardSwipe()
  if (isHorizontalSwipe) {
    switchDashboardMainCard(nextTarget)
  }
}

function onSalesSummaryLoaded(payload) {
  salesActivePeriod.value = String(payload?.period || salesPreferences.defaultPeriod || 'month')
}

function openSalesSettings() {
  copySalesPreferencesToDraft()
  salesSettingsVisible.value = true
}

async function confirmDiscardSalesSettings() {
  if (!salesSettingsDirty.value) {
    return true
  }
  try {
    await confirmAction('确认退出更改吗？内容将不会保存。', '退出确认', '退出')
    copySalesPreferencesToDraft()
    return true
  } catch (error) {
    return false
  }
}

function handleSalesSettingsBeforeClose(done) {
  confirmDiscardSalesSettings().then((ok) => {
    if (ok) {
      done()
    }
  })
}

async function requestCloseSalesSettings() {
  if (await confirmDiscardSalesSettings()) {
    salesSettingsVisible.value = false
  }
}

function saveSalesSettings() {
  const normalized = normalizeSalesPreferences(salesSettingsDraft)
  salesPreferences.saleKind = normalized.saleKind
  salesPreferences.defaultPeriod = normalized.defaultPeriod
  salesPreferences.compareMode = normalized.compareMode
  salesPreferences.defaultScope = normalized.defaultScope
  activeSalesScope.value = normalized.defaultScope
  salesActivePeriod.value = normalized.defaultPeriod
  persistSalesPreferences()
  salesPanelKey.value += 1
  salesSettingsVisible.value = false
  ElMessage.success('销售额设置已保存')
}

loadSalesPreferences()
copySalesPreferencesToDraft()

function goToScope(scope) {
  router.push({ name: 'work-orders', query: { scope } })
}

function openCreateWorkOrder() {
  router.push({ name: 'work-orders', query: { compose: '1', type: 'transfer' } })
}

function openWorkOrders() {
  router.push({ name: 'work-orders' })
}

function openSalesScanner() {
  if (!authStore.can('sales.write')) {
    return
  }
  if (isEngineerRole.value) {
    router.push({ name: 'repair-sales-entry' })
    return
  }
  router.push({ name: 'sales-entry', query: { scan: '1' } })
}

function openOwnSchedule() {
  const shopId = Number(authStore.shopId || 0)
  if (shopId <= 0) {
    router.push({ name: 'shops-manage' })
    return
  }
  const month = String(scheduleSummary.dateFrom || '').slice(0, 7) || activeMonthToken()
  router.push({
    name: 'shop-schedule',
    params: { shopId },
    query: month ? { month } : {},
  })
}

function activeMonthToken() {
  const now = new Date()
  return `${now.getFullYear()}-${`${now.getMonth() + 1}`.padStart(2, '0')}`
}

function openScheduleRangeDialog() {
  scheduleDraftPreset.value = schedulePeriodPreset.value
  scheduleDraftRange.value = Array.isArray(scheduleDateRange.value) ? [...scheduleDateRange.value] : []
  scheduleRangeDialogVisible.value = true
}

function applyDraftPreset(preset) {
  scheduleDraftPreset.value = preset
  scheduleDraftRange.value = resolveRangeFromPreset(preset)
}

function resetRangeToDefault() {
  scheduleDraftPreset.value = 'this_month'
  scheduleDraftRange.value = resolveRangeFromPreset('this_month')
}

async function confirmScheduleRange() {
  schedulePeriodPreset.value = scheduleDraftPreset.value
  scheduleDateRange.value = Array.isArray(scheduleDraftRange.value) ? [...scheduleDraftRange.value] : []
  scheduleRangeDialogVisible.value = false
  await loadScheduleSummary(true)
}

async function loadScheduleSummary(showError = false) {
  if (!showScheduleCard.value) {
    return
  }
  scheduleLoading.value = true
  const presetRange = resolveRangeFromPreset(schedulePeriodPreset.value)
  const hasCustomRange = Array.isArray(scheduleDateRange.value)
    && scheduleDateRange.value.length === 2
    && (
      scheduleDateRange.value[0] !== presetRange[0]
      || scheduleDateRange.value[1] !== presetRange[1]
    )
  const payload = await apiGet('/shop-schedules/me/summary', {
    token: authStore.token,
    query: {
      period: schedulePeriodPreset.value,
      date_from: hasCustomRange ? (scheduleDateRange.value?.[0] || '') : '',
      date_to: hasCustomRange ? (scheduleDateRange.value?.[1] || '') : '',
    },
  })
  scheduleLoading.value = false
  if (!payload?.success) {
    if (showError) {
      ElMessage.error(payload?.message || '排班摘要加载失败')
    }
    return
  }
  scheduleSummary.period = String(payload.period || schedulePeriodPreset.value || 'this_month')
  scheduleSummary.periodLabel = String(payload.periodLabel || '本月')
  scheduleSummary.dateFrom = String(payload.dateFrom || '')
  scheduleSummary.dateTo = String(payload.dateTo || '')
  scheduleSummary.dateRangeLabel = scheduleSummary.dateFrom && scheduleSummary.dateTo
    ? `${scheduleSummary.dateFrom} 至 ${scheduleSummary.dateTo}`
    : scheduleSummary.periodLabel
  scheduleSummary.shiftCount = Number(payload.shiftCount || 0)
  scheduleSummary.workDays = Number(payload.workDays || 0)
  scheduleSummary.tomorrowShifts = Array.isArray(payload.tomorrowShifts) ? payload.tomorrowShifts : []
}

async function loadWorkOrderDashboard() {
  if (!authStore.can('workorders.read')) {
    return
  }
  const payload = await apiGet('/work-orders/dashboard', {
    token: authStore.token,
  })
  if (!payload?.success) {
    return
  }
  dashboard.draftCount = Number(payload.draftCount || 0)
  dashboard.pendingCount = Number(payload.pendingCount || 0)
  dashboard.approvalCount = Number(payload.approvalCount || 0)
  dashboard.mineCount = Number(payload.draftCount || 0) + Number(payload.pendingCount || 0)
}

onMounted(() => {
  scheduleDateRange.value = resolveRangeFromPreset(schedulePeriodPreset.value)
  scheduleDraftRange.value = [...scheduleDateRange.value]
  void Promise.all([loadSalesStoreOptions(), loadWorkOrderDashboard(), loadScheduleSummary()])
})
</script>
