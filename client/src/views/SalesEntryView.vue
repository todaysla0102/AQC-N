<template>
  <section class="sales-entry-page sales-workbench">
    <div class="sales-workbench-grid">
      <section class="card-surface sales-panel motion-fade-slide" style="--motion-delay: 0.08s">
        <template v-if="!isRepairMode">
          <div class="goods-search-shell sales-entry-search-shell">
            <el-input
              v-model.trim="searchKeyword"
              clearable
              placeholder="搜索品牌 / 系列 / 型号 / 条码"
              class="goods-search-input sales-entry-search-input"
              @keyup.enter="searchSuggestions"
            />

            <div class="toolbar-actions goods-search-actions sales-entry-search-actions">
              <el-button type="primary" class="scanner-cta sales-entry-search-action-scanner" :loading="scannerPending" @click="openScannerDialog">
                {{ scanning ? '识别中...' : scannerPending ? '启动中...' : '摄像头识别条码' }}
              </el-button>
              <el-button class="sales-entry-search-action-repair" @click="goRepairEntry">维修销售录入</el-button>
              <el-button class="sales-entry-search-action-query" :loading="suggestionsLoading || barcodeLoading" @click="searchSuggestions">查询</el-button>
              <el-button class="sales-entry-search-action-reset" @click="onResetSearch">重置</el-button>
            </div>
          </div>

          <section class="sales-filter-shell goods-filter-shell sales-entry-filter-shell">
            <div class="sales-filter-trigger-row">
              <button type="button" class="sales-filter-trigger" :class="{ active: filterPanelOpen }" @click="filterPanelOpen = !filterPanelOpen">
                <div class="sales-filter-trigger-copy">
                  <span>筛选</span>
                  <strong>{{ filterPanelOpen ? '收起商品筛选' : '展开商品筛选' }}</strong>
                </div>
                <div class="sales-filter-trigger-meta">
                  <div class="sales-filter-trigger-stats">
                    <span>已筛选 {{ activeFilterCount }} 项</span>
                    <strong>{{ suggestions.length }} 条候选</strong>
                  </div>
                </div>
              </button>
            </div>

            <CollapsePanelTransition>
              <div v-if="filterPanelOpen" class="sales-filter-collapse-shell">
                <section class="sales-filter-panel goods-filter-panel sales-entry-filter-panel">
                  <header class="sales-filter-head">
                  <div class="sales-filter-head-copy">
                    <h2>筛选</h2>
                    <span>扫码、品牌、系列与索引定位</span>
                  </div>
                  <div class="toolbar-actions sales-filter-head-actions">
                    <el-button type="primary" :loading="suggestionsLoading || barcodeLoading" @click="searchSuggestions">查询</el-button>
                    <el-button class="sales-filter-reset-btn" :disabled="!activeFilterCount" @click="onResetSearch">清空筛选</el-button>
                  </div>
                </header>

                  <div class="sales-filter-grid sales-entry-filter-grid">
                  <div class="sales-filter-field sales-filter-field-wide">
                    <label class="sales-filter-label">条码定位</label>
                    <el-input
                      v-model.trim="barcodeInput"
                      clearable
                      placeholder="扫描或输入条码后按回车"
                      class="full-width"
                      @keyup.enter="lookupBarcode"
                    />
                  </div>

                  <div class="sales-filter-field">
                    <label class="sales-filter-label">品牌</label>
                    <el-select v-model="searchBrand" clearable filterable placeholder="筛选品牌" class="full-width" @change="onSearchBrandChange">
                      <el-option
                        v-for="option in meta.brandOptions"
                        :key="option.value"
                        :label="`${option.label} (${option.count})`"
                        :value="option.value"
                      />
                    </el-select>
                  </div>

                  <div class="sales-filter-field">
                    <label class="sales-filter-label">系列</label>
                    <el-select v-model="searchSeries" clearable filterable placeholder="筛选系列" class="full-width" @change="searchSuggestions">
                      <el-option
                        v-for="option in meta.seriesOptions"
                        :key="option.value"
                        :label="`${option.label} (${option.count})`"
                        :value="option.value"
                      />
                    </el-select>
                  </div>
                </div>

                  <div class="sales-filter-footer">
                  <div class="sales-filter-index-shell">
                    <span class="sales-filter-subtitle">索引筛选</span>
                    <div class="catalog-index-bar compact sales-filter-index-bar">
                      <button
                        type="button"
                        class="index-chip"
                        :class="{ active: !searchIndex }"
                        @click="setSearchIndex('')"
                      >
                        全部
                      </button>
                      <button
                        v-for="option in meta.indexOptions"
                        :key="option.key"
                        type="button"
                        class="index-chip"
                        :class="{ active: searchIndex === option.key }"
                        @click="setSearchIndex(option.key)"
                      >
                        <span>{{ option.key }}</span>
                        <small>{{ option.count }}</small>
                      </button>
                    </div>
                  </div>
                  </div>
                </section>
              </div>
            </CollapsePanelTransition>
          </section>

          <div v-if="hasSearchedSuggestions" class="table-shell open-table-shell">
            <el-table :data="suggestions" border stripe v-loading="suggestionsLoading" empty-text="暂无匹配商品">
              <el-table-column prop="brand" label="品牌" min-width="110" />
              <el-table-column prop="series" label="系列" min-width="140" show-overflow-tooltip />
              <el-table-column prop="model" label="型号" min-width="180" show-overflow-tooltip />
              <el-table-column label="价格" min-width="100">
                <template #default="{ row }">¥ {{ formatMoney(row.price) }}</template>
              </el-table-column>
              <el-table-column prop="barcode" label="条码" min-width="150" show-overflow-tooltip />
              <el-table-column label="操作" :width="suggestionActionColumnWidth" fixed="right">
                <template #default="{ row }">
                  <ResponsiveTableActions :menu-width="148">
                    <el-button text type="primary" @click="selectGoods(row)">选择</el-button>
                  </ResponsiveTableActions>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </template>

        <template v-else>
          <section class="goods-editor-hero sales-record-editor-hero">
            <div class="goods-code-card">
              <span>维修销售录入</span>
              <strong>{{ repairEntryHeaderTitle }}</strong>
              <div class="goods-preview-meta">
                <span>不需要选择商品，提交后只会进入维修销售记录</span>
              </div>
            </div>
            <div class="toolbar-actions goods-search-actions sales-entry-search-actions">
              <el-button @click="goGoodsEntry">返回销售录入</el-button>
            </div>
          </section>
        </template>
      </section>

      <section class="card-surface sales-panel motion-fade-slide" style="--motion-delay: 0.16s">
        <div class="selected-goods-card" :class="{ empty: isRepairMode ? !form.shopId : !form.goodsId }">
          <template v-if="!isRepairMode && form.goodsId">
            <strong>{{ goodsDisplayName }}</strong>
            <div class="selected-goods-meta">
              <span>条码 {{ form.goodsBarcode }}</span>
              <span>品牌 {{ form.goodsBrand }}</span>
              <span>系列 {{ form.goodsSeries }}</span>
              <span>型号 {{ form.goodsModel }}</span>
              <span v-if="selectedGoodsInventoryLoading">库存加载中...</span>
              <span v-else-if="showShopSelector && form.shipShopId">当前发货店铺/仓库库存 {{ selectedGoodsShopQuantity }}</span>
              <span v-else-if="showShopSelector">当前发货店铺/仓库库存待选择</span>
              <span>总库存 {{ selectedGoodsTotalStock }}</span>
            </div>
          </template>
          <template v-else-if="isRepairMode">
            <strong>{{ repairEntryHeaderTitle }}</strong>
            <div class="selected-goods-meta">
              <span>{{ form.shopName || '未选择维修点' }}</span>
              <span>{{ resolveSelectedSalespersonDisplay() || '未选择工程师' }}</span>
            </div>
          </template>
          <template v-else>
            <strong>尚未选择商品</strong>
          </template>
        </div>

        <el-form label-position="top" class="entry-form" @submit.prevent="onSubmit" @keydown.enter="handleEntryFormEnter">
          <div class="entry-grid">
            <el-form-item label="销售时间" class="entry-field entry-field-sold-at">
              <el-input v-model="form.soldAt" type="datetime-local" />
            </el-form-item>
            <el-form-item v-if="!isRepairMode" label="数量" class="entry-field entry-field-quantity">
              <el-input-number v-model="form.quantity" :min="1" :max="1000000" class="full-width" />
            </el-form-item>
            <el-form-item v-if="!isRepairMode" label="单价（元）" class="entry-field entry-field-unit-price">
              <el-input :model-value="`¥ ${formatMoney(form.unitPrice)}`" readonly class="sales-entry-readonly-input" />
            </el-form-item>
            <el-form-item v-if="!isRepairMode" label="应收金额（元）" class="entry-field entry-field-receivable">
              <el-input :model-value="`¥ ${formatMoney(form.receivableAmount)}`" readonly class="sales-entry-readonly-input" />
            </el-form-item>
            <el-form-item :label="isRepairMode ? '实收金额（元）' : '实收金额（元）'" class="entry-field entry-field-received entry-field-emphasis">
              <el-input
                :model-value="receivedAmountDisplayValue"
                :placeholder="receivedAmountPlaceholder"
                inputmode="decimal"
                class="full-width sales-entry-amount-input"
                @input="onReceivedAmountInput"
                @focus="onReceivedAmountFocus"
                @blur="onReceivedAmountBlur"
              />
            </el-form-item>
            <el-form-item v-if="!isRepairMode" label="优惠券（元，可选）" class="entry-field entry-field-coupon">
              <el-input-number
                v-model="form.couponAmount"
                :min="0"
                :step="0.01"
                :precision="2"
                :max="99999999"
                class="full-width"
              />
            </el-form-item>
            <el-form-item v-if="!isRepairMode" label="折扣" class="entry-field entry-field-discount">
              <el-input :model-value="discountDisplay" readonly />
            </el-form-item>
            <el-form-item v-if="!isRepairMode" label="渠道" class="entry-field entry-field-channel">
              <el-select
                v-model="form.channel"
                filterable
                allow-create
                default-first-option
                class="full-width"
                placeholder="请选择销售渠道"
                @change="onChannelChange"
              >
                <el-option
                  v-for="option in channelOptions"
                  :key="option"
                  :label="option"
                  :value="option"
                />
              </el-select>
            </el-form-item>
            <el-form-item v-if="showShopSelector" :label="isRepairMode ? '销售店铺' : '销售店铺'" class="entry-field entry-field-shop">
              <el-select
                v-model="form.shopId"
                class="full-width"
                filterable
                clearable
                placeholder="请选择销售店铺"
                @visible-change="onShopSelectVisible"
                @change="onShopChange"
              >
                <el-option
                  v-for="option in storeOptions"
                  :key="option.id"
                  :label="option.name"
                  :value="option.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item v-if="showShipShopSelector" label="发货店铺 / 仓库" class="entry-field entry-field-shop">
              <el-select
                v-model="form.shipShopId"
                class="full-width"
                filterable
                clearable
                placeholder="请选择发货店铺 / 仓库"
                @visible-change="onShopSelectVisible"
                @change="onShipShopChange"
              >
                <el-option
                  v-for="option in shipLocationOptions"
                  :key="`ship-${option.id}`"
                  :label="option.shopType === SHOP_TYPE_WAREHOUSE ? `${option.name} · 仓库` : option.name"
                  :value="option.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item :label="isRepairMode ? '工程师' : '销售员'" class="entry-field entry-field-salesperson">
              <el-select
                v-model="form.salesperson"
                class="full-width"
                filterable
                clearable
                placeholder="请选择销售员"
                @visible-change="onSalespersonSelectVisible"
              >
                <el-option
                  v-for="option in selectableSalespersonOptions"
                  :key="option.username"
                  :label="option.displayName ? `${option.username} · ${option.displayName}` : option.username"
                  :value="option.username"
                />
              </el-select>
            </el-form-item>
            <el-form-item v-if="!isRepairMode" label="客户姓名" class="entry-field entry-field-customer">
              <el-input v-model.trim="form.customerName" placeholder="可选" />
            </el-form-item>
          </div>

          <el-form-item label="备注">
            <el-input
              v-model.trim="form.note"
              type="textarea"
              :rows="4"
              maxlength="5000"
              show-word-limit
              placeholder="可记录活动、售后说明或特殊备注"
            />
          </el-form-item>

          <div class="form-actions sales-entry-form-actions">
            <el-button type="primary" class="sales-entry-submit-primary" :loading="submitting" native-type="submit">{{ isRepairMode ? '提交维修销售记录' : '提交销售记录' }}</el-button>
            <el-button class="sales-entry-submit-secondary" @click="goRecords">{{ isRepairMode ? '查看维修销售记录' : '查看销售记录' }}</el-button>
            <el-button v-if="!isRepairMode" class="sales-entry-submit-import" @click="salesImportDialogVisible = true">导入历史销售</el-button>
          </div>
        </el-form>

        <el-alert
          v-if="message"
          :title="message"
          :type="isError ? 'error' : 'success'"
          :closable="false"
          show-icon
          class="page-alert"
        />
      </section>
    </div>

    <el-dialog
      v-model="scannerDialogVisible"
      title="本次销售商品"
      width="min(520px, 94vw)"
      destroy-on-close
      append-to-body
      class="scanner-modal aqc-app-dialog"
      @closed="closeScannerDialog"
    >
      <div class="scanner-modal-body">
        <div
          class="scanner-stage scanner-modal-stage"
          :class="{ interactive: scannerManualFocusSupported }"
          @click="onScannerStageFocus"
        >
          <video ref="videoRef" autoplay playsinline muted />
          <div class="scanner-reticle scanner-reticle-barcode" aria-hidden="true"></div>
          <span v-if="scannerManualFocusSupported" class="scanner-focus-badge">点按画面手动对焦</span>
        </div>

        <p class="scan-hint scanner-modal-hint">
          {{ scannerHint }}
        </p>

        <div class="scanner-result-card" :class="{ empty: !form.goodsId && !scannerResultText }">
          <template v-if="form.goodsId">
            <span>已识别商品</span>
            <strong>{{ goodsDisplayName }}</strong>
            <div class="selected-goods-meta">
              <span>条码 {{ form.goodsBarcode }}</span>
            </div>
          </template>
          <template v-else>
            <span>扫码结果</span>
            <strong>{{ scannerResultText || '等待识别条码' }}</strong>
            <p>识别成功后会自动回填到本次销售商品。</p>
          </template>
        </div>
      </div>

      <template #footer>
        <div class="form-actions">
          <el-button v-if="form.goodsId || scannerResultText" type="primary" @click="closeScannerDialog">确定</el-button>
          <el-button v-else @click="closeScannerDialog">关闭</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="salesImportDialogVisible"
      title="导入历史销售"
      width="min(860px, 96vw)"
      destroy-on-close
      append-to-body
      align-center
      class="aqc-app-dialog sales-import-dialog"
    >
      <div class="selected-goods-card sales-import-card sales-import-dialog-card">
        <div class="sales-import-head">
          <div>
            <strong>历史销售表导入</strong>
            <p>支持旧系统导出的 `ShoppingOrderClockItem` 销售表，建议先校验再正式导入。导入成功后会同步扣减对应门店库存。</p>
          </div>
          <input
            ref="importFileInputRef"
            class="sales-import-file-input"
            type="file"
            accept=".xlsx"
            @change="onImportFileChange"
          />
          <div class="sales-import-toolbar">
            <el-button @click="openImportPicker">选择表格</el-button>
            <el-button :disabled="!importFile" :loading="importDryRunPending" @click="runSalesTemplateImport(true)">先校验</el-button>
            <el-button type="primary" :disabled="!importFile" :loading="importPending" @click="runSalesTemplateImport(false)">
              校验并导入
            </el-button>
            <el-button text :disabled="!importFile" @click="clearImportFile">清空</el-button>
          </div>
        </div>

        <div class="selected-goods-meta sales-import-meta">
          <span v-if="importFile">已选文件 {{ importFile.name }}</span>
          <span v-else>请选择 `.xlsx` 销售表</span>
          <span v-if="importStats.totalRows">总行数 {{ importStats.totalRows }}</span>
          <span v-if="importStats.rowsReady">可导入 {{ importStats.rowsReady }}</span>
          <span v-if="importStats.imported">已导入 {{ importStats.imported }}</span>
          <span v-if="importStats.duplicates">重复 {{ importStats.duplicates }}</span>
        </div>

        <div v-if="importResult?.message" class="sales-import-result" :class="{ error: !importResult.success }">
          <strong>{{ importResult.message }}</strong>

          <div class="sales-import-stats">
            <span v-if="importStats.matchedGoods">商品匹配 {{ importStats.matchedGoods }}</span>
            <span v-if="importStats.matchedShops">门店匹配 {{ importStats.matchedShops }}</span>
            <span v-if="importStats.receivedTotal">实收合计 ¥ {{ formatMoney(importStats.receivedTotal) }}</span>
            <span v-if="importStats.skipped">跳过 {{ importStats.skipped }}</span>
          </div>

          <div v-if="importAliasItems.length" class="sales-import-error-list">
            <span>已自动标准化门店</span>
            <ul>
              <li v-for="item in importAliasItems" :key="item.name">{{ item.name }} × {{ item.count }}</li>
            </ul>
          </div>

          <div v-if="(importStats.unmatchedGoods || []).length" class="sales-import-error-list">
            <span>未匹配商品</span>
            <ul>
              <li
                v-for="item in (importStats.unmatchedGoods || []).slice(0, 5)"
                :key="`${item.order}-${item.model}`"
              >
                {{ item.order }} / {{ [item.brand, item.series, item.model].filter(Boolean).join(' ') || '未识别商品' }}
              </li>
            </ul>
          </div>

          <div v-if="(importStats.unmatchedShops || []).length" class="sales-import-error-list">
            <span>未匹配门店</span>
            <ul>
              <li
                v-for="item in (importStats.unmatchedShops || []).slice(0, 5)"
                :key="`${item.order}-${item.shop}`"
              >
                {{ item.order }} / {{ item.shop }}<template v-if="item.mappedShop && item.mappedShop !== item.shop"> -> {{ item.mappedShop }}</template>
              </li>
            </ul>
          </div>

          <div v-if="(importStats.outOfScopeShops || []).length" class="sales-import-error-list">
            <span>超出账号门店范围</span>
            <ul>
              <li
                v-for="item in (importStats.outOfScopeShops || []).slice(0, 5)"
                :key="`${item.order}-${item.shopId}`"
              >
                {{ item.order }} / {{ item.shop }}
              </li>
            </ul>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="form-actions">
          <el-button @click="salesImportDialogVisible = false">关闭</el-button>
        </div>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import CollapsePanelTransition from '../components/CollapsePanelTransition.vue'
