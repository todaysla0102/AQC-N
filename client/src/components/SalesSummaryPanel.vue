<template>
  <article class="card-surface chart-panel sales-summary-panel motion-fade-slide" :class="{ minimal: minimal }">
    <header class="panel-head" :class="{ compact: minimal }">
      <div>
        <slot name="panel-tag" :label="resolvedPanelTag">
          <p v-if="showPanelTag && resolvedPanelTag" class="panel-tag">{{ resolvedPanelTag }}</p>
        </slot>
        <slot name="title" :title="displayTitle || titleFallback">
          <button
            v-if="titleInteractive"
            type="button"
            class="sales-summary-title-trigger"
            @click="emit('title-click')"
          >
            {{ displayTitle || titleFallback }}
          </button>
          <h2 v-else>{{ displayTitle || titleFallback }}</h2>
        </slot>
      </div>
      <div
        v-if="showKpi || (allowToggleChart && toggleButtonPosition === 'header') || hasHeaderActionsSlot"
        class="sales-summary-head-actions"
      >
        <slot name="header-actions" />
        <button
          v-if="showKpi && kpiInteractive"
          type="button"
          class="sales-kpi sales-kpi-trigger"
          @click="emit('kpi-click')"
        >
          <strong>¥ {{ formatMoney(summary.sales) }}</strong>
          <span :class="{ up: summary.uplift >= 0, down: summary.uplift < 0 }">
            {{ compareLabel }} {{ formatCompareDelta(summary.uplift || 0) }}
          </span>
        </button>
        <div v-else-if="showKpi" class="sales-kpi">
          <strong v-if="showKpi">¥ {{ formatMoney(summary.sales) }}</strong>
          <span v-if="showKpi" :class="{ up: summary.uplift >= 0, down: summary.uplift < 0 }">
            {{ compareLabel }} {{ formatCompareDelta(summary.uplift || 0) }}
          </span>
        </div>
        <el-button
          v-if="allowToggleChart && toggleButtonPosition === 'header'"
          class="sales-chart-toggle"
          @click="toggleChart"
        >
          {{ showChart ? '隐藏图表' : '显示图表' }}
        </el-button>
      </div>
    </header>

    <div v-if="showStats" class="summary-stats-grid">
      <template v-for="card in summaryCards" :key="card.key">
        <el-popover
          v-if="card.detail"
          trigger="hover"
          placement="top"
          :width="220"
          popper-class="sales-calendar-popover sales-summary-champion-popper"
        >
          <div class="sales-calendar-tooltip">
            <span>{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
            <small>销售额 {{ formatTooltipAmount(card.detail.amount) }} · 销量 {{ card.detail.quantity }}</small>
          </div>
          <template #reference>
            <article class="summary-stat-card summary-stat-card-interactive">
              <span>{{ card.label }}</span>
              <strong>{{ card.value }}</strong>
            </article>
          </template>
        </el-popover>

        <article
          v-else
          class="summary-stat-card"
        >
          <span>{{ card.label }}</span>
          <strong>{{ card.value }}</strong>
        </article>
      </template>
    </div>

    <div v-if="showChart" class="sales-chart-shell motion-fade-slide chart-appear">
      <div ref="chartRef" class="sales-chart" />
    </div>

    <div class="metric-grid">
      <button
        v-for="metric in summary.metrics"
        :key="metric.key"
        type="button"
        class="metric-chip"
        :class="{ active: metric.key === activePeriod }"
        @click="changePeriod(metric.key)"
      >
        <span>{{ metric.label }}</span>
        <strong>¥ {{ formatMoney(metric.sales) }}</strong>
        <em :class="{ up: metric.uplift >= 0, down: metric.uplift < 0 }">
          {{ metricCompareLabel(metric.key) }} {{ formatCompareDelta(metric.uplift || 0) }}
        </em>
      </button>
    </div>

    <div v-if="allowToggleChart && toggleButtonPosition === 'footer'" class="sales-summary-footer">
      <el-button class="sales-chart-toggle" @click="toggleChart">
        {{ showChart ? '隐藏图表' : '显示图表' }}
      </el-button>
    </div>
  </article>
</template>

<script setup>
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, useSlots, watch } from 'vue'

