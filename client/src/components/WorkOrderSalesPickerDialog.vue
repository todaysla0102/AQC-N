<template>
  <el-dialog
    :model-value="modelValue"
    :title="title"
    width="min(1320px, 96vw)"
    append-to-body
    align-center
    destroy-on-close
    class="aqc-app-dialog work-order-batch-dialog"
    @update:model-value="emit('update:modelValue', $event)"
    @opened="onOpened"
  >
    <div class="work-order-picker-shell">
      <section class="catalog-controls card-surface work-order-picker-controls">
        <div class="goods-search-shell">
          <el-input
            v-model.trim="keyword"
            clearable
            placeholder="搜索订单号 / 商品 / 销售员 / 店铺"
            class="goods-search-input"
            @keyup.enter="onSearch"
          />

          <div class="toolbar-actions goods-search-actions">
            <el-button :loading="loading" @click="onSearch">查询</el-button>
            <el-button @click="onReset">重置</el-button>
          </div>
        </div>

        <section class="sales-filter-shell goods-filter-shell">
          <div class="sales-filter-trigger-row">
            <button
              type="button"
              class="sales-filter-trigger"
              :class="{ active: filterPanelOpen }"
              @click="filterPanelOpen = !filterPanelOpen"
            >
              <div class="sales-filter-trigger-copy">
                <span>筛选</span>
                <strong>{{ filterPanelOpen ? '收起销售筛选' : '展开销售筛选' }}</strong>
              </div>
              <div class="sales-filter-trigger-meta">
                <div class="sales-filter-trigger-stats">
                  <span>已筛选 {{ activeFilterCount }} 项</span>
                  <strong>{{ total }} 条记录</strong>
                </div>
              </div>
            </button>
          </div>

          <CollapsePanelTransition>
            <div v-if="filterPanelOpen" class="sales-filter-collapse-shell">
              <section class="sales-filter-panel goods-filter-panel">
                <div class="sales-filter-grid goods-filter-grid work-order-picker-grid">
                  <div class="sales-filter-field">
                    <label class="sales-filter-label">订单号</label>
                    <el-input v-model.trim="orderNumFilter" clearable class="full-width" placeholder="输入订单号" @keyup.enter="onSearch" />
                  </div>

                  <div class="sales-filter-field">
                    <label class="sales-filter-label">销售员</label>
                    <el-select
                      v-model="salespersonFilter"
                      clearable
                      filterable
                      class="full-width"
                      placeholder="筛选销售员"
                    >
                      <el-option
                        v-for="option in meta.salespersonOptions"
                        :key="option.value"
                        :label="option.label + ' (' + option.count + ')'"
                        :value="option.value"
                      />
                    </el-select>
                  </div>

                  <div class="sales-filter-field">
                    <label class="sales-filter-label">品牌</label>
                    <el-select
                      v-model="brandFilter"
                      clearable
                      filterable
                      class="full-width"
                      placeholder="筛选品牌"
                      @change="onBrandChange"
                    >
                      <el-option
                        v-for="option in meta.brandOptions"
                        :key="option.value"
                        :label="option.label + ' (' + option.count + ')'"
                        :value="option.value"
                      />
                    </el-select>
                  </div>

                  <div class="sales-filter-field">
                    <label class="sales-filter-label">系列</label>
                    <el-select
                      v-model="seriesFilter"
                      clearable
                      filterable
                      class="full-width"
                      placeholder="筛选系列"
                    >
                      <el-option
                        v-for="option in meta.seriesOptions"
                        :key="option.value"
                        :label="option.label + ' (' + option.count + ')'"
                        :value="option.value"
                      />
                    </el-select>
                  </div>

                  <div class="sales-filter-field">
                    <label class="sales-filter-label">型号</label>
                    <el-input v-model.trim="modelFilter" clearable class="full-width" placeholder="输入型号" @keyup.enter="onSearch" />
                  </div>

                  <div class="sales-filter-field sales-filter-field-wide">
                    <label class="sales-filter-label">销售时间</label>
                    <el-date-picker
                      v-model="dateRange"
                      type="daterange"
                      unlink-panels
                      clearable
                      class="full-width"
                      start-placeholder="开始日期"
                      end-placeholder="结束日期"
                      range-separator="至"
                      value-format="YYYY-MM-DD"
                    />
                  </div>
                </div>
              </section>
            </div>
          </CollapsePanelTransition>
        </section>
      </section>

      <section class="catalog-table card-surface work-order-picker-table">
        <div class="table-shell open-table-shell">
          <el-table :data="records" border stripe v-loading="loading" empty-text="暂无匹配销售记录">
            <el-table-column prop="soldAt" label="销售时间" min-width="170" show-overflow-tooltip />
            <el-table-column prop="orderNum" label="订单号" min-width="180" show-overflow-tooltip />
            <el-table-column prop="salesperson" label="销售员" min-width="120" show-overflow-tooltip />
            <el-table-column prop="shopName" label="销售店铺" min-width="160" show-overflow-tooltip />
            <el-table-column prop="receivedAmount" label="实付金额" min-width="110">
              <template #default="{ row }">¥ {{ formatMoney(row.receivedAmount) }}</template>
            </el-table-column>
            <el-table-column prop="goodsDisplayName" label="商品名称" min-width="220" show-overflow-tooltip />
            <el-table-column prop="unitPrice" label="单价" min-width="100">
              <template #default="{ row }">¥ {{ formatMoney(row.unitPrice) }}</template>
            </el-table-column>
            <el-table-column prop="quantity" label="数量" min-width="90" />
            <el-table-column label="单位" width="80" align="center">
              <template #default>只</template>
            </el-table-column>
            <el-table-column prop="receivableAmount" label="应付金额" min-width="110">
              <template #default="{ row }">¥ {{ formatMoney(row.receivableAmount) }}</template>
            </el-table-column>
            <el-table-column prop="goodsBarcode" label="条码" min-width="160" show-overflow-tooltip />
            <el-table-column prop="note" label="备注" min-width="180" show-overflow-tooltip />
            <el-table-column label="操作" :width="actionColumnWidth" fixed="right">
              <template v-if="multiple" #header>
                <div class="work-order-picker-action-head">
                  <span>操作</span>
                  <el-button text type="primary" size="small" :disabled="!records.length" @click.stop="toggleCurrentPageSelection">
                    {{ allCurrentPageSelected ? '取消全选本页' : '全选本页' }}
                  </el-button>
                </div>
              </template>
              <template #default="{ row }">
                <div v-if="multiple && selectionMap[row.id]" class="work-order-picker-row-selection table-action-inline">
                  <el-input-number
                    v-model="selectionMap[row.id].quantity"
                    :min="1"
                    :max="Math.max(Number(row.quantity || 1), 1)"
                    :controls="false"
                    class="full-width"
                  />
                  <el-button text type="danger" @click="removeSelection(row.id)">取消</el-button>
                </div>
                <div v-else class="table-action-inline">
                  <el-button text type="primary" @click="selectRecord(row)">{{ multiple ? '选择' : '选中' }}</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="pager-wrap">
          <el-pagination
            background
            layout="total, prev, pager, next"
            :total="total"
            :current-page="page"
            :page-size="pageSize"
            @current-change="onPageChange"
          />
        </div>
      </section>
    </div>

    <button
      v-if="multiple && selectedQuantityTotal > 0"
      type="button"
      class="work-order-picker-fab"
      @click="summaryVisible = !summaryVisible"
    >
      {{ selectedQuantityTotal }}
    </button>

    <section v-if="multiple && summaryVisible && selectedRows.length" class="card-surface work-order-picker-summary-card">
      <header class="work-order-picker-summary-head">
        <strong>已选 {{ selectedRows.length }} 条 · 共 {{ selectedQuantityTotal }} 件</strong>
        <div class="toolbar-actions">
          <el-button @click="clearSelection">清空</el-button>
          <el-button type="primary" @click="confirmSelection">确认</el-button>
        </div>
      </header>
      <div class="table-shell open-table-shell">
        <el-table :data="selectedRows" border stripe size="small">
          <el-table-column prop="soldAt" label="销售时间" min-width="150" show-overflow-tooltip />
          <el-table-column prop="orderNum" label="订单号" min-width="160" show-overflow-tooltip />
          <el-table-column prop="goodsDisplayName" label="商品名称" min-width="180" show-overflow-tooltip />
          <el-table-column prop="quantity" label="数量" width="112">
            <template #default="{ row }">
              <el-input-number
                v-model="row.quantity"
                :min="1"
                :max="Math.max(Number(row.maxQuantity || row.quantity || 1), 1)"
                :controls="false"
                class="full-width"
              />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="90" fixed="right">
            <template #default="{ row }">
              <div class="table-action-inline">
                <el-button text type="danger" @click="removeSelection(row.id)">取消</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </section>

    <template #footer>
      <div class="form-actions">
        <el-button @click="emit('update:modelValue', false)">关闭</el-button>
        <el-button v-if="multiple" type="primary" :disabled="!selectedRows.length" @click="confirmSelection">确认批量录入</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'

