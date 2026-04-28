<template>
  <el-dialog
    :model-value="modelValue"
    :title="title"
    width="min(1180px, 96vw)"
    append-to-body
    align-center
    destroy-on-close
    class="aqc-app-dialog work-order-goods-picker-dialog"
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
              <el-select
                v-model="brandFilter"
                clearable
                filterable
                placeholder="筛选品牌"
                class="full-width"
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
                placeholder="筛选系列"
                class="full-width"
                @change="onSearch"
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
              <el-input
                v-model.trim="modelFilter"
                clearable
                placeholder="输入型号"
                class="full-width"
                @keyup.enter="onSearch"
              />
            </div>

            <div class="sales-filter-field">
              <label class="sales-filter-label">条码</label>
              <el-input
                v-model.trim="barcodeFilter"
                clearable
                placeholder="输入条码"
                class="full-width"
                @keyup.enter="onSearch"
              />
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
          <el-table
            ref="tableRef"
            :data="items"
            :row-key="(row) => Number(row.id || 0)"
            border
            stripe
            v-loading="loading"
            empty-text="暂无匹配商品"
            @row-dblclick="selectGoods"
            @selection-change="handleSelectionChange"
          >
            <el-table-column v-if="multiple" type="selection" width="52" reserve-selection />
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
              <template #default="{ row }">
                <div class="table-action-inline">
                  <el-button text type="primary" @click="selectGoods(row)">{{ multiple ? (isRowSelected(row) ? '已选' : '选择') : '选择' }}</el-button>
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
      v-if="multiple && selectedCount > 0"
      type="button"
      class="work-order-picker-fab"
      @click="summaryVisible = !summaryVisible"
    >
      {{ selectedCount }}
    </button>

    <section v-if="multiple && summaryVisible && selectedRows.length" class="card-surface work-order-picker-summary-card">
      <header class="work-order-picker-summary-head">
        <strong>已选 {{ selectedRows.length }} 个商品</strong>
        <div class="toolbar-actions">
          <el-button @click="clearSelection">清空</el-button>
          <el-button type="primary" @click="confirmSelectedGoods">确认选择</el-button>
        </div>
      </header>
      <div class="table-shell open-table-shell">
        <el-table :data="selectedRows" border stripe size="small">
          <el-table-column prop="model" label="型号" min-width="180" show-overflow-tooltip />
          <el-table-column prop="brand" label="品牌" min-width="120" show-overflow-tooltip />
          <el-table-column prop="series" label="系列" min-width="140" show-overflow-tooltip />
          <el-table-column prop="barcode" label="条码" min-width="160" show-overflow-tooltip />
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
        <span v-if="multiple" class="dialog-selection-summary">已选 {{ selectedCount }} 个商品</span>
        <el-button @click="emit('update:modelValue', false)">关闭</el-button>
        <el-button v-if="multiple" type="primary" :disabled="!selectedCount" @click="confirmSelectedGoods">确认选择</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'

import { useMobileViewport } from '../composables/useMobileViewport'
import { apiGet } from '../services/api'
import { useAuthStore } from '../stores/auth'
import { resolveTableActionWidth } from '../utils/tableActions'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  title: {
    type: String,
    default: '选择商品',
  },
  distributionShopId: {
    type: Number,
    default: null,
  },
  quantityLabel: {
    type: String,
    default: '商品数量',
  },
  secondaryDistributionShopId: {
    type: Number,
    default: null,
  },
  secondaryQuantityLabel: {
    type: String,
    default: '',
  },
  multiple: {
    type: Boolean,
    default: false,
  },
  selectedItems: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['update:modelValue', 'select', 'confirm'])

const authStore = useAuthStore()
const { isMobileViewport } = useMobileViewport()

