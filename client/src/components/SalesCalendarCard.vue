<template>
  <section
    :class="rootClass"
    :style="rootStyle"
  >
    <header class="panel-head sales-calendar-head">
      <div>
        <label
          v-if="showScopeSelect"
          class="dashboard-sales-title-select sales-calendar-scope-select"
          aria-label="切换日历点位"
        >
          <span class="panel-tag dashboard-sales-scope-label">{{ scopeDisplayLabel }}</span>
          <select :value="scopeValue" @change="onScopeChange">
            <option v-if="canSelectTotalScope" value="">{{ totalScopeLabel }}</option>
            <option
              v-for="option in normalizedScopeOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>
        </label>
        <p v-else-if="scopeDisplayLabel" class="panel-tag dashboard-sales-scope-label">{{ scopeDisplayLabel }}</p>
        <button
          v-if="titleInteractive"
          type="button"
          class="sales-summary-title-trigger"
          @click="emit('title-click')"
        >
          {{ title }}
        </button>
        <h2 v-else>{{ title }}</h2>
      </div>
      <div class="sales-summary-head-actions sales-calendar-summary-head">
        <div class="sales-kpi">
          <strong>¥ {{ formatMoney(calendar.totalAmount) }}</strong>
          <span>{{ calendar.activeDays }} 天有销售 · {{ calendar.totalQuantity }} 件商品</span>
        </div>
      </div>
    </header>

    <div class="sales-calendar-nav">
      <el-button circle :disabled="calendarLoading" @click="shiftCalendarMonth(-1)" aria-label="上一月">
        <span class="calendar-nav-arrow">‹</span>
      </el-button>
      <el-popover
        v-model:visible="calendarPickerVisible"
        trigger="click"
        placement="bottom"
        :width="340"
        popper-class="sales-calendar-picker-popper"
        @show="syncCalendarPickerState"
      >
        <template #reference>
          <button type="button" class="sales-calendar-month-trigger">
            <span class="sales-calendar-month-part">{{ calendarDisplayYear }}</span>
            <span class="sales-calendar-month-part">{{ calendarDisplayMonth }}</span>
          </button>
        </template>

        <div class="sales-calendar-picker">
          <div class="sales-calendar-picker-head">
            <span>快速跳转</span>
          </div>
          <el-select v-model="calendarPickerYear" class="full-width sales-calendar-year-select">
            <el-option
              v-for="year in calendarYearOptions"
              :key="year"
              :label="`${year}年`"
              :value="year"
            />
          </el-select>
          <div class="sales-calendar-picker-months">
            <button
              v-for="monthOption in calendarMonthOptions"
              :key="monthOption.value"
              type="button"
              class="sales-calendar-picker-month-chip"
              :class="{ active: monthOption.value === calendarPickerMonth }"
              @click="jumpCalendarMonth(monthOption.value)"
            >
              {{ monthOption.label }}
            </button>
          </div>
        </div>
      </el-popover>
      <el-button circle :disabled="calendarLoading" @click="shiftCalendarMonth(1)" aria-label="下一月">
        <span class="calendar-nav-arrow">›</span>
      </el-button>
    </div>

    <transition :name="calendarTransitionName" mode="out-in">
      <div :key="calendarMonth" class="sales-calendar-board" :class="{ 'is-loading': calendarLoading }">
        <div class="sales-calendar-weekdays">
          <span v-for="weekday in weekdayLabels" :key="weekday">{{ weekday }}</span>
        </div>
        <div class="sales-calendar-grid">
          <el-popover
            v-for="day in calendar.days"
            :key="day.date"
            trigger="hover"
            placement="top"
            :width="220"
            popper-class="sales-calendar-popover"
            :show-after="70"
          >
            <div class="sales-calendar-tooltip">
              <span>{{ formatCalendarTooltipDate(day.date) }}</span>
              <strong>{{ formatCalendarTooltipAmount(day.amount) }}</strong>
              <small>销量 {{ day.quantity }} · 客单价 {{ formatCalendarTicketValue(day.averageTicketValue) }}</small>
            </div>
            <template #reference>
              <article
                class="sales-calendar-day"
                :class="{
                  'is-outside': !day.isCurrentMonth,
                  'is-today': day.isToday,
                  'has-sales': day.amount !== 0 || day.quantity !== 0,
                  'has-negative-sales': day.amount < 0,
                }"
                role="button"
                tabindex="0"
                @click.stop="openCalendarDetail(day)"
                @keyup.enter.stop="openCalendarDetail(day)"
              >
                <div class="sales-calendar-day-number">{{ day.day }}</div>
                <div class="sales-calendar-day-amount">{{ formatCalendarAmount(day.amount) }}</div>
              </article>
            </template>
          </el-popover>
        </div>
      </div>
    </transition>

    <Teleport to="body">
      <transition name="calendar-detail-pop">
        <div v-if="calendarDetailVisible" class="sales-calendar-modal-layer" @click.self="closeCalendarDetail">
          <section class="card-surface sales-calendar-modal">
            <header class="sales-calendar-modal-head">
              <div class="sales-calendar-modal-copy">
                <span>{{ formatCalendarTooltipDate(calendarDetailDay?.date || '') }}</span>
                <h3>{{ calendarDetailShop ? calendarDetailShop.label : '销售详情' }}</h3>
              </div>
              <button type="button" class="sales-calendar-modal-close" @click="closeCalendarDetail">×</button>
            </header>

            <transition name="calendar-drill-panel" mode="out-in">
              <div
                :key="calendarDetailPerson ? `person-${calendarDetailShop?.label}-${calendarDetailPerson.label}` : calendarDetailShop ? `shop-${calendarDetailShop.label}` : 'day-overview'"
                class="sales-calendar-modal-stage"
                v-loading="calendarPersonDetailLoading"
              >
                <template v-if="!calendarDetailShop">
                  <div class="sales-calendar-detail-stats sales-calendar-detail-stats-lg">
                    <article class="sales-calendar-detail-stat">
                      <span>销售额</span>
                      <strong>{{ formatCalendarTooltipAmount(calendarDetailDay?.amount || 0) }}</strong>
                    </article>
                    <article class="sales-calendar-detail-stat">
                      <span>销售数量</span>
                      <strong>{{ calendarDetailDay?.quantity || 0 }}</strong>
                    </article>
                    <article class="sales-calendar-detail-stat">
                      <span>客单价</span>
                      <strong>{{ formatCalendarTicketValue(calendarDetailDay?.averageTicketValue || 0) }}</strong>
                    </article>
                  </div>

                  <div v-if="calendarDetailDay?.breakdowns?.length" class="sales-calendar-breakdown sales-calendar-breakdown-modal">
                    <div class="sales-calendar-breakdown-head">
                      <span>{{ calendarDetailDay?.breakdownTitle || '详细统计' }}</span>
                      <small v-if="calendarDetailDay?.breakdownMode === 'shop'">点击店铺销售额查看店铺内统计</small>
                      <small v-else-if="calendarDetailDay?.breakdownMode === 'salesperson'">点击人员查看当日商品销售情况</small>
                    </div>
                    <div class="sales-calendar-breakdown-list">
                      <button
                        v-for="item in calendarDetailDay?.breakdowns || []"
                        :key="`${calendarDetailDay?.date}-${item.label}`"
                        type="button"
                        class="sales-calendar-breakdown-item sales-calendar-breakdown-button"
                        :class="{ clickable: canOpenCalendarBreakdown(item) }"
                        @click="openCalendarBreakdown(item)"
                      >
                        <div class="sales-calendar-breakdown-main">
                          <span>{{ item.label }}</span>
                          <small>销量 {{ item.quantity }} · 客单价 {{ formatCalendarTicketValue(item.averageTicketValue) }}</small>
                        </div>
                        <div class="sales-calendar-breakdown-side">
                          <strong>{{ formatCalendarTooltipAmount(item.amount) }}</strong>
                          <el-icon v-if="canOpenCalendarBreakdown(item)" class="sales-calendar-breakdown-arrow"><ArrowRight /></el-icon>
                        </div>
                      </button>
                    </div>
                  </div>

                  <div v-else class="sales-calendar-empty-state">
                    <span>当天暂无销售明细</span>
                  </div>
                </template>

                <template v-else-if="!calendarDetailPerson">
                  <button type="button" class="sales-calendar-detail-back" @click="closeCalendarShopDetail">
                    <el-icon><ArrowLeft /></el-icon>
                    <span>返回当日总览</span>
                  </button>

                  <div class="sales-calendar-detail-stats sales-calendar-detail-stats-lg">
                    <article class="sales-calendar-detail-stat">
                      <span>{{ calendarDetailDay?.breakdownMode === 'shop' ? '店铺销售额' : '人员销售额' }}</span>
                      <strong>{{ formatCalendarTooltipAmount(calendarDetailShop.amount) }}</strong>
                    </article>
                    <article class="sales-calendar-detail-stat">
                      <span>销售数量</span>
                      <strong>{{ calendarDetailShop.quantity }}</strong>
                    </article>
                    <article class="sales-calendar-detail-stat">
                      <span>客单价</span>
                      <strong>{{ formatCalendarTicketValue(calendarDetailShop.averageTicketValue) }}</strong>
                    </article>
                    <article class="sales-calendar-detail-stat">
                      <span>订单数</span>
                      <strong>{{ calendarDetailShop.orderCount || 0 }}</strong>
                    </article>
                  </div>

                  <div v-if="calendarDetailShop.drilldowns?.length" class="sales-calendar-breakdown sales-calendar-breakdown-modal">
                    <div class="sales-calendar-breakdown-head">
                      <span>{{ calendarDetailShop.drilldownTitle || '店铺内统计' }}</span>
                      <small>点击人员查看当日商品销售情况</small>
                    </div>
                    <div class="sales-calendar-breakdown-list">
                      <button
                        v-for="item in calendarDetailShop.drilldowns || []"
                        :key="`${calendarDetailDay?.date}-${calendarDetailShop.label}-${item.label}`"
                        type="button"
                        class="sales-calendar-breakdown-item sales-calendar-breakdown-button"
                        @click="openCalendarPersonDetail(item)"
                      >
                        <div class="sales-calendar-breakdown-main">
                          <span>{{ item.label }}</span>
                          <small>销量 {{ item.quantity }} · 客单价 {{ formatCalendarTicketValue(item.averageTicketValue) }}</small>
                        </div>
                        <div class="sales-calendar-breakdown-side">
                          <strong>{{ formatCalendarTooltipAmount(item.amount) }}</strong>
                          <el-icon class="sales-calendar-breakdown-arrow"><ArrowRight /></el-icon>
                        </div>
                      </button>
                    </div>
                  </div>

                  <div v-else class="sales-calendar-empty-state">
                    <span>暂无人员销售明细</span>
                  </div>
                </template>

                <template v-else>
                  <button type="button" class="sales-calendar-detail-back" @click="closeCalendarPersonDetail">
                    <el-icon><ArrowLeft /></el-icon>
                    <span>{{ calendarDetailDay?.breakdownMode === 'salesperson' ? '返回当日总览' : '返回店铺详情' }}</span>
                  </button>

                  <div class="sales-calendar-detail-stats sales-calendar-detail-stats-lg">
                    <article class="sales-calendar-detail-stat">
                      <span>{{ isRepairMode ? '工程师销售额' : '人员销售额' }}</span>
                      <strong>{{ formatCalendarTooltipAmount(calendarDetailPerson.amount) }}</strong>
                    </article>
                    <article class="sales-calendar-detail-stat">
                      <span>销售数量</span>
                      <strong>{{ calendarDetailPerson.quantity }}</strong>
                    </article>
                    <article class="sales-calendar-detail-stat">
                      <span>客单价</span>
                      <strong>{{ formatCalendarTicketValue(calendarDetailPerson.averageTicketValue) }}</strong>
                    </article>
                    <article class="sales-calendar-detail-stat">
                      <span>订单数</span>
                      <strong>{{ calendarDetailPerson.orderCount || 0 }}</strong>
                    </article>
                  </div>

                  <div class="sales-calendar-breakdown sales-calendar-breakdown-modal">
                    <div class="sales-calendar-breakdown-head">
                      <span>{{ isRepairMode ? '当日维修明细' : '当日商品销售明细' }}</span>
                    </div>
                    <div v-if="calendarDetailPersonEntries.length" class="sales-calendar-breakdown-list">
                      <div
                        v-for="item in calendarDetailPersonEntries"
                        :key="`${calendarDetailDay?.date}-${calendarDetailShop?.label}-${calendarDetailPerson.label}-${item.label}`"
                        class="sales-calendar-breakdown-item"
                      >
                        <div class="sales-calendar-breakdown-main">
                          <span>{{ item.label }}</span>
                          <small>{{ item.meta }}</small>
                        </div>
                        <div class="sales-calendar-breakdown-side">
                          <strong>{{ formatCalendarTooltipAmount(item.amount) }}</strong>
                        </div>
                      </div>
                    </div>

                    <div v-else class="sales-calendar-empty-state sales-calendar-detail-inline-empty">
                      <span>当天暂无更细的商品销售明细</span>
                    </div>
                  </div>
                </template>
              </div>
            </transition>
          </section>
        </div>
      </transition>
    </Teleport>
  </section>
