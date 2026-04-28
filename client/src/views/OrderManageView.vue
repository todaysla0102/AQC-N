<template>
  <section class="order-manage-page card-surface">
    <header class="section-head">
      <h2>订单管理</h2>
      <p>直接读取 AQC-O 迁移订单，并按旧后台的兼容方式上传物流订单。</p>
    </header>

    <el-alert
      v-if="loadError"
      :title="loadError"
      type="warning"
      :closable="false"
      show-icon
      class="page-alert"
    />

    <div class="records-toolbar">
      <el-input
        v-model.trim="keyword"
        clearable
        placeholder="搜索订单号 / 收件人 / 手机 / 商品"
        class="toolbar-search"
        @keyup.enter="onSearch"
      />
      <el-select v-model="statusFilter" clearable placeholder="订单状态" style="width: 140px">
        <el-option label="未支付" :value="0" />
        <el-option label="已支付" :value="1" />
        <el-option label="已发货" :value="2" />
        <el-option label="已收货" :value="3" />
        <el-option label="已完成" :value="4" />
        <el-option label="已售后" :value="9" />
        <el-option label="已取消" :value="88" />
      </el-select>
      <el-select v-model="importedFilter" clearable placeholder="上传状态" style="width: 140px">
        <el-option label="未上传" :value="false" />
        <el-option label="已上传" :value="true" />
      </el-select>
      <div class="toolbar-actions">
        <el-button @click="onSearch" :loading="loading">查询</el-button>
        <el-button @click="loadOrders" :loading="loading">刷新</el-button>
      </div>
    </div>

    <div class="table-shell">
      <el-table :data="orders" border stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="88" />
        <el-table-column prop="orderNum" label="订单号" min-width="190" show-overflow-tooltip />
        <el-table-column prop="userName" label="会员" min-width="120" show-overflow-tooltip />
        <el-table-column label="收件信息" min-width="220">
          <template #default="{ row }">
            <div class="cell-stack">
              <strong>{{ row.recipientName || '-' }}</strong>
              <span>{{ row.recipientPhone || '-' }}</span>
              <small>{{ row.recipientAddress || '-' }}</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="goodsSummary" label="商品摘要" min-width="240" show-overflow-tooltip />
        <el-table-column label="支付金额" width="126">
          <template #default="{ row }">¥ {{ formatMoney(row.pocket || row.totalFee || row.total) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="108">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">{{ row.statusLabel }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="已上传" width="92">
          <template #default="{ row }">
            <el-tag :type="row.isImported ? 'success' : 'info'">{{ row.isImported ? '是' : '否' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="uploadCount" label="上传次数" width="96" />
        <el-table-column prop="createdAt" label="创建时间" min-width="160" />
        <el-table-column label="操作" :width="actionColumnWidth" fixed="right">
          <template #default="{ row }">
            <ResponsiveTableActions>
              <el-button text type="primary" @click="openDetail(row.id)">详情</el-button>
              <el-button
                v-if="authStore.can('orders.upload')"
                text
                type="warning"
                :disabled="!canUpload(row)"
                :loading="uploadingId === row.id"
                @click="onUpload(row)"
              >
                上传订单
              </el-button>
            </ResponsiveTableActions>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="pager-wrap">
      <el-pagination
        background
        layout="total, prev, pager, next, sizes"
        :total="total"
        :current-page="page"
        :page-size="pageSize"
        :page-sizes="[10, 20, 50]"
        @current-change="onPageChange"
        @size-change="onPageSizeChange"
      />
    </div>

    <el-drawer
      v-model="drawerVisible"
      title="订单详情"
      size="min(960px, 96vw)"
      destroy-on-close
    >
      <div v-loading="detailLoading" class="order-detail-wrap">
        <template v-if="detail">
          <div class="detail-grid">
            <div class="detail-item">
              <span>订单ID</span>
              <strong>{{ detail.id }}</strong>
            </div>
            <div class="detail-item">
              <span>订单号</span>
              <strong>{{ detail.orderNum || '-' }}</strong>
            </div>
            <div class="detail-item">
              <span>订单状态</span>
              <strong>{{ detail.statusLabel }}</strong>
            </div>
            <div class="detail-item">
              <span>支付方式</span>
              <strong>{{ detail.payTypeLabel }}</strong>
            </div>
            <div class="detail-item">
              <span>收件人</span>
              <strong>{{ detail.recipientName || '-' }}</strong>
            </div>
            <div class="detail-item">
              <span>收件手机</span>
              <strong>{{ detail.recipientPhone || '-' }}</strong>
            </div>
            <div class="detail-item detail-item-wide">
              <span>收件地址</span>
              <strong>{{ detail.recipientAddress || '-' }}</strong>
            </div>
            <div class="detail-item detail-item-wide">
              <span>备注</span>
              <strong>{{ detail.remark || '-' }}</strong>
            </div>
          </div>

          <div class="detail-section">
            <div class="detail-section-head">
              <h3>商品明细</h3>
              <span>{{ detail.quantityTotal }} 件 / {{ detail.itemCount }} 行</span>
            </div>
            <div class="table-shell">
              <el-table :data="detail.items" border stripe>
                <el-table-column prop="id" label="明细ID" width="92" />
                <el-table-column prop="goodsName" label="商品名称" min-width="180" show-overflow-tooltip />
                <el-table-column prop="goodspec" label="商品规格" min-width="120" show-overflow-tooltip />
                <el-table-column prop="goodsSpecName" label="规格属性" min-width="160" show-overflow-tooltip />
                <el-table-column prop="quantity" label="数量" width="88" />
                <el-table-column label="单价" width="110">
                  <template #default="{ row }">¥ {{ formatMoney(row.price) }}</template>
                </el-table-column>
                <el-table-column label="小计" width="110">
                  <template #default="{ row }">¥ {{ formatMoney(row.totalAmount) }}</template>
                </el-table-column>
                <el-table-column prop="weightKg" label="重量(kg)" width="108" />
              </el-table>
            </div>
          </div>

          <div class="detail-section">
            <div class="detail-section-head">
              <h3>上传日志</h3>
              <span>{{ detail.uploads.length }} 条</span>
              <el-button text type="primary" @click="openUploadLogCenter(detail)">进入日志页</el-button>
            </div>
            <div class="table-shell">
              <el-table :data="detail.uploads" border stripe empty-text="尚未上传">
                <el-table-column prop="generatedOrderNum" label="上传单号" min-width="200" show-overflow-tooltip />
                <el-table-column prop="cargoName" label="货物" min-width="150" show-overflow-tooltip />
                <el-table-column label="结果" width="88">
                  <template #default="{ row }">
                    <el-tag :type="row.success ? 'success' : 'danger'">{{ row.success ? '成功' : '失败' }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="responseMessage" label="响应" min-width="220" show-overflow-tooltip />
                <el-table-column prop="uploadedAt" label="上传时间" min-width="160" />
              </el-table>
            </div>
          </div>
        </template>
      </div>
    </el-drawer>
  </section>
</template>

<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import ResponsiveTableActions from '../components/ResponsiveTableActions.vue'
import { useMobileViewport } from '../composables/useMobileViewport'
import { apiGet, apiPost } from '../services/api'
import { useAuthStore } from '../stores/auth'
import { resolveTableActionWidth } from '../utils/tableActions'

const authStore = useAuthStore()
const { isMobileViewport } = useMobileViewport()
const route = useRoute()
const router = useRouter()

const loading = ref(false)
const detailLoading = ref(false)
const drawerVisible = ref(false)
const uploadingId = ref(0)
const loadError = ref('')

const keyword = ref('')
const statusFilter = ref(undefined)
const importedFilter = ref(undefined)

const orders = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const detail = ref(null)
const actionColumnWidth = computed(() => resolveTableActionWidth([[
  '详情',
  authStore.can('orders.upload') ? '上传订单' : '',
]], {
  compact: isMobileViewport.value,
  minWidth: 112,
  maxWidth: 208,
}))

function formatMoney(value) {
  return new Intl.NumberFormat('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(value || 0))
}

function statusTagType(status) {
  if (Number(status) === 2 || Number(status) === 4) {
    return 'success'
  }
  if (Number(status) === 1 || Number(status) === 3) {
    return 'warning'
  }
  if (Number(status) === 9 || Number(status) === 88) {
    return 'info'
  }
  return 'danger'
}

function canUpload(row) {
  return Number(row.status || 0) >= 1 && Number(row.status || 0) < 9 && !row.isImported && Number(row.uploadCount || 0) <= 0
}

function applyOrderStateFromRoute() {
  const routeKeyword = String(route.query.keyword || route.query.spotlight_order_num || '').trim()
  const routeStatus = route.query.status
  const routeImported = String(route.query.imported || '').trim()
  keyword.value = routeKeyword
  statusFilter.value = routeStatus !== undefined && routeStatus !== null && String(routeStatus).trim() !== ''
    ? Number(routeStatus)
    : undefined
  if (routeImported === 'true') {
    importedFilter.value = true
  } else if (routeImported === 'false') {
    importedFilter.value = false
  } else {
    importedFilter.value = undefined
  }
  page.value = 1
}

async function loadOrders() {
  loading.value = true
  loadError.value = ''
  const payload = await apiGet('/orders', {
    token: authStore.token,
    query: {
      page: String(page.value),
      page_size: String(pageSize.value),
      ...(keyword.value ? { q: keyword.value } : {}),
      ...(statusFilter.value !== undefined && statusFilter.value !== null ? { status: String(statusFilter.value) } : {}),
      ...(importedFilter.value !== undefined && importedFilter.value !== null ? { imported: String(importedFilter.value) } : {}),
    },
  })
  loading.value = false

  if (!payload?.success) {
    orders.value = []
    total.value = 0
    loadError.value = payload?.message || '订单加载失败'
    return
  }

  orders.value = payload.orders || []
  total.value = Number(payload.total || 0)
}

async function openDetail(orderId) {
  detailLoading.value = true
  drawerVisible.value = true
  const payload = await apiGet(`/orders/${orderId}`, {
    token: authStore.token,
  })
  detailLoading.value = false

  if (!payload?.success || !payload.order) {
    detail.value = null
    ElMessage.error(payload?.message || '订单详情加载失败')
    return
  }

  detail.value = payload.order
}

async function onUpload(row) {
  try {
    await ElMessageBox.confirm(
      `确认按 AQC-O 兼容方式上传订单「${row.orderNum || row.id}」吗？`,
      '上传确认',
      {
        confirmButtonText: '开始上传',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }

  uploadingId.value = row.id
  const payload = await apiPost(`/orders/${row.id}/upload`, {}, {
    token: authStore.token,
  })
  uploadingId.value = 0

  if (!payload?.success) {
    ElMessage.error(payload?.message || '订单上传失败')
    return
  }

  if (Number(payload.failedCount || 0) > 0) {
    ElMessage.warning(payload.message || '订单部分上传成功')
  } else {
    ElMessage.success(payload.message || '订单上传成功')
  }
  await Promise.all([
    loadOrders(),
    drawerVisible.value ? openDetail(row.id) : Promise.resolve(),
  ])
}

async function openUploadLogCenter(row) {
  if (!row?.id) {
    return
  }
  await router.push({
    name: 'log-center',
    query: {
      type: 'order_upload',
      order_id: String(row.id),
      subject_name: row.orderNum || `订单 ${row.id}`,
      back: route.fullPath,
    },
  })
}

function onSearch() {
  page.value = 1
  void loadOrders()
}

function onPageChange(nextPage) {
  page.value = nextPage
  void loadOrders()
}

function onPageSizeChange(nextSize) {
  pageSize.value = nextSize
  page.value = 1
  void loadOrders()
}

applyOrderStateFromRoute()
void loadOrders()

watch(
  () => [route.query.keyword, route.query.spotlight_order_num, route.query.status, route.query.imported],
  () => {
    applyOrderStateFromRoute()
    void loadOrders()
  },
)
</script>