const loading = ref(false)
const tableRef = ref(null)
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
const selectedGoodsMap = ref(new Map())
const summaryVisible = ref(false)
const actionColumnWidth = ref(112)
const showSecondaryQuantity = computed(() => (
  Number(props.secondaryDistributionShopId || 0) > 0 && String(props.secondaryQuantityLabel || '').trim().length > 0
))
const selectedCount = computed(() => selectedGoodsMap.value.size)
const selectedRows = computed(() => Array.from(selectedGoodsMap.value.values()))
const quantityFilterLabel = computed(() => {
  const label = String(props.quantityLabel || '').trim()
  return label || '库存数量'
})

const meta = reactive({
  brandOptions: [],
  seriesOptions: [],
})

function formatMoney(value) {
  return Number(value || 0).toFixed(2)
}

function updateActionWidth() {
  actionColumnWidth.value = resolveTableActionWidth([[props.multiple ? '已选' : '选择']], {
    compact: isMobileViewport.value,
    minWidth: 92,
    maxWidth: 126,
  })
}

function normalizeSelectedItem(item) {
  const id = Number(item?.id || 0)
  if (!id) {
    return null
  }
  return { ...item, id }
}

function resetSelectedGoods() {
  const nextMap = new Map()
  if (props.multiple) {
    for (const item of props.selectedItems || []) {
      const normalized = normalizeSelectedItem(item)
      if (normalized) {
        nextMap.set(normalized.id, normalized)
      }
    }
  }
  selectedGoodsMap.value = nextMap
}

function isRowSelected(row) {
  return selectedGoodsMap.value.has(Number(row?.id || 0))
}

function syncCurrentPageSelection() {
  if (!props.multiple || !tableRef.value) {
    return
  }
  nextTick(() => {
    if (!tableRef.value) {
      return
    }
    tableRef.value.clearSelection()
    items.value.forEach((row) => {
      if (isRowSelected(row)) {
        tableRef.value.toggleRowSelection(row, true)
      }
    })
  })
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
  syncCurrentPageSelection()
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

function selectGoods(row) {
  if (props.multiple) {
    toggleMultipleRow(row)
    return
  }
  emit('select', row)
  emit('update:modelValue', false)
}

function toggleMultipleRow(row) {
  if (!props.multiple || !tableRef.value) {
    return
  }
  tableRef.value.toggleRowSelection(row, !isRowSelected(row))
}

function handleSelectionChange(selection) {
  if (!props.multiple) {
    return
  }
  const nextMap = new Map(selectedGoodsMap.value)
  const currentPageIds = new Set(items.value.map((item) => Number(item.id || 0)))
  currentPageIds.forEach((id) => {
    nextMap.delete(id)
  })
  selection.forEach((row) => {
    const normalized = normalizeSelectedItem(row)
    if (normalized) {
      nextMap.set(normalized.id, normalized)
    }
  })
  selectedGoodsMap.value = nextMap
}

function confirmSelectedGoods() {
  emit('confirm', Array.from(selectedGoodsMap.value.values()))
  emit('update:modelValue', false)
}

function clearSelection() {
  selectedGoodsMap.value = new Map()
  syncCurrentPageSelection()
}

function removeSelection(id) {
  const nextMap = new Map(selectedGoodsMap.value)
  nextMap.delete(Number(id || 0))
  selectedGoodsMap.value = nextMap
  syncCurrentPageSelection()
}

async function onOpened() {
  updateActionWidth()
  resetSelectedGoods()
  summaryVisible.value = selectedGoodsMap.value.size > 0
  hasStockFilter.value = props.distributionShopId && quantityFilterLabel.value.includes('发货') ? 'nonzero' : ''
  await onSearch()
}

watch(
  () => [props.modelValue, props.distributionShopId, props.secondaryDistributionShopId, props.quantityLabel, props.multiple, props.selectedItems],
  ([visible]) => {
    if (!visible) {
      return
    }
    updateActionWidth()
    resetSelectedGoods()
    summaryVisible.value = selectedGoodsMap.value.size > 0
    hasStockFilter.value = props.distributionShopId && quantityFilterLabel.value.includes('发货') ? 'nonzero' : ''
    void onSearch()
  },
)

watch(selectedCount, (count) => {
  if (!count) {
    summaryVisible.value = false
  }
})
</script>