</template>

<script setup>
import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onBeforeUnmount, onMounted, reactive, ref, useAttrs, watch } from 'vue'

import { apiGet } from '../services/api'
import { useAuthStore } from '../stores/auth'

defineOptions({
  inheritAttrs: false,
})

const props = defineProps({
  query: {
    type: Object,
    default: () => ({}),
  },
  title: {
    type: String,
    default: '日历',
  },
  titleInteractive: {
    type: Boolean,
    default: false,
  },
  isRepairMode: {
    type: Boolean,
    default: false,
  },
  scopeValue: {
    type: String,
    default: '',
  },
  scopeLabel: {
    type: String,
    default: '',
  },
  scopeOptions: {
    type: Array,
    default: () => [],
  },
  showScopeSelect: {
    type: Boolean,
    default: true,
  },
  canSelectTotalScope: {
    type: Boolean,
    default: true,
  },
  totalScopeLabel: {
    type: String,
    default: '总销售额',
  },
  motionDelay: {
    type: String,
    default: '0.16s',
  },
  autoRefreshMs: {
    type: Number,
    default: 0,
  },
})

const emit = defineEmits(['update:scopeValue', 'scope-change', 'title-click', 'loaded'])
const attrs = useAttrs()
const authStore = useAuthStore()

const calendarLoading = ref(false)
const calendarMonth = ref(getCurrentMonthToken())
const calendarTransitionName = ref('calendar-slide-next')
const calendarPickerVisible = ref(false)
const calendarPickerYear = ref(Number(getCurrentMonthToken().slice(0, 4)))
const calendarPickerMonth = ref(Number(getCurrentMonthToken().slice(5, 7)))
const weekdayLabels = ['S', 'M', 'T', 'W', 'T', 'F', 'S']
const calendarDetailVisible = ref(false)
const calendarDetailDay = ref(null)
const calendarDetailShopLabel = ref('')
const calendarDetailPersonLabel = ref('')
const calendarPersonDetailLoading = ref(false)
const calendarDetailPersonEntries = ref([])
let calendarLoadRequestId = 0
let autoRefreshTimer = null
let autoRefreshPending = false

