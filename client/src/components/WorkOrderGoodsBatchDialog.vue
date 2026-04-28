<template>
  <el-dialog
    :model-value="modelValue"
    :title="title"
    width="min(1260px, 96vw)"
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
            placeholder="搜索品牌 / 系列 / 型号 / 条码"
            class="goods-search-input"
            @keyup.enter="onSearch"
          />

          <div class="toolbar-actions goods-search-actions">
            <el-button :loading="loading" @click="onSearch">查询</el-button>
            <el-button @click="onReset">重置</el-button>
          </div>
        </div>

        <section class="sales-filter-shell goods-filter-shell">
          <div class="sales-filter-grid goods-filter-grid work-order-picker-grid">
            <div class="sales-filter-field">
              <label class="sales-filter-label">品牌</label>
              <el-select v-model="brandFilter" clearable filterable placeholder="筛选品牌" class="full-width" @change="onBrandChange">
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
              <el-select v-model="seriesFilter" clearable filterable placeholder="筛选系列" class="full-width" @change="onSearch">
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
              <el-input v-model.trim="modelFilter" clearable placeholder="输入型号" class="full-width" @keyup.enter="onSearch" />
            </div>

            <div class="sales-filter-field">
              <label class="sales-filter-label">条码</label>
              <el-input v-model.trim="barcodeFilter" clearable placeholder="输入条码" class="full-width" @keyup.enter="onSearch" />
            </div>

            <div v-if="distributionShopId" class="sales-filter-field">
              <label class="sales-filter-label">{{ quantityFilterLabel }}</label>
              <el-select
                v-model="hasStockFilter"
                clearable
                placeholder="全部"
                class="full-width"
                @change="onSearch"
              >
                <el-option label="库存不为0" value="nonzero" />
                <el-option label="库存异常（小于0）" value="negative" />
              </el-select>
            </div>
          </div>
        </section>
      </section>

      <section class="catalog-table card-surface work-order-picker-table">
        <div class="table-shell open-table-shell">
          <el-table :data="items" border stripe v-loading="loading" empty-text="暂无匹配商品">
            <el-table-column prop="model" label="型号" min-width="220" show-overflow-tooltip />
            <el-table-column prop="shopQuantity" :label="quantityLabel" min-width="110" />
            <el-table-column
              v-if="showSecondaryQuantity"
              prop="secondaryShopQuantity"
              :label="secondaryQuantityLabel"
              min-width="110"
            />
            <el-table-column prop="price" label="价格" min-width="110">
              <template #default="{ row }">¥ {{ formatMoney(row.price) }}</template>
            </el-table-column>
            <el-table-column prop="brand" label="品牌" min-width="140" />
            <el-table-column prop="series" label="系列" min-width="160" show-overflow-tooltip />
            <el-table-column prop="barcode" label="条码" min-width="170" show-overflow-tooltip />
            <el-table-column label="操作" :width="actionColumnWidth" fixed="right">
              <template #header>
                <div class="work-order-picker-action-head">
                  <span>操作</span>
                  <el-button text type="primary" size="small" :disabled="!items.length" @click.stop="toggleCurrentPageSelection">
                    {{ allCurrentPageSelected ? '取消全选本页' : '全选本页' }}
                  </el-button>
                </div>
              </template>
              <template #default="{ row }">
                <div v-if="selectionMap[row.id]" class="work-order-picker-row-selection table-action-inline">
                  <el-input-number
                    v-model="selectionMap[row.id].quantity"
                    :min="1"
                    :controls="false"
                    class="full-width"
                  />
                  <el-button text type="danger" @click="removeSelection(row.id)">取消</el-button>
                </div>
                <el-button v-else text type="primary" @click="selectGoods(row)">选择</el-button>
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
      v-if="selectedQuantityTotal > 0"
      type="button"
      class="work-order-picker-fab"
      @click="summaryVisible = !summaryVisible"
    >
      {{ selectedQuantityTotal }}
    </button>

    <section v-if="summaryVisible && selectedRows.length" class="card-surface work-order-picker-summary-card">
      <header class="work-order-picker-summary-head">
        <strong>已选 {{ selectedRows.length }} 款 · 共 {{ selectedQuantityTotal }} 件</strong>
        <div class="toolbar-actions">
          <el-button @click="clearSelection">清空</el-button>
          <el-button type="primary" @click="confirmSelection">确认</el-button>
        </div>
      </header>
      <div class="table-shell open-table-shell">
        <el-table :data="selectedRows" border stripe size="small">
          <el-table-column prop="model" label="型号" min-width="180" show-overflow-tooltip />
          <el-table-column prop="quantity" label="数量" width="112">
            <template #default="{ row }">
              <el-input-number
                v-model="row.quantity"
                :min="1"
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
        <el-button type="primary" :disabled="!selectedRows.length" @click="confirmSelection">确认批量录入</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'

import { useMobileViewport } from '../composables/useMobileViewport'
import { apiGet } from '../services/api'
import { useAuthStore } from '../stores/auth'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '批量录入商品' },
  distributionShopId: { type: Number, default: null },
  quantityLabel: { type: String, default: '商品数量' },
  secondaryDistributionShopId: { type: Number, default: null },
  secondaryQuantityLabel: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue', 'confirm'])

const authStore = useAuthStore()
const { isMobileViewport } = useMobileViewport()