import ResponsiveTableActions from '../components/ResponsiveTableActions.vue'
import { useBarcodeScanner } from '../composables/useBarcodeScanner'
import { useMobileViewport } from '../composables/useMobileViewport'
import { apiGet, apiPost, apiUpload } from '../services/api'
import { useAuthStore } from '../stores/auth'
import { getShanghaiDateTimeLocalValue } from '../utils/shanghaiTime'
import { resolveTableActionWidth } from '../utils/tableActions'
import { SHOP_TYPE_REPAIR, SHOP_TYPE_STORE, SHOP_TYPE_WAREHOUSE } from '../utils/shops'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()
const { isMobileViewport } = useMobileViewport()
const isRepairMode = computed(() => route.name === 'repair-sales-entry')

const message = ref('')
const isError = ref(false)
const submitting = ref(false)
const barcodeLoading = ref(false)
const suggestionsLoading = ref(false)
const searchKeyword = ref('')
const searchBrand = ref('')
const searchSeries = ref('')
const searchIndex = ref('')
const barcodeInput = ref('')
const filterPanelOpen = ref(false)
const suggestions = ref([])
const hasSearchedSuggestions = ref(false)
const scannerDialogVisible = ref(false)
const scannerResultText = ref('')
const salesImportDialogVisible = ref(false)
const importFileInputRef = ref(null)
const importFile = ref(null)
const importPending = ref(false)
const importDryRunPending = ref(false)
const importResult = ref(null)
const storeOptions = ref([])
const shopOptions = ref([])
const salespersonOptions = ref([])
const receivedManuallyEdited = ref(false)
const receivedAmountInput = ref('')
const selectedGoodsInventoryLoading = ref(false)
const selectedGoodsInventories = ref([])
const selectedGoodsTotalStock = ref(0)
const lastSelectedSalesShopId = ref(null)
const suggestionActionColumnWidth = computed(() => resolveTableActionWidth([['选择']], {
  compact: isMobileViewport.value,
  minWidth: 92,
  maxWidth: 126,
}))