const calendar = reactive({
  month: '',
  monthLabel: '',
  totalAmount: 0,
  totalQuantity: 0,
  activeDays: 0,
  days: [],
})

const calendarMonthOptions = Array.from({ length: 12 }, (_, index) => ({
  value: index + 1,
  label: `${String(index + 1).padStart(2, '0')}月`,
}))

const rootClass = computed(() => [
  'card-surface',
  'sales-calendar-card',
  'motion-fade-slide',
  attrs.class,
])

const rootStyle = computed(() => ({
  ...(attrs.style && typeof attrs.style === 'object' ? attrs.style : {}),
  '--motion-delay': props.motionDelay,
}))

const querySignature = computed(() => JSON.stringify(props.query || {}))
const calendarDisplayYear = computed(() => `${parseCalendarMonthToken(calendarMonth.value).year}年`)
const calendarDisplayMonth = computed(() => `${String(parseCalendarMonthToken(calendarMonth.value).month).padStart(2, '0')}月`)
const scopeDisplayLabel = computed(() => {
  const scope = String(props.scopeLabel || '').trim() || (props.scopeValue ? String(props.scopeValue) : '总')
  return `${scope} · ${calendarDisplayMonth.value}`
})
const normalizedScopeOptions = computed(() => props.scopeOptions
  .map((option) => ({
    label: String(option?.label || option?.name || option?.value || '').trim(),
    value: String(option?.value ?? option?.id ?? option?.label ?? option?.name ?? '').trim(),
  }))
  .filter((option) => option.label && option.value))

