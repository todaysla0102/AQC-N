<template>
  <section class="account-page account-overview-page">
    <article class="card-surface account-overview-hero motion-fade-slide">
      <div class="account-overview-copy">
        <p class="panel-tag">统计与账户</p>
        <h2>{{ authStore.user?.displayName || 'AQC 成员' }}</h2>
        <div class="account-overview-meta">
          <span>{{ authStore.user?.aqcRoleName || '销售员' }}</span>
          <span>{{ shopSummary }}</span>
          <span>{{ authStore.user?.phone || authStore.user?.username || '-' }}</span>
        </div>
      </div>

      <div class="toolbar-actions account-overview-actions">
        <el-button type="primary" @click="router.push({ name: 'account-settings' })">账户设置</el-button>
      </div>
    </article>

    <section class="account-overview-grid">
      <article
        class="card-surface account-stat-card account-tenure-card motion-fade-slide"
        style="--motion-delay: 0.06s"
        role="button"
        tabindex="0"
        @click="cycleTenureDisplayMode"
        @keydown.enter.prevent="cycleTenureDisplayMode"
        @keydown.space.prevent="cycleTenureDisplayMode"
      >
        <div class="account-stat-card-head">
          <span class="account-stat-card-label">已加入 AQC</span>
          <span class="account-tenure-mode">{{ tenureDisplayModeLabel }}</span>
        </div>
        <div class="account-tenure-value">
          <strong>{{ joinedDaysDisplay }}</strong>
          <small>{{ employmentDateDisplay }}</small>
        </div>
      </article>

      <article
        class="card-surface account-stat-card account-commission-card motion-fade-slide"
        style="--motion-delay: 0.1s"
        role="button"
        tabindex="0"
        @click="goToOwnSalesRecords"
        @keydown.enter.prevent="goToOwnSalesRecords"
        @keydown.space.prevent="goToOwnSalesRecords"
      >
        <div class="account-stat-card-head">
          <span class="account-stat-card-label">参考提成</span>
          <button type="button" class="account-period-trigger" @click.stop="openRangeDialog('commission')">
            {{ commissionPeriodDisplayLabel }}
          </button>
        </div>

        <div class="account-commission-shell">
          <span class="account-commission-sales-amount">销售额 ¥ {{ formatMoney(performance.salesAmount) }}</span>
          <small class="account-commission-rate">× {{ commissionRateDisplay }}</small>
          <strong class="account-commission-value">¥ {{ formatMoney(performance.commissionAmount) }}</strong>
        </div>
      </article>

      <article
        class="card-surface account-stat-card account-ranking-card motion-fade-slide"
        style="--motion-delay: 0.14s"
        role="button"
        tabindex="0"
        @click="rankingDialogVisible = true"
        @keydown.enter.prevent="rankingDialogVisible = true"
        @keydown.space.prevent="rankingDialogVisible = true"
      >
        <div class="account-stat-card-head">
          <div class="account-ranking-scope-tabs" @click.stop>
            <button
              type="button"
              class="account-ranking-scope-tab"
              :class="{ active: rankingScope === 'shop' }"
              @click="setRankingScope('shop')"
            >
              店铺内排名
            </button>
            <button
              type="button"
              class="account-ranking-scope-tab"
              :class="{ active: rankingScope === 'company' }"
              @click="setRankingScope('company')"
            >
              全公司排名
            </button>
          </div>
          <button type="button" class="account-period-trigger" @click.stop="openRangeDialog('ranking')">
            {{ rankingPeriodDisplayLabel }}
          </button>
        </div>

        <div class="account-ranking-main">
          <div class="account-ranking-neighbor top" :class="{ hidden: !performance.previousEntry }">
            <span>{{ performance.previousEntry?.rank ? `第 ${performance.previousEntry.rank} 名` : '暂无更高名次' }}</span>
            <strong>{{ performance.previousEntry?.name || '-' }}</strong>
            <small>¥ {{ formatMoney(performance.previousEntry?.amount) }}</small>
          </div>

          <div class="account-ranking-current">
            <strong>{{ performance.currentRank > 0 ? `#${performance.currentRank}` : '--' }}</strong>
            <span>{{ performance.currentRank > 0 ? `共 ${performance.rankingCount} 人` : '暂无排名数据' }}</span>
            <p>{{ performance.currentEntry?.name || authStore.displayName || '-' }}</p>
            <small>¥ {{ formatMoney(performance.currentEntry?.amount) }}</small>
          </div>

          <div class="account-ranking-neighbor bottom" :class="{ hidden: !performance.nextEntry }">
            <span>{{ performance.nextEntry?.rank ? `第 ${performance.nextEntry.rank} 名` : '暂无下一位' }}</span>
            <strong>{{ performance.nextEntry?.name || '-' }}</strong>
            <small>¥ {{ formatMoney(performance.nextEntry?.amount) }}</small>
          </div>
        </div>
      </article>
    </section>

    <el-alert v-if="message" :title="message" :type="messageError ? 'error' : 'success'" :closable="false" show-icon />

    <ResponsiveDialog
      v-model="rangeDialogVisible"
      :title="rangeDialogTitle"
      width="min(720px, 94vw)"
      class="aqc-app-dialog account-range-dialog"
      mobile-subtitle="统计与账户"
    >
      <div class="goods-editor-shell account-range-dialog-shell">
        <div class="goods-compare-presets goods-sales-range-presets">
          <button
            v-for="preset in periodPresetOptions"
            :key="preset.value"
            type="button"
            class="goods-compare-preset-chip"
            :class="{ active: activeDraftPreset === preset.value }"
            @click="applyDraftPreset(preset.value)"
          >
            <span>{{ preset.label }}</span>
          </button>
        </div>

        <div class="sales-filter-grid account-range-grid">
          <div class="sales-filter-field sales-filter-field-wide">
            <label class="sales-filter-label">自定义时间范围</label>
            <el-date-picker
              v-model="activeDraftRange"
              type="daterange"
              unlink-panels
              class="full-width"
              value-format="YYYY-MM-DD"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
            />
          </div>

          <div v-if="showCommissionRateField" class="sales-filter-field account-rate-field">
            <label class="sales-filter-label">提成比例</label>
            <div class="account-rate-input-shell">
              <el-input-number
                v-model="commissionDraftRatePercent"
                :min="0"
                :max="100"
                :step="0.1"
                :precision="2"
                controls-position="right"
                class="full-width"
              />
              <span class="account-rate-input-suffix">%</span>
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="form-actions">
          <el-button @click="resetRangeToDefault">恢复本月</el-button>
          <el-button @click="rangeDialogVisible = false">关闭</el-button>
          <el-button type="primary" :loading="loading" @click="confirmRangeSelection">应用</el-button>
        </div>
      </template>
    </ResponsiveDialog>

    <ResponsiveDialog
      v-model="rankingDialogVisible"
      title="业绩排名"
      width="min(760px, 95vw)"
      class="aqc-app-dialog account-ranking-dialog"
      mobile-subtitle="统计与账户"
    >
      <div class="goods-editor-shell account-ranking-dialog-shell">
        <section class="card-surface account-ranking-dialog-toolbar">
          <div class="account-ranking-dialog-copy">
            <strong>{{ performance.rankScopeLabel || '店铺内排名' }}</strong>
            <span>{{ rankingPeriodDisplayLabel }}</span>
          </div>
          <button type="button" class="account-period-trigger" @click="openRangeDialog('ranking')">
            {{ rankingPeriodDisplayLabel }}
          </button>
        </section>

        <section class="catalog-table card-surface">
          <div class="table-shell open-table-shell">
            <el-table :data="performance.rankings" border stripe empty-text="暂无排名数据">
              <el-table-column prop="rank" label="名次" width="90" />
              <el-table-column prop="name" label="姓名" min-width="180" />
              <el-table-column v-if="rankingScope === 'company'" prop="shopName" label="所属店铺" min-width="180" show-overflow-tooltip />
              <el-table-column prop="quantity" label="销量" min-width="100" />
              <el-table-column label="销售额" min-width="140">
                <template #default="{ row }">¥ {{ formatMoney(row.amount) }}</template>
              </el-table-column>
            </el-table>
          </div>
        </section>
      </div>

      <template #footer>
        <div class="form-actions">
          <el-button @click="rankingDialogVisible = false">关闭</el-button>
        </div>
      </template>
    </ResponsiveDialog>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import ResponsiveDialog from '../components/ResponsiveDialog.vue'
