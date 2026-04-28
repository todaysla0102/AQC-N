<template>
  <section class="dashboard-page work-order-dashboard-page">
    <div class="dashboard-home-grid">
      <div class="dashboard-home-main">
        <SalesSummaryPanel
          v-if="authStore.can('sales.read')"
          panel-tag="主页"
          :display-title="salesSummaryTitle"
          :title-fallback="salesSummaryTitle"
          :query="salesSummaryQuery"
          :show-panel-tag="true"
          :show-kpi="true"
          :show-stats="false"
          :minimal="true"
          default-period="month"
          :auto-refresh-ms="15000"
        />

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
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import SalesSummaryPanel from '../components/SalesSummaryPanel.vue'
import { apiGet } from '../services/api'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const router = useRouter()
const isEngineerRole = computed(() => authStore.aqcRoleKey === 'aqc_engineer')

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
const salesSummaryTitle = computed(() => (isEngineerRole.value ? '维修销售额' : '销售额'))
const salesSummaryQuery = computed(() => (isEngineerRole.value ? { sale_kind: 'repair' } : {}))
const salesEntryButtonLabel = computed(() => (isEngineerRole.value ? '录入维修销售' : '扫码录入销售'))

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
  void Promise.all([loadWorkOrderDashboard(), loadScheduleSummary()])
})
</script>