import { apiGet } from '../services/api'
import { useAuthStore } from '../stores/auth'
import { useThemeStore } from '../stores/theme'

const props = defineProps({
  panelTag: {
    type: String,
    default: '销售趋势',
  },
  titleFallback: {
    type: String,
    default: '销售额',
  },
  allowToggleChart: {
    type: Boolean,
    default: false,
  },
  chartInitiallyHidden: {
    type: Boolean,
    default: false,
  },
  query: {
    type: Object,
    default: () => ({}),
  },
  displayTitle: {
    type: String,
    default: '销售额',
  },
  panelTagSuffix: {
    type: String,
    default: '',
  },
  showPanelTag: {
    type: Boolean,
    default: true,
  },
  showKpi: {
    type: Boolean,
    default: true,
  },
  showStats: {
    type: Boolean,
    default: true,
  },
  minimal: {
    type: Boolean,
    default: false,
  },
  toggleButtonPosition: {
    type: String,
    default: 'header',
  },
  defaultPeriod: {
    type: String,
    default: 'day',
  },
  autoRefreshMs: {
    type: Number,
    default: 0,
  },
  titleInteractive: {
    type: Boolean,
    default: false,
  },
  kpiInteractive: {
    type: Boolean,
    default: false,
  },
  comparisonMode: {
    type: String,
    default: 'period_total',
  },
  compactCompareAmounts: {
    type: Boolean,
    default: false,
  },
  compactAxisLabels: {
    type: Boolean,
    default: false,
  },
})
const emit = defineEmits(['loaded', 'title-click', 'kpi-click'])

const authStore = useAuthStore()
const themeStore = useThemeStore()
const slots = useSlots()

const chartRef = ref(null)
const chart = ref(null)
const resizeObserver = ref(null)
const activePeriod = ref(props.defaultPeriod || 'day')
const showChart = ref(!props.chartInitiallyHidden)
let chartResizeFrame = null
let chartResizeTimers = []
let autoRefreshTimer = null
let autoRefreshPending = false

const summary = reactive({
  title: '今日累计销售额',
  sales: 0,
  uplift: 0,
  metrics: [],
  points: [],
  yTicks: [],
  receivableTotal: 0,
  receivedTotal: 0,
  couponTotal: 0,
  discountAmountTotal: 0,
  averageTicketValue: 0,
  quantityTotal: 0,
  orderCount: 0,
  topSalespersonLabel: '今日个人销冠',
  topShopLabel: '今日店铺销冠',
  topSalespersonName: '暂无',
  topShopName: '暂无',
  topSalesperson: {
    name: '暂无',
    amount: 0,
    quantity: 0,
  },
  topShop: {
    name: '暂无',
    amount: 0,
    quantity: 0,
  },
})

const querySignature = computed(() => JSON.stringify(props.query || {}))

const summaryCards = computed(() => [
  { key: 'received', label: '实收总额', value: `¥ ${formatMoney(summary.receivedTotal)}` },
  { key: 'receivable', label: '应收总额', value: `¥ ${formatMoney(summary.receivableTotal)}` },
  { key: 'averageTicket', label: '客单价', value: `¥ ${formatMoney(summary.averageTicketValue)}` },
  { key: 'quantity', label: '销售数量', value: `${summary.quantityTotal || 0}` },
  { key: 'topSalesperson', label: summary.topSalespersonLabel || '今日个人销冠', value: summary.topSalespersonName || '暂无', detail: summary.topSalesperson },
  { key: 'topShop', label: summary.topShopLabel || '今日店铺销冠', value: summary.topShopName || '暂无', detail: summary.topShop },
])