const calendarYearOptions = computed(() => {
  const currentYear = Number(getCurrentMonthToken().slice(0, 4))
  const activeYear = parseCalendarMonthToken(calendarMonth.value).year || currentYear
  const startYear = Math.min(currentYear, activeYear) - 5
  const endYear = Math.max(currentYear, activeYear) + 2
  return Array.from({ length: endYear - startYear + 1 }, (_, index) => endYear - index)
})

const calendarDetailShop = computed(() => {
  if (!calendarDetailDay.value || !calendarDetailShopLabel.value) {
    return null
  }
  return (calendarDetailDay.value.breakdowns || []).find((item) => item.label === calendarDetailShopLabel.value) || null
})

const calendarDetailPerson = computed(() => {
  if (!calendarDetailShop.value || !calendarDetailPersonLabel.value) {
    return null
  }
  return (calendarDetailShop.value.drilldowns || []).find((item) => item.label === calendarDetailPersonLabel.value) || null
})

function formatMoney(value) {
  return new Intl.NumberFormat('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value || 0)
}

function truncateDecimal(value, digits = 2) {
  const factor = 10 ** digits
  return Math.floor(Number(value || 0) * factor) / factor
}

function getCurrentMonthToken() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

function parseCalendarMonthToken(token) {
  const [yearText, monthText] = String(token || getCurrentMonthToken()).split('-')
  return {
    year: Number(yearText || 0),
    month: Number(monthText || 1),
  }
}

function buildCalendarMonthToken(year, month) {
  return `${Number(year || 0)}-${String(Number(month || 1)).padStart(2, '0')}`
}

function syncCalendarPickerState() {
  const parsed = parseCalendarMonthToken(calendarMonth.value)
  calendarPickerYear.value = parsed.year
  calendarPickerMonth.value = parsed.month
}

function formatCalendarAmount(value) {
  const amount = Number(value || 0)
  if (amount === 0) {
    return '0'
  }
  const sign = amount < 0 ? '-' : ''
  const absolute = Math.abs(amount)
  if (absolute >= 10000) {
    return `${sign}${truncateDecimal(absolute / 10000).toFixed(2)}w`
  }
  if (absolute >= 1000) {
    return `${sign}${truncateDecimal(absolute / 1000).toFixed(2)}k`
  }
  return `${sign}${Math.floor(absolute)}`
}

function formatCalendarTooltipAmount(value) {
  const amount = Number(value || 0)
  if (amount === 0) {
    return '¥ 0.00'
  }
  return `${amount > 0 ? '+' : '-'}¥ ${formatMoney(Math.abs(amount))}`
}

function formatCalendarTicketValue(value) {
  return `¥ ${formatMoney(value || 0)}`
}

function formatCalendarTooltipDate(value) {
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  const weekday = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][date.getDay()]
  return `${value} ${weekday}`
}