import CollapsePanelTransition from './CollapsePanelTransition.vue'
import { useMobileViewport } from '../composables/useMobileViewport'
import { apiGet } from '../services/api'
import { useAuthStore } from '../stores/auth'
import { resolveTableActionWidth } from '../utils/tableActions'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '选择销售记录' },
  shopId: { type: Number, default: null },
  multiple: { type: Boolean, default: false },
  returnableOnly: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'select', 'confirm'])

const authStore = useAuthStore()
const { isMobileViewport } = useMobileViewport()

const loading = ref(false)
const page = ref(1)
const pageSize = ref(12)
const total = ref(0)
const keyword = ref('')
const orderNumFilter = ref('')
const salespersonFilter = ref('')
const brandFilter = ref('')
const seriesFilter = ref('')
const modelFilter = ref('')
const dateRange = ref([])
const filterPanelOpen = ref(false)
const records = ref([])
const summaryVisible = ref(false)
const actionColumnWidth = computed(() => {
  if (isMobileViewport.value) {
    return 92
  }
  if (props.multiple) {
    return 180
  }
  return resolveTableActionWidth([['选中']], {
    compact: false,
    minWidth: 92,
    maxWidth: 126,
  })
})
const selectionMap = reactive({})

const meta = reactive({
  brandOptions: [],
  seriesOptions: [],
  salespersonOptions: [],
})