const activeMetric = computed(() => summary.metrics.find((item) => item.key === activePeriod.value) || null)
const hasHeaderActionsSlot = computed(() => Boolean(slots['header-actions']))
const resolvedPanelTag = computed(() => {
  const baseLabel = activeMetric.value?.label || props.panelTag
  const suffix = String(props.panelTagSuffix || '').trim()
  return suffix ? `${baseLabel} · ${suffix}` : baseLabel
})
const compareLabel = computed(() => metricCompareLabel(activePeriod.value))

function getThemeColor(name, fallback) {
  if (typeof window === 'undefined') {
    return fallback
  }
  const value = window.getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return value || fallback
}

function toRgba(hexColor, alpha) {
  const hex = String(hexColor || '').trim().replace('#', '')
  if (hex.length !== 6) {
    return `rgba(200, 177, 107, ${alpha})`
  }
  const r = Number.parseInt(hex.slice(0, 2), 16)
  const g = Number.parseInt(hex.slice(2, 4), 16)
  const b = Number.parseInt(hex.slice(4, 6), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

function formatMoney(value) {
  return new Intl.NumberFormat('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value || 0)
}

function formatTooltipAmount(value) {
  const amount = Number(value || 0)
  if (amount === 0) {
    return `¥ ${formatMoney(0)}`
  }
  return `${amount > 0 ? '+' : '-'}¥ ${formatMoney(Math.abs(amount))}`
}

function formatAxisMoney(value) {
  if (props.compactAxisLabels) {
    return formatCompactMoney(value, { prefix: '¥' })
  }
  return `¥${new Intl.NumberFormat('zh-CN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value || 0)}`
}

function truncateDecimal(value, digits = 2) {
  const factor = 10 ** digits
  return Math.floor(Number(value || 0) * factor) / factor
}

function trimFixed(value, digits = 2) {
  return truncateDecimal(value, digits)
    .toFixed(digits)
    .replace(/\.?0+$/, '')
}

function formatCompactMoney(value, options = {}) {
  const amount = Number(value || 0)
  const prefix = String(options.prefix || '')
  if (amount === 0) {
    return `${prefix}0`
  }
  const sign = amount < 0 ? '-' : ''
  const absolute = Math.abs(amount)
  if (absolute >= 10000) {
    return `${sign}${prefix}${trimFixed(absolute / 10000)}w`
  }
  if (absolute >= 1000) {
    return `${sign}${prefix}${trimFixed(absolute / 1000)}k`
  }
  return `${sign}${prefix}${new Intl.NumberFormat('zh-CN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(absolute)}`
}

function formatCompareDelta(value) {
  const amount = Number(value || 0)
  const sign = amount >= 0 ? '+' : '-'
  if (props.compactCompareAmounts) {
    return `${sign}${formatCompactMoney(Math.abs(amount), { prefix: '¥' })}`
  }
  return `${sign}¥ ${formatMoney(Math.abs(amount))}`
}

function formatPointLabel(value, period) {
  if (!value) {
    return ''
  }
  if (period === 'day') {
    return value.slice(0, 16)
  }
  if (period === 'ytd') {
    const [year, month] = value.split('-')
    return `${year}年${month}月`
  }
  return value
}

function metricCompareLabel(period) {
  if (props.comparisonMode === 'year_over_year') {
    return '同比'
  }
  if (props.comparisonMode === 'period_elapsed') {
    if (period === 'day') {
      return '较昨日同期'
    }
    if (period === 'week') {
      return '较上周同期'
    }
    if (period === 'month') {
      return '较上月同期'
    }
    return '较去年同期'
  }
  if (period === 'day') {
    return '较昨日'
  }
  if (period === 'week') {
    return '较上周'
  }
  if (period === 'month') {
    return '较上月'
  }
  if (period === 'range') {
    return '较上一时段'
  }
  return '较去年同期'
}

const lineColor = computed(() => getThemeColor('--accent-color', themeStore.isDark ? '#e2cf9b' : '#c8b16b'))

function disposeChart() {
  if (chart.value) {
    chart.value.dispose()
    chart.value = null
  }
}

function clearScheduledChartResize() {
  if (typeof window === 'undefined') {
    return
  }
  if (chartResizeFrame !== null) {
    window.cancelAnimationFrame(chartResizeFrame)
    chartResizeFrame = null
  }
  chartResizeTimers.forEach((timerId) => window.clearTimeout(timerId))
  chartResizeTimers = []
}

function scheduleChartResize() {
  if (typeof window === 'undefined') {
    return
  }
  clearScheduledChartResize()
  const runResize = () => {
    chart.value?.resize()
  }
  chartResizeFrame = window.requestAnimationFrame(() => {
    chartResizeFrame = window.requestAnimationFrame(() => {
      chartResizeFrame = null
      runResize()
    })
  })
  ;[120, 240, 420].forEach((delay) => {
    const timerId = window.setTimeout(runResize, delay)
    chartResizeTimers.push(timerId)
  })
}

async function fetchSummary(period = activePeriod.value, options = {}) {
  const { animate = true } = options
  const payload = await apiGet('/sales/summary', {
    token: authStore.token,
    query: {
      period,
      ...(props.query || {}),
    },
  })

  if (!payload?.success) {
    ElMessage.error(payload?.message || '销售统计加载失败')
    return
  }

  activePeriod.value = payload.period
  summary.title = payload.title || '销售额'
  summary.sales = Number(payload.sales || 0)
  summary.uplift = Number(payload.uplift || 0)
  summary.metrics = payload.metrics || []
  summary.points = payload.points || []
  summary.yTicks = payload.yTicks || []
  summary.receivableTotal = Number(payload.receivableTotal || 0)
  summary.receivedTotal = Number(payload.receivedTotal || 0)
  summary.couponTotal = Number(payload.couponTotal || 0)
  summary.discountAmountTotal = Number(payload.discountAmountTotal || 0)
  summary.averageTicketValue = Number(payload.averageTicketValue || 0)
  summary.quantityTotal = Number(payload.quantityTotal || 0)
  summary.orderCount = Number(payload.orderCount || 0)
  summary.topSalespersonLabel = String(payload.topSalespersonLabel || '今日个人销冠')
  summary.topShopLabel = String(payload.topShopLabel || '今日店铺销冠')
  summary.topSalespersonName = String(payload.topSalespersonName || '暂无')
  summary.topShopName = String(payload.topShopName || '暂无')
  summary.topSalesperson = {
    name: String(payload.topSalesperson?.name || summary.topSalespersonName || '暂无'),
    amount: Number(payload.topSalesperson?.amount || 0),
    quantity: Number(payload.topSalesperson?.quantity || 0),
  }
  summary.topShop = {
    name: String(payload.topShop?.name || summary.topShopName || '暂无'),
    amount: Number(payload.topShop?.amount || 0),
    quantity: Number(payload.topShop?.quantity || 0),
  }
  emit('loaded', {
    ...payload,
    period: payload.period,
    title: summary.title,
    receivableTotal: summary.receivableTotal,
    receivedTotal: summary.receivedTotal,
    quantityTotal: summary.quantityTotal,
    orderCount: summary.orderCount,
  })

  if (showChart.value) {
    await nextTick()
    renderChart({ animate })
  }
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
    fetchSummary(activePeriod.value, { animate: false }).finally(() => {
      autoRefreshPending = false
    })
  }, Number(props.autoRefreshMs))
}

function renderChart(options = {}) {
  const { animate = true } = options
  if (!showChart.value || !chartRef.value) {
    return
  }
  if (chart.value && chart.value.getDom() !== chartRef.value) {
    disposeChart()
  }
  if (!chart.value) {
    chart.value = echarts.init(chartRef.value)
  }
  chart.value.clear()

  const xData = summary.points.map((item) => item.x)
  const yData = summary.points.map((item) => Number(item.y || 0))
  const yTicks = summary.yTicks.map((item) => Number(item || 0))
  const rawAxisTop = yTicks.length ? Math.max(yTicks[yTicks.length - 1], ...yData, 0) : Math.max(...yData, 0)
  const axisTop = rawAxisTop > 0 ? rawAxisTop : 1
  const axisInterval = yTicks.length > 1 ? yTicks[1] - yTicks[0] : axisTop <= 4 ? 1 : undefined
  const axisTextColor = themeStore.isDark ? '#a8b2ac' : '#5b6f82'
  const splitLineColor = themeStore.isDark ? 'rgba(244,245,239,0.12)' : 'rgba(111,130,150,0.12)'
  const tooltipBackground = themeStore.isDark ? 'rgba(18, 22, 20, 0.94)' : 'rgba(255, 255, 255, 0.94)'
  const tooltipBorder = themeStore.isDark ? 'rgba(244,245,239,0.14)' : 'rgba(17,17,17,0.08)'
  const tooltipText = themeStore.isDark ? '#f4f5ef' : '#111111'
  const axisPointerColor = themeStore.isDark ? toRgba(lineColor.value, 0.36) : toRgba(lineColor.value, 0.22)
  const useCategoryInset = activePeriod.value !== 'day'

  chart.value.setOption({
    backgroundColor: 'transparent',
    animationDuration: animate ? 1120 : 0,
    animationEasing: 'exponentialOut',
    animationDurationUpdate: animate ? 760 : 0,
    animationEasingUpdate: 'exponentialOut',
    grid: {
      left: activePeriod.value === 'day' ? 58 : 64,
      right: 28,
      top: 30,
      bottom: 54,
      containLabel: false,
    },
    tooltip: {
      trigger: 'axis',
      confine: true,
      backgroundColor: tooltipBackground,
      borderColor: tooltipBorder,
      borderWidth: 1,
      extraCssText: 'border-radius: 18px; box-shadow: 0 18px 40px rgba(0,0,0,0.12);',
      textStyle: {
        color: tooltipText,
      },
      position: (point, _params, _dom, _rect, size) => {
        const [mouseX, mouseY] = point
        const [boxWidth, boxHeight] = size.contentSize
        const [viewWidth, viewHeight] = size.viewSize
        let left = mouseX + 18
        if (left + boxWidth > viewWidth - 12) {
          left = mouseX - boxWidth - 18
        }
        let top = mouseY - boxHeight / 2
        if (top < 12) {
          top = 12
        }
        if (top + boxHeight > viewHeight - 12) {
          top = viewHeight - boxHeight - 12
        }
        return [left, top]
      },
      axisPointer: {
        type: 'line',
        lineStyle: {
          color: axisPointerColor,
          width: 1.5,
        },
      },
      formatter: (params) => {
        const point = Array.isArray(params) ? params[0] : params
        const index = point?.dataIndex ?? 0
        const current = summary.points[index] || {}
        const label = formatPointLabel(current.x, activePeriod.value)
        return [
          `<div style="display:grid;gap:10px;min-width:196px;">`,
          `<div style="font-size:12px;color:${axisTextColor};">${label}</div>`,
          `<div style="display:flex;align-items:center;justify-content:space-between;gap:16px;">`,
          `<span style="display:inline-flex;align-items:center;gap:8px;"><i style="width:9px;height:9px;border-radius:999px;background:${lineColor.value};display:inline-block;"></i>此段销售额</span>`,
          `<strong style="font-size:16px;">¥ ${formatMoney(current.segmentSales || 0)}</strong>`,
          `</div>`,
          `<div style="display:flex;align-items:center;justify-content:space-between;gap:16px;">`,
          `<span style="color:${axisTextColor};">销售数量</span>`,
          `<span>${current.quantity || 0}</span>`,
          `</div>`,
          `</div>`,
        ].join('')
      },
    },
    xAxis: {
      type: 'category',
      data: xData,
      boundaryGap: useCategoryInset,
      axisTick: { show: true, alignWithLabel: true },
      axisLine: { lineStyle: { color: splitLineColor } },
      axisLabel: {
        color: axisTextColor,
        fontSize: 11,
        margin: 16,
        showMinLabel: true,
        showMaxLabel: true,
        hideOverlap: false,
        formatter: (value, index) => {
          if (activePeriod.value === 'day') {
            return index % 3 === 0 ? value.slice(11, 16) : ''
          }
          if (activePeriod.value === 'ytd') {
            return value.slice(5)
          }
          return index % 2 === 0 ? value.slice(5) : ''
        },
      },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: axisTop,
      interval: axisInterval,
      axisTick: { show: true },
      axisLine: {
        lineStyle: {
          color: splitLineColor,
        },
      },
      axisLabel: {
        color: axisTextColor,
        margin: 14,
        showMinLabel: true,
        showMaxLabel: true,
        formatter: (value) => formatAxisMoney(value),
      },
      splitLine: {
        lineStyle: {
          color: splitLineColor,
        },
      },
    },
    series: [
      {
        type: 'line',
        smooth: true,
        smoothMonotone: 'x',
        animationDuration: animate ? 1120 : 0,
        animationEasing: 'exponentialOut',
        animationDurationUpdate: animate ? 760 : 0,
        animationEasingUpdate: 'exponentialOut',
        animationDelay: animate ? ((index) => index * 28) : 0,
        symbol: 'circle',
        symbolSize: 5,
        showSymbol: false,
        lineStyle: {
          width: 3,
          color: lineColor.value,
        },
        itemStyle: {
          color: lineColor.value,
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: toRgba(lineColor.value, themeStore.isDark ? 0.34 : 0.24) },
            { offset: 1, color: toRgba(lineColor.value, 0.04) },
          ]),
        },
        emphasis: {
          focus: 'series',
          scale: true,
          itemStyle: {
            color: lineColor.value,
            borderColor: themeStore.isDark ? '#121614' : '#ffffff',
            borderWidth: 2,
          },
        },
        data: yData,
      },
    ],
  }, {
    notMerge: true,
    lazyUpdate: false,
  })
  scheduleChartResize()
}