const meta = reactive({
  brandOptions: [],
  seriesOptions: [],
  indexOptions: [],
})

const channelOptions = ['门店', '小程序', '企业微信', '私域', '团购', '其他']

const defaultSoldAt = getShanghaiDateTimeLocalValue()

const form = reactive({
  soldAt: defaultSoldAt,
  goodsId: null,
  goodsCode: '',
  goodsBrand: '',
  goodsSeries: '',
  goodsModel: '',
  goodsBarcode: '',
  unitPrice: 0,
  receivableAmount: 0,
  receivedAmount: 0,
  couponAmount: 0,
  quantity: 1,
  channel: '门店',
  shopId: null,
  shopName: '',
  shipShopId: null,
  shipShopName: '',
  salesperson: authStore.user?.username || '',
  customerName: '',
  note: '',
})

const showShopSelector = computed(() => (isRepairMode.value ? true : form.channel === '门店'))
const showShipShopSelector = computed(() => !isRepairMode.value && showShopSelector.value)

const priceFormatter = new Intl.NumberFormat('zh-CN', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

const goodsDisplayName = computed(() => {
  return [form.goodsBrand, form.goodsSeries, form.goodsModel].filter(Boolean).join(' ').trim() || '未选择商品'
})
const repairEntryHeaderTitle = computed(() => form.shopName || defaultUserShopName.value || '维修销售')

const importStats = computed(() => importResult.value?.stats || {})

const importAliasItems = computed(() => {
  return Object.entries(importStats.value.aliasCounts || {}).map(([name, count]) => ({
    name,
    count: Number(count || 0),
  }))
})

const discountRateValue = computed(() => {
  const receivable = Number(form.receivableAmount || 0)
  const received = Number(form.receivedAmount || 0)
  if (receivable <= 0) {
    return 0
  }
  if (received >= receivable) {
    return 10
  }
  return Number(((received / receivable) * 10).toFixed(2))
})

const receivedAmountDisplayValue = computed(() => (
  receivedManuallyEdited.value ? receivedAmountInput.value : ''
))

const receivedAmountPlaceholder = computed(() => {
  const suggestedAmount = Number(form.receivableAmount || form.receivedAmount || 0)
  if (suggestedAmount > 0) {
    return `¥ ${formatMoney(suggestedAmount)}`
  }
  return '请输入实收金额'
})

const discountDisplay = computed(() => {
  const receivable = Number(form.receivableAmount || 0)
  const received = Number(form.receivedAmount || 0)
  if (receivable <= 0) {
    return '/'
  }
  if (Math.abs(receivable - received) < 0.005 && discountRateValue.value >= 9.99) {
    return '/'
  }
  return discountRateValue.value.toFixed(2)
})

const defaultUserShopId = computed(() => {
  const scopedShopIds = Array.isArray(authStore.user?.shopIds) ? authStore.user.shopIds : []
  if (scopedShopIds.length) {
    return scopedShopIds[0]
  }
  return authStore.user?.shopId || null
})

const defaultUserShopName = computed(() => {
  const scopedShopNames = Array.isArray(authStore.user?.shopNames) ? authStore.user.shopNames : []
  if (scopedShopNames.length) {
    return scopedShopNames[0]
  }
  return authStore.user?.shopName || ''
})

const shipLocationOptions = computed(() => shopOptions.value)
function isRepairEngineerEligible(option) {
  const roleKey = String(option?.aqcRoleKey || '').trim()
  return roleKey === 'aqc_engineer' || roleKey === 'aqc_admin'
}

const selectableSalespersonOptions = computed(() => {
  if (!isRepairMode.value) {
    return salespersonOptions.value
  }
  return salespersonOptions.value.filter((item) => isRepairEngineerEligible(item))
})

const selectedGoodsShopQuantity = computed(() => {
  const currentShopId = Number(form.shipShopId || 0)
  if (!currentShopId) {
    return 0
  }
  const matched = selectedGoodsInventories.value.find((item) => Number(item.shopId || 0) === currentShopId)
  return Number(matched?.quantity || 0)
})

const activeFilterCount = computed(() => {
  let count = 0
  if (barcodeInput.value) count += 1
  if (searchBrand.value) count += 1
  if (searchSeries.value) count += 1
  if (searchIndex.value) count += 1
  return count
})

const {
  videoRef,
  scanning,
  scannerPending,
  scannerHint,
  scannerManualFocusSupported,
  startScanner,
  stopScanner,
  focusScannerAt,
} = useBarcodeScanner({
  onDetected: async (code) => {
    scannerResultText.value = code
    barcodeInput.value = code
    await lookupBarcode()
    await stopScanner()
  },
})

async function onScannerStageFocus(event) {
  await focusScannerAt(event)
}

function formatMoney(value) {
  return priceFormatter.format(Number(value || 0))
}

function toLocalDateTimePayload(value) {
  const text = String(value || '').trim()
  if (!text) {
    return null
  }
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(text)) {
    return `${text}:00`
  }
  return text
}