function canOpenCalendarBreakdown(item) {
  return Array.isArray(item?.drilldowns) && item.drilldowns.length > 0
}

function openCalendarDetail(day) {
  calendarDetailDay.value = day
  calendarDetailShopLabel.value = ''
  calendarDetailPersonLabel.value = ''
  calendarDetailPersonEntries.value = []
  calendarPersonDetailLoading.value = false
  calendarDetailVisible.value = true
}

function closeCalendarDetail() {
  calendarDetailVisible.value = false
  calendarDetailDay.value = null
  calendarDetailShopLabel.value = ''
  calendarDetailPersonLabel.value = ''
  calendarDetailPersonEntries.value = []
  calendarPersonDetailLoading.value = false
}

function openCalendarShopDetail(label) {
  if (!calendarDetailVisible.value) {
    return
  }
  calendarDetailShopLabel.value = label
  calendarDetailPersonLabel.value = ''
  calendarDetailPersonEntries.value = []
}

function closeCalendarShopDetail() {
  calendarDetailShopLabel.value = ''
  calendarDetailPersonLabel.value = ''
  calendarDetailPersonEntries.value = []
  calendarPersonDetailLoading.value = false
}

function openCalendarBreakdown(item) {
  if (!canOpenCalendarBreakdown(item)) {
    return
  }
  openCalendarShopDetail(item.label)
  if (calendarDetailDay.value?.breakdownMode === 'salesperson') {
    void openCalendarPersonDetail(item.drilldowns[0])
  }
}