const loading = ref(false)
const page = ref(1)
const pageSize = ref(12)
const total = ref(0)
const keyword = ref('')
const brandFilter = ref('')
const seriesFilter = ref('')
const modelFilter = ref('')
const barcodeFilter = ref('')
const hasStockFilter = ref('')
const items = ref([])
const summaryVisible = ref(false)
const actionColumnWidth = computed(() => (isMobileViewport.value ? 92 : 180))
const selectionMap = reactive({})
const showSecondaryQuantity = computed(() => (
  Number(props.secondaryDistributionShopId || 0) > 0 && String(props.secondaryQuantityLabel || '').trim().length > 0
))
const quantityFilterLabel = computed(() => {
  const label = String(props.quantityLabel || '').trim()
  return label || '库存数量'
})

const meta = reactive({
  brandOptions: [],
  seriesOptions: [],
})

const selectedRows = computed(() => Object.values(selectionMap))
const allCurrentPageSelected = computed(() => (
  items.value.length > 0 && items.value.every((row) => Boolean(selectionMap[row.id]))
))

const selectedQuantityTotal = computed(() => (
  selectedRows.value.reduce((sum, item) => sum + Number(item.quantity || 0), 0)
))

function formatMoney(value) {
  return Number(value || 0).toFixed(2)
}

function clearSelection() {
  Object.keys(selectionMap).forEach((key) => {
    delete selectionMap[key]
  })
  summaryVisible.value = false
}

function selectGoods(row) {
  selectionMap[row.id] = {
    ...row,
    quantity: 1,
  }
}

function selectCurrentPage() {
  items.value.forEach((row) => {
    if (!selectionMap[row.id]) {
      selectGoods(row)
    }
  })
}

function unselectCurrentPage() {
  items.value.forEach((row) => {
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

function removeSelection(rowId) {
  delete selectionMap[rowId]
  if (!Object.keys(selectionMap).length) {
    summaryVisible.value = false
  }
}

async function loadMeta() {
  const payload = await apiGet('/goods/catalog/meta', {
    token: authStore.token,
    query: {
      q: keyword.value || undefined,
      brand: brandFilter.value || undefined,
      series: seriesFilter.value || undefined,
      model: modelFilter.value || undefined,
      barcode: barcodeFilter.value || undefined,
      distribution_shop_id: props.distributionShopId || undefined,
      has_stock: hasStockFilter.value || undefined,
    },
  })
  if (!payload?.success) {
    return
  }
  meta.brandOptions = payload.brandOptions || []
  meta.seriesOptions = payload.seriesOptions || []
}

async function loadGoods() {
  loading.value = true
  const query = {
    page: page.value,
    page_size: pageSize.value,
    q: keyword.value || undefined,
    brand: brandFilter.value || undefined,
    series: seriesFilter.value || undefined,
    model: modelFilter.value || undefined,
    barcode: barcodeFilter.value || undefined,
    catalog_only: 'false',
    sort_field: 'updated_at',
    sort_order: 'desc',
    has_stock: hasStockFilter.value || undefined,
  }
  const [primaryPayload, secondaryPayload] = await Promise.all([
    apiGet('/goods/items', {
      token: authStore.token,
      query: {
        ...query,
        distribution_shop_id: props.distributionShopId || undefined,
      },
    }),
    showSecondaryQuantity.value
      ? apiGet('/goods/items', {
        token: authStore.token,
        query: {
          ...query,
          distribution_shop_id: props.secondaryDistributionShopId || undefined,
        },
      })
      : Promise.resolve(null),
  ])
  loading.value = false
  if (!primaryPayload?.success && !secondaryPayload?.success) {
    items.value = []
    total.value = 0
    return
  }
  const fallbackItems = secondaryPayload?.items || []
  const primaryItems = primaryPayload?.items || fallbackItems
  const secondaryMap = new Map(fallbackItems.map((item) => [Number(item.id), item]))
  items.value = primaryItems.map((item) => ({
    ...item,
    shopQuantity: Number(item.shopQuantity || 0),
    secondaryShopQuantity: Number(secondaryMap.get(Number(item.id))?.shopQuantity || 0),
  }))
  total.value = Number(primaryPayload?.total || secondaryPayload?.total || 0)
}

async function onSearch() {
  page.value = 1
  await Promise.all([loadMeta(), loadGoods()])
}

async function onReset() {
  keyword.value = ''
  brandFilter.value = ''
  seriesFilter.value = ''
  modelFilter.value = ''
  barcodeFilter.value = ''
  hasStockFilter.value = props.distributionShopId && quantityFilterLabel.value.includes('发货') ? 'nonzero' : ''
  await onSearch()
}

async function onBrandChange() {
  seriesFilter.value = ''
  await onSearch()
}

async function onPageChange(nextPage) {
  page.value = nextPage
  await loadGoods()
}

function confirmSelection() {
  emit('confirm', selectedRows.value)
  clearSelection()
  emit('update:modelValue', false)
}

async function onOpened() {
  actionColumnWidth.value = isMobileViewport.value ? 92 : 180
  hasStockFilter.value = props.distributionShopId && quantityFilterLabel.value.includes('发货') ? 'nonzero' : ''
  await onSearch()
}

watch(
  () => [props.modelValue, props.distributionShopId, props.secondaryDistributionShopId, props.quantityLabel],
  ([visible]) => {
    if (!visible) {
      clearSelection()
      return
    }
    actionColumnWidth.value = isMobileViewport.value ? 92 : 180
    hasStockFilter.value = props.distributionShopId && quantityFilterLabel.value.includes('发货') ? 'nonzero' : ''
    clearSelection()
    void onSearch()
  },
)
</script>