function resolveSalespersonPayload() {
  const selectedValue = String(form.salesperson || '').trim()
  if (!selectedValue) {
    return authStore.displayName || authStore.user?.username || ''
  }
  const matched = selectableSalespersonOptions.value.find((item) => item.username === selectedValue || item.displayName === selectedValue)
  if (matched) {
    return matched.displayName || matched.username || selectedValue
  }
  return selectedValue
}

function resolveSelectedSalespersonDisplay() {
  const selectedValue = String(form.salesperson || '').trim()
  if (!selectedValue) {
    return ''
  }
  const matched = selectableSalespersonOptions.value.find((item) => item.username === selectedValue || item.displayName === selectedValue)
  return matched?.displayName || matched?.username || selectedValue
}

function setMessage(text, error = false) {
  message.value = text
  isError.value = error
}

function applyDefaultReceivedAmount() {
  const suggestedAmount = Number(form.receivableAmount || 0)
  form.receivedAmount = suggestedAmount > 0 ? suggestedAmount : 0
  if (isRepairMode.value) {
    form.receivableAmount = Number(form.receivedAmount || 0)
  }
}

function normalizeReceivedAmountInput(value) {
  return String(value || '')
    .replace(/[^\d.]/g, '')
    .replace(/(\..*)\./g, '$1')
}