function changePeriod(period) {
  if (period === activePeriod.value) {
    return
  }
  void fetchSummary(period, { animate: true })
}

async function toggleChart() {
  showChart.value = !showChart.value
}

function handleResize() {
  chart.value?.resize()
}

function disconnectResizeObserver() {
  resizeObserver.value?.disconnect?.()
  resizeObserver.value = null
}

function observeChartLayout() {
  disconnectResizeObserver()
  if (typeof window === 'undefined' || typeof window.ResizeObserver === 'undefined') {
    return
  }
  const targets = [chartRef.value, chartRef.value?.parentElement].filter(Boolean)
  if (!targets.length) {
    return
  }
  const observer = new window.ResizeObserver(() => {
    handleResize()
  })
  targets.forEach((target) => observer.observe(target))
  resizeObserver.value = observer
}

watch(
  () => themeStore.isDark,
  async () => {
    if (!showChart.value) {
      return
    }
    await nextTick()
    renderChart({ animate: false })
  },
)

watch(
  showChart,
  async (visible) => {
    if (!visible) {
      disconnectResizeObserver()
      clearScheduledChartResize()
      disposeChart()
      return
    }
    await nextTick()
    renderChart({ animate: false })
    observeChartLayout()
    scheduleChartResize()
  },
)

watch(
  querySignature,
  () => {
    void fetchSummary(activePeriod.value, { animate: true })
  },
)

watch(
  () => props.autoRefreshMs,
  () => {
    startAutoRefreshTimer()
  },
)

onMounted(async () => {
  await fetchSummary(activePeriod.value)
  observeChartLayout()
  startAutoRefreshTimer()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  disconnectResizeObserver()
  clearScheduledChartResize()
  clearAutoRefreshTimer()
  window.removeEventListener('resize', handleResize)
  disposeChart()
})

defineExpose({
  reload: (options = {}) => fetchSummary(activePeriod.value, options),
})
</script>