function buildCalendarPersonQuery({ date, shopName, salesperson }) {
  return {
    ...(props.query || {}),
    ...(shopName ? { shop_name: shopName } : {}),
    salesperson,
    date_from: date,
    date_to: date,
    page: 1,
    page_size: 200,
    sort_field: 'sold_at',
    sort_order: 'asc',
  }
}

function resolveCalendarPersonEntryLabel(record) {
  if (props.isRepairMode) {
    return String(record.note || '').trim() || String(record.orderNum || '').trim() || '维修项目'
  }
  return String(record.goodsModel || record.goodsDisplayName || '').trim()
    || [record.goodsBrand, record.goodsSeries].filter(Boolean).join(' ')
    || String(record.orderNum || '').trim()
    || '未命名商品'
}

function buildCalendarPersonEntries(records) {
  const grouped = new Map()
  for (const item of Array.isArray(records) ? records : []) {
    const label = resolveCalendarPersonEntryLabel(item)
    const current = grouped.get(label) || {
      label,
      amount: 0,
      quantity: 0,
      orderNums: new Set(),
    }
    current.amount = Number((current.amount + Number(item.receivedAmount || 0)).toFixed(2))
    current.quantity += Number(item.quantity || 0)
    if (item.orderNum) {
      current.orderNums.add(item.orderNum)
    }
    grouped.set(label, current)
  }
  return [...grouped.values()]
    .sort((left, right) => {
      if (right.amount !== left.amount) {
        return right.amount - left.amount
      }
      return String(left.label || '').localeCompare(String(right.label || ''), 'zh-CN')
    })
    .map((item) => ({
      label: item.label,
      amount: Number(item.amount || 0),
      meta: `${props.isRepairMode ? '单数' : '销量'} ${item.quantity || 0} · 订单 ${item.orderNums.size}`,
    }))
}

async function openCalendarPersonDetail(item) {
  if (!calendarDetailDay.value || !calendarDetailShop.value || !item?.label) {
    return
  }
  calendarDetailPersonLabel.value = ''
  calendarDetailPersonEntries.value = []
  if (Array.isArray(item.entries) && item.entries.length) {
    calendarDetailPersonEntries.value = item.entries
    calendarDetailPersonLabel.value = item.label
    return
  }
  calendarPersonDetailLoading.value = true
  const payload = await apiGet('/sales/records', {
    token: authStore.token,
    query: buildCalendarPersonQuery({
      date: calendarDetailDay.value.date,
      shopName: calendarDetailDay.value.breakdownMode === 'shop' ? calendarDetailShop.value.label : '',
      salesperson: item.label,
    }),
  })
  calendarPersonDetailLoading.value = false
  if (!payload?.success) {
    ElMessage.error(payload?.message || '人员销售明细加载失败')
    return
  }
  calendarDetailPersonEntries.value = buildCalendarPersonEntries(payload.records || [])
  calendarDetailPersonLabel.value = item.label
}