function formatEditableAmount(value) {
  const numericValue = Number(value || 0)
  if (!Number.isFinite(numericValue) || numericValue <= 0) {
    return ''
  }
  return String(Number(numericValue.toFixed(2)))
}

function openImportPicker() {
  importFileInputRef.value?.click()
}

function onImportFileChange(event) {
  const nextFile = event?.target?.files?.[0] || null
  if (event?.target) {
    event.target.value = ''
  }
  if (!nextFile) {
    return
  }
  if (!String(nextFile.name || '').toLowerCase().endsWith('.xlsx')) {
    importFile.value = null
    importResult.value = null
    setMessage('仅支持导入 .xlsx 销售表', true)
    ElMessage.error('仅支持导入 .xlsx 销售表')
    return
  }
  importFile.value = nextFile
  importResult.value = null
  setMessage(`已选择销售表：${nextFile.name}`)
}

function clearImportFile() {
  importFile.value = null
  importResult.value = null
  if (importFileInputRef.value) {
    importFileInputRef.value.value = ''
  }
}

async function runSalesTemplateImport(dryRun = false) {
  if (!importFile.value) {
    setMessage('请先选择需要导入的销售表', true)
    return
  }

  if (dryRun) {
    importDryRunPending.value = true
  } else {
    importPending.value = true
  }

  const payload = await apiUpload('/sales/template-import', importFile.value, {
    token: authStore.token,
    query: {
      dry_run: dryRun ? 'true' : 'false',
    },
    timeoutMs: 60000,
  })

  if (dryRun) {
    importDryRunPending.value = false
  } else {
    importPending.value = false
  }

  importResult.value = payload || { success: false, message: dryRun ? '校验失败' : '导入失败', stats: {} }
  setMessage(importResult.value.message || (dryRun ? '校验失败' : '导入失败'), !importResult.value.success)

  if (importResult.value.success) {
    ElMessage.success(importResult.value.message || (dryRun ? '校验通过' : '导入成功'))
    if (!dryRun && hasSearchedSuggestions.value) {
      await loadSuggestions()
    }
    if (!dryRun && form.goodsId) {
      await loadSelectedGoodsInventory(form.goodsId)
    }
    return
  }
  ElMessage.error(importResult.value.message || (dryRun ? '校验失败' : '导入失败'))
}

