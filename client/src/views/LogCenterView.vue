<template>
  <section class="log-center-page account-page">
    <section class="motion-fade-slide log-center-toolbar-row" style="--motion-delay: 0.04s">
      <div class="log-center-toolbar-copy">
        <div class="log-center-toolbar-meta">
          <span>{{ activeTypeMeta.label }}</span>
          <span v-if="contextLabel">{{ contextLabel }}</span>
          <span>{{ totalRecords }} 条记录</span>
          <span v-if="isInventoryType">当前库存 {{ inventoryCurrentTotal }}</span>
          <span v-else-if="isOrderUploadType">成功 {{ orderUploadSuccessCount }} · 失败 {{ orderUploadFailedCount }}</span>
          <span v-else-if="isUpdateType">{{ updateTimestampLabel }}</span>
        </div>
      </div>

      <div class="toolbar-actions log-center-toolbar-actions">
        <el-button @click="goBack">返回</el-button>
        <el-button :loading="loading" @click="refreshLogs">刷新</el-button>
      </div>
    </section>

    <section class="sales-filter-shell log-center-filter-shell motion-fade-slide" style="--motion-delay: 0.08s">
      <div class="sales-filter-trigger-row">
        <button type="button" class="sales-filter-trigger" :class="{ active: filterPanelOpen }" @click="filterPanelOpen = !filterPanelOpen">
          <div class="sales-filter-trigger-copy">
            <span>搜索与筛选</span>
            <strong>{{ filterPanelOpen ? '收起当前日志筛选' : '展开当前日志筛选' }}</strong>
          </div>
          <div class="sales-filter-trigger-meta">
            <div class="sales-filter-trigger-stats">
              <span>已筛选 {{ activeFilterCount }} 项</span>
              <strong>{{ totalRecords }} 条结果</strong>
            </div>
          </div>
        </button>
      </div>

      <CollapsePanelTransition>
        <div v-if="filterPanelOpen" class="sales-filter-collapse-shell">
          <section class="sales-filter-panel log-center-filter-panel">
            <header class="sales-filter-head">
              <div class="sales-filter-head-copy">
                <h2>筛选</h2>
                <span>{{ activeTypeMeta.label }}</span>
              </div>
              <div class="toolbar-actions sales-filter-head-actions">
                <el-button type="primary" :loading="loading" @click="onSearch">查询</el-button>
                <el-button :disabled="!activeFilterCount" @click="resetFilters">清空筛选</el-button>
              </div>
            </header>

            <div class="sales-filter-grid log-center-filter-grid">
              <div class="sales-filter-field sales-filter-field-wide">
                <label class="sales-filter-label">关键词</label>
                <el-input
                  v-model.trim="keyword"
                  clearable
                  :placeholder="keywordPlaceholder"
                  class="full-width"
                  @keyup.enter="onSearch"
                />
              </div>

              <div v-if="showGoodsSelector" class="sales-filter-field">
                <label class="sales-filter-label">商品</label>
                <el-select
                  v-model="selectedGoodsId"
                  class="full-width"
                  filterable
                  remote
                  reserve-keyword
                  clearable
                  placeholder="搜索并选择商品"
                  :remote-method="loadGoodsOptions"
                  :loading="goodsOptionsLoading"
                >
                  <el-option
                    v-for="item in goodsOptions"
                    :key="item.id"
                    :label="item.label"
                    :value="item.id"
                  />
                </el-select>
              </div>

              <div v-if="showShopSelector" class="sales-filter-field">
                <label class="sales-filter-label">{{ isShopScheduleType ? '排班店铺' : '店铺 / 仓库' }}</label>
                <el-select
                  v-model="selectedShopId"
                  class="full-width"
                  filterable
                  remote
                  reserve-keyword
                  clearable
                  placeholder="搜索并选择店铺 / 仓库"
                  :remote-method="loadShopOptions"
                  :loading="shopOptionsLoading"
                >
                  <el-option
                    v-for="item in shopOptions"
                    :key="item.id"
                    :label="item.label"
                    :value="item.id"
                  />
                </el-select>
              </div>

              <div v-if="showMonthSelector" class="sales-filter-field">
                <label class="sales-filter-label">月份</label>
                <el-date-picker
                  v-model="selectedMonth"
                  type="month"
                  value-format="YYYY-MM"
                  placeholder="筛选月份"
                  class="full-width"
                />
              </div>

              <div v-if="showOrderSelector" class="sales-filter-field">
                <label class="sales-filter-label">订单</label>
                <el-select
                  v-model="selectedOrderId"
                  class="full-width"
                  filterable
                  remote
                  reserve-keyword
                  clearable
                  placeholder="搜索并选择订单"
                  :remote-method="loadOrderOptions"
                  :loading="orderOptionsLoading"
                >
                  <el-option
                    v-for="item in orderOptions"
                    :key="item.id"
                    :label="item.label"
                    :value="item.id"
                  />
                </el-select>
              </div>

              <div v-if="showWorkOrderScopeFilter" class="sales-filter-field">
                <label class="sales-filter-label">范围</label>
                <el-select v-model="workOrderScope" class="full-width">
                  <el-option
                    v-for="item in workOrderScopeOptions"
                    :key="item.value"
                    :label="item.label"
                    :value="item.value"
                  />
                </el-select>
              </div>

              <div v-if="showWorkOrderTypeFilter" class="sales-filter-field">
                <label class="sales-filter-label">工单类型</label>
                <el-select v-model="workOrderType" clearable placeholder="全部工单类型" class="full-width">
                  <el-option
                    v-for="item in workOrderTypeOptions"
                    :key="item.value"
                    :label="item.label"
                    :value="item.value"
                  />
                </el-select>
              </div>

              <div v-if="showUpdateScopeFilter" class="sales-filter-field">
                <label class="sales-filter-label">范围</label>
                <el-select v-model="updateScopeFilter" class="full-width">
                  <el-option label="全部范围" value="all" />
                  <el-option
                    v-for="scope in updateScopeOptions"
                    :key="scope"
                    :label="scope"
                    :value="scope"
                  />
                </el-select>
              </div>

              <div v-if="showUpdateVersionFilter" class="sales-filter-field">
                <label class="sales-filter-label">版本</label>
                <el-select v-model="updateVersionFilter" class="full-width">
                  <el-option label="全部版本" value="all" />
                  <el-option
                    v-for="version in updateVersionOptions"
                    :key="version"
                    :label="version"
                    :value="version"
                  />
                </el-select>
              </div>

              <div v-if="showOrderUploadSuccessFilter" class="sales-filter-field">
                <label class="sales-filter-label">结果</label>
                <el-select v-model="orderUploadSuccessFilter" class="full-width">
                  <el-option label="全部结果" value="all" />
                  <el-option label="成功" value="success" />
                  <el-option label="失败" value="failed" />
                </el-select>
              </div>

              <div v-if="showReportPeriodFilter" class="sales-filter-field">
                <label class="sales-filter-label">报告类型</label>
                <el-select v-model="reportPeriodFilter" class="full-width">
                  <el-option label="全部报告" value="all" />
                  <el-option label="日报" value="day" />
                  <el-option label="周报" value="week" />
                  <el-option label="月报" value="month" />
                </el-select>
              </div>

              <div v-if="showReportScopeFilter" class="sales-filter-field">
                <label class="sales-filter-label">报告范围</label>
                <el-select v-model="reportScopeFilter" class="full-width">
                  <el-option
                    v-for="item in reportScopeOptions"
                    :key="item.value"
                    :label="item.label"
                    :value="item.value"
                  />
                </el-select>
              </div>

              <div class="sales-filter-field sales-filter-field-wide">
                <label class="sales-filter-label">日期范围</label>
                <div class="log-center-date-range">
                  <el-date-picker
                    v-model="dateFrom"
                    type="date"
                    value-format="YYYY-MM-DD"
                    placeholder="开始日期"
                    class="full-width"
                  />
                  <span class="log-center-date-range-separator">至</span>
                  <el-date-picker
                    v-model="dateTo"
                    type="date"
                    value-format="YYYY-MM-DD"
                    placeholder="结束日期"
                    class="full-width"
                  />
                </div>
              </div>
            </div>
          </section>
        </div>
      </CollapsePanelTransition>
    </section>

    <el-alert v-if="errorMessage && !hasData" :title="errorMessage" type="error" :closable="false" show-icon />

    <section v-if="isUpdateType" class="update-log-history-list log-center-update-list" v-loading="loading">
      <article
        v-for="entry in pagedUpdateEntries"
        :key="`${entry.date}-${entry.version || ''}-${entry.title}`"
        class="card-surface motion-fade-slide update-log-entry"
      >
        <div class="update-log-entry-copy">
          <div class="update-log-entry-meta">
            <span>{{ entry.date }}</span>
            <span v-if="entry.version" class="update-log-entry-tag">{{ entry.version }}</span>
            <span
              v-for="scopeTag in entry.scopeTags"
              :key="`${entry.date}-${entry.version || ''}-${entry.title}-${scopeTag}`"
              class="update-log-entry-tag"
            >
              {{ scopeTag }}
            </span>
          </div>
          <strong>{{ entry.title }}</strong>
          <p v-if="entry.summary">{{ entry.summary }}</p>
        </div>
        <ul v-if="entry.highlights.length" class="update-log-entry-list">
          <li v-for="item in entry.highlights" :key="item">{{ item }}</li>
        </ul>
      </article>

      <div v-if="!loading && !pagedUpdateEntries.length" class="update-log-empty log-center-empty">
        <strong>没有匹配的更新日志</strong>
        <p>{{ errorMessage || '可以换一个关键词，或清空筛选条件后再试。' }}</p>
      </div>
    </section>

    <article v-else class="card-surface motion-fade-slide log-center-table-card" style="--motion-delay: 0.12s">
      <div class="table-shell open-table-shell" v-loading="loading">
        <el-table :data="tableRows" border stripe :empty-text="emptyText">
          <template v-if="isReportType">
            <el-table-column prop="createdAt" label="生成时间" min-width="180" show-overflow-tooltip />
            <el-table-column prop="title" label="报告标题" min-width="260" show-overflow-tooltip />
            <el-table-column prop="periodLabel" label="类型" min-width="110" />
            <el-table-column prop="rangeLabel" label="统计周期" min-width="200" show-overflow-tooltip />
            <el-table-column prop="scopeLabel" label="报告范围" min-width="180" show-overflow-tooltip />
            <el-table-column label="摘要" min-width="280" show-overflow-tooltip>
              <template #default="{ row }">{{ formatHighlights(row.highlights) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="104" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openReportRow(row)">查看</el-button>
              </template>
            </el-table-column>
          </template>

          <template v-else-if="isGoodsInventoryType">
            <el-table-column prop="goodsModel" label="商品型号" min-width="220" show-overflow-tooltip />
            <el-table-column label="店铺 / 仓库" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">{{ row.shopName || '-' }}</template>
            </el-table-column>
            <el-table-column prop="changeContent" label="变更内容" min-width="220" show-overflow-tooltip />
            <el-table-column prop="quantityBefore" label="变更前" min-width="100" />
            <el-table-column prop="quantityAfter" label="变更后" min-width="100" />
            <el-table-column prop="totalQuantityAfter" label="商品总数" min-width="110" />
            <el-table-column prop="createdAt" label="变更时间" min-width="180" show-overflow-tooltip />
            <el-table-column prop="operatorName" label="操作人员" min-width="140" show-overflow-tooltip />
            <el-table-column label="操作" width="104" fixed="right">
              <template #default="{ row }">
                <el-button v-if="resolveTraceTarget(row)" link type="primary" @click="traceLogRecord(row)">追溯</el-button>
                <span v-else>-</span>
              </template>
            </el-table-column>
          </template>

          <template v-else-if="isShopInventoryType">
            <el-table-column prop="goodsModel" label="商品型号" min-width="220" show-overflow-tooltip />
            <el-table-column prop="changeContent" label="变更内容" min-width="220" show-overflow-tooltip />
            <el-table-column prop="quantityBefore" label="变更前" min-width="100" />
            <el-table-column prop="quantityAfter" label="变更后" min-width="100" />
            <el-table-column prop="totalQuantityAfter" label="商品总数" min-width="110" />
            <el-table-column prop="createdAt" label="变更时间" min-width="180" show-overflow-tooltip />
            <el-table-column prop="operatorName" label="操作人员" min-width="140" show-overflow-tooltip />
            <el-table-column label="操作" width="104" fixed="right">
              <template #default="{ row }">
                <el-button v-if="resolveTraceTarget(row)" link type="primary" @click="traceLogRecord(row)">追溯</el-button>
                <span v-else>-</span>
              </template>
            </el-table-column>
          </template>

          <template v-else-if="isWorkOrderType">
            <el-table-column prop="createdAt" label="操作时间" min-width="180" show-overflow-tooltip />
            <el-table-column prop="orderNum" label="工单号" min-width="180" show-overflow-tooltip />
            <el-table-column prop="orderTypeLabel" label="工单类型" min-width="120" show-overflow-tooltip />
            <el-table-column prop="actionLabel" label="操作" min-width="120" show-overflow-tooltip />
            <el-table-column prop="reason" label="原因" min-width="200" show-overflow-tooltip />
            <el-table-column prop="applicantName" label="申请人" min-width="120" show-overflow-tooltip />
            <el-table-column prop="approverName" label="审批人" min-width="120" show-overflow-tooltip />
            <el-table-column prop="actorName" label="操作人" min-width="120" show-overflow-tooltip />
            <el-table-column prop="comment" label="备注" min-width="220" show-overflow-tooltip />
            <el-table-column label="操作" width="104" fixed="right">
              <template #default="{ row }">
                <el-button v-if="resolveTraceTarget(row)" link type="primary" @click="traceLogRecord(row)">追溯</el-button>
                <span v-else>-</span>
              </template>
            </el-table-column>
          </template>

          <template v-else-if="isShopScheduleType">
            <el-table-column prop="createdAt" label="操作时间" min-width="180" show-overflow-tooltip />
            <el-table-column prop="operatorName" label="操作人" min-width="120" show-overflow-tooltip />
            <el-table-column prop="summary" label="摘要" min-width="320" show-overflow-tooltip />
            <el-table-column label="变更明细" min-width="340" show-overflow-tooltip>
              <template #default="{ row }">{{ formatHighlights(row.highlights) }}</template>
            </el-table-column>
          </template>

          <template v-else-if="isShopTargetType">
            <el-table-column prop="createdAt" label="操作时间" min-width="180" show-overflow-tooltip />
            <el-table-column prop="operatorName" label="操作人" min-width="120" show-overflow-tooltip />
            <el-table-column prop="summary" label="摘要" min-width="320" show-overflow-tooltip />
            <el-table-column label="变更明细" min-width="340" show-overflow-tooltip>
              <template #default="{ row }">{{ formatHighlights(row.highlights) }}</template>
            </el-table-column>
          </template>

          <template v-else-if="isOrderUploadType">
            <el-table-column prop="legacyOrderNum" label="原订单号" min-width="180" show-overflow-tooltip />
            <el-table-column prop="generatedOrderNum" label="上传单号" min-width="220" show-overflow-tooltip />
            <el-table-column prop="cargoName" label="货物" min-width="150" show-overflow-tooltip />
            <el-table-column label="结果" width="96">
              <template #default="{ row }">
                <el-tag :type="row.success ? 'success' : 'danger'">{{ row.success ? '成功' : '失败' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="responseMessage" label="响应" min-width="220" show-overflow-tooltip />
            <el-table-column prop="createdByName" label="操作人" min-width="120" show-overflow-tooltip />
            <el-table-column prop="uploadedAt" label="上传时间" min-width="180" show-overflow-tooltip />
            <el-table-column label="操作" width="104" fixed="right">
              <template #default="{ row }">
                <el-button v-if="resolveTraceTarget(row)" link type="primary" @click="traceLogRecord(row)">追溯</el-button>
                <span v-else>-</span>
              </template>
            </el-table-column>
          </template>
        </el-table>
      </div>
    </article>

    <div v-if="showPagination" class="pager-wrap log-center-pager">
      <el-pagination
        background
        :layout="pagerLayout"
        :total="totalRecords"
        :current-page="page"
        :page-size="pageSize"
        :page-sizes="pageSizes"
        @current-change="onPageChange"
        @size-change="onPageSizeChange"
      />
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import CollapsePanelTransition from '../components/CollapsePanelTransition.vue'
import { useMobileViewport } from '../composables/useMobileViewport'
import { apiGet } from '../services/api'
import { useAuthStore } from '../stores/auth'
import { LOG_CENTER_TYPE_META, normalizeLogCenterType, sanitizeLogBackPath } from '../utils/logCenter'
import { compareUpdateLogVersionsDesc, fetchUpdateLogEntries } from '../utils/updateLog'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { isMobileViewport } = useMobileViewport()

const loading = ref(false)
const errorMessage = ref('')
const filterPanelOpen = ref(false)
const keyword = ref('')
const dateFrom = ref('')
const dateTo = ref('')
const workOrderScope = ref('mine')
const workOrderType = ref('')
const updateScopeFilter = ref('all')
const updateVersionFilter = ref('all')
const orderUploadSuccessFilter = ref('all')
const reportPeriodFilter = ref('all')
const reportScopeFilter = ref('all')
const page = ref(1)
const pageSize = ref(20)
const tableRows = ref([])
const total = ref(0)
const inventoryCurrentTotal = ref(0)
const orderUploadSuccessCount = ref(0)
const orderUploadFailedCount = ref(0)
const updateEntries = ref([])
const updateUpdatedAt = ref('')
const workOrderTypeOptions = ref([])
const selectedGoodsId = ref(null)
const selectedGoodsLabel = ref('')
const selectedShopId = ref(null)
const selectedShopLabel = ref('')
const selectedMonth = ref('')
const selectedOrderId = ref(null)
const selectedOrderLabel = ref('')
const goodsOptions = ref([])
const shopOptions = ref([])
const orderOptions = ref([])
const goodsOptionsLoading = ref(false)
const shopOptionsLoading = ref(false)
const orderOptionsLoading = ref(false)

let loadSeq = 0

const activeType = computed(() => normalizeLogCenterType(route.query.type))
const activeTypeMeta = computed(() => LOG_CENTER_TYPE_META[activeType.value] || LOG_CENTER_TYPE_META.update)
const isUpdateType = computed(() => activeType.value === 'update')
const isWorkOrderType = computed(() => activeType.value === 'work_order')
const isGoodsInventoryType = computed(() => activeType.value === 'goods_inventory')
const isShopInventoryType = computed(() => activeType.value === 'shop_inventory')
const isInventoryType = computed(() => isGoodsInventoryType.value || isShopInventoryType.value)
const isShopScheduleType = computed(() => activeType.value === 'shop_schedule')
const isShopTargetType = computed(() => activeType.value === 'shop_target')
const isOrderUploadType = computed(() => activeType.value === 'order_upload')
const isReportType = computed(() => activeType.value === 'report')
const contextLabel = computed(() => {
  if (isGoodsInventoryType.value) {
    return selectedGoodsLabel.value || String(route.query.subject_name || '').trim()
  }
  if (isShopInventoryType.value || isShopScheduleType.value || isShopTargetType.value) {
    return selectedShopLabel.value || String(route.query.subject_name || '').trim()
  }
  if (isOrderUploadType.value) {
    return selectedOrderLabel.value || String(route.query.subject_name || '').trim()
  }
  return String(route.query.subject_name || '').trim()
})
const returnPath = computed(() => sanitizeLogBackPath(route.query.back, '/'))

const showGoodsSelector = computed(() => isGoodsInventoryType.value)
const showShopSelector = computed(() => isShopInventoryType.value || isShopScheduleType.value || isShopTargetType.value)
const showMonthSelector = computed(() => isShopScheduleType.value || isShopTargetType.value)
const showOrderSelector = computed(() => isOrderUploadType.value)
const showWorkOrderScopeFilter = computed(() => isWorkOrderType.value)
const showWorkOrderTypeFilter = computed(() => isWorkOrderType.value)
const showUpdateScopeFilter = computed(() => isUpdateType.value)
const showUpdateVersionFilter = computed(() => isUpdateType.value)
const showOrderUploadSuccessFilter = computed(() => isOrderUploadType.value)
const showReportPeriodFilter = computed(() => isReportType.value)
const showReportScopeFilter = computed(() => isReportType.value)
const reportScopeOptions = computed(() => {
  const items = [{ value: 'all', label: '全部范围' }]
  if (authStore.isAdmin) {
    items.push({ value: 'company', label: '总报告' })
  }
  items.push({ value: 'shop', label: '门店报告' })
  return items
})

const workOrderScopeOptions = computed(() => {
  const items = [
    { value: 'mine', label: '我的工单' },
    { value: 'pending', label: '待审批' },
    { value: 'draft', label: '草稿箱' },
  ]
  if (authStore.can('workorders.approve')) {
    items.push({ value: 'approver', label: '待我审核' })
  }
  if (authStore.isAdmin) {
    items.push({ value: 'all', label: '全部记录' })
  }
  return items
})

const keywordPlaceholder = computed(() => {
  if (isGoodsInventoryType.value) return '搜索型号 / 店铺 / 变更内容 / 操作人员'
  if (isShopInventoryType.value) return '搜索型号 / 变更内容 / 操作人员'
  if (isWorkOrderType.value) return '搜索工单号 / 原因 / 操作人 / 备注'
  if (isShopScheduleType.value) return '搜索摘要 / 操作人 / 变更明细'
  if (isShopTargetType.value) return '搜索摘要 / 操作人 / 变更明细'
  if (isOrderUploadType.value) return '搜索订单号 / 上传单号 / 货物 / 响应'
  if (isReportType.value) return '搜索报告标题 / 周期范围 / 摘要'
  return '搜索标题、摘要或更新点'
})

const updateTimestampLabel = computed(() => {
  const text = String(updateUpdatedAt.value || '').trim()
  return text ? `更新于 ${text.replace('T', ' ').slice(0, 16)}` : '更新时间待同步'
})

const updateScopeOptions = computed(() => (
  [...new Set(updateEntries.value.flatMap((item) => item.scopeTags || []))]
    .sort((left, right) => left.localeCompare(right, 'zh-Hans-CN'))
))

const updateVersionOptions = computed(() => (
  [...new Set(updateEntries.value.map((item) => item.majorVersion).filter(Boolean))]
    .sort(compareUpdateLogVersionsDesc)
))

const filteredUpdateEntries = computed(() => {
  const keywordText = String(keyword.value || '').trim().toLowerCase()
  const startText = String(dateFrom.value || '').trim()
  const endText = String(dateTo.value || '').trim()

  return updateEntries.value.filter((entry) => {
    if (updateScopeFilter.value !== 'all' && !(entry.scopeTags || []).includes(updateScopeFilter.value)) {
      return false
    }
    if (updateVersionFilter.value !== 'all' && entry.majorVersion !== updateVersionFilter.value) {
      return false
    }
    if (startText && entry.date < startText) {
      return false
    }
    if (endText && entry.date > endText) {
      return false
    }
    if (!keywordText) {
      return true
    }
    const haystack = [
      entry.date,
      entry.version,
      entry.majorVersion,
      entry.title,
      entry.scope,
      ...(entry.scopeTags || []),
      entry.summary,
      ...(entry.highlights || []),
    ]
      .join('\n')
      .toLowerCase()
    return haystack.includes(keywordText)
  })
})

const pagedUpdateEntries = computed(() => {
  const startIndex = Math.max(page.value - 1, 0) * pageSize.value
  return filteredUpdateEntries.value.slice(startIndex, startIndex + pageSize.value)
})

const totalRecords = computed(() => (isUpdateType.value ? filteredUpdateEntries.value.length : Number(total.value || 0)))
const hasData = computed(() => (isUpdateType.value ? updateEntries.value.length > 0 : tableRows.value.length > 0))
const pageSizes = computed(() => (isUpdateType.value ? [10, 20, 50] : [20, 50, 100, 200]))
const pagerLayout = computed(() => (
  isMobileViewport.value
    ? 'prev, pager, next'
    : 'total, prev, pager, next, sizes'
))
const showPagination = computed(() => totalRecords.value > pageSize.value)

const activeFilterCount = computed(() => {
  let count = 0
  if (keyword.value) count += 1
  if (isGoodsInventoryType.value && selectedGoodsId.value) count += 1
  if ((isShopInventoryType.value || isShopScheduleType.value || isShopTargetType.value) && selectedShopId.value) count += 1
  if ((isShopScheduleType.value || isShopTargetType.value) && selectedMonth.value) count += 1
  if (isOrderUploadType.value && selectedOrderId.value) count += 1
  if (dateFrom.value || dateTo.value) count += 1
  if (isWorkOrderType.value && workOrderScope.value && workOrderScope.value !== 'mine') count += 1
  if (isWorkOrderType.value && workOrderType.value) count += 1
  if (isUpdateType.value && updateScopeFilter.value !== 'all') count += 1
  if (isUpdateType.value && updateVersionFilter.value !== 'all') count += 1
  if (isOrderUploadType.value && orderUploadSuccessFilter.value !== 'all') count += 1
  if (isReportType.value && reportPeriodFilter.value !== 'all') count += 1
  if (isReportType.value && reportScopeFilter.value !== 'all') count += 1
  return count
})

const emptyText = computed(() => {
  if (isReportType.value) return '暂无报告日志'
  if (isGoodsInventoryType.value && !selectedGoodsId.value) return '请先选择商品后查询日志'
  if (isShopInventoryType.value && !selectedShopId.value) return '请先选择店铺 / 仓库后查询日志'
  if (isShopScheduleType.value && !selectedShopId.value) return '请先选择排班店铺后查询日志'
  if (isShopTargetType.value && !selectedShopId.value) return '请先选择目标店铺后查询日志'
  if (isGoodsInventoryType.value || isShopInventoryType.value) return '暂无库存日志'
  if (isWorkOrderType.value) return '暂无工单日志'
  if (isShopScheduleType.value) return '暂无排班日志'
  if (isShopTargetType.value) return '暂无目标日志'
  if (isOrderUploadType.value) return '暂无上传日志'
  return '暂无日志'
})

function normalizeWorkOrderScope(value) {
  const clean = String(value || '').trim()
  return workOrderScopeOptions.value.some((item) => item.value === clean) ? clean : 'mine'
}

function parseQueryText(key) {
  return String(route.query[key] || '').trim()
}

function formatHighlights(value) {
  const items = Array.isArray(value) ? value.filter(Boolean) : []
  return items.length ? items.join(' / ') : '-'
}

async function loadGoodsOptions(query = '') {
  goodsOptionsLoading.value = true
  const payload = await apiGet('/goods/items', {
    token: authStore.token,
    query: {
      page: '1',
      page_size: '20',
      q: String(query || '').trim(),
      catalog_only: 'false',
    },
  })
  goodsOptionsLoading.value = false
  if (!payload?.success) {
    return
  }
  goodsOptions.value = (payload.items || []).map((item) => ({
    id: Number(item.id || 0),
    label: String(item.model || item.barcode || `商品 ${item.id || ''}`).trim(),
  }))
}

async function loadShopOptions(query = '') {
  shopOptionsLoading.value = true
  const payload = await apiGet('/shops', {
    token: authStore.token,
    query: {
      page: '1',
      page_size: '100',
      ...(String(query || '').trim() ? { q: String(query || '').trim() } : {}),
    },
  })
  shopOptionsLoading.value = false
  if (!payload?.success) {
    return
  }
  shopOptions.value = (payload.shops || []).map((item) => ({
    id: Number(item.id || 0),
    label: String(item.name || `店铺 ${item.id || ''}`).trim(),
  }))
}

async function loadOrderOptions(query = '') {
  orderOptionsLoading.value = true
  const payload = await apiGet('/orders', {
    token: authStore.token,
    query: {
      page: '1',
      page_size: '20',
      ...(String(query || '').trim() ? { q: String(query || '').trim() } : {}),
    },
  })
  orderOptionsLoading.value = false
  if (!payload?.success) {
    return
  }
  orderOptions.value = (payload.orders || []).map((item) => ({
    id: Number(item.id || 0),
    label: String(item.orderNum || `订单 ${item.id || ''}`).trim(),
  }))
}

function syncSelectedLabels() {
  if (selectedGoodsId.value) {
    const matched = goodsOptions.value.find((item) => Number(item.id) === Number(selectedGoodsId.value))
    if (matched) selectedGoodsLabel.value = matched.label
  } else {
    selectedGoodsLabel.value = ''
  }
  if (selectedShopId.value) {
    const matched = shopOptions.value.find((item) => Number(item.id) === Number(selectedShopId.value))
    if (matched) selectedShopLabel.value = matched.label
  } else {
    selectedShopLabel.value = ''
  }
  if (selectedOrderId.value) {
    const matched = orderOptions.value.find((item) => Number(item.id) === Number(selectedOrderId.value))
    if (matched) selectedOrderLabel.value = matched.label
  } else {
    selectedOrderLabel.value = ''
  }
}

async function ensureWorkOrderMeta() {
  if (workOrderTypeOptions.value.length || !authStore.can('workorders.read')) {
    return
  }
  const payload = await apiGet('/work-orders/meta', {
    token: authStore.token,
  })
  if (payload?.success) {
    workOrderTypeOptions.value = payload.types || []
  }
}

function buildInventoryQuery() {
  return {
    page: String(page.value),
    page_size: String(pageSize.value),
    ...(isGoodsInventoryType.value && selectedShopId.value ? { shop_id: String(selectedShopId.value) } : {}),
    ...(isShopInventoryType.value && selectedGoodsId.value ? { item_id: String(selectedGoodsId.value) } : {}),
    ...(keyword.value ? { q: keyword.value } : {}),
    ...(dateFrom.value ? { date_from: dateFrom.value } : {}),
    ...(dateTo.value ? { date_to: dateTo.value } : {}),
  }
}

async function loadGoodsInventoryLogs(seq) {
  if (!selectedGoodsId.value) {
    tableRows.value = []
    total.value = 0
    inventoryCurrentTotal.value = 0
    return
  }
  const payload = await apiGet(`/goods/items/${selectedGoodsId.value}/inventory-logs`, {
    token: authStore.token,
    query: buildInventoryQuery(),
  })
  if (seq !== loadSeq) return
  if (!payload?.success) {
    errorMessage.value = payload?.message || '库存日志加载失败'
    tableRows.value = []
    total.value = 0
    inventoryCurrentTotal.value = 0
    return
  }
  tableRows.value = payload.logs || []
  total.value = Number(payload.total || 0)
  inventoryCurrentTotal.value = Number(payload.currentQuantityTotal || 0)
}

async function loadShopInventoryLogs(seq) {
  if (!selectedShopId.value) {
    tableRows.value = []
    total.value = 0
    inventoryCurrentTotal.value = 0
    return
  }
  const payload = await apiGet(`/shops/${selectedShopId.value}/inventory-logs`, {
    token: authStore.token,
    query: buildInventoryQuery(),
  })
  if (seq !== loadSeq) return
  if (!payload?.success) {
    errorMessage.value = payload?.message || '库存日志加载失败'
    tableRows.value = []
    total.value = 0
    inventoryCurrentTotal.value = 0
    return
  }
  tableRows.value = payload.logs || []
  total.value = Number(payload.total || 0)
  inventoryCurrentTotal.value = Number(payload.currentQuantityTotal || 0)
}

async function loadWorkOrderLogs(seq) {
  await ensureWorkOrderMeta()
  const payload = await apiGet('/work-orders/logs', {
    token: authStore.token,
    query: {
      page: String(page.value),
      page_size: String(pageSize.value),
      scope: workOrderScope.value || 'mine',
      ...(workOrderType.value ? { order_type: workOrderType.value } : {}),
      ...(keyword.value ? { keyword: keyword.value } : {}),
      ...(dateFrom.value ? { date_start: dateFrom.value } : {}),
      ...(dateTo.value ? { date_end: dateTo.value } : {}),
    },
  })
  if (seq !== loadSeq) return
  if (!payload?.success) {
    errorMessage.value = payload?.message || '工单日志加载失败'
    tableRows.value = []
    total.value = 0
    return
  }
  tableRows.value = payload.logs || []
  total.value = Number(payload.total || 0)
}

async function loadShopScheduleLogs(seq) {
  if (!selectedShopId.value) {
    tableRows.value = []
    total.value = 0
    return
  }
  const payload = await apiGet(`/shop-schedules/${selectedShopId.value}/logs`, {
    token: authStore.token,
    query: {
      page: String(page.value),
      page_size: String(pageSize.value),
      ...(keyword.value ? { q: keyword.value } : {}),
      ...(selectedMonth.value ? { month: selectedMonth.value } : {}),
      ...(dateFrom.value ? { date_start: dateFrom.value } : {}),
      ...(dateTo.value ? { date_end: dateTo.value } : {}),
    },
  })
  if (seq !== loadSeq) return
  if (!payload?.success) {
    errorMessage.value = payload?.message || '排班日志加载失败'
    tableRows.value = []
    total.value = 0
    return
  }
  tableRows.value = payload.logs || []
  total.value = Number(payload.total || 0)
}

async function loadShopTargetLogs(seq) {
  if (!selectedShopId.value) {
    tableRows.value = []
    total.value = 0
    return
  }
  const payload = await apiGet(`/shop-targets/${selectedShopId.value}/logs`, {
    token: authStore.token,
    query: {
      page: String(page.value),
      page_size: String(pageSize.value),
      ...(keyword.value ? { q: keyword.value } : {}),
      ...(selectedMonth.value ? { month: selectedMonth.value } : {}),
      ...(dateFrom.value ? { date_start: dateFrom.value } : {}),
      ...(dateTo.value ? { date_end: dateTo.value } : {}),
    },
  })
  if (seq !== loadSeq) return
  if (!payload?.success) {
    errorMessage.value = payload?.message || '目标日志加载失败'
    tableRows.value = []
    total.value = 0
    return
  }
  tableRows.value = payload.logs || []
  total.value = Number(payload.total || 0)
}

async function loadOrderUploadLogs(seq) {
  const successFilter = orderUploadSuccessFilter.value === 'success'
    ? true
    : orderUploadSuccessFilter.value === 'failed'
      ? false
      : undefined
  const payload = await apiGet('/orders/logs', {
    token: authStore.token,
    query: {
      page: String(page.value),
      page_size: String(pageSize.value),
      ...(keyword.value ? { q: keyword.value } : {}),
      ...(selectedOrderId.value ? { order_id: String(selectedOrderId.value) } : {}),
      ...(successFilter === undefined ? {} : { success: String(successFilter) }),
      ...(dateFrom.value ? { date_start: dateFrom.value } : {}),
      ...(dateTo.value ? { date_end: dateTo.value } : {}),
    },
  })
  if (seq !== loadSeq) return
  if (!payload?.success) {
    errorMessage.value = payload?.message || '上传日志加载失败'
    tableRows.value = []
    total.value = 0
    orderUploadSuccessCount.value = 0
    orderUploadFailedCount.value = 0
    return
  }
  tableRows.value = payload.uploads || []
  total.value = Number(payload.total || 0)
  orderUploadSuccessCount.value = Number(payload.successCount || 0)
  orderUploadFailedCount.value = Number(payload.failedCount || 0)
}

async function loadReportLogs(seq) {
  const payload = await apiGet('/reports/logs', {
    token: authStore.token,
    query: {
      page: String(page.value),
      page_size: String(pageSize.value),
      ...(keyword.value ? { q: keyword.value } : {}),
      ...(reportPeriodFilter.value !== 'all' ? { period_key: reportPeriodFilter.value } : {}),
      ...(reportScopeFilter.value !== 'all' ? { scope_type: reportScopeFilter.value } : {}),
      ...(dateFrom.value ? { date_start: dateFrom.value } : {}),
      ...(dateTo.value ? { date_end: dateTo.value } : {}),
    },
  })
  if (seq !== loadSeq) return
  if (!payload?.success) {
    errorMessage.value = payload?.message || '报告日志加载失败'
    tableRows.value = []
    total.value = 0
    return
  }
  tableRows.value = payload.logs || []
  total.value = Number(payload.total || 0)
}

async function loadUpdateLogs(seq) {
  try {
    const payload = await fetchUpdateLogEntries()
    if (seq !== loadSeq) return
    updateEntries.value = payload.entries
    updateUpdatedAt.value = payload.updatedAt
    errorMessage.value = ''
  } catch (error) {
    if (seq !== loadSeq) return
    updateEntries.value = []
    updateUpdatedAt.value = ''
    errorMessage.value = error instanceof Error && error.message ? error.message : '更新日志读取失败'
  }
}

async function loadCurrentLogData() {
  const seq = ++loadSeq
  loading.value = true
  errorMessage.value = ''

  if (!isUpdateType.value) {
    tableRows.value = []
    total.value = 0
  }
  inventoryCurrentTotal.value = 0
  orderUploadSuccessCount.value = 0
  orderUploadFailedCount.value = 0

  try {
    if (isUpdateType.value) {
      await loadUpdateLogs(seq)
    } else if (isGoodsInventoryType.value) {
      await loadGoodsInventoryLogs(seq)
    } else if (isShopInventoryType.value) {
      await loadShopInventoryLogs(seq)
    } else if (isWorkOrderType.value) {
      await loadWorkOrderLogs(seq)
    } else if (isShopScheduleType.value) {
      await loadShopScheduleLogs(seq)
    } else if (isShopTargetType.value) {
      await loadShopTargetLogs(seq)
    } else if (isOrderUploadType.value) {
      await loadOrderUploadLogs(seq)
    } else if (isReportType.value) {
      await loadReportLogs(seq)
    }
  } finally {
    if (seq === loadSeq) {
      loading.value = false
    }
  }
}

function applyRouteState() {
  keyword.value = parseQueryText('keyword')
  dateFrom.value = parseQueryText('date_start')
  dateTo.value = parseQueryText('date_end')
  workOrderScope.value = normalizeWorkOrderScope(parseQueryText('scope'))
  workOrderType.value = parseQueryText('order_type')
  updateScopeFilter.value = parseQueryText('update_scope') || 'all'
  updateVersionFilter.value = parseQueryText('update_version') || 'all'
  orderUploadSuccessFilter.value = parseQueryText('success_filter') || 'all'
  reportPeriodFilter.value = parseQueryText('period_key') || 'all'
  reportScopeFilter.value = parseQueryText('scope_type') || 'all'
  selectedGoodsId.value = Number(route.query.item_id || 0) || null
  selectedGoodsLabel.value = String(route.query.subject_name || '').trim()
  selectedShopId.value = Number(route.query.shop_id || 0) || null
  selectedShopLabel.value = String(route.query.subject_name || '').trim()
  selectedMonth.value = parseQueryText('month')
  selectedOrderId.value = Number(route.query.order_id || 0) || null
  selectedOrderLabel.value = String(route.query.subject_name || '').trim()
  filterPanelOpen.value = false
  page.value = 1
  pageSize.value = isUpdateType.value ? 10 : 20
}

function onSearch() {
  page.value = 1
  void loadCurrentLogData()
}

function resetFilters() {
  keyword.value = ''
  dateFrom.value = ''
  dateTo.value = ''
  selectedGoodsId.value = null
  selectedGoodsLabel.value = ''
  selectedShopId.value = null
  selectedShopLabel.value = ''
  selectedMonth.value = ''
  selectedOrderId.value = null
  selectedOrderLabel.value = ''
  workOrderScope.value = 'mine'
  workOrderType.value = ''
  updateScopeFilter.value = 'all'
  updateVersionFilter.value = 'all'
  orderUploadSuccessFilter.value = 'all'
  reportPeriodFilter.value = 'all'
  reportScopeFilter.value = 'all'
  page.value = 1
  void loadCurrentLogData()
}

function onPageChange(nextPage) {
  page.value = nextPage
  void loadCurrentLogData()
}

function onPageSizeChange(nextSize) {
  pageSize.value = nextSize
  page.value = 1
  void loadCurrentLogData()
}

function goBack() {
  if (returnPath.value) {
    router.push(returnPath.value)
    return
  }
  if (window.history.length > 1) {
    router.back()
    return
  }
  router.push({ name: 'dashboard' })
}

function refreshLogs() {
  void loadCurrentLogData()
}

function parseTraceToken(text, label) {
  const source = String(text || '').trim()
  if (!source) {
    return ''
  }
  const matcher = source.match(new RegExp(`${label}\\s*[:：]?\\s*([A-Za-z0-9_-]+)`))
  return String(matcher?.[1] || '').trim()
}

function buildWorkOrderTraceTarget({ workOrderId = 0, orderNum = '' } = {}) {
  const cleanOrderNum = String(orderNum || '').trim()
  const cleanWorkOrderId = Number(workOrderId || 0)
  if (!cleanOrderNum && !cleanWorkOrderId) {
    return null
  }
  return {
    name: 'work-orders',
    query: {
      scope: authStore.isAdmin ? 'all' : (workOrderScope.value || 'mine'),
      ...(cleanOrderNum ? { keyword: cleanOrderNum } : {}),
      ...(cleanWorkOrderId ? { spotlight_work_order: String(cleanWorkOrderId) } : {}),
    },
  }
}

function buildSalesTraceTarget(orderNum = '') {
  const cleanOrderNum = String(orderNum || '').trim()
  if (!cleanOrderNum) {
    return null
  }
  return {
    name: 'sales-records',
    query: {
      spotlight_order_num: cleanOrderNum,
    },
  }
}

function buildOrderTraceTarget({ orderNum = '' } = {}) {
  const cleanOrderNum = String(orderNum || '').trim()
  if (!cleanOrderNum) {
    return null
  }
  return {
    name: 'orders',
    query: {
      keyword: cleanOrderNum,
      spotlight_order_num: cleanOrderNum,
    },
  }
}

function resolveTraceTarget(row) {
  if (!row) {
    return null
  }

  if (isWorkOrderType.value) {
    return buildWorkOrderTraceTarget({
      workOrderId: row.workOrderId,
      orderNum: row.orderNum,
    })
  }

  if (isOrderUploadType.value) {
    return buildOrderTraceTarget({
      orderNum: row.legacyOrderNum || row.generatedOrderNum,
    })
  }

  if (!isInventoryType.value) {
    return null
  }

  const relatedType = String(row.relatedType || '').trim().toLowerCase()
  const relatedId = Number(row.relatedId || 0)
  const workOrderNum = parseTraceToken(row.changeContent, '工单')
  const saleOrderNum = parseTraceToken(row.changeContent, '订单')

  if (relatedType === 'work_order' || workOrderNum) {
    return buildWorkOrderTraceTarget({
      workOrderId: relatedType === 'work_order' ? relatedId : 0,
      orderNum: workOrderNum,
    })
  }

  if (relatedType.startsWith('sale_') || saleOrderNum) {
    return buildSalesTraceTarget(saleOrderNum)
  }

  return null
}

function traceLogRecord(row) {
  const target = resolveTraceTarget(row)
  if (!target) {
    return
  }
  void router.push(target)
}

function openReportRow(row) {
  if (!row?.id) {
    return
  }
  void router.push({
    name: 'reports',
    query: {
      report_id: String(row.id),
      back: route.fullPath,
    },
  })
}

watch(
  () => route.query,
  () => {
    applyRouteState()
    if (selectedGoodsId.value && !goodsOptions.value.some((item) => Number(item.id) === Number(selectedGoodsId.value))) {
      goodsOptions.value = [{ id: Number(selectedGoodsId.value), label: selectedGoodsLabel.value || `商品 ${selectedGoodsId.value}` }, ...goodsOptions.value]
    }
    if (selectedShopId.value && !shopOptions.value.some((item) => Number(item.id) === Number(selectedShopId.value))) {
      shopOptions.value = [{ id: Number(selectedShopId.value), label: selectedShopLabel.value || `店铺 ${selectedShopId.value}` }, ...shopOptions.value]
    }
    if (selectedOrderId.value && !orderOptions.value.some((item) => Number(item.id) === Number(selectedOrderId.value))) {
      orderOptions.value = [{ id: Number(selectedOrderId.value), label: selectedOrderLabel.value || `订单 ${selectedOrderId.value}` }, ...orderOptions.value]
    }
    void loadCurrentLogData()
  },
  { immediate: true, deep: true },
)

watch([selectedGoodsId, selectedShopId, selectedOrderId, goodsOptions, shopOptions, orderOptions], () => {
  syncSelectedLabels()
})

watch(filteredUpdateEntries, (entries) => {
  if (!isUpdateType.value) {
    return
  }
  const maxPage = Math.max(Math.ceil(entries.length / pageSize.value), 1)
  if (page.value > maxPage) {
    page.value = maxPage
  }
})
</script>

<style scoped>
.log-center-page {
  display: grid;
  gap: 16px;
  width: 100%;
}

.log-center-toolbar-row {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  min-height: 74px;
  padding: 4px 4px 0;
}

.log-center-toolbar-copy {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.log-center-toolbar-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  color: var(--text-secondary);
  font-size: 13px;
}

.log-center-toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;
}

.log-center-table-card,
.log-center-empty-card {
  border-radius: 26px;
}

.log-center-filter-shell {
  display: grid;
  gap: 10px;
}

.log-center-filter-grid {
  align-items: end;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.log-center-filter-grid > .sales-filter-field {
  min-width: 0;
}

.log-center-filter-grid > .sales-filter-field-wide {
  grid-column: span 2;
}

.log-center-table-card {
  overflow: hidden;
}

.log-center-empty-card {
  padding: 28px;
  display: grid;
  gap: 10px;
}

.log-center-empty-card strong {
  color: var(--text-primary);
  font-size: 20px;
  font-weight: 700;
}

.log-center-empty-card p {
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.7;
}

.log-center-update-list {
  display: grid;
  gap: 16px;
}

.log-center-empty {
  border-radius: 26px;
  background: var(--bg-elevated);
}

.log-center-date-range {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: 10px;
}

.log-center-date-range-separator {
  color: var(--text-light);
  font-size: 13px;
}

@media (max-width: 980px) {
  .log-center-page {
    gap: 14px;
  }

  .log-center-toolbar-row {
    align-items: stretch;
    flex-direction: column;
    min-height: unset;
    padding: 0;
  }

  .log-center-table-card {
    border-radius: 24px;
  }

  .log-center-table-card {
    padding: 0;
  }

  .log-center-filter-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }

  .log-center-filter-grid > .sales-filter-field-wide {
    grid-column: span 2;
  }
}

@media (max-width: 640px) {
  .log-center-toolbar-actions {
    justify-content: flex-start;
  }

  .log-center-date-range {
    grid-template-columns: minmax(0, 1fr);
  }

  .log-center-date-range-separator {
    display: none;
  }

  .log-center-filter-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .log-center-filter-grid > .sales-filter-field-wide {
    grid-column: span 1;
  }
}
</style>