import { apiGet } from '../services/api'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const router = useRouter()

const loading = ref(false)
const message = ref('')
const messageError = ref(false)
const rangeDialogVisible = ref(false)
const rankingDialogVisible = ref(false)
const rangeDialogTarget = ref('commission')
const rankingScope = ref('shop')
const DEFAULT_COMMISSION_RATE_PERCENT = 2
const COMMISSION_RATE_STORAGE_PREFIX = 'aqc_n_commission_rate_percent:'
const commissionPeriodPreset = ref('this_month')
const commissionDateRange = ref([])
const commissionDraftPreset = ref('this_month')
const commissionDraftRange = ref([])
const commissionRatePercent = ref(loadStoredCommissionRatePercent(authStore.user?.id))
const commissionDraftRatePercent = ref(commissionRatePercent.value)
const rankingPeriodPreset = ref('this_month')
const rankingDateRange = ref([])
const rankingDraftPreset = ref('this_month')
const rankingDraftRange = ref([])
const tenureDisplayModes = ['days', 'weeks', 'months', 'years']
const tenureDisplayMode = ref('days')

const performance = reactive({
  period: 'this_month',
  periodLabel: '本月',
  rangeLabel: '',
  commissionPeriod: 'this_month',
  commissionPeriodLabel: '本月',
  commissionRangeLabel: '',
  rankingPeriod: 'this_month',
  rankingPeriodLabel: '本月',
  rankingRangeLabel: '',
  employmentDate: '',
  joinedDays: null,
  commissionRate: commissionRatePercent.value / 100,
  salesAmount: 0,
  commissionAmount: 0,
  formulaText: '',
  rankScopeLabel: '店铺内排名',
  currentRank: 0,
  rankingCount: 0,
  currentEntry: { name: '', amount: 0, quantity: 0 },
  previousEntry: null,
  nextEntry: null,
  rankings: [],
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

const shopSummary = computed(() => {
  const names = Array.isArray(authStore.user?.shopNames) ? authStore.user.shopNames.filter(Boolean) : []
  if (names.length) {
    return names.join('、')
  }
  return authStore.user?.shopName || '未绑定店铺'
})

const tenureDisplayModeLabel = computed(() => {
  const map = {
    days: '按天',
    weeks: '按周',
    months: '按月',
    years: '按年',
  }
  return map[tenureDisplayMode.value] || '按天'
})

const joinedDaysDisplay = computed(() => {
  if (performance.joinedDays == null) {
    return '--'
  }
  return formatTenureDisplay(Number(performance.joinedDays || 0), tenureDisplayMode.value)
})

const employmentDateDisplay = computed(() => {
  return performance.employmentDate ? `入职时间 ${performance.employmentDate}` : '尚未设置入职时间'
})

const commissionPeriodDisplayLabel = computed(() => {
  return performance.commissionPeriodLabel || '本月'
})

const rankingPeriodDisplayLabel = computed(() => {
  return performance.rankingPeriodLabel || '本月'
})

const showCommissionRateField = computed(() => rangeDialogTarget.value === 'commission')

const commissionRateDisplay = computed(() => formatPercentLabel(
  Number.isFinite(Number(performance.commissionRate))
    ? performance.commissionRate
    : (commissionRatePercent.value / 100),
))

const rangeDialogTitle = computed(() => {
  return rangeDialogTarget.value === 'ranking' ? '排名时间范围' : '业绩时间范围'
})

const activeDraftPreset = computed({
  get() {
    return rangeDialogTarget.value === 'ranking' ? rankingDraftPreset.value : commissionDraftPreset.value
  },
  set(value) {
    if (rangeDialogTarget.value === 'ranking') {
      rankingDraftPreset.value = value
      return
    }
    commissionDraftPreset.value = value
  },
})

const activeDraftRange = computed({
  get() {
    return rangeDialogTarget.value === 'ranking' ? rankingDraftRange.value : commissionDraftRange.value
  },
  set(value) {
    if (rangeDialogTarget.value === 'ranking') {
      rankingDraftRange.value = Array.isArray(value) ? value : []
      return
    }
    commissionDraftRange.value = Array.isArray(value) ? value : []
  },
})

function setMessage(text, isError = false) {
  message.value = text
  messageError.value = isError
}

function formatMoney(value) {
  return new Intl.NumberFormat('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(value || 0))
}

function formatTenureDisplay(totalDays, mode) {
  const days = Math.max(Number(totalDays || 0), 0)
  if (mode === 'weeks') {
    return `${Math.floor(days / 7)} 周余 ${days % 7} 天`
  }
  if (mode === 'months') {
    return `${Math.floor(days / 30)} 月余 ${days % 30} 天`
  }
  if (mode === 'years') {
    return `${Math.floor(days / 365)} 年余 ${days % 365} 天`
  }
  return `${days} 天`
}

function cycleTenureDisplayMode() {
  const currentIndex = tenureDisplayModes.indexOf(tenureDisplayMode.value)
  const nextIndex = currentIndex < 0 ? 0 : (currentIndex + 1) % tenureDisplayModes.length
  tenureDisplayMode.value = tenureDisplayModes[nextIndex]
}

function formatDateValue(date) {
  const year = date.getFullYear()
  const month = `${date.getMonth() + 1}`.padStart(2, '0')
  const day = `${date.getDate()}`.padStart(2, '0')
  return `${year}-${month}-${day}`
}

function sanitizeCommissionRatePercent(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return DEFAULT_COMMISSION_RATE_PERCENT
  }
  return Math.min(100, Math.max(0, Math.round(numeric * 100) / 100))
}

function commissionRateStorageKey(userId) {
  const suffix = Number(userId || 0) > 0 ? String(Number(userId)) : 'default'
  return `${COMMISSION_RATE_STORAGE_PREFIX}${suffix}`
}

function loadStoredCommissionRatePercent(userId) {
  if (typeof window === 'undefined') {
    return DEFAULT_COMMISSION_RATE_PERCENT
  }
  const raw = window.localStorage.getItem(commissionRateStorageKey(userId))
  return sanitizeCommissionRatePercent(raw == null ? DEFAULT_COMMISSION_RATE_PERCENT : raw)
}

function saveStoredCommissionRatePercent(value, userId) {
  if (typeof window === 'undefined') {
    return
  }
  window.localStorage.setItem(commissionRateStorageKey(userId), String(sanitizeCommissionRatePercent(value)))
}

function formatPercentLabel(rate) {
  const percent = sanitizeCommissionRatePercent(Number(rate || 0) * 100)
  if (Number.isInteger(percent)) {
    return `${percent}%`
  }
  return `${percent.toFixed(percent % 1 === 0 ? 0 : (percent * 10) % 1 === 0 ? 1 : 2)}%`
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

function openRangeDialog(target = 'commission') {
  rangeDialogTarget.value = target === 'ranking' ? 'ranking' : 'commission'
  if (rangeDialogTarget.value === 'ranking') {
    rankingDraftPreset.value = rankingPeriodPreset.value
    rankingDraftRange.value = Array.isArray(rankingDateRange.value) ? [...rankingDateRange.value] : []
  } else {
    commissionDraftPreset.value = commissionPeriodPreset.value
    commissionDraftRange.value = Array.isArray(commissionDateRange.value) ? [...commissionDateRange.value] : []
    commissionDraftRatePercent.value = commissionRatePercent.value
  }
  rangeDialogVisible.value = true
}

function applyDraftPreset(preset) {
  activeDraftPreset.value = preset
  activeDraftRange.value = resolveRangeFromPreset(preset)
}

function resetRangeToDefault() {
  const nextRange = resolveRangeFromPreset('this_month')
  if (rangeDialogTarget.value === 'ranking') {
    rankingDraftPreset.value = 'this_month'
    rankingDraftRange.value = [...nextRange]
    return
  }
  commissionDraftPreset.value = 'this_month'
  commissionDraftRange.value = [...nextRange]
  commissionDraftRatePercent.value = commissionRatePercent.value
}

async function confirmRangeSelection() {
  if (rangeDialogTarget.value === 'ranking') {
    rankingPeriodPreset.value = rankingDraftPreset.value
    rankingDateRange.value = Array.isArray(rankingDraftRange.value) ? [...rankingDraftRange.value] : []
  } else {
    commissionPeriodPreset.value = commissionDraftPreset.value
    commissionDateRange.value = Array.isArray(commissionDraftRange.value) ? [...commissionDraftRange.value] : []
    commissionRatePercent.value = sanitizeCommissionRatePercent(commissionDraftRatePercent.value)
    saveStoredCommissionRatePercent(commissionRatePercent.value, authStore.user?.id)
  }
  rangeDialogVisible.value = false
  await loadPerformance()
}

async function setRankingScope(scope) {
  if (rankingScope.value === scope) {
    return
  }
  rankingScope.value = scope
  await loadPerformance()
}

async function loadPerformance() {
  loading.value = true
  const commissionPresetRange = resolveRangeFromPreset(commissionPeriodPreset.value)
  const hasCommissionCustomRange = Array.isArray(commissionDateRange.value)
    && commissionDateRange.value.length === 2
    && (
      commissionDateRange.value[0] !== commissionPresetRange[0]
      || commissionDateRange.value[1] !== commissionPresetRange[1]
    )
  const rankingPresetRange = resolveRangeFromPreset(rankingPeriodPreset.value)
  const hasRankingCustomRange = Array.isArray(rankingDateRange.value)
    && rankingDateRange.value.length === 2
    && (
      rankingDateRange.value[0] !== rankingPresetRange[0]
      || rankingDateRange.value[1] !== rankingPresetRange[1]
    )
  const query = {
    scope: rankingScope.value,
    commission_period: commissionPeriodPreset.value,
    commission_date_from: hasCommissionCustomRange ? (commissionDateRange.value?.[0] || '') : '',
    commission_date_to: hasCommissionCustomRange ? (commissionDateRange.value?.[1] || '') : '',
    commission_rate: String(commissionRatePercent.value / 100),
    ranking_period: rankingPeriodPreset.value,
    ranking_date_from: hasRankingCustomRange ? (rankingDateRange.value?.[0] || '') : '',
    ranking_date_to: hasRankingCustomRange ? (rankingDateRange.value?.[1] || '') : '',
  }
  const payload = await apiGet('/sales/account-performance', {
    token: authStore.token,
    query,
  })
  loading.value = false
  if (!payload?.success) {
    setMessage(payload?.message || '加载统计与账户数据失败', true)
    return
  }

  performance.period = String(payload.period || 'this_month')
  performance.periodLabel = String(payload.periodLabel || '本月')
  performance.rangeLabel = String(payload.rangeLabel || '')
  performance.commissionPeriod = String(payload.commissionPeriod || payload.period || 'this_month')
  performance.commissionPeriodLabel = String(payload.commissionPeriodLabel || payload.periodLabel || '本月')
  performance.commissionRangeLabel = String(payload.commissionRangeLabel || payload.rangeLabel || '')
  performance.rankingPeriod = String(payload.rankingPeriod || payload.period || 'this_month')
  performance.rankingPeriodLabel = String(payload.rankingPeriodLabel || payload.periodLabel || '本月')
  performance.rankingRangeLabel = String(payload.rankingRangeLabel || payload.rangeLabel || '')
  performance.employmentDate = String(payload.employmentDate || '')
  performance.joinedDays = payload.joinedDays == null ? null : Number(payload.joinedDays)
  performance.commissionRate = Math.min(1, Math.max(0, Number(payload.commissionRate ?? (commissionRatePercent.value / 100)) || 0))
  performance.salesAmount = Number(payload.salesAmount || 0)
  performance.commissionAmount = Number(payload.commissionAmount || 0)
  performance.formulaText = String(payload.formulaText || '')
  performance.rankScopeLabel = String(payload.rankScopeLabel || '店铺内排名')
  performance.currentRank = Number(payload.currentRank || 0)
  performance.rankingCount = Number(payload.rankingCount || 0)
  performance.currentEntry = payload.currentEntry || { name: authStore.displayName || '', amount: 0, quantity: 0 }
  performance.previousEntry = payload.previousEntry || null
  performance.nextEntry = payload.nextEntry || null
  performance.rankings = Array.isArray(payload.rankings) ? payload.rankings : []
  commissionRatePercent.value = sanitizeCommissionRatePercent(performance.commissionRate * 100)
}

async function goToOwnSalesRecords() {
  const dateRange = Array.isArray(commissionDateRange.value) ? commissionDateRange.value : []
  const salesperson = performance.salesAmount > 0
    ? String(performance.currentEntry?.name || authStore.displayName || authStore.user?.displayName || '').trim()
    : ''
  await router.push({
    name: authStore.aqcRoleKey === 'aqc_engineer' ? 'repair-sales-records' : 'sales-records',
    query: {
      account_salesperson: salesperson,
      account_date_from: String(dateRange[0] || ''),
      account_date_to: String(dateRange[1] || ''),
    },
  })
}

onMounted(async () => {
  commissionDateRange.value = resolveRangeFromPreset(commissionPeriodPreset.value)
  commissionDraftRange.value = [...commissionDateRange.value]
  rankingDateRange.value = resolveRangeFromPreset(rankingPeriodPreset.value)
  rankingDraftRange.value = [...rankingDateRange.value]
  await loadPerformance()
})
</script>