async function loadMeta() {
  if (isRepairMode.value) {
    meta.brandOptions = []
    meta.seriesOptions = []
    meta.indexOptions = []
    return
  }
  const payload = await apiGet('/goods/catalog/meta', {
    token: authStore.token,
    query: {
      catalog_only: 'true',
      ...(searchKeyword.value ? { q: searchKeyword.value } : {}),
      ...(searchBrand.value ? { brand: searchBrand.value } : {}),
      ...(barcodeInput.value ? { barcode: barcodeInput.value } : {}),
      ...(searchIndex.value ? { index_key: searchIndex.value } : {}),
    },
  })
  if (!payload?.success) {
    return
  }
  meta.brandOptions = payload.brandOptions || []
  meta.seriesOptions = payload.seriesOptions || []
  meta.indexOptions = payload.indexOptions || []
}

async function loadSuggestions() {
  if (isRepairMode.value) {
    suggestions.value = []
    return
  }
  suggestionsLoading.value = true
  const payload = await apiGet('/goods/items', {
    token: authStore.token,
    query: {
      page: '1',
      page_size: '10',
      catalog_only: 'true',
      sort_field: 'product_code',
      sort_order: 'desc',
      ...(searchKeyword.value ? { q: searchKeyword.value } : {}),
      ...(searchBrand.value ? { brand: searchBrand.value } : {}),
      ...(searchSeries.value ? { series: searchSeries.value } : {}),
      ...(barcodeInput.value ? { barcode: barcodeInput.value } : {}),
      ...(searchIndex.value ? { index_key: searchIndex.value } : {}),
    },
  })
  suggestionsLoading.value = false
  if (!payload?.success) {
    ElMessage.error(payload?.message || '商品检索失败')
    return
  }
  suggestions.value = payload.items || []
}

async function loadShopOptions() {
  if (isRepairMode.value) {
    const repairPayload = await apiGet('/shops', {
      token: authStore.token,
      query: {
        page: '1',
        page_size: '100',
        shop_type: String(SHOP_TYPE_REPAIR),
      },
    })
    if (!repairPayload?.success) {
      return
    }
    storeOptions.value = (repairPayload.shops || []).map((item) => ({
      id: item.id,
      name: item.name,
      shopType: SHOP_TYPE_REPAIR,
    })).sort((left, right) => Number(left.id || 0) - Number(right.id || 0))
    shopOptions.value = [...storeOptions.value]
    return
  }
  const [storePayload, warehousePayload] = await Promise.all([
    apiGet('/shops', {
      token: authStore.token,
      query: {
        page: '1',
        page_size: '100',
        shop_type: String(SHOP_TYPE_STORE),
      },
    }),
    apiGet('/shops', {
      token: authStore.token,
      query: {
        page: '1',
        page_size: '100',
        shop_type: String(SHOP_TYPE_WAREHOUSE),
      },
    }),
  ])
  if (!storePayload?.success || !warehousePayload?.success) {
    return
  }
  storeOptions.value = (storePayload.shops || []).map((item) => ({
    id: item.id,
    name: item.name,
    shopType: SHOP_TYPE_STORE,
  })).sort((left, right) => Number(left.id || 0) - Number(right.id || 0))
  shopOptions.value = [
    ...storeOptions.value,
    ...(warehousePayload.shops || []).map((item) => ({
      id: item.id,
      name: item.name,
      shopType: SHOP_TYPE_WAREHOUSE,
    })),
  ].sort((left, right) => Number(left.id || 0) - Number(right.id || 0))
}

async function loadSalespersonOptions() {
  const payload = await apiGet('/users/options', {
    token: authStore.token,
    query: {
      limit: '200',
    },
  })
  if (!payload?.success) {
    return
  }

  const options = payload.options || []
  const currentUsername = authStore.user?.username || ''
  if (currentUsername && !options.some((item) => item.username === currentUsername)) {
    options.unshift({
      id: Number(authStore.user?.id || 0),
      username: currentUsername,
      displayName: authStore.displayName,
      aqcRoleKey: authStore.aqcRoleKey,
      aqcRoleName: authStore.user?.aqcRoleName || '',
    })
  }
  salespersonOptions.value = options

  if (!form.salesperson) {
    form.salesperson = currentUsername
  }
  if (defaultUserShopId.value && !form.shopId) {
    form.shopId = defaultUserShopId.value
    form.shopName = defaultUserShopName.value
    form.shipShopId = isRepairMode.value ? null : defaultUserShopId.value
    form.shipShopName = isRepairMode.value ? '' : defaultUserShopName.value
  }
  if (isRepairMode.value && isRepairEngineerEligible(authStore.user)) {
    form.salesperson = currentUsername
  }
}

async function loadSelectedGoodsInventory(itemId) {
  const numericId = Number(itemId || 0)
  if (!numericId) {
    selectedGoodsInventories.value = []
    selectedGoodsTotalStock.value = 0
    return
  }

  selectedGoodsInventoryLoading.value = true
  const payload = await apiGet('/goods/items/' + numericId + '/inventory', {
    token: authStore.token,
    timeoutMs: 12000,
  })
  selectedGoodsInventoryLoading.value = false

  if (!payload?.success) {
    selectedGoodsInventories.value = []
    selectedGoodsTotalStock.value = 0
    ElMessage.error(payload?.message || '商品库存加载失败')
    return
  }

  selectedGoodsInventories.value = payload.inventories || []
  selectedGoodsTotalStock.value = Number(payload.totalStock || 0)
}

async function searchSuggestions() {
  hasSearchedSuggestions.value = true
  await Promise.all([loadMeta(), loadSuggestions()])
}

async function onResetSearch() {
  if (isRepairMode.value) {
    form.soldAt = defaultSoldAt
    form.receivableAmount = 0
    form.receivedAmount = 0
    receivedAmountInput.value = ''
    receivedManuallyEdited.value = false
    form.shopId = defaultUserShopId.value
    form.shopName = defaultUserShopName.value
    form.salesperson = authStore.user?.username || ''
    form.note = ''
    return
  }
  searchKeyword.value = ''
  searchBrand.value = ''
  searchSeries.value = ''
  searchIndex.value = ''
  barcodeInput.value = ''
  scannerResultText.value = ''
  suggestions.value = []
  hasSearchedSuggestions.value = false
  filterPanelOpen.value = false
  clearSelectedGoods()
  await loadMeta()
}