const activeFilterCount = computed(() => {
  let count = 0
  if (orderNumFilter.value) count += 1
  if (salespersonFilter.value) count += 1
  if (brandFilter.value) count += 1
  if (seriesFilter.value) count += 1
  if (modelFilter.value) count += 1
  if (Array.isArray(dateRange.value) && (dateRange.value[0] || dateRange.value[1])) count += 1
  return count
})

const selectedRows = computed(() => Object.values(selectionMap))
const allCurrentPageSelected = computed(() => (
  records.value.length > 0 && records.value.every((row) => Boolean(selectionMap[row.id]))
))

const selectedQuantityTotal = computed(() => (
  selectedRows.value.reduce((sum, item) => sum + Number(item.quantity || 0), 0)
))

function formatMoney(value) {
  return Number(value || 0).toFixed(2)
}

function buildQuery(includePaging = true) {
  const query = {
    q: keyword.value || undefined,
    order_num: orderNumFilter.value || undefined,
    salesperson: salespersonFilter.value || undefined,
    brand: brandFilter.value || undefined,
    series: seriesFilter.value || undefined,
    model: modelFilter.value || undefined,
    shop_id: props.shopId || undefined,
    sale_status: props.returnableOnly ? 'normal' : undefined,
    date_from: Array.isArray(dateRange.value) ? dateRange.value[0] || undefined : undefined,
    date_to: Array.isArray(dateRange.value) ? dateRange.value[1] || undefined : undefined,
  }
  if (includePaging) {
    query.page = page.value
    query.page_size = pageSize.value
  }
  return query
}

function clearSelection() {
  Object.keys(selectionMap).forEach((key) => {
    delete selectionMap[key]
  })
  summaryVisible.value = false
}

function selectRecord(row) {
  if (!props.multiple) {
    emit('select', row)
    emit('update:modelValue', false)
    return
  }
  selectionMap[row.id] = {
    ...row,
    quantity: Math.max(Number(row.quantity || 1), 1),
    maxQuantity: Math.max(Number(row.quantity || 1), 1),
  }
}

function selectCurrentPage() {
  records.value.forEach((row) => {
    if (!selectionMap[row.id]) {
      selectRecord(row)
    }
  })
}

function unselectCurrentPage() {
  records.value.forEach((row) => {
    delete selectionMap[row.id]
  })
  if (!Object.keys(selectionMap).length) {
    summaryVisible.value = false
  }
}

function toggleCurrentPageSelection() {
  if (allCurrentPageSelected.value) {
    unselectCurrentPage()
    return
  }
  selectCurrentPage()
}

function removeSelection(recordId) {
  delete selectionMap[recordId]
  if (!Object.keys(selectionMap).length) {
    summaryVisible.value = false
  }
}

async function loadMeta() {
  const payload = await apiGet('/sales/meta', {
    token: authStore.token,
    query: buildQuery(false),
  })
  if (!payload?.success) {
    return
  }
  meta.brandOptions = payload.brandOptions || []
  meta.seriesOptions = payload.seriesOptions || []
  meta.salespersonOptions = payload.salespersonOptions || []
}

async function loadRecords() {
  loading.value = true
  const payload = await apiGet('/sales/records', {
    token: authStore.token,
    query: buildQuery(true),
  })
  loading.value = false
  if (!payload?.success) {
    records.value = []
    total.value = 0
    return
  }
  records.value = payload.records || []
  total.value = Number(payload.total || 0)
}

async function onSearch() {
  page.value = 1
  await Promise.all([loadMeta(), loadRecords()])
}

async function onReset() {
  keyword.value = ''
  orderNumFilter.value = ''
  salespersonFilter.value = ''
  brandFilter.value = ''
  seriesFilter.value = ''
  modelFilter.value = ''
  dateRange.value = []
  await onSearch()
}

async function onBrandChange() {
  if (seriesFilter.value && !meta.seriesOptions.some((item) => item.value === seriesFilter.value)) {
    seriesFilter.value = ''
  }
  await onSearch()
}

async function onPageChange(nextPage) {
  page.value = nextPage
  await loadRecords()
}

function confirmSelection() {
  emit('confirm', selectedRows.value)
  clearSelection()
  emit('update:modelValue', false)
}

async function onOpened() {
  actionColumnWidth.value = isMobileViewport.value ? 92 : 180
  await onSearch()
}

watch(
  () => [props.modelValue, props.shopId, props.multiple],
  ([visible]) => {
    if (!visible) {
      clearSelection()
      return
    }
    actionColumnWidth.value = isMobileViewport.value ? 92 : 180
    clearSelection()
    void onSearch()
  },
)
</script>