function closeCalendarPersonDetail() {
  if (calendarDetailDay.value?.breakdownMode === 'salesperson') {
    closeCalendarShopDetail()
    return
  }
  calendarDetailPersonLabel.value = ''
  calendarDetailPersonEntries.value = []
  calendarPersonDetailLoading.value = false
}

async function loadCalendar(options = {}) {
  const { silent = false, preserveDetail = false } = options
  const requestId = ++calendarLoadRequestId
  if (!silent) {
    calendarLoading.value = true
  }
  if (!preserveDetail) {
    closeCalendarDetail()
  }
  const payload = await apiGet('/sales/calendar', {
    token: authStore.token,
    query: {
      ...(props.query || {}),
      month: calendarMonth.value,
    },
  })
  if (requestId !== calendarLoadRequestId) {
    return
  }
  if (!silent) {
    calendarLoading.value = false
  }

  if (!payload?.success) {
    if (!silent) {
      ElMessage.error(payload?.message || '销售日历加载失败')
    }
    return
  }

  calendar.month = payload.month || calendarMonth.value
  calendar.monthLabel = payload.monthLabel || calendarMonth.value
  calendar.totalAmount = Number(payload.totalAmount || 0)
  calendar.totalQuantity = Number(payload.totalQuantity || 0)
  calendar.activeDays = Number(payload.activeDays || 0)
  calendar.days = payload.days || []
  emit('loaded', { ...payload })
}

function clearAutoRefreshTimer() {
  if (autoRefreshTimer !== null && typeof window !== 'undefined') {
    window.clearInterval(autoRefreshTimer)
    autoRefreshTimer = null
  }
}

function startAutoRefreshTimer() {
  clearAutoRefreshTimer()
  if (typeof window === 'undefined' || Number(props.autoRefreshMs || 0) <= 0) {
    return
  }
  autoRefreshTimer = window.setInterval(() => {
    if (document.visibilityState === 'hidden' || autoRefreshPending) {
      return
    }
    autoRefreshPending = true
    loadCalendar({ silent: true, preserveDetail: true }).finally(() => {
      autoRefreshPending = false
    })
  }, Number(props.autoRefreshMs))
}

function shiftCalendarMonth(step) {
  closeCalendarDetail()
  calendarPickerVisible.value = false
  calendarTransitionName.value = step >= 0 ? 'calendar-slide-next' : 'calendar-slide-prev'
  const { year, month } = parseCalendarMonthToken(calendarMonth.value)
  const nextDate = new Date(year, month - 1 + step, 1)
  calendarMonth.value = `${nextDate.getFullYear()}-${String(nextDate.getMonth() + 1).padStart(2, '0')}`
  syncCalendarPickerState()
  void loadCalendar()
}

function jumpCalendarMonth(monthValue) {
  const nextToken = buildCalendarMonthToken(calendarPickerYear.value, monthValue)
  if (nextToken === calendarMonth.value) {
    calendarPickerVisible.value = false
    return
  }
  closeCalendarDetail()
  calendarTransitionName.value = nextToken > calendarMonth.value ? 'calendar-slide-next' : 'calendar-slide-prev'
  calendarPickerMonth.value = Number(monthValue || 1)
  calendarMonth.value = nextToken
  calendarPickerVisible.value = false
  void loadCalendar()
}

function onScopeChange(event) {
  const nextValue = String(event?.target?.value || '')
  emit('update:scopeValue', nextValue)
  emit('scope-change', nextValue)
}

watch(querySignature, () => {
  void loadCalendar()
})

watch(
  () => props.autoRefreshMs,
  () => {
    startAutoRefreshTimer()
  },
)

onMounted(() => {
  void loadCalendar()
  startAutoRefreshTimer()
})

onBeforeUnmount(() => {
  clearAutoRefreshTimer()
})

defineExpose({
  loadCalendar,
  reload: loadCalendar,
})
</script>