function selectGoods(item) {
  const baseUnitPrice = Number(item.originalPrice || item.price || item.salePrice || 0)
  form.goodsId = item.id
  form.goodsCode = ''
  form.goodsBrand = item.brand || ''
  form.goodsSeries = item.series || ''
  form.goodsModel = item.model || ''
  form.goodsBarcode = item.barcode || ''
  form.unitPrice = baseUnitPrice
  const computedAmount = Number((baseUnitPrice * Number(form.quantity || 1)).toFixed(2))
  form.receivableAmount = computedAmount
  form.receivedAmount = computedAmount
  form.couponAmount = 0
  receivedManuallyEdited.value = false
  receivedAmountInput.value = ''
  barcodeInput.value = item.barcode || ''
  scannerResultText.value = [item.brand, item.series, item.model].filter(Boolean).join(' ')
  setMessage(`已选择商品：${[item.brand, item.series, item.model].filter(Boolean).join(' ')}`)
}

function clearSelectedGoods() {
  form.goodsId = null
  form.goodsCode = ''
  form.goodsBrand = ''
  form.goodsSeries = ''
  form.goodsModel = ''
  form.goodsBarcode = ''
  form.unitPrice = 0
  form.receivableAmount = 0
  form.receivedAmount = 0
  form.couponAmount = 0
  receivedManuallyEdited.value = false
  receivedAmountInput.value = ''
  barcodeInput.value = ''
  selectedGoodsInventories.value = []
  selectedGoodsTotalStock.value = 0
  selectedGoodsInventoryLoading.value = false
}

function onReceivedAmountFocus() {
  if (!receivedManuallyEdited.value) {
    receivedAmountInput.value = ''
  }
}

function onReceivedAmountInput(value) {
  receivedAmountInput.value = normalizeReceivedAmountInput(value)
  receivedManuallyEdited.value = true
  const parsed = Number(receivedAmountInput.value)
  form.receivedAmount = Number.isFinite(parsed) ? parsed : 0
  if (isRepairMode.value) {
    form.receivableAmount = Number(form.receivedAmount || 0)
  }
}

function onReceivedAmountBlur() {
  if (!String(receivedAmountInput.value || '').trim()) {
    receivedManuallyEdited.value = false
    receivedAmountInput.value = ''
    applyDefaultReceivedAmount()
    return
  }
  receivedAmountInput.value = formatEditableAmount(form.receivedAmount)
}

function onChannelChange() {
  if (isRepairMode.value) {
    return
  }
  if (form.channel === '门店') {
    if (!shopOptions.value.length) {
      void loadShopOptions()
    }
    return
  }
  form.shopId = null
  form.shopName = ''
  form.shipShopId = null
  form.shipShopName = ''
}

function onShopSelectVisible(visible) {
  if (visible && !shopOptions.value.length) {
    void loadShopOptions()
  }
}

function onSalespersonSelectVisible(visible) {
  if (visible && !salespersonOptions.value.length) {
    void loadSalespersonOptions()
  }
}

function onShopChange(shopId) {
  const previousSalesShopId = Number(lastSelectedSalesShopId.value || 0)
  const matched = storeOptions.value.find((item) => item.id === shopId)
  form.shopName = matched?.name || ''
  if (isRepairMode.value) {
    lastSelectedSalesShopId.value = matched?.id || null
    return
  }
  if (!form.shipShopId || Number(form.shipShopId || 0) === previousSalesShopId || !form.shipShopName) {
    form.shipShopId = matched?.id || null
    form.shipShopName = matched?.name || ''
  }
  lastSelectedSalesShopId.value = matched?.id || null
}

function onShipShopChange(shopId) {
  const matched = shopOptions.value.find((item) => item.id === shopId)
  form.shipShopName = matched?.name || ''
}

async function lookupBarcode() {
  const barcode = (barcodeInput.value || '').trim()
  if (!barcode) {
    setMessage('请输入或扫描条码', true)
    return
  }

  barcodeLoading.value = true
  const payload = await apiGet(`/goods/barcode/${encodeURIComponent(barcode)}`, {
    token: authStore.token,
    query: {
      catalog_only: 'true',
    },
  })
  barcodeLoading.value = false

  if (!payload?.success || !payload.item) {
    setMessage(payload?.message || '未找到匹配条码的商品', true)
    return
  }

  selectGoods(payload.item)
}

function setSearchIndex(value) {
  searchIndex.value = value
  if (hasSearchedSuggestions.value) {
    void Promise.all([loadMeta(), loadSuggestions()])
    return
  }
  void loadMeta()
}

function onSearchBrandChange() {
  if (searchSeries.value && !meta.seriesOptions.some((item) => item.value === searchSeries.value)) {
    searchSeries.value = ''
  }
  if (hasSearchedSuggestions.value) {
    void Promise.all([loadMeta(), loadSuggestions()])
    return
  }
  void loadMeta()
}

async function openScannerDialog() {
  scannerDialogVisible.value = true
  scannerResultText.value = form.goodsId ? goodsDisplayName.value : ''
  await nextTick()
  await startScanner()
}

async function closeScannerDialog() {
  scannerDialogVisible.value = false
  await stopScanner()
}

async function onSubmit() {
  if (!isRepairMode.value && !form.goodsId) {
    setMessage('请先选择商品或通过条码匹配商品', true)
    return
  }
  if (!isRepairMode.value && (!form.receivableAmount || form.receivableAmount <= 0)) {
    setMessage('请输入正确的应收金额', true)
    return
  }
  if (!form.receivedAmount || form.receivedAmount <= 0) {
    setMessage('请输入正确的实收金额', true)
    return
  }
  if (showShopSelector.value && !form.shopId) {
    setMessage(isRepairMode.value ? '请选择销售店铺' : '门店销售请选择销售店铺', true)
    return
  }
  if (showShipShopSelector.value && !form.shipShopId) {
    setMessage('门店销售请选择发货店铺 / 仓库', true)
    return
  }

  submitting.value = true
  const payload = await apiPost(
    '/sales/records',
    {
      saleKind: isRepairMode.value ? 'repair' : 'goods',
      soldAt: toLocalDateTimePayload(form.soldAt),
      goodsId: isRepairMode.value ? null : form.goodsId,
      goodsCode: isRepairMode.value ? '' : form.goodsCode,
      goodsBrand: isRepairMode.value ? '' : form.goodsBrand,
      goodsSeries: isRepairMode.value ? '' : form.goodsSeries,
      goodsModel: isRepairMode.value ? '' : form.goodsModel,
      goodsBarcode: isRepairMode.value ? '' : form.goodsBarcode,
      unitPrice: Number(isRepairMode.value ? (form.receivedAmount || 0) : (form.unitPrice || 0)),
      receivableAmount: Number(isRepairMode.value ? (form.receivedAmount || 0) : (form.receivableAmount || 0)),
      receivedAmount: Number(form.receivedAmount || 0),
      couponAmount: Number(isRepairMode.value ? 0 : (form.couponAmount || 0)),
      discountRate: isRepairMode.value ? 10 : discountRateValue.value,
      amount: Number(form.receivedAmount || 0),
      quantity: Number(isRepairMode.value ? 1 : (form.quantity || 1)),
      channel: isRepairMode.value ? '维修' : form.channel,
      shopId: form.shopId,
      shopName: form.shopName,
      shipShopId: isRepairMode.value ? null : form.shipShopId,
      shipShopName: isRepairMode.value ? '' : form.shipShopName,
      salesperson: resolveSalespersonPayload(),
      customerName: isRepairMode.value ? '' : form.customerName,
      note: form.note,
    },
    { token: authStore.token },
  )
  submitting.value = false

  if (!payload?.success) {
    setMessage(payload?.message || '录入失败', true)
    return
  }

  ElMessage.success(payload.message || '提交成功')
  setMessage(payload.message || (isRepairMode.value ? '维修销售录入成功' : '录入成功'))
  form.quantity = 1
  form.receivableAmount = 0
  form.receivedAmount = 0
  form.couponAmount = 0
  form.channel = isRepairMode.value ? '维修' : '门店'
  form.shopId = defaultUserShopId.value
  form.shopName = defaultUserShopName.value
  form.shipShopId = isRepairMode.value ? null : defaultUserShopId.value
  form.shipShopName = isRepairMode.value ? '' : defaultUserShopName.value
  lastSelectedSalesShopId.value = defaultUserShopId.value
  form.salesperson = authStore.user?.username || form.salesperson
  form.customerName = ''
  form.note = ''
  receivedManuallyEdited.value = false
  receivedAmountInput.value = ''
  if (!isRepairMode.value) {
    clearSelectedGoods()
  }
  if (!isRepairMode.value && hasSearchedSuggestions.value) {
    await loadSuggestions()
  }
}

function handleEntryFormEnter(event) {
  const target = event?.target
  const tagName = String(target?.tagName || '').toLowerCase()
  const isTextArea = tagName === 'textarea'
  const isSubmitControl = target?.closest?.('.sales-entry-submit-primary')
  if (isTextArea || isSubmitControl) {
    return
  }
  event.preventDefault()
  event.stopPropagation()
  if (isMobileViewport.value && typeof target?.blur === 'function') {
    target.blur()
  }
}

function goRecords() {
  router.push({ name: isRepairMode.value ? 'repair-sales-records' : 'sales-records' })
}

function goRepairEntry() {
  router.push({ name: 'repair-sales-entry' })
}

function goGoodsEntry() {
  router.push({ name: 'sales-entry' })
}

watch(
  () => [form.quantity, form.unitPrice],
  () => {
    if (isRepairMode.value) {
      return
    }
    if (!form.goodsId) {
      return
    }
    const computedAmount = Number((Number(form.quantity || 0) * Number(form.unitPrice || 0)).toFixed(2))
    const previousReceivable = Number(form.receivableAmount || 0)
    const shouldSyncReceived =
      !receivedManuallyEdited.value || Math.abs(Number(form.receivedAmount || 0) - previousReceivable) < 0.005
    form.receivableAmount = computedAmount
    if (shouldSyncReceived) {
      form.receivedAmount = computedAmount
      receivedManuallyEdited.value = false
      receivedAmountInput.value = ''
    }
  },
  { deep: true },
)

onMounted(() => {
  void (async () => {
    await Promise.all([loadMeta(), loadShopOptions(), loadSalespersonOptions()])
    if (defaultUserShopId.value) {
      form.shopId = defaultUserShopId.value
      form.shopName = defaultUserShopName.value
      form.shipShopId = isRepairMode.value ? null : defaultUserShopId.value
      form.shipShopName = isRepairMode.value ? '' : defaultUserShopName.value
      lastSelectedSalesShopId.value = defaultUserShopId.value
    }
    if (authStore.user?.username) {
      form.salesperson = authStore.user.username
    }
    if (isRepairMode.value) {
      form.channel = '维修'
      form.quantity = 1
      applyDefaultReceivedAmount()
    }
    if (!isRepairMode.value && String(route.query.scan || '').trim() === '1') {
      await openScannerDialog()
    }
  })()
})

watch(
  () => form.goodsId,
  (nextGoodsId) => {
    if (isRepairMode.value) {
      return
    }
    if (!nextGoodsId) {
      selectedGoodsInventories.value = []
      selectedGoodsTotalStock.value = 0
      selectedGoodsInventoryLoading.value = false
      return
    }
    void loadSelectedGoodsInventory(nextGoodsId)
  },
)

onBeforeUnmount(() => {
  stopScanner()
})
</script>
