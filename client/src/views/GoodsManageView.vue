<template>
  <section class="goods-manage-page goods-catalog-page">
    <section class="catalog-controls card-surface motion-fade-slide" style="--motion-delay: 0.08s">
      <div class="goods-search-shell">
        <el-input
          v-model.trim="keyword"
          clearable
          placeholder="搜索品牌 / 系列 / 型号 / 条码"
          class="goods-search-input"
          @keyup.enter="onSearch"
        />

        <div class="toolbar-actions goods-search-actions">
          <el-button type="primary" class="scanner-cta" :loading="catalogScannerPending" @click="openCatalogScannerDialog">
            {{ catalogScanning ? '识别中...' : catalogScannerPending ? '启动中...' : '摄像头识别条码' }}
          </el-button>
          <el-button :loading="loading" @click="onSearch">查询</el-button>
          <el-button @click="onResetFilters">重置</el-button>
          <el-dropdown v-if="authStore.can('goods.write')" trigger="click" @command="onImportMenuCommand">
            <el-button>导入商品表</el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="catalog">历史商品表</el-dropdown-item>
                <el-dropdown-item command="inventory">库存表</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button @click="openInventoryCompareDialog">对比</el-button>
          <el-button v-if="authStore.can('goods.write')" type="primary" @click="openCreate">新增商品</el-button>
        </div>
      </div>

      <section class="sales-filter-shell goods-filter-shell">
        <div class="sales-filter-trigger-row">
          <button type="button" class="sales-filter-trigger" :class="{ active: filterPanelOpen }" @click="filterPanelOpen = !filterPanelOpen">
            <div class="sales-filter-trigger-copy">
              <span>筛选</span>
              <strong>{{ filterPanelOpen ? '收起商品筛选' : '展开商品筛选' }}</strong>
            </div>
            <div class="sales-filter-trigger-meta">
              <div class="sales-filter-trigger-stats">
                <span>已筛选 {{ activeFilterCount }} 项</span>
                <strong>{{ total }} 条结果</strong>
              </div>
            </div>
          </button>
        </div>

        <CollapsePanelTransition>
          <div v-if="filterPanelOpen" class="sales-filter-collapse-shell">
            <section class="sales-filter-panel goods-filter-panel">
              <header class="sales-filter-head">
              <div class="sales-filter-head-copy">
                <h2>筛选</h2>
                <span>{{ currentSortLabel }}</span>
              </div>
              <div class="toolbar-actions sales-filter-head-actions">
                <el-button type="primary" :loading="loading" @click="onSearch">查询</el-button>
                <el-button class="sales-filter-reset-btn" :disabled="!activeFilterCount" @click="onResetFilters">清空筛选</el-button>
              </div>
            </header>

              <div class="sales-filter-grid goods-filter-grid">
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
                <label class="sales-filter-label">属性</label>
                <el-select
                  v-model="attributeFilter"
                  clearable
                  placeholder="筛选属性"
                  class="full-width"
                  @change="onSearch"
                >
                  <el-option
                    v-for="option in meta.attributeOptions"
                    :key="option.value"
                    :label="option.label + ' (' + option.count + ')'"
                    :value="option.value"
                  />
                </el-select>
              </div>

              <div class="sales-filter-field">
                <label class="sales-filter-label">条码</label>
                <el-input
                  v-model.trim="barcodeFilter"
                  clearable
                  placeholder="输入条码"
                  class="full-width"
                  @keyup.enter="lookupCatalogBarcode"
                />
              </div>

              <div class="sales-filter-field">
                <label class="sales-filter-label">库存</label>
                <el-select
                  v-model="hasStockFilter"
                  clearable
                  placeholder="全部商品"
                  class="full-width"
                  @change="onSearch"
                >
                  <el-option label="库存不为0" :value="'nonzero'" />
                  <el-option label="库存为0" :value="'zero'" />
                  <el-option label="库存异常（小于0）" :value="'negative'" />
                </el-select>
              </div>

              <div class="sales-filter-field">
                <label class="sales-filter-label">最低价</label>
                <el-input-number
                  v-model="priceMin"
                  :min="0"
                  :precision="2"
                  :controls="false"
                  placeholder="最低价"
                  class="full-width"
                />
              </div>

              <div class="sales-filter-field">
                <label class="sales-filter-label">最高价</label>
                <el-input-number
                  v-model="priceMax"
                  :min="0"
                  :precision="2"
                  :controls="false"
                  placeholder="最高价"
                  class="full-width"
                />
              </div>
            </div>

              <div class="sales-filter-footer">
              <div class="sales-filter-index-shell">
                <span class="sales-filter-subtitle">索引筛选</span>
                <div class="catalog-index-bar compact sales-filter-index-bar">
                  <button
                    type="button"
                    class="index-chip"
                    :class="{ active: !indexFilter }"
                    @click="setIndexFilter('')"
                  >
                    全部
                  </button>
                  <button
                    v-for="option in meta.indexOptions"
                    :key="option.key"
                    type="button"
                    class="index-chip"
                    :class="{ active: indexFilter === option.key }"
                    @click="setIndexFilter(option.key)"
                  >
                    <span>{{ option.key }}</span>
                    <small>{{ option.count }}</small>
                  </button>
                </div>
              </div>

              <div class="catalog-meta-row sales-filter-meta-row">
                <div class="catalog-meta-copy">
                  <span>当前排序</span>
                  <strong>{{ currentSortLabel }}</strong>
                </div>
                <div class="catalog-meta-copy">
                  <span>筛选结果</span>
                  <strong>{{ total }} 条</strong>
                </div>
                <div class="catalog-meta-copy">
                  <span>库存数量</span>
                  <strong>{{ filteredStockTotal }}</strong>
                </div>
                <div class="catalog-meta-copy">
                  <span>{{ inventoryCompareActive ? '公司销量' : '销量' }}</span>
                  <strong>{{ filteredSalesTotal }}</strong>
                </div>
              </div>
              </div>
            </section>
          </div>
        </CollapsePanelTransition>
      </section>
    </section>

    <section ref="goodsTableRef" class="catalog-table card-surface motion-fade-slide" style="--motion-delay: 0.16s">
      <div class="table-shell open-table-shell">
        <el-table
          class="goods-main-table"
          :data="tableItems"
          border
          stripe
          v-loading="loading"
          @sort-change="onSortChange"
        >
          <el-table-column
            prop="model"
            min-width="220"
            sortable="custom"
            fixed="left"
            class-name="aqc-fixed-left-column goods-model-fixed-column"
            label-class-name="aqc-fixed-left-column goods-model-fixed-column"
          >
            <template #header>
              <span class="goods-model-fixed-head">型号</span>
            </template>
            <template #default="{ row }">
              <span class="goods-model-fixed-cell" :title="row.model || '-'">{{ row.model || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="modelAttribute" label="属性" width="82" />
          <el-table-column v-if="inventoryCompareActive" prop="stock" label="总库存" min-width="108" sortable="custom">
            <template #default="{ row }">
              <span class="goods-stock-pill">{{ Number(row.stock || 0) }}</span>
            </template>
          </el-table-column>
          <el-table-column v-if="inventoryCompareActive" label="总金额" min-width="124">
            <template #default="{ row }">¥ {{ formatMoney(getCompareTotalAmount(row)) }}</template>
          </el-table-column>
          <el-table-column prop="price" label="价格" min-width="120" sortable="custom">
            <template #default="{ row }">¥ {{ formatMoney(row.price) }}</template>
          </el-table-column>
          <el-table-column prop="salesCount" min-width="124" sortable="custom" label-class-name="goods-sales-sortable-header">
            <template #header>
              <span class="goods-sales-title">{{ inventoryCompareActive ? '公司销量' : '销量' }}</span>
              <button type="button" class="goods-sales-range-trigger" @click.stop="openSalesRangeDialog">
                {{ salesRangeLabelShort }}
              </button>
            </template>
            <template #default="{ row }">
              <span class="goods-sales-value">{{ Number(row.salesCount || 0) }}</span>
            </template>
          </el-table-column>
          <template v-if="inventoryCompareActive">
            <el-table-column
              v-for="location in inventoryCompareSelectedLocations"
              :key="location.shopId"
              :label="location.shopShortName"
              min-width="300"
              align="center"
            >
              <el-table-column :prop="`compareQuantity_${location.shopId}`" label="库存" min-width="100" sortable="custom">
                <template #default="{ row }">
                  <span class="goods-stock-pill">{{ getCompareQuantity(row, location.shopId) }}</span>
                </template>
              </el-table-column>
              <el-table-column :prop="`compareSales_${location.shopId}`" label="销量" min-width="100" sortable="custom">
                <template #default="{ row }">
                  <span class="goods-sales-value">{{ getCompareSalesCount(row, location.shopId) }}</span>
                </template>
              </el-table-column>
            </el-table-column>
          </template>
          <template v-else>
            <el-table-column prop="stock" label="数量" min-width="100" sortable="custom">
              <template #default="{ row }">
                <span class="goods-stock-pill">{{ row.stock }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="brand" label="品牌" min-width="140" sortable="custom" />
            <el-table-column prop="series" label="系列" min-width="180" sortable="custom" show-overflow-tooltip />
            <el-table-column prop="barcode" label="条码" min-width="170" sortable="custom" show-overflow-tooltip />
            <el-table-column prop="updatedAt" label="更新时间" min-width="170" show-overflow-tooltip />
          </template>
          <el-table-column label="操作" :width="actionColumnWidth" fixed="right">
            <template #default="{ row }">
              <ResponsiveTableActions :menu-width="180">
                <el-button type="primary" text @click="openDistribution(row)">分布</el-button>
                <el-button v-if="authStore.can('goods.write')" type="primary" text @click="openEditMenu(row)">编辑</el-button>
                <el-button v-if="authStore.can('goods.manage')" type="danger" text @click="onDelete(row.id)">删除</el-button>
              </ResponsiveTableActions>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="pager-wrap">
        <el-pagination
          background
          :layout="pagerLayout"
          :total="total"
          :current-page="page"
          :page-size="pageSize"
          :page-sizes="[10, 20, 50, 100, 200]"
          @current-change="onPageChange"
          @size-change="onPageSizeChange"
        />
      </div>
    </section>

    <el-dialog
      v-model="goodsImportDialogVisible"
      title="导入历史商品表"
      width="min(760px, 96vw)"
      append-to-body
      align-center
      destroy-on-close
      class="aqc-app-dialog goods-import-dialog"
    >
      <div class="goods-import-shell">
        <p class="scan-hint goods-import-hint">
          支持旧系统商品表，至少包含 `品牌 / 系列 / 型号 / 价格 / 条码`。本次导入只新增新商品，已存在商品会自动跳过，不会覆盖原数据。
        </p>

        <input
          ref="goodsImportFileInputRef"
          class="goods-import-file-input"
          type="file"
          accept=".xlsx"
          @change="onGoodsImportFileChange"
        />

        <div class="selected-goods-card goods-import-card">
          <div class="goods-import-toolbar">
            <el-button @click="openGoodsImportPicker">选择表格</el-button>
            <el-button :disabled="!goodsImportFile" :loading="goodsImportDryRunPending" @click="runGoodsImport(true)">先校验</el-button>
            <el-button type="primary" :disabled="!goodsImportFile" :loading="goodsImportPending" @click="runGoodsImport(false)">
              校验并导入
            </el-button>
            <el-button text :disabled="!goodsImportFile" @click="clearGoodsImportFile">清空</el-button>
          </div>

          <div class="selected-goods-meta goods-import-meta">
            <span v-if="goodsImportFile">已选文件 {{ goodsImportFile.name }}</span>
            <span v-else>请选择 `.xlsx` 商品表</span>
            <span v-if="goodsImportStats.totalRows">总行数 {{ goodsImportStats.totalRows }}</span>
            <span v-if="goodsImportStats.createdCandidates">可新增 {{ goodsImportStats.createdCandidates }}</span>
            <span v-if="goodsImportStats.created">已导入 {{ goodsImportStats.created }}</span>
            <span v-if="goodsImportStats.duplicates">重复 {{ goodsImportStats.duplicates }}</span>
          </div>

          <div v-if="goodsImportResult?.message" class="sales-import-result" :class="{ error: !goodsImportResult.success }">
            <strong>{{ goodsImportResult.message }}</strong>

            <div class="sales-import-stats">
              <span v-if="goodsImportStats.rowsReady">可处理 {{ goodsImportStats.rowsReady }}</span>
              <span v-if="goodsImportStats.skipped">空行跳过 {{ goodsImportStats.skipped }}</span>
            </div>

            <div v-if="(goodsImportStats.invalidRows || []).length" class="sales-import-error-list">
              <span>无效行</span>
              <ul>
                <li v-for="item in (goodsImportStats.invalidRows || []).slice(0, 6)" :key="`invalid-${item.row}`">
                  第 {{ item.row }} 行 / {{ item.message }}
                </li>
              </ul>
            </div>

            <div v-if="goodsImportDuplicateItems.length" class="sales-import-error-list">
              <span>重复商品</span>
              <ul>
                <li v-for="item in goodsImportDuplicateItems" :key="`dup-${item.row}-${item.model || item.barcode}`">
                  第 {{ item.row }} 行 / {{ [item.brand, item.series, item.model].filter(Boolean).join(' ') || item.barcode }}
                  <template v-if="item.reason"> / {{ item.reason }}</template>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="form-actions">
          <el-button @click="goodsImportDialogVisible = false">关闭</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="inventoryImportDialogVisible"
      title="导入库存表"
      width="min(860px, 96vw)"
      append-to-body
      align-center
      destroy-on-close
      class="aqc-app-dialog goods-import-dialog"
    >
      <div class="goods-import-shell">
        <p class="scan-hint goods-import-hint">
          支持旧系统 `.xls` 库存表，会按 `商品全名 = 型号` 精确匹配现有商品，并按表内店铺/仓库数量覆盖对应库存。缺失型号与歧义型号会自动跳过并在结果中提示，允许库存导入负数。
        </p>

        <input
          ref="inventoryImportFileInputRef"
          class="goods-import-file-input"
          type="file"
          accept=".xls"
          multiple
          @change="onInventoryImportFileChange"
        />

        <div class="selected-goods-card goods-import-card">
          <div class="goods-import-toolbar">
            <el-button @click="openInventoryImportPicker">选择库存表</el-button>
            <el-button :disabled="!inventoryImportFiles.length" :loading="inventoryImportDryRunPending" @click="runInventoryImport(true)">先校验</el-button>
            <el-button type="primary" :disabled="!inventoryImportFiles.length" :loading="inventoryImportPending" @click="runInventoryImport(false)">
              校验并导入
            </el-button>
            <el-button text :disabled="!inventoryImportFiles.length" @click="clearInventoryImportFiles">清空</el-button>
          </div>

          <div class="selected-goods-meta goods-import-meta">
            <span v-if="inventoryImportFiles.length">已选 {{ inventoryImportFiles.length }} 个文件</span>
            <span v-else>请选择一个或多个 `.xls` 库存表</span>
            <span v-if="inventoryImportStats.totalRows">总行数 {{ inventoryImportStats.totalRows }}</span>
            <span v-if="inventoryImportStats.rowsReady">可更新 {{ inventoryImportStats.rowsReady }}</span>
            <span v-if="inventoryImportStats.updatedGoods">已更新 {{ inventoryImportStats.updatedGoods }}</span>
            <span v-if="inventoryImportStats.changedEntries">变更 {{ inventoryImportStats.changedEntries }}</span>
          </div>

          <div v-if="inventoryImportSelectedNames.length" class="goods-import-file-tags">
            <span v-for="name in inventoryImportSelectedNames" :key="name" class="goods-import-file-tag">{{ name }}</span>
          </div>

          <div v-if="inventoryImportResult?.message" class="sales-import-result" :class="{ error: inventoryImportHasBlockingIssue }">
            <strong>{{ inventoryImportResult.message }}</strong>

            <div class="sales-import-stats">
              <span v-if="inventoryImportStats.fileReports?.length">文件 {{ inventoryImportStats.fileReports.length }}</span>
              <span v-if="inventoryImportStats.skippedRiskGoods">风险跳过 {{ inventoryImportStats.skippedRiskGoods }}</span>
              <span v-if="inventoryImportStats.unmatchedZeroGoods?.length">零库存缺失 {{ inventoryImportStats.unmatchedZeroGoods.length }}</span>
            </div>

            <div v-if="inventoryImportFileReports.length" class="sales-import-error-list">
              <span>文件结果</span>
              <ul>
                <li v-for="item in inventoryImportFileReports" :key="`inventory-file-${item.file}`">
                  {{ item.file }} / {{ item.message }}
                </li>
              </ul>
            </div>

            <div v-if="inventoryImportUnmatchedItems.length" class="sales-import-error-list">
              <span>缺失型号</span>
              <ul>
                <li v-for="item in inventoryImportUnmatchedItems" :key="`inventory-missing-${item.file}-${item.model}`">
                  {{ item.file }} / {{ item.model }} / 合计 {{ item.totalQuantity }}
                </li>
              </ul>
            </div>

            <div v-if="inventoryImportAmbiguousItems.length" class="sales-import-error-list">
              <span>歧义型号</span>
              <ul>
                <li v-for="item in inventoryImportAmbiguousItems" :key="`inventory-ambiguous-${item.file}-${item.model}`">
                  {{ item.file }} / {{ item.model }} / 命中 {{ item.goodsIds?.length || 0 }} 条商品
                </li>
              </ul>
            </div>

            <div v-if="inventoryImportUnmatchedShops.length" class="sales-import-error-list">
              <span>未匹配店铺/仓库</span>
              <ul>
                <li v-for="item in inventoryImportUnmatchedShops" :key="`inventory-shop-${item}`">
                  {{ item }}
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="form-actions">
          <el-button @click="inventoryImportDialogVisible = false">关闭</el-button>
        </div>
      </template>
    </el-dialog>

    <ResponsiveDialog
      v-model="createFlowVisible"
      title="新增商品"
      width="min(980px, 96vw)"
      class="aqc-app-dialog goods-create-dialog"
      mobile-subtitle="商品管理"
      :initial-snap="0.64"
      :expanded-snap="0.94"
    >
      <div class="goods-create-shell" v-loading="createFlowLoading || dialogMetaLoading">
        <div class="goods-step-strip">
          <button
            v-for="step in createStepOptions"
            :key="step.value"
            type="button"
            class="goods-step-button"
            :class="{ active: createStep === step.value, completed: createStep > step.value }"
            :disabled="step.value === 2 && !createCanProceed && createStep < 2"
            @click="goToCreateStep(step.value)"
          >
            <span class="step-number">{{ step.value }}</span>
            <span>{{ step.label }}</span>
          </button>
        </div>

        <section v-show="createStep === 1" class="goods-create-panel">
          <el-form label-position="top" class="dialog-form goods-editor-form">
            <div class="goods-editor-grid">
              <el-form-item label="品牌">
                <el-select
                  v-model="form.brand"
                  filterable
                  allow-create
                  default-first-option
                  clearable
                  class="full-width"
                  placeholder="选择或输入品牌"
                  @change="onDialogBrandChange"
                >
                  <el-option
                    v-for="option in dialogMeta.brandOptions"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
              </el-form-item>

              <el-form-item label="系列">
                <el-select
                  v-model="form.series"
                  filterable
                  allow-create
                  default-first-option
                  clearable
                  class="full-width"
                  placeholder="选择或输入系列"
                >
                  <el-option
                    v-for="option in dialogMeta.seriesOptions"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
              </el-form-item>

              <el-form-item label="型号">
                <el-input v-model.trim="form.model" maxlength="191" placeholder="如：GMA-P2110SC-4A" />
              </el-form-item>

              <el-form-item label="属性">
                <el-select v-model="form.modelAttribute" class="full-width">
                  <el-option
                    v-for="option in goodsAttributeOptions"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
              </el-form-item>

              <el-form-item label="价格（元）">
                <el-input-number
                  v-model="form.price"
                  :min="0"
                  :max="999999999"
                  :step="0.01"
                  :precision="2"
                  class="full-width"
                />
              </el-form-item>

              <el-form-item label="条码" class="dialog-span-full">
                <div class="barcode-compose">
                  <el-input
                    v-model.trim="form.barcode"
                    maxlength="64"
                    placeholder="支持手动输入或扫码"
                  />
                  <el-button type="primary" plain :loading="dialogScannerPending" @click="openDialogScannerDialog">
                    {{ dialogScanning ? '识别中...' : dialogScannerPending ? '启动中...' : '摄像头扫码' }}
                  </el-button>
                </div>
              </el-form-item>

              <div class="dialog-span-full goods-preview-card">
                <span>自动名称</span>
                <strong>{{ displayName }}</strong>
                <div class="goods-preview-meta">
                  <span>条码 {{ resolvedBarcodePreview || '待输入或扫码' }}</span>
                  <span>价格 ¥ {{ formatMoney(form.price) }}</span>
                </div>
              </div>
            </div>
          </el-form>
        </section>

        <section v-show="createStep === 2" class="goods-create-panel">
          <section class="inventory-hero-card inventory-hero-card-strong">
            <span>当前合计</span>
            <strong>{{ createDraftTotal }}</strong>
            <h3>{{ createModelTitle }}</h3>
            <p>{{ createHeroSubtitle }}</p>
          </section>

          <section class="inventory-button-grid">
            <div v-for="location in createInventoryLocations" :key="location.shopId" class="inventory-button-row">
              <button
                type="button"
                class="inventory-button-minus"
                :disabled="getCreateDraftQuantity(location.shopId) <= 0"
                @click="adjustCreateQuantity(location.shopId, -1)"
              >
                -
              </button>
              <button type="button" class="inventory-button-main" @click="adjustCreateQuantity(location.shopId, 1)">
                {{ location.shopShortName }}
              </button>
              <div class="inventory-button-count">{{ getCreateDraftQuantity(location.shopId) }}</div>
            </div>
          </section>
        </section>
      </div>

      <template #footer>
        <div class="form-actions goods-step-actions">
          <el-button v-if="createStep === 2" :disabled="!createDraftDirty" @click="resetCreateDraft">重置</el-button>
          <el-button @click="createFlowVisible = false">取消</el-button>
          <el-button v-if="createStep > 1" @click="prevCreateStep">上一步</el-button>
          <el-button v-if="createStep < createStepOptions.length" type="primary" :disabled="!createCanProceed" @click="nextCreateStep">
            下一步
          </el-button>
          <el-button v-else type="primary" :loading="createSubmitting" @click="completeCreateFlow">
            完成
          </el-button>
        </div>
      </template>
    </ResponsiveDialog>

    <el-dialog
      v-model="editMenuVisible"
      width="min(560px, 92vw)"
      append-to-body
      align-center
      destroy-on-close
      class="aqc-app-dialog goods-flow-dialog"
    >
      <template #header>
        <div class="dialog-heading dialog-heading-compact">
          <h3>选择编辑菜单</h3>
          <p>{{ editMenuDisplayName }}</p>
        </div>
      </template>

      <div class="goods-flow-choice">
        <button type="button" class="goods-flow-card" @click="openPropertyEditorFromMenu">
          <strong>商品属性</strong>
          <p>继续编辑品牌、系列、型号、价格和条码。</p>
        </button>

        <button type="button" class="goods-flow-card accent" @click="openQuantityEditorFromMenu">
          <strong>商品数量</strong>
          <p>继续编辑商品的库存分布。</p>
        </button>
      </div>
    </el-dialog>

    <ResponsiveDialog
      v-model="dialogVisible"
      :title="propertyDialogTitle"
      width="min(760px, 96vw)"
      class="goods-editor-dialog aqc-app-dialog"
      mobile-subtitle="商品管理"
      :initial-snap="0.62"
      :expanded-snap="0.92"
    >
      <div class="goods-editor-shell" v-loading="detailLoading || dialogMetaLoading">
        <section class="goods-editor-hero">
          <div class="goods-editor-copy">
            <p class="panel-tag">Catalog Draft</p>
            <h3>更新商品属性</h3>
            <p>
              这里仅维护商品属性信息。商品数量已拆分到单独菜单中，避免属性编辑和库存分布互相干扰。
            </p>
          </div>

        </section>

        <el-form label-position="top" class="dialog-form goods-editor-form">
          <div class="goods-editor-grid">
            <el-form-item label="品牌">
              <el-select
                v-model="form.brand"
                filterable
                allow-create
                default-first-option
                clearable
                class="full-width"
                placeholder="选择或输入品牌"
                @change="onDialogBrandChange"
              >
                <el-option
                  v-for="option in dialogMeta.brandOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="系列">
              <el-select
                v-model="form.series"
                filterable
                allow-create
                default-first-option
                clearable
                class="full-width"
                placeholder="选择或输入系列"
              >
                <el-option
                  v-for="option in dialogMeta.seriesOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="型号">
              <el-input v-model.trim="form.model" maxlength="191" placeholder="如：GMA-P2110SC-4A" />
            </el-form-item>

            <el-form-item label="属性">
              <el-select v-model="form.modelAttribute" class="full-width">
                <el-option
                  v-for="option in goodsAttributeOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="价格（元）">
              <el-input-number
                v-model="form.price"
                :min="0"
                :max="999999999"
                :step="0.01"
                :precision="2"
                class="full-width"
              />
            </el-form-item>

            <el-form-item label="条码" class="dialog-span-full">
              <div class="barcode-compose">
                <el-input
                  v-model.trim="form.barcode"
                  maxlength="64"
                  placeholder="支持手动输入或扫码"
                />
                <el-button type="primary" plain :loading="dialogScannerPending" @click="openDialogScannerDialog">
                  {{ dialogScanning ? '识别中...' : dialogScannerPending ? '启动中...' : '摄像头扫码' }}
                </el-button>
              </div>
            </el-form-item>

            <div class="dialog-span-full goods-preview-card">
              <span>自动名称</span>
              <strong>{{ displayName }}</strong>
              <div class="goods-preview-meta">
                <span>条码 {{ resolvedBarcodePreview || '待输入或扫码' }}</span>
                <span>价格 ¥ {{ formatMoney(form.price) }}</span>
              </div>
            </div>
          </div>
        </el-form>
      </div>

      <template #footer>
        <div class="form-actions">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="onSubmit">保存</el-button>
        </div>
      </template>
    </ResponsiveDialog>

    <el-dialog
      v-model="inventoryCompareDialogVisible"
      title="对比模式"
      width="min(980px, 96vw)"
      append-to-body
      align-center
      destroy-on-close
      class="aqc-app-dialog goods-compare-dialog"
    >
      <section class="catalog-controls card-surface goods-compare-panel">
        <div class="goods-compare-toggle-row">
          <span class="sales-filter-label">开启对比模式</span>
          <el-switch v-model="inventoryCompareSettings.enabled" class="goods-compare-toggle-switch" @change="onInventoryCompareToggle" />
        </div>

        <div class="goods-compare-preset-row">
          <el-input
            v-model.trim="inventoryComparePresetName"
            clearable
            maxlength="30"
            placeholder="输入预设名称"
            class="goods-compare-preset-input"
            @keyup.enter="saveInventoryComparePreset"
          />
          <div class="toolbar-actions">
            <el-button @click="resetInventoryCompareSelectionToCurrent">重置</el-button>
            <el-button type="primary" @click="saveInventoryComparePreset">保存预设</el-button>
          </div>
        </div>

        <div v-if="inventoryCompareSettings.presets.length" class="goods-compare-presets">
          <div
            v-for="preset in inventoryCompareSettings.presets"
            :key="preset.id"
            class="goods-compare-preset-chip-wrap"
          >
            <button
              type="button"
              class="goods-compare-preset-chip"
              :class="{ active: isInventoryComparePresetActive(preset) }"
              @click="applyInventoryComparePreset(preset)"
            >
              <span>{{ preset.name }}</span>
              <small>{{ preset.locationIds.length }} 项</small>
            </button>
            <button
              type="button"
              class="goods-compare-preset-delete"
              aria-label="删除预设"
              @click.stop="deleteInventoryComparePreset(preset)"
            >
              ×
            </button>
          </div>
        </div>

        <div class="goods-compare-selection-summary">
          <span>已选 {{ inventoryCompareSettings.locationIds.length }} 个店铺 / 仓库</span>
          <strong>{{ inventoryCompareSelectionLabel }}</strong>
        </div>

        <div class="inventory-button-grid goods-compare-location-grid">
          <div
            v-for="location in inventoryCompareLocationOptions"
            :key="location.shopId"
            class="inventory-button-row goods-compare-location-row"
          >
            <button
              type="button"
              class="inventory-button-main goods-compare-location-button"
              :class="{ active: inventoryCompareSettings.locationIds.includes(location.shopId) }"
              @click="toggleInventoryCompareLocation(location.shopId)"
            >
              {{ location.shopShortName }}
              <span
                v-if="inventoryCompareSettings.locationIds.includes(location.shopId)"
                class="goods-compare-location-order"
              >
                {{ inventoryCompareSettings.locationIds.indexOf(location.shopId) + 1 }}
              </span>
            </button>
          </div>
        </div>
      </section>

      <template #footer>
        <div class="form-actions">
          <el-button @click="clearInventoryCompareSelection">清空选择</el-button>
          <el-button @click="inventoryCompareDialogVisible = false">关闭</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="salesRangeDialogVisible"
      title="销量时间范围"
      width="min(760px, 96vw)"
      append-to-body
      align-center
      destroy-on-close
      class="aqc-app-dialog goods-sales-range-dialog"
    >
      <section class="catalog-controls card-surface goods-sales-range-panel">
        <header class="sales-filter-head">
          <div class="sales-filter-head-copy">
            <h2>销量口径</h2>
            <span>{{ salesRangeLabel }}</span>
          </div>
          <div class="toolbar-actions sales-filter-head-actions">
            <el-button @click="resetSalesRange">恢复总销量</el-button>
            <el-button type="primary" @click="applySalesRange">应用</el-button>
          </div>
        </header>

        <div class="goods-compare-presets goods-sales-range-presets">
          <button
            v-for="preset in salesRangePresetOptions"
            :key="preset.value"
            type="button"
            class="goods-compare-preset-chip"
            :class="{ active: salesRangePreset === preset.value }"
            @click="applySalesRangePreset(preset.value)"
          >
            <span>{{ preset.label }}</span>
          </button>
        </div>

        <div class="sales-filter-grid goods-sales-range-grid">
          <div class="sales-filter-field sales-filter-field-wide">
            <label class="sales-filter-label">自定义时间范围</label>
            <el-date-picker
              v-model="salesDateRangeDraft"
              type="daterange"
              value-format="YYYY-MM-DD"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              class="full-width"
              unlink-panels
            />
          </div>
        </div>
      </section>
    </el-dialog>

    <MobileBottomSheet
      v-if="isMobileViewport"
      v-model="distributionDialogVisible"
      title="商品分布"
      subtitle="商品管理"
    >
      <div class="goods-distribution-shell goods-distribution-mobile-shell" v-loading="distributionLoading">
        <div class="goods-distribution-mobile-panel">
          <section class="goods-distribution-mobile-summary-bar">
            <article class="goods-distribution-mobile-summary-item">
              <span>总库存</span>
              <strong>{{ distributionTotalStock }}</strong>
            </article>
            <article class="goods-distribution-mobile-summary-item">
              <span>库存金额</span>
              <strong>¥ {{ formatMoney(distributionTotalAmount) }}</strong>
            </article>
          </section>

          <section class="goods-distribution-mobile-title">
            <strong>{{ distributionModelTitle }}</strong>
            <p>{{ distributionHeroSubtitle }}</p>
          </section>

          <div class="goods-distribution-mobile-utility">
            <el-button @click="openInventoryLogDialog(distributionItem)">库存日志</el-button>
          </div>

          <section class="goods-distribution-mobile-summary-bar">
            <article class="goods-distribution-mobile-summary-item">
              <span>有货点位</span>
              <strong>{{ distributionPositiveCount }}</strong>
            </article>
            <article class="goods-distribution-mobile-summary-item">
              <span>点位明细</span>
              <strong>{{ distributionRows.length }}</strong>
            </article>
          </section>
        </div>

        <section v-if="distributionRows.length" class="goods-distribution-mobile-list">
          <article
            v-for="row in distributionRows"
            :key="row.shopId"
            class="goods-distribution-mobile-row goods-distribution-row-actionable"
            role="button"
            tabindex="0"
            @click="openDistributionActionMenu(row)"
            @keyup.enter="openDistributionActionMenu(row)"
          >
            <div class="goods-distribution-mobile-main">
              <strong>{{ displayShopName(row.shopName || row.shopShortName) || '未命名点位' }}</strong>
              <span>
                {{ formatShopType(row.shopType) }}
                <template v-if="row.unitPrice"> · 单价 ¥ {{ formatMoney(row.unitPrice) }}</template>
              </span>
            </div>
            <div class="goods-distribution-mobile-side">
              <small>库存数量</small>
              <strong>{{ row.quantity }}</strong>
              <span>¥ {{ formatMoney(row.lineAmount) }}</span>
            </div>
          </article>
        </section>

        <div v-else class="goods-distribution-mobile-empty">
          <strong>暂无库存分布</strong>
          <p>当前商品还没有可展示的店铺或仓库库存。</p>
        </div>
      </div>
    </MobileBottomSheet>

    <el-dialog
      v-else
      v-model="distributionDialogVisible"
      title="商品分布"
      width="min(1120px, 96vw)"
      append-to-body
      align-center
      destroy-on-close
      class="aqc-app-dialog goods-distribution-dialog"
    >
      <div class="goods-distribution-shell" v-loading="distributionLoading">
        <section class="inventory-hero-card inventory-hero-card-strong">
          <span>总库存</span>
          <strong>{{ distributionTotalStock }}</strong>
          <h3>{{ distributionModelTitle }}</h3>
          <p>{{ distributionHeroSubtitle }}</p>
          <div class="toolbar-actions inventory-hero-actions">
            <el-button @click="openInventoryLogDialog(distributionItem)">库存日志</el-button>
          </div>
        </section>

        <div class="table-shell open-table-shell inventory-table-shell">
          <el-table
            :data="distributionRows"
            border
            stripe
            empty-text="暂无库存分布"
            show-summary
            :summary-method="distributionTableSummary"
            @row-click="openDistributionActionMenu"
          >
            <el-table-column label="店铺 / 仓库名称" min-width="260" show-overflow-tooltip>
              <template #default="{ row }">{{ row.shopName || row.shopShortName }}</template>
            </el-table-column>
            <el-table-column prop="quantity" label="库存数量" min-width="110" />
            <el-table-column prop="unitPrice" label="单价" min-width="120">
              <template #default="{ row }">¥ {{ formatMoney(row.unitPrice) }}</template>
            </el-table-column>
            <el-table-column prop="lineAmount" label="金额" min-width="140">
              <template #default="{ row }">¥ {{ formatMoney(row.lineAmount) }}</template>
            </el-table-column>
          </el-table>
        </div>
      </div>

      <template #footer>
        <div class="form-actions">
          <el-button @click="distributionDialogVisible = false">关闭</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="inventoryLogDialogVisible"
      title="库存日志"
      width="min(1180px, 97vw)"
      append-to-body
      align-center
      destroy-on-close
      class="aqc-app-dialog goods-inventory-log-dialog"
    >
      <div class="goods-distribution-shell inventory-log-shell" v-loading="inventoryLogLoading">
        <section class="inventory-hero-card inventory-hero-card-strong">
          <span>总库存</span>
          <strong>{{ inventoryLogCurrentTotal }}</strong>
          <h3>{{ inventoryLogModelTitle }}</h3>
          <p>按商品查看所有店铺 / 仓库的库存变更记录。</p>
          <div class="inventory-hero-meta">共 {{ inventoryLogTotal }} 条日志</div>
        </section>

        <section class="catalog-controls card-surface inventory-log-panel">
          <div class="records-toolbar catalog-toolbar inventory-log-toolbar">
            <el-input
              v-model.trim="inventoryLogKeyword"
              clearable
              placeholder="搜索型号 / 店铺 / 变更内容 / 操作人员"
              class="toolbar-search toolbar-search-wide"
              @keyup.enter="onInventoryLogSearch"
            />

            <el-date-picker
              v-model="inventoryLogDateFrom"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="开始日期"
              style="width: 160px"
            />

            <el-date-picker
              v-model="inventoryLogDateTo"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="结束日期"
              style="width: 160px"
            />

            <div class="toolbar-actions">
              <el-button :loading="inventoryLogLoading" @click="onInventoryLogSearch">查询</el-button>
              <el-button @click="resetInventoryLogFilters">重置</el-button>
            </div>
          </div>

          <div class="table-shell open-table-shell">
            <el-table :data="inventoryLogRows" border stripe empty-text="暂无库存日志">
              <el-table-column prop="goodsModel" label="商品型号" min-width="220" show-overflow-tooltip />
              <el-table-column label="店铺 / 仓库" min-width="180" show-overflow-tooltip>
                <template #default="{ row }">{{ displayShopName(row.shopName) || '-' }}</template>
              </el-table-column>
              <el-table-column prop="changeContent" label="变更内容" min-width="220" show-overflow-tooltip />
              <el-table-column prop="quantityBefore" label="变更前" min-width="100" />
              <el-table-column prop="quantityAfter" label="变更后" min-width="100" />
              <el-table-column prop="totalQuantityAfter" label="商品总数" min-width="110" />
              <el-table-column prop="createdAt" label="变更时间" min-width="180" show-overflow-tooltip />
              <el-table-column prop="operatorName" label="操作人员" min-width="140" show-overflow-tooltip />
            </el-table>
          </div>

          <div class="pager-wrap">
            <el-pagination
              background
              layout="total, prev, pager, next, sizes"
              :total="inventoryLogTotal"
              :current-page="inventoryLogPage"
              :page-size="inventoryLogPageSize"
              :page-sizes="[20, 50, 100, 200]"
              @current-change="onInventoryLogPageChange"
              @size-change="onInventoryLogPageSizeChange"
            />
          </div>
        </section>
      </div>

      <template #footer>
        <div class="form-actions">
          <el-button @click="inventoryLogDialogVisible = false">关闭</el-button>
        </div>
      </template>
    </el-dialog>

    <ResponsiveDialog
      v-model="distributionActionMenuVisible"
      :title="distributionActionTitle"
      width="min(360px, 92vw)"
      :z-index="8620"
      :mobile-base-z-index="8620"
      class="aqc-app-dialog goods-distribution-action-dialog"
      mobile-subtitle="商品分布"
    >
      <section class="work-order-category-chooser goods-distribution-action-chooser">
        <button type="button" class="work-order-category-card goods-distribution-action-card" @click="createTransferFromDistribution">
          <strong>创建商品调拨单</strong>
          <small>{{ distributionActionSubtitle }}</small>
        </button>
        <button type="button" class="work-order-category-card goods-distribution-action-card" @click="viewDistributionInventoryLogs">
          <strong>查看日志</strong>
          <small>{{ distributionActionSubtitle }}</small>
        </button>
      </section>
    </ResponsiveDialog>

    <ResponsiveDialog
      v-model="quantityDialogVisible"
      title="商品数量"
      width="min(980px, 96vw)"
      class="aqc-app-dialog goods-quantity-dialog"
      mobile-subtitle="商品管理"
      :initial-snap="0.64"
      :expanded-snap="0.94"
    >
      <div class="goods-distribution-shell goods-quantity-shell" v-loading="quantityLoading">
        <section class="inventory-hero-card inventory-hero-card-strong">
          <span>当前合计</span>
          <strong>{{ quantityDraftTotal }}</strong>
          <h3>{{ quantityModelTitle }}</h3>
          <p>{{ quantityHeroSubtitle }}</p>
        </section>

        <section class="inventory-button-grid">
          <div v-for="location in quantityInventories" :key="location.shopId" class="inventory-button-row">
            <button
              type="button"
              class="inventory-button-minus"
              @click="adjustQuantity(location.shopId, -1)"
            >
              -
            </button>
            <button type="button" class="inventory-button-main" @click="adjustQuantity(location.shopId, 1)">
              {{ location.shopShortName }}
            </button>
            <div class="inventory-button-count">{{ getDraftQuantity(location.shopId) }}</div>
          </div>
        </section>
      </div>

      <template #footer>
        <div class="form-actions">
          <el-button :disabled="!quantityDirty" @click="resetQuantityDraft">重置</el-button>
          <el-button @click="quantityDialogVisible = false">关闭</el-button>
          <el-button type="primary" :loading="quantitySubmitting" :disabled="!quantityDirty" @click="saveQuantityDraft">
            保存数量
          </el-button>
        </div>
      </template>
    </ResponsiveDialog>

    <el-dialog
      v-model="catalogScannerDialogVisible"
      title="扫码定位商品"
      width="min(520px, 94vw)"
      destroy-on-close
      append-to-body
      class="scanner-modal aqc-app-dialog"
      @closed="closeCatalogScannerDialog"
    >
      <div class="scanner-modal-body">
        <div
          class="scanner-stage scanner-modal-stage"
          :class="{ interactive: catalogScannerManualFocusSupported }"
          @click="onCatalogScannerStageFocus"
        >
          <video ref="catalogVideoRef" autoplay playsinline muted />
          <div class="scanner-reticle scanner-reticle-barcode" aria-hidden="true"></div>
          <span v-if="catalogScannerManualFocusSupported" class="scanner-focus-badge">点按画面手动对焦</span>
        </div>
        <p class="scan-hint scanner-modal-hint">{{ catalogScannerHint }}</p>
        <div class="scanner-result-card" :class="{ empty: !catalogScannerResultName && !catalogScannedCode }">
          <span>扫码结果</span>
          <strong>{{ catalogScannerResultName || catalogScannedCode || '等待识别条码' }}</strong>
          <p>识别成功后会自动收束到当前商品目录结果中。</p>
        </div>
      </div>

      <template #footer>
        <div class="form-actions">
          <el-button v-if="catalogScannerResultName || catalogScannedCode" type="primary" @click="closeCatalogScannerDialog">确定</el-button>
          <el-button v-else @click="closeCatalogScannerDialog">关闭</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="dialogScannerDialogVisible"
      title="扫码填写条码"
      width="min(520px, 94vw)"
      destroy-on-close
      append-to-body
      class="scanner-modal aqc-app-dialog"
      @closed="closeDialogScannerDialog"
    >
      <div class="scanner-modal-body">
        <div
          class="scanner-stage scanner-modal-stage goods-dialog-scanner"
          :class="{ interactive: dialogScannerManualFocusSupported }"
          @click="onDialogScannerStageFocus"
        >
          <video ref="dialogVideoRef" autoplay playsinline muted />
          <div class="scanner-reticle scanner-reticle-barcode" aria-hidden="true"></div>
          <span v-if="dialogScannerManualFocusSupported" class="scanner-focus-badge">点按画面手动对焦</span>
        </div>
        <p class="scan-hint scanner-modal-hint">{{ dialogScannerHint }}</p>
        <div class="scanner-result-card" :class="{ empty: !dialogScannerResultText }">
          <span>扫码结果</span>
          <strong>{{ dialogScannerResultText || '等待识别条码' }}</strong>
          <p>识别成功后会自动回填到当前商品条码字段。</p>
        </div>
      </div>

      <template #footer>
        <div class="form-actions">
          <el-button v-if="dialogScannerResultText" type="primary" @click="closeDialogScannerDialog">确定</el-button>
          <el-button v-else @click="closeDialogScannerDialog">关闭</el-button>
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
import MobileBottomSheet from '../components/MobileBottomSheet.vue'
import ResponsiveDialog from '../components/ResponsiveDialog.vue'
import ResponsiveTableActions from '../components/ResponsiveTableActions.vue'
import { useMobileViewport } from '../composables/useMobileViewport'
import { useBarcodeScanner } from '../composables/useBarcodeScanner'
import { apiDelete, apiGet, apiPost, apiPut, apiUpload } from '../services/api'
import { useAuthStore } from '../stores/auth'
import { confirmDestructiveAction } from '../utils/confirm'
import { buildLogCenterQuery } from '../utils/logCenter'
import { getShanghaiParts } from '../utils/shanghaiTime'
import { resolveTableActionWidth } from '../utils/tableActions'
import { displayShopName, normalizeLocationRow, sortLocationsById, SHOP_TYPE_OTHER_WAREHOUSE, SHOP_TYPE_STORE, SHOP_TYPE_WAREHOUSE } from '../utils/shops'

const INVENTORY_COMPARE_STORAGE_KEY = 'aqc_goods_inventory_compare'

const authStore = useAuthStore()
const { isMobileViewport } = useMobileViewport()
const route = useRoute()
const router = useRouter()

const loading = ref(false)
const metaLoading = ref(false)
const dialogMetaLoading = ref(false)
const submitting = ref(false)
const createFlowVisible = ref(false)
const createFlowLoading = ref(false)
const createSubmitting = ref(false)
const goodsImportDialogVisible = ref(false)
const goodsImportFileInputRef = ref(null)
const goodsImportFile = ref(null)
const goodsImportPending = ref(false)
const goodsImportDryRunPending = ref(false)
const goodsImportResult = ref(null)
const inventoryImportDialogVisible = ref(false)
const inventoryImportFileInputRef = ref(null)
const inventoryImportFiles = ref([])
const inventoryImportPending = ref(false)
const inventoryImportDryRunPending = ref(false)
const inventoryImportResult = ref(null)
const inventoryCompareDialogVisible = ref(false)
const salesRangeDialogVisible = ref(false)
const createStep = ref(1)
const createInventoryLocations = ref([])
const createDraftMap = ref({})
const createInitialMap = ref({})
const inventoryCompareLocationOptions = ref([])
const inventoryComparePresetName = ref('')
const inventoryCompareSettings = ref({
  enabled: false,
  locationIds: [],
  presets: [],
})
const salesRangePreset = ref('all')
const salesDateRange = ref([])
const salesDateRangeDraft = ref([])
const filterPanelOpen = ref(false)
const barcodeLookupLoading = ref(false)
const total = ref(0)
const filteredStockTotal = ref(0)
const filteredSalesTotal = ref(0)
const page = ref(1)
const pageSize = ref(20)
const pagerLayout = computed(() => (isMobileViewport.value ? 'prev, pager, next' : 'total, prev, pager, next, sizes'))
const keyword = ref('')
const brandFilter = ref('')
const seriesFilter = ref('')
const modelFilter = ref('')
const attributeFilter = ref('')
const barcodeFilter = ref('')
const hasStockFilter = ref('')
const indexFilter = ref('')
const priceMin = ref(undefined)
const priceMax = ref(undefined)
const sortField = ref('updated_at')
const sortOrder = ref('desc')

const items = ref([])
const dialogVisible = ref(false)
const editingId = ref(0)
const detailLoading = ref(false)
const editMenuVisible = ref(false)
const editMenuTarget = ref(null)
const distributionDialogVisible = ref(false)
const distributionLoading = ref(false)
const distributionItem = ref(null)
const distributionInventories = ref([])
const distributionTotalStock = ref(0)
const distributionActionMenuVisible = ref(false)
const distributionActionRow = ref(null)
const inventoryLogDialogVisible = ref(false)
const inventoryLogLoading = ref(false)
const inventoryLogTarget = ref(null)
const inventoryLogRows = ref([])
const inventoryLogTotal = ref(0)
const inventoryLogCurrentTotal = ref(0)
const inventoryLogPage = ref(1)
const inventoryLogPageSize = ref(20)
const inventoryLogKeyword = ref('')
const inventoryLogDateFrom = ref('')
const inventoryLogDateTo = ref('')
const quantityDialogVisible = ref(false)
const quantityLoading = ref(false)
const quantitySubmitting = ref(false)
const quantityItem = ref(null)
const quantityInventories = ref([])
const quantityDraftMap = ref({})
const quantityInitialMap = ref({})
const actionColumnWidth = computed(() => resolveTableActionWidth([[
  '分布',
  authStore.can('goods.write') ? '编辑' : '',
  authStore.can('goods.manage') ? '删除' : '',
]], {
  compact: isMobileViewport.value,
  minWidth: 112,
  maxWidth: 260,
}))
const goodsTableRef = ref(null)
const goodsImportStats = computed(() => goodsImportResult.value?.stats || {})
const goodsImportDuplicateItems = computed(() => (goodsImportStats.value.duplicateItems || []).slice(0, 6))
const inventoryImportStats = computed(() => inventoryImportResult.value?.stats || {})
const inventoryImportFileReports = computed(() => inventoryImportStats.value.fileReports || [])
const inventoryImportUnmatchedItems = computed(() => (inventoryImportStats.value.unmatchedGoods || []).slice(0, 20))
const inventoryImportAmbiguousItems = computed(() => (inventoryImportStats.value.ambiguousGoods || []).slice(0, 20))
const inventoryImportUnmatchedShops = computed(() => inventoryImportStats.value.unmatchedShops || [])
const inventoryImportSelectedNames = computed(() => inventoryImportFiles.value.map((item) => item.name))
const inventoryImportHasBlockingIssue = computed(() => Boolean(inventoryImportUnmatchedShops.value.length))

const catalogScannerDialogVisible = ref(false)
const catalogScannedCode = ref('')
const catalogScannerResultName = ref('')
const dialogScannerDialogVisible = ref(false)
const dialogScannerResultText = ref('')

const meta = reactive({
  totalItems: 0,
  brandCount: 0,
  seriesCount: 0,
  priceMin: 0,
  priceMax: 0,
  brandOptions: [],
  seriesOptions: [],
  attributeOptions: [],
  indexOptions: [],
})

const dialogMeta = reactive({
  brandOptions: [],
  seriesOptions: [],
})

const form = reactive({
  brand: '',
  series: '',
  model: '',
  modelAttribute: '-',
  barcode: '',
  price: 0,
})

const goodsAttributeOptions = [
  { value: '-', label: '-' },
  { value: '保', label: '保' },
  { value: '畅', label: '畅' },
]

function createEmptyInventoryCompareSettings() {
  return {
    enabled: false,
    locationIds: [],
    presets: [],
  }
}

const createStepOptions = [
  { value: 1, label: '商品属性' },
  { value: 2, label: '商品数量' },
]

const {
  videoRef: catalogVideoRef,
  scanning: catalogScanning,
  scannerPending: catalogScannerPending,
  scannerHint: catalogScannerHint,
  scannerManualFocusSupported: catalogScannerManualFocusSupported,
  startScanner: startCatalogScanner,
  stopScanner: stopCatalogScanner,
  focusScannerAt: focusCatalogScannerAt,
} = useBarcodeScanner({
  onDetected: async (code) => {
    catalogScannedCode.value = code
    barcodeFilter.value = code
    await lookupCatalogBarcode()
    await stopCatalogScanner()
  },
})

const {
  videoRef: dialogVideoRef,
  scanning: dialogScanning,
  scannerPending: dialogScannerPending,
  scannerHint: dialogScannerHint,
  scannerManualFocusSupported: dialogScannerManualFocusSupported,
  startScanner: startDialogScanner,
  stopScanner: stopDialogScanner,
  focusScannerAt: focusDialogScannerAt,
} = useBarcodeScanner({
  onDetected: async (code) => {
    form.barcode = code
    dialogScannerResultText.value = code
    ElMessage.success('条码已回填')
    await stopDialogScanner()
  },
})

async function onCatalogScannerStageFocus(event) {
  await focusCatalogScannerAt(event)
}

async function onDialogScannerStageFocus(event) {
  await focusDialogScannerAt(event)
}

const displayName = computed(() => buildItemName(form))
const propertyDialogTitle = computed(() => '商品属性')
const resolvedBarcodePreview = computed(() => cleanText(form.barcode))
const salesRangePresetOptions = [
  { value: 'all', label: '总销量' },
  { value: 'yesterday', label: '昨日' },
  { value: 'today', label: '今日' },
  { value: 'last_week', label: '上周' },
  { value: 'this_week', label: '本周' },
  { value: 'last_month', label: '上月' },
  { value: 'this_month', label: '本月' },
  { value: 'last_year', label: '去年' },
  { value: 'this_year', label: '本年' },
]
const currentSortLabel = computed(() => {
  const labelMap = {
    updated_at: '更新时间',
    brand: '品牌',
    series: '系列',
    model: '型号',
    price: '价格',
    sales_count: '销量',
    barcode: '条码',
    stock: '数量',
  }
  if (sortField.value.startsWith('compareQuantity_')) {
    const shopId = Number(sortField.value.split('_').pop() || 0)
    const location = inventoryCompareLocationOptions.value.find((item) => Number(item.shopId) === shopId)
    return `${location?.shopShortName || '点位'} 库存 ${sortOrder.value === 'asc' ? '正序' : '倒序'}`
  }
  if (sortField.value.startsWith('compareSales_')) {
    const shopId = Number(sortField.value.split('_').pop() || 0)
    const location = inventoryCompareLocationOptions.value.find((item) => Number(item.shopId) === shopId)
    return `${location?.shopShortName || '点位'} 销量 ${sortOrder.value === 'asc' ? '正序' : '倒序'}`
  }
  const base = labelMap[sortField.value] || '更新时间'
  return base + ' ' + (sortOrder.value === 'asc' ? '正序' : '倒序')
})
const salesRangeLabel = computed(() => {
  if (salesRangePreset.value) {
    return salesRangePresetOptions.find((item) => item.value === salesRangePreset.value)?.label || '预设范围'
  }
  if (Array.isArray(salesDateRange.value) && salesDateRange.value[0] && salesDateRange.value[1]) {
    return `${salesDateRange.value[0]} 至 ${salesDateRange.value[1]}`
  }
  return '总销量'
})
const salesRangeLabelShort = computed(() => salesRangeLabel.value)
const activeFilterEntries = computed(() => ([
  ['关键词', keyword.value],
  ['品牌', brandFilter.value],
  ['系列', seriesFilter.value],
  ['型号', modelFilter.value],
  ['属性', attributeFilter.value],
  ['条码', barcodeFilter.value],
  ['库存', hasStockFilter.value],
  ['索引', indexFilter.value],
  ['最低价', priceMin.value],
  ['最高价', priceMax.value],
]).filter(([, value]) => String(value ?? '').trim()))
const activeFilterCount = computed(() => activeFilterEntries.value.length)
const editMenuDisplayName = computed(() => buildItemName(editMenuTarget.value) || '当前商品')
const distributionModelTitle = computed(() => cleanText(distributionItem.value?.model) || '未设置型号')
const inventoryLogModelTitle = computed(() => buildItemName(inventoryLogTarget.value) || '当前商品')
const distributionPositiveCount = computed(() => distributionInventories.value.filter((item) => Number(item.quantity || 0) > 0).length)
const distributionHeroSubtitle = computed(() => buildInventorySubtitle(distributionItem.value, distributionPositiveCount.value))
const distributionActionTitle = computed(() => (
  displayShopName(distributionActionRow.value?.shopName || distributionActionRow.value?.shopShortName) || '快捷操作'
))
const distributionActionSubtitle = computed(() => {
  const goodsLabel = buildItemName(distributionItem.value)
  const sourceLabel = displayShopName(distributionActionRow.value?.shopName || distributionActionRow.value?.shopShortName) || '当前点位'
  const targetLabel = displayShopName(authStore.user?.shopName || '') || '人员默认店铺'
  if (!authStore.shopId) {
    return `已带入 ${goodsLabel} 与 ${sourceLabel}，调入点位可在工单中补选`
  }
  if (Number(authStore.shopId || 0) === Number(distributionActionRow.value?.shopId || 0)) {
    return `已带入 ${goodsLabel} 与 ${sourceLabel}，当前默认店铺与调出点位相同`
  }
  return `已带入 ${goodsLabel}，默认从 ${sourceLabel} 调往 ${targetLabel}`
})
const distributionRows = computed(() => {
  const unitPrice = Number(distributionItem.value?.price || 0)
  return [...distributionInventories.value].sort((left, right) => {
    const quantityGap = Number(right.quantity || 0) - Number(left.quantity || 0)
    if (quantityGap !== 0) {
      return quantityGap
    }
    return String(left.shopName || '').localeCompare(String(right.shopName || ''), 'zh-CN')
  }).map((item) => ({
    ...item,
    unitPrice,
    lineAmount: unitPrice * Number(item.quantity || 0),
  }))
})
const distributionTotalAmount = computed(() => (
  distributionRows.value.reduce((sum, item) => sum + Number(item.lineAmount || 0), 0)
))
const inventoryCompareSelectedLocations = computed(() => (
  inventoryCompareSettings.value.locationIds
    .map((shopId) => inventoryCompareLocationOptions.value.find((item) => Number(item.shopId) === Number(shopId)))
    .filter(Boolean)
))
const inventoryCompareActive = computed(() => (
  Boolean(inventoryCompareSettings.value.enabled) && inventoryCompareSelectedLocations.value.length > 0
))
const inventoryCompareSelectionLabel = computed(() => {
  if (!inventoryCompareSettings.value.locationIds.length) {
    return '尚未选择对比点位'
  }
  return inventoryCompareSettings.value.locationIds
    .map((shopId) => inventoryCompareLocationOptions.value.find((item) => Number(item.shopId) === Number(shopId))?.shopShortName || '')
    .filter(Boolean)
    .join(' / ')
})
const tableItems = computed(() => {
  if (!sortField.value.startsWith('compareQuantity_') && !sortField.value.startsWith('compareSales_')) {
    return items.value
  }
  const metric = sortField.value.startsWith('compareQuantity_') ? 'quantity' : 'sales'
  const shopId = Number(sortField.value.split('_').pop() || 0)
  const direction = sortOrder.value === 'asc' ? 1 : -1
  return [...items.value].sort((left, right) => {
    const leftValue = metric === 'quantity' ? getCompareQuantity(left, shopId) : getCompareSalesCount(left, shopId)
    const rightValue = metric === 'quantity' ? getCompareQuantity(right, shopId) : getCompareSalesCount(right, shopId)
    if (leftValue !== rightValue) {
      return (leftValue - rightValue) * direction
    }
    return String(left?.model || '').localeCompare(String(right?.model || ''), 'zh-CN') * direction
  })
})
const quantityModelTitle = computed(() => cleanText(quantityItem.value?.model) || '未设置型号')
const quantityPositiveCount = computed(() => quantityInventories.value.filter((item) => getDraftQuantity(item.shopId) > 0).length)
const quantityHeroSubtitle = computed(() => buildInventorySubtitle(quantityItem.value, quantityPositiveCount.value))
const quantityDraftTotal = computed(() => quantityInventories.value.reduce((sum, item) => sum + getDraftQuantity(item.shopId), 0))
const quantityDirty = computed(() => quantityInventories.value.some((item) => getDraftQuantity(item.shopId) !== Number(quantityInitialMap.value[item.shopId] || 0)))
const createModelTitle = computed(() => cleanText(form.model) || '未设置型号')
const createPositiveCount = computed(() => createInventoryLocations.value.filter((item) => getCreateDraftQuantity(item.shopId) > 0).length)
const createHeroSubtitle = computed(() => buildInventorySubtitle(form, createPositiveCount.value))
const createDraftTotal = computed(() => createInventoryLocations.value.reduce((sum, item) => sum + getCreateDraftQuantity(item.shopId), 0))
const createDraftDirty = computed(() => createInventoryLocations.value.some((item) => getCreateDraftQuantity(item.shopId) !== Number(createInitialMap.value[item.shopId] || 0)))
const createCanProceed = computed(() => isPropertyFormValid())
const priceFormatter = new Intl.NumberFormat('zh-CN', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

let goodsAbortController = null
let metaAbortController = null
let dialogMetaAbortController = null
let goodsFetchSeq = 0
let metaFetchSeq = 0
let dialogMetaFetchSeq = 0
let isUnmounted = false

function formatMoney(value) {
  return priceFormatter.format(Number(value || 0))
}

function cleanText(value) {
  return String(value || '').trim()
}

function getShanghaiDateString(date = new Date()) {
  const parts = getShanghaiParts(date)
  return `${parts.year}-${parts.month}-${parts.day}`
}

function getShanghaiDateAtMidnight(dateString) {
  return new Date(`${dateString}T00:00:00+08:00`)
}

function shiftDays(dateString, days) {
  const base = getShanghaiDateAtMidnight(dateString)
  base.setUTCDate(base.getUTCDate() + Number(days || 0))
  return getShanghaiDateString(base)
}

function startOfMonth(dateString) {
  const base = getShanghaiDateAtMidnight(dateString)
  base.setUTCDate(1)
  return getShanghaiDateString(base)
}

function endOfMonth(dateString) {
  const base = getShanghaiDateAtMidnight(startOfMonth(dateString))
  base.setUTCMonth(base.getUTCMonth() + 1)
  base.setUTCDate(0)
  return getShanghaiDateString(base)
}

function startOfYear(dateString) {
  return `${String(dateString || '').slice(0, 4)}-01-01`
}

function endOfYear(dateString) {
  return `${String(dateString || '').slice(0, 4)}-12-31`
}

function startOfWeek(dateString) {
  const base = getShanghaiDateAtMidnight(dateString)
  const weekDay = base.getUTCDay() || 7
  base.setUTCDate(base.getUTCDate() - weekDay + 1)
  return getShanghaiDateString(base)
}

function resolveSalesRangeFromPreset(preset) {
  if (preset === 'all') {
    return []
  }
  const today = getShanghaiDateString()
  if (preset === 'yesterday') {
    const target = shiftDays(today, -1)
    return [target, target]
  }
  if (preset === 'today') {
    return [today, today]
  }
  if (preset === 'this_week') {
    return [startOfWeek(today), shiftDays(startOfWeek(today), 6)]
  }
  if (preset === 'last_week') {
    const thisWeekStart = startOfWeek(today)
    const lastWeekEnd = shiftDays(thisWeekStart, -1)
    return [startOfWeek(lastWeekEnd), lastWeekEnd]
  }
  if (preset === 'this_month') {
    return [startOfMonth(today), endOfMonth(today)]
  }
  if (preset === 'last_month') {
    const lastMonthDate = shiftDays(startOfMonth(today), -1)
    return [startOfMonth(lastMonthDate), endOfMonth(lastMonthDate)]
  }
  if (preset === 'this_year') {
    return [startOfYear(today), endOfYear(today)]
  }
  if (preset === 'last_year') {
    const year = Number(String(today || '').slice(0, 4)) - 1
    return [`${year}-01-01`, `${year}-12-31`]
  }
  return ['', '']
}

function buildItemName(item) {
  return [cleanText(item?.brand), cleanText(item?.series), cleanText(item?.model)].filter(Boolean).join(' ') || '未命名商品'
}

function buildBrandSeriesText(item) {
  return [cleanText(item?.brand), cleanText(item?.series)].filter(Boolean).join(' / ') || '未设置品牌 / 系列'
}

function buildInventorySubtitle(item, positiveCount) {
  return buildBrandSeriesText(item) + ' · 有货点位 ' + String(positiveCount)
}

function normalizeInventoryComparePreset(rawPreset) {
  const presetId = String(rawPreset?.id || Date.now())
  const name = cleanText(rawPreset?.name) || '未命名预设'
  const locationIds = Array.from(new Set(
    (Array.isArray(rawPreset?.locationIds) ? rawPreset.locationIds : [])
      .map((item) => Number(item))
      .filter((item) => item > 0),
  ))
  return {
    id: presetId,
    name,
    locationIds,
  }
}

function normalizeInventoryCompareSettings(rawValue) {
  const source = rawValue && typeof rawValue === 'object' ? rawValue : {}
  return {
    enabled: Boolean(source.enabled),
    locationIds: Array.from(new Set(
      (Array.isArray(source.locationIds) ? source.locationIds : [])
        .map((item) => Number(item))
        .filter((item) => item > 0),
    )),
    presets: (Array.isArray(source.presets) ? source.presets : [])
      .map((item) => normalizeInventoryComparePreset(item))
      .filter((item) => item.locationIds.length > 0),
  }
}

function readInventoryCompareSettings() {
  if (typeof window === 'undefined' || typeof window.localStorage === 'undefined') {
    return createEmptyInventoryCompareSettings()
  }
  try {
    const raw = window.localStorage.getItem(INVENTORY_COMPARE_STORAGE_KEY)
    if (!raw) {
      return createEmptyInventoryCompareSettings()
    }
    return normalizeInventoryCompareSettings(JSON.parse(raw))
  } catch (error) {
    return createEmptyInventoryCompareSettings()
  }
}

function persistInventoryCompareSettings(settings) {
  const normalized = normalizeInventoryCompareSettings(settings)
  inventoryCompareSettings.value = normalized
  if (typeof window !== 'undefined' && typeof window.localStorage !== 'undefined') {
    window.localStorage.setItem(INVENTORY_COMPARE_STORAGE_KEY, JSON.stringify(normalized))
  }
}

function getCompareQuantity(row, shopId) {
  return Number(row?.compareQuantities?.[String(shopId)] || 0)
}

function getCompareSalesCount(row, shopId) {
  return Number(row?.compareSalesCounts?.[String(shopId)] || 0)
}

function getCompareTotalAmount(row) {
  return Number(row?.stock || 0) * Number(row?.price || 0)
}

function formatShopType(shopType) {
  return Number(shopType || 0) === SHOP_TYPE_WAREHOUSE ? '仓库' : '店铺'
}

function computeEan13CheckDigit(base12) {
  const digits = String(base12 || '').replace(/\D/g, '')
  if (digits.length !== 12) {
    return ''
  }

  let sum = 0
  for (let index = 0; index < digits.length; index += 1) {
    const num = Number(digits[index] || 0)
    sum += index % 2 === 0 ? num : num * 3
  }
  return String((10 - (sum % 10)) % 10)
}

function distributionTableSummary({ columns, data }) {
  const totalQuantity = data.reduce((sum, item) => sum + Number(item.quantity || 0), 0)
  const totalAmount = data.reduce((sum, item) => sum + Number(item.lineAmount || 0), 0)
  return columns.map((column, index) => {
    if (index === 0) {
      return '合计'
    }
    if (column.property === 'quantity') {
      return String(totalQuantity)
    }
    if (column.property === 'lineAmount') {
      return `¥ ${formatMoney(totalAmount)}`
    }
    return ''
  })
}

function isPropertyFormValid() {
  if (!cleanText(form.brand) || !cleanText(form.series) || !cleanText(form.model)) {
    return false
  }
  return Number(form.price || 0) > 0
}

function buildQuery() {
  const localCompareSort = sortField.value.startsWith('compareQuantity_') || sortField.value.startsWith('compareSales_')
  const backendSortField = localCompareSort ? 'updated_at' : sortField.value
  const backendSortOrder = localCompareSort ? 'desc' : sortOrder.value
  return {
    page: String(page.value),
    page_size: String(pageSize.value),
    catalog_only: 'true',
    sort_field: backendSortField,
    sort_order: backendSortOrder,
    ...(keyword.value ? { q: keyword.value } : {}),
    ...(brandFilter.value ? { brand: brandFilter.value } : {}),
    ...(seriesFilter.value ? { series: seriesFilter.value } : {}),
    ...(modelFilter.value ? { model: modelFilter.value } : {}),
    ...(attributeFilter.value ? { model_attribute: attributeFilter.value } : {}),
    ...(barcodeFilter.value ? { barcode: barcodeFilter.value } : {}),
    ...(hasStockFilter.value ? { has_stock: hasStockFilter.value } : {}),
    ...(indexFilter.value ? { index_key: indexFilter.value } : {}),
    ...(priceMin.value !== undefined && priceMin.value !== null && priceMin.value !== '' ? { price_min: String(priceMin.value) } : {}),
    ...(priceMax.value !== undefined && priceMax.value !== null && priceMax.value !== '' ? { price_max: String(priceMax.value) } : {}),
    ...(Array.isArray(salesDateRange.value) && salesDateRange.value[0] ? { sales_date_start: salesDateRange.value[0] } : {}),
    ...(Array.isArray(salesDateRange.value) && salesDateRange.value[1] ? { sales_date_end: salesDateRange.value[1] } : {}),
    ...(inventoryCompareActive.value ? { compare_shop_ids: inventoryCompareSettings.value.locationIds.join(',') } : {}),
  }
}

function buildMetaQuery() {
  const query = buildQuery()
  delete query.page
  delete query.page_size
  delete query.sort_field
  delete query.sort_order
  return query
}

function resetForm() {
  form.brand = ''
  form.series = ''
  form.model = ''
  form.modelAttribute = '-'
  form.barcode = ''
  form.price = 0
}

function resetCreateFlowState() {
  createStep.value = 1
  createInventoryLocations.value = []
  createDraftMap.value = {}
  createInitialMap.value = {}
}

function openSalesRangeDialog() {
  salesDateRangeDraft.value = Array.isArray(salesDateRange.value) ? [...salesDateRange.value] : []
  salesRangeDialogVisible.value = true
}

function applySalesRangePreset(preset) {
  salesRangePreset.value = preset
  salesDateRangeDraft.value = resolveSalesRangeFromPreset(preset)
}

async function applySalesRange() {
  const nextRange = Array.isArray(salesDateRangeDraft.value) ? [...salesDateRangeDraft.value] : []
  if (nextRange[0] && nextRange[1] && nextRange[0] > nextRange[1]) {
    ElMessage.warning('开始日期不能晚于结束日期')
    return
  }
  if ((nextRange[0] && !nextRange[1]) || (!nextRange[0] && nextRange[1])) {
    ElMessage.warning('请选择完整的开始和结束日期')
    return
  }
  if (!nextRange[0] && !nextRange[1]) {
    salesRangePreset.value = 'all'
  } else if (!salesRangePreset.value || JSON.stringify(resolveSalesRangeFromPreset(salesRangePreset.value)) !== JSON.stringify(nextRange)) {
    salesRangePreset.value = ''
  }
  salesDateRange.value = salesRangePreset.value === 'all' ? [] : nextRange
  salesRangeDialogVisible.value = false
  page.value = 1
  await loadGoods()
}

async function resetSalesRange() {
  salesRangePreset.value = 'all'
  salesDateRange.value = []
  salesDateRangeDraft.value = []
  salesRangeDialogVisible.value = false
  page.value = 1
  await loadGoods()
}

function onImportMenuCommand(command) {
  if (command === 'inventory') {
    inventoryImportDialogVisible.value = true
    return
  }
  openGoodsImportDialog()
}

function openGoodsImportDialog() {
  goodsImportDialogVisible.value = true
}

function openGoodsImportPicker() {
  goodsImportFileInputRef.value?.click()
}

function onGoodsImportFileChange(event) {
  const nextFile = event?.target?.files?.[0] || null
  if (event?.target) {
    event.target.value = ''
  }
  if (!nextFile) {
    return
  }
  if (!String(nextFile.name || '').toLowerCase().endsWith('.xlsx')) {
    goodsImportFile.value = null
    goodsImportResult.value = null
    ElMessage.error('仅支持导入 .xlsx 商品表')
    return
  }
  goodsImportFile.value = nextFile
  goodsImportResult.value = null
  ElMessage.success('已选择商品表：' + nextFile.name)
}

function clearGoodsImportFile() {
  goodsImportFile.value = null
  goodsImportResult.value = null
  if (goodsImportFileInputRef.value) {
    goodsImportFileInputRef.value.value = ''
  }
}

async function runGoodsImport(dryRun = false) {
  if (!goodsImportFile.value) {
    ElMessage.warning('请先选择需要导入的商品表')
    return
  }

  if (dryRun) {
    goodsImportDryRunPending.value = true
  } else {
    goodsImportPending.value = true
  }

  const payload = await apiUpload('/goods/template-import', goodsImportFile.value, {
    token: authStore.token,
    query: {
      dry_run: dryRun ? 'true' : 'false',
    },
    timeoutMs: 60000,
  })

  if (dryRun) {
    goodsImportDryRunPending.value = false
  } else {
    goodsImportPending.value = false
  }

  goodsImportResult.value = payload || { success: false, message: dryRun ? '校验失败' : '导入失败', stats: {} }

  if (!goodsImportResult.value.success) {
    ElMessage.error(goodsImportResult.value.message || (dryRun ? '校验失败' : '导入失败'))
    return
  }

  ElMessage.success(goodsImportResult.value.message || (dryRun ? '校验完成' : '导入成功'))
  if (!dryRun) {
    await reloadAll()
  }
}

function openInventoryImportPicker() {
  inventoryImportFileInputRef.value?.click()
}

function onInventoryImportFileChange(event) {
  const nextFiles = Array.from(event?.target?.files || [])
  if (event?.target) {
    event.target.value = ''
  }
  if (!nextFiles.length) {
    return
  }
  const invalidFile = nextFiles.find((item) => !String(item.name || '').toLowerCase().endsWith('.xls'))
  if (invalidFile) {
    inventoryImportFiles.value = []
    inventoryImportResult.value = null
    ElMessage.error('库存表仅支持导入 .xls 文件')
    return
  }
  inventoryImportFiles.value = nextFiles
  inventoryImportResult.value = null
  ElMessage.success('已选择 ' + nextFiles.length + ' 个库存表')
}

function clearInventoryImportFiles() {
  inventoryImportFiles.value = []
  inventoryImportResult.value = null
  if (inventoryImportFileInputRef.value) {
    inventoryImportFileInputRef.value.value = ''
  }
}

function aggregateInventoryImportReports(results, dryRun) {
  const stats = {
    totalRows: 0,
    rowsReady: 0,
    matchedGoods: 0,
    matchedShops: 0,
    updatedGoods: 0,
    changedEntries: 0,
    skippedRows: 0,
    skippedRiskGoods: 0,
    unmatchedGoods: [],
    unmatchedZeroGoods: [],
    ambiguousGoods: [],
    unmatchedShops: [],
    fileReports: [],
  }
  const unmatchedShopSet = new Set()
  let overallSuccess = true

  for (const item of results) {
    const payload = item?.payload || {}
    const report = payload?.stats || {}
    stats.totalRows += Number(report.totalRows || 0)
    stats.rowsReady += Number(report.rowsReady || 0)
    stats.matchedGoods += Number(report.matchedGoods || 0)
    stats.matchedShops = Math.max(stats.matchedShops, Number(report.matchedShops || 0))
    stats.updatedGoods += Number(report.updatedGoods || 0)
    stats.changedEntries += Number(report.changedEntries || 0)
    stats.skippedRows += Number(report.skippedRows || 0)
    stats.skippedRiskGoods += Number(report.skippedRiskGoods || 0)
    stats.unmatchedGoods.push(...(report.unmatchedGoods || []))
    stats.unmatchedZeroGoods.push(...(report.unmatchedZeroGoods || []))
    stats.ambiguousGoods.push(...(report.ambiguousGoods || []))
    for (const shopName of report.unmatchedShops || []) {
      if (shopName) {
        unmatchedShopSet.add(shopName)
      }
    }
    stats.fileReports.push({
      file: item.fileName,
      success: Boolean(payload?.success),
      message: payload?.message || (dryRun ? '校验完成' : '导入完成'),
    })
    if (!payload?.success) {
      overallSuccess = false
    }
  }

  stats.unmatchedShops = [...unmatchedShopSet]

  let message = ''
  if (dryRun) {
    if (stats.unmatchedShops.length) {
      message = `校验未通过，存在 ${stats.unmatchedShops.length} 个未匹配店铺/仓库`
    } else {
      message = `校验完成，可更新 ${stats.rowsReady} 个商品库存；缺失型号 ${stats.unmatchedGoods.length} 个，歧义型号 ${stats.ambiguousGoods.length} 个`
    }
  } else if (stats.updatedGoods > 0) {
    message = `成功更新 ${stats.updatedGoods} 个商品库存，写入 ${stats.changedEntries} 条库存变更；跳过缺失/歧义型号 ${stats.unmatchedGoods.length + stats.ambiguousGoods.length} 个`
  } else {
    message = `没有写入库存变更；跳过缺失型号 ${stats.unmatchedGoods.length} 个、歧义型号 ${stats.ambiguousGoods.length} 个`
  }

  return {
    success: overallSuccess && !stats.unmatchedShops.length,
    message,
    stats,
  }
}

async function runInventoryImport(dryRun = false) {
  if (!inventoryImportFiles.value.length) {
    ElMessage.warning('请先选择需要导入的库存表')
    return
  }

  if (dryRun) {
    inventoryImportDryRunPending.value = true
  } else {
    inventoryImportPending.value = true
  }

  const results = []
  for (const file of inventoryImportFiles.value) {
    const payload = await apiUpload('/goods/inventory-import', file, {
      token: authStore.token,
      query: {
        dry_run: dryRun ? 'true' : 'false',
      },
      timeoutMs: 120000,
    })
    results.push({ fileName: file.name, payload })
  }

  if (dryRun) {
    inventoryImportDryRunPending.value = false
  } else {
    inventoryImportPending.value = false
  }

  inventoryImportResult.value = aggregateInventoryImportReports(results, dryRun)

  if (!inventoryImportResult.value.success) {
    ElMessage.error(inventoryImportResult.value.message || (dryRun ? '校验失败' : '导入失败'))
  } else {
    ElMessage.success(inventoryImportResult.value.message || (dryRun ? '校验完成' : '导入成功'))
  }

  if (!dryRun) {
    await reloadAll()
  }
}

async function loadMeta() {
  const seq = ++metaFetchSeq
  if (metaAbortController) {
    metaAbortController.abort()
  }
  const controller = new AbortController()
  metaAbortController = controller
  metaLoading.value = true

  try {
    const payload = await apiGet('/goods/catalog/meta', {
      token: authStore.token,
      timeoutMs: 12000,
      signal: controller.signal,
      query: buildMetaQuery(),
    })
    if (isUnmounted || seq !== metaFetchSeq || !payload?.success) {
      return
    }
    meta.totalItems = Number(payload.totalItems || 0)
    meta.brandCount = Number(payload.brandCount || 0)
    meta.seriesCount = Number(payload.seriesCount || 0)
    meta.priceMin = Number(payload.priceMin || 0)
    meta.priceMax = Number(payload.priceMax || 0)
    meta.brandOptions = payload.brandOptions || []
    meta.seriesOptions = payload.seriesOptions || []
    meta.attributeOptions = payload.attributeOptions || []
    meta.indexOptions = payload.indexOptions || []
  } finally {
    if (metaAbortController === controller) {
      metaAbortController = null
    }
    if (!isUnmounted && seq === metaFetchSeq) {
      metaLoading.value = false
    }
  }
}

async function loadDialogMeta(brand = '') {
  const seq = ++dialogMetaFetchSeq
  if (dialogMetaAbortController) {
    dialogMetaAbortController.abort()
  }
  const controller = new AbortController()
  dialogMetaAbortController = controller
  dialogMetaLoading.value = true

  try {
    const payload = await apiGet('/goods/catalog/meta', {
      token: authStore.token,
      timeoutMs: 12000,
      signal: controller.signal,
      query: {
        catalog_only: 'true',
        draft_context: 'true',
        ...(brand ? { brand } : {}),
      },
    })
    if (isUnmounted || seq !== dialogMetaFetchSeq || !payload?.success) {
      return
    }
    dialogMeta.brandOptions = payload.brandOptions || []
    dialogMeta.seriesOptions = payload.seriesOptions || []
  } finally {
    if (dialogMetaAbortController === controller) {
      dialogMetaAbortController = null
    }
    if (!isUnmounted && seq === dialogMetaFetchSeq) {
      dialogMetaLoading.value = false
    }
  }
}

async function loadGoods() {
  const seq = ++goodsFetchSeq
  if (goodsAbortController) {
    goodsAbortController.abort()
  }
  const controller = new AbortController()
  goodsAbortController = controller
  loading.value = true

  try {
    const payload = await apiGet('/goods/items', {
      token: authStore.token,
      timeoutMs: 12000,
      signal: controller.signal,
      query: buildQuery(),
    })
    if (isUnmounted || seq !== goodsFetchSeq) {
      return
    }
    if (!payload?.success) {
      filteredStockTotal.value = 0
      filteredSalesTotal.value = 0
      ElMessage.error(payload?.message || '商品数据加载失败')
      return
    }
    items.value = (payload.items || []).map((item) => ({
      ...item,
      compareQuantities: item?.compareQuantities && typeof item.compareQuantities === 'object'
        ? item.compareQuantities
        : {},
      compareSalesCounts: item?.compareSalesCounts && typeof item.compareSalesCounts === 'object'
        ? item.compareSalesCounts
        : {},
      salesCount: Number(item?.salesCount ?? item?.saleNum ?? 0),
    }))
    total.value = Number(payload.total || 0)
    filteredStockTotal.value = payload.stockTotal !== undefined && payload.stockTotal !== null
      ? Number(payload.stockTotal || 0)
      : items.value.reduce((sum, item) => sum + Number(item.stock || 0), 0)
    filteredSalesTotal.value = payload.salesTotal !== undefined && payload.salesTotal !== null
      ? Number(payload.salesTotal || 0)
      : items.value.reduce((sum, item) => sum + Number(item.salesCount || 0), 0)
  } finally {
    if (goodsAbortController === controller) {
      goodsAbortController = null
    }
    if (!isUnmounted && seq === goodsFetchSeq) {
      loading.value = false
    }
  }
}

async function reloadAll() {
  await Promise.all([loadMeta(), loadGoods()])
}

function onBrandChange() {
  if (seriesFilter.value && !meta.seriesOptions.some((item) => item.value === seriesFilter.value)) {
    seriesFilter.value = ''
  }
  page.value = 1
  void Promise.all([loadMeta(), loadGoods()])
}

function onDialogBrandChange() {
  void loadDialogMeta(cleanText(form.brand))
}

function setIndexFilter(value) {
  indexFilter.value = value
  page.value = 1
  void Promise.all([loadMeta(), loadGoods()])
}

function onSearch() {
  page.value = 1
  void Promise.all([loadMeta(), loadGoods()])
}

async function lookupCatalogBarcode() {
  const barcode = cleanText(barcodeFilter.value)
  if (!barcode) {
    ElMessage.warning('请先输入或扫描条码')
    return
  }

  barcodeLookupLoading.value = true
  const payload = await apiGet('/goods/barcode/' + encodeURIComponent(barcode), {
    token: authStore.token,
    timeoutMs: 12000,
    query: {
      catalog_only: 'true',
    },
  })
  barcodeLookupLoading.value = false

  if (!payload?.success || !payload.item) {
    ElMessage.error(payload?.message || '未找到匹配条码的商品')
    return
  }

  const matchedItem = payload.item
  barcodeFilter.value = matchedItem.barcode || barcode
  keyword.value = ''
  page.value = 1
  catalogScannerResultName.value = buildItemName(matchedItem)
  await Promise.all([loadMeta(), loadGoods()])
  ElMessage.success('已定位商品：' + buildItemName(matchedItem))
}

async function openCatalogScannerDialog() {
  catalogScannerDialogVisible.value = true
  catalogScannedCode.value = ''
  catalogScannerResultName.value = ''
  await nextTick()
  await startCatalogScanner()
}

async function closeCatalogScannerDialog() {
  catalogScannerDialogVisible.value = false
  await stopCatalogScanner()
}

async function openDialogScannerDialog() {
  dialogScannerDialogVisible.value = true
  dialogScannerResultText.value = cleanText(form.barcode)
  await nextTick()
  await startDialogScanner()
}

async function closeDialogScannerDialog() {
  dialogScannerDialogVisible.value = false
  await stopDialogScanner()
}

function onResetFilters() {
  keyword.value = ''
  brandFilter.value = ''
  seriesFilter.value = ''
  modelFilter.value = ''
  attributeFilter.value = ''
  barcodeFilter.value = ''
  hasStockFilter.value = ''
  indexFilter.value = ''
  priceMin.value = undefined
  priceMax.value = undefined
  salesRangePreset.value = 'all'
  salesDateRange.value = []
  salesDateRangeDraft.value = []
  sortField.value = 'updated_at'
  sortOrder.value = 'desc'
  page.value = 1
  void reloadAll()
}

function onSortChange({ prop, order }) {
  if ((String(prop).startsWith('compareQuantity_') || String(prop).startsWith('compareSales_')) && !order) {
    sortField.value = 'updated_at'
    sortOrder.value = 'desc'
    return
  }

  if (!prop || !order) {
    sortField.value = 'updated_at'
    sortOrder.value = 'desc'
    page.value = 1
    void loadGoods()
    return
  }

  if (String(prop).startsWith('compareQuantity_') || String(prop).startsWith('compareSales_')) {
    sortField.value = String(prop)
    sortOrder.value = order === 'ascending' ? 'asc' : 'desc'
    return
  }

  {
    const map = {
      brand: 'brand',
      series: 'series',
      model: 'model',
      price: 'price',
      salesCount: 'sales_count',
      barcode: 'barcode',
      stock: 'stock',
    }
    sortField.value = map[prop] || 'updated_at'
    sortOrder.value = order === 'ascending' ? 'asc' : 'desc'
  }
  page.value = 1
  void loadGoods()
}

function onPageChange(nextPage) {
  page.value = nextPage
  void loadGoods()
}

function onPageSizeChange(nextSize) {
  pageSize.value = nextSize
  page.value = 1
  void loadGoods()
}

async function loadCreateLocations() {
  const [storesPayload, warehousesPayload] = await Promise.all([
    apiGet('/shops', {
      token: authStore.token,
      query: { page: '1', page_size: '100', shop_type: String(SHOP_TYPE_STORE) },
    }),
    apiGet('/shops', {
      token: authStore.token,
      query: { page: '1', page_size: '100', shop_type: String(SHOP_TYPE_WAREHOUSE) },
    }),
  ])

  if (!storesPayload?.success || !warehousesPayload?.success) {
    ElMessage.error(storesPayload?.message || warehousesPayload?.message || '店铺/仓库列表加载失败')
    createInventoryLocations.value = []
    createDraftMap.value = {}
    createInitialMap.value = {}
    return
  }

  const locations = sortLocationsById([
    ...(storesPayload.shops || []).map((item) => normalizeLocationRow(item, SHOP_TYPE_STORE)),
    ...(warehousesPayload.shops || []).map((item) => normalizeLocationRow(item, SHOP_TYPE_WAREHOUSE)),
  ])
  createInventoryLocations.value = locations
  const nextMap = Object.fromEntries(locations.map((item) => [item.shopId, 0]))
  createInitialMap.value = nextMap
  createDraftMap.value = { ...nextMap }
}

async function loadInventoryCompareLocations() {
  const [storesPayload, warehousesPayload, otherPayload] = await Promise.all([
    apiGet('/shops', {
      token: authStore.token,
      query: { page: '1', page_size: '100', shop_type: String(SHOP_TYPE_STORE) },
    }),
    apiGet('/shops', {
      token: authStore.token,
      query: { page: '1', page_size: '100', shop_type: String(SHOP_TYPE_WAREHOUSE) },
    }),
    apiGet('/shops', {
      token: authStore.token,
      query: { page: '1', page_size: '100', shop_type: String(SHOP_TYPE_OTHER_WAREHOUSE) },
    }),
  ])

  if (!storesPayload?.success || !warehousesPayload?.success || !otherPayload?.success) {
    ElMessage.error(storesPayload?.message || warehousesPayload?.message || otherPayload?.message || '店铺/仓库列表加载失败')
    inventoryCompareLocationOptions.value = []
    return
  }

  inventoryCompareLocationOptions.value = sortLocationsById([
    ...(storesPayload.shops || []).map((item) => normalizeLocationRow(item, SHOP_TYPE_STORE)),
    ...(warehousesPayload.shops || []).map((item) => normalizeLocationRow(item, SHOP_TYPE_WAREHOUSE)),
    ...(otherPayload.shops || []).map((item) => normalizeLocationRow(item, SHOP_TYPE_OTHER_WAREHOUSE)),
  ])
  const validIds = new Set(inventoryCompareLocationOptions.value.map((item) => Number(item.shopId)))
  const nextSettings = normalizeInventoryCompareSettings({
    ...inventoryCompareSettings.value,
    locationIds: inventoryCompareSettings.value.locationIds.filter((item) => validIds.has(Number(item))),
    presets: inventoryCompareSettings.value.presets.map((item) => ({
      ...item,
      locationIds: item.locationIds.filter((shopId) => validIds.has(Number(shopId))),
    })),
  })
  persistInventoryCompareSettings(nextSettings)
}

function openInventoryCompareDialog() {
  inventoryCompareDialogVisible.value = true
}

function resetInventoryCompareSelectionToCurrent() {
  inventoryComparePresetName.value = ''
}

async function toggleInventoryCompareLocation(shopId) {
  const normalizedId = Number(shopId || 0)
  if (normalizedId <= 0) {
    return
  }
  const exists = inventoryCompareSettings.value.locationIds.includes(normalizedId)
  const nextSettings = {
    ...inventoryCompareSettings.value,
    locationIds: exists
      ? inventoryCompareSettings.value.locationIds.filter((item) => item !== normalizedId)
      : [...inventoryCompareSettings.value.locationIds, normalizedId],
  }
  persistInventoryCompareSettings(nextSettings)
  page.value = 1
  await loadGoods()
}

function isInventoryComparePresetActive(preset) {
  const normalized = normalizeInventoryComparePreset(preset)
  return JSON.stringify(normalized.locationIds) === JSON.stringify(inventoryCompareSettings.value.locationIds)
}

async function applyInventoryComparePreset(preset) {
  const normalized = normalizeInventoryComparePreset(preset)
  persistInventoryCompareSettings({
    ...inventoryCompareSettings.value,
    enabled: true,
    locationIds: normalized.locationIds,
  })
  page.value = 1
  await loadGoods()
}

function saveInventoryComparePreset() {
  const name = cleanText(inventoryComparePresetName.value)
  if (!name) {
    ElMessage.warning('请先输入预设名称')
    return
  }
  if (!inventoryCompareSettings.value.locationIds.length) {
    ElMessage.warning('请先选择至少一个店铺 / 仓库')
    return
  }
  const nextPreset = normalizeInventoryComparePreset({
    id: Date.now().toString(36),
    name,
    locationIds: inventoryCompareSettings.value.locationIds,
  })
  persistInventoryCompareSettings({
    ...inventoryCompareSettings.value,
    presets: [
      nextPreset,
      ...inventoryCompareSettings.value.presets.filter((item) => cleanText(item?.name) !== nextPreset.name),
    ],
  })
  inventoryComparePresetName.value = ''
  ElMessage.success('预设已保存')
}

async function deleteInventoryComparePreset(preset) {
  const normalized = normalizeInventoryComparePreset(preset)
  if (!normalized.id) {
    return
  }
  try {
    await confirmDestructiveAction(`确认删除预设“${normalized.name}”吗？删除后无法恢复。`, '删除预设')
  } catch (_error) {
    return
  }
  persistInventoryCompareSettings({
    ...inventoryCompareSettings.value,
    presets: inventoryCompareSettings.value.presets.filter((item) => String(item?.id || '') !== normalized.id),
  })
  ElMessage.success('预设已删除')
}

async function onInventoryCompareToggle(enabled) {
  if (enabled && !inventoryCompareSettings.value.locationIds.length) {
    ElMessage.warning('开启库存对比模式前，请先选择至少一个店铺 / 仓库')
    persistInventoryCompareSettings({
      ...inventoryCompareSettings.value,
      enabled: false,
    })
    return
  }
  persistInventoryCompareSettings({
    ...inventoryCompareSettings.value,
    enabled: Boolean(enabled),
  })
  page.value = 1
  await loadGoods()
}

async function clearInventoryCompareSelection() {
  persistInventoryCompareSettings({
    ...inventoryCompareSettings.value,
    enabled: false,
    locationIds: [],
  })
  page.value = 1
  await loadGoods()
}

async function openCreate() {
  editingId.value = 0
  resetForm()
  resetCreateFlowState()
  createFlowVisible.value = true
  createFlowLoading.value = true
  try {
    await Promise.all([loadDialogMeta(''), loadCreateLocations()])
  } finally {
    createFlowLoading.value = false
  }
}

function goToCreateStep(step) {
  if (step === 1) {
    createStep.value = 1
    return
  }
  if (step === 2 && createCanProceed.value) {
    createStep.value = 2
  }
}

function nextCreateStep() {
  if (createStep.value === 1 && createCanProceed.value) {
    createStep.value = 2
  }
}

function prevCreateStep() {
  if (createStep.value > 1) {
    createStep.value -= 1
  }
}

function getCreateDraftQuantity(shopId) {
  return Number(createDraftMap.value[shopId] || 0)
}

function adjustCreateQuantity(shopId, delta) {
  const nextQuantity = Math.max(0, getCreateDraftQuantity(shopId) + Number(delta || 0))
  createDraftMap.value = {
    ...createDraftMap.value,
    [shopId]: nextQuantity,
  }
}

function resetCreateDraft() {
  createDraftMap.value = { ...createInitialMap.value }
}

function openEditMenu(row) {
  editMenuTarget.value = row
  editMenuVisible.value = true
}

async function openPropertyEditor(targetRow) {
  const row = targetRow || editMenuTarget.value
  if (!row) {
    return
  }

  editMenuVisible.value = false
  editingId.value = row.id
  dialogVisible.value = true
  detailLoading.value = true

  try {
    const payload = await apiGet('/goods/items/' + row.id, {
      token: authStore.token,
      timeoutMs: 12000,
    })
    if (isUnmounted) {
      return
    }
    if (!payload?.success || !payload.item) {
      ElMessage.error(payload?.message || '商品详情加载失败')
      return
    }

    const item = payload.item
    form.brand = item.brand || ''
    form.series = item.series || ''
    form.model = item.model || ''
    form.modelAttribute = item.modelAttribute || '-'
    form.barcode = item.barcode || ''
    form.price = Number(item.price || 0)
    await loadDialogMeta(form.brand)
  } finally {
    detailLoading.value = false
  }
}

function openPropertyEditorFromMenu() {
  void openPropertyEditor(editMenuTarget.value)
}

async function fetchInventoryPayload(itemId) {
  return apiGet('/goods/items/' + itemId + '/inventory', {
    token: authStore.token,
    timeoutMs: 12000,
  })
}

async function fetchGoodsItemDetail(itemId) {
  return apiGet('/goods/items/' + itemId, {
    token: authStore.token,
    timeoutMs: 12000,
  })
}

function primeDistributionState(payload) {
  distributionItem.value = payload?.item || null
  distributionInventories.value = (payload?.inventories || []).map((item) => normalizeLocationRow(item, item.shopType))
  distributionTotalStock.value = Number(payload?.totalStock || 0)
}

function primeQuantityState(payload) {
  quantityItem.value = payload?.item || null
  quantityInventories.value = sortLocationsById((payload?.inventories || []).map((item) => normalizeLocationRow(item, item.shopType)))
  const nextMap = {}
  for (const entry of quantityInventories.value) {
    nextMap[entry.shopId] = Number(entry.quantity || 0)
  }
  quantityInitialMap.value = nextMap
  quantityDraftMap.value = { ...nextMap }
}

function buildInventoryLogQuery() {
  return {
    page: String(inventoryLogPage.value),
    page_size: String(inventoryLogPageSize.value),
    ...(inventoryLogKeyword.value ? { q: inventoryLogKeyword.value } : {}),
    ...(inventoryLogDateFrom.value ? { date_from: inventoryLogDateFrom.value } : {}),
    ...(inventoryLogDateTo.value ? { date_to: inventoryLogDateTo.value } : {}),
  }
}

async function loadInventoryLogs() {
  const itemId = Number(inventoryLogTarget.value?.id || 0)
  if (!itemId) {
    inventoryLogRows.value = []
    inventoryLogTotal.value = 0
    inventoryLogCurrentTotal.value = 0
    return
  }
  inventoryLogLoading.value = true
  const payload = await apiGet('/goods/items/' + itemId + '/inventory-logs', {
    token: authStore.token,
    timeoutMs: 12000,
    query: buildInventoryLogQuery(),
  })
  inventoryLogLoading.value = false
  if (!payload?.success) {
    ElMessage.error(payload?.message || '库存日志加载失败')
    return
  }
  inventoryLogRows.value = payload.logs || []
  inventoryLogTotal.value = Number(payload.total || 0)
  inventoryLogCurrentTotal.value = Number(payload.currentQuantityTotal || 0)
}

async function openDistribution(row) {
  distributionDialogVisible.value = true
  distributionLoading.value = true
  const payload = await fetchInventoryPayload(row.id)
  distributionLoading.value = false

  if (!payload?.success) {
    ElMessage.error(payload?.message || '商品分布加载失败')
    return
  }

  primeDistributionState(payload)
}

function openDistributionActionMenu(row) {
  if (!row?.shopId) {
    ElMessage.warning('当前点位信息未准备完成')
    return
  }
  if (!distributionItem.value?.id) {
    ElMessage.warning('当前商品信息未准备完成')
    return
  }
  distributionActionRow.value = row
  if (isMobileViewport.value) {
    distributionDialogVisible.value = false
    nextTick(() => {
      distributionActionMenuVisible.value = true
    })
    return
  }
  distributionActionMenuVisible.value = true
}

async function createTransferFromDistribution() {
  const sourceShopId = Number(distributionActionRow.value?.shopId || 0)
  const goodsId = Number(distributionItem.value?.id || 0)
  if (!sourceShopId || !goodsId) {
    ElMessage.warning('当前商品分布信息未准备完成')
    return
  }
  const defaultTargetShopId = Number(authStore.shopId || 0) || null
  const nextQuery = {
    compose: '1',
    type: 'transfer',
    prefill_source_shop_id: String(sourceShopId),
    prefill_goods_id: String(goodsId),
  }
  if (defaultTargetShopId && defaultTargetShopId !== sourceShopId) {
    nextQuery.prefill_target_shop_id = String(defaultTargetShopId)
  }
  distributionActionMenuVisible.value = false
  distributionDialogVisible.value = false
  await router.push({ name: 'work-orders', query: nextQuery })
  if (!defaultTargetShopId) {
    ElMessage.info('已带入商品和调出点位，请在工单中补选调入店铺 / 仓库')
    return
  }
  if (defaultTargetShopId === sourceShopId) {
    ElMessage.warning('已带入商品和调出点位，当前账号默认店铺与调出点位相同，请在工单中改选调入店铺 / 仓库')
  }
}

async function viewDistributionInventoryLogs() {
  const sourceShopId = Number(distributionActionRow.value?.shopId || 0)
  const goodsId = Number(distributionItem.value?.id || 0)
  if (!sourceShopId || !goodsId) {
    ElMessage.warning('当前商品分布信息未准备完成')
    return
  }
  const goodsLabel = buildItemName(distributionItem.value)
  const sourceLabel = displayShopName(distributionActionRow.value?.shopName || distributionActionRow.value?.shopShortName) || '当前点位'
  distributionActionMenuVisible.value = false
  distributionDialogVisible.value = false
  await router.push({
    name: 'log-center',
    query: buildLogCenterQuery({
      type: 'goods_inventory',
      item_id: String(goodsId),
      shop_id: String(sourceShopId),
      subject_name: `${sourceLabel} · ${goodsLabel}`,
      back: '/goods',
    }),
  })
}

async function consumeSpotlightQuery(keys) {
  const nextQuery = { ...route.query }
  let changed = false
  for (const key of keys) {
    if (key in nextQuery) {
      delete nextQuery[key]
      changed = true
    }
  }
  if (changed) {
    await router.replace({ query: nextQuery })
  }
}

function scrollGoodsTableIntoView() {
  nextTick(() => {
    goodsTableRef.value?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
  })
}

async function applyGoodsSpotlightFromRoute() {
  const goodsId = Number(route.query.spotlight_goods || 0)
  const distributionId = Number(route.query.spotlight_distribution || 0)
  const targetId = distributionId || goodsId
  if (!targetId) {
    return
  }

  const payload = await fetchGoodsItemDetail(targetId)
  if (!payload?.success || !payload.item) {
    await consumeSpotlightQuery(['spotlight_goods', 'spotlight_distribution'])
    return
  }

  const item = payload.item
  keyword.value = [item.brand, item.series, item.model].filter(Boolean).join(' ')
  brandFilter.value = item.brand || ''
  seriesFilter.value = item.series || ''
  modelFilter.value = item.barcode ? '' : (item.model || '')
  attributeFilter.value = item.modelAttribute && item.modelAttribute !== '-' ? item.modelAttribute : ''
  barcodeFilter.value = item.barcode || ''
  hasStockFilter.value = ''
  indexFilter.value = item.indexKey || ''
  priceMin.value = undefined
  priceMax.value = undefined
  sortField.value = 'updated_at'
  sortOrder.value = 'desc'
  page.value = 1

  await Promise.all([loadMeta(), loadGoods()])
  scrollGoodsTableIntoView()

  if (distributionId) {
    await openDistribution(item)
  }

  await consumeSpotlightQuery(['spotlight_goods', 'spotlight_distribution'])
}

function buildGoodsInventoryLogBackPath(row) {
  return router.resolve({
    name: 'goods-manage',
    query: {
      ...route.query,
      spotlight_distribution: String(row?.id || ''),
    },
  }).fullPath
}

async function openInventoryLogDialog(row) {
  if (!row?.id) {
    ElMessage.warning('当前商品信息未准备完成')
    return
  }
  await router.push({
    name: 'log-center',
    query: {
      type: 'goods_inventory',
      item_id: String(row.id),
      subject_name: buildItemName(row),
      back: buildGoodsInventoryLogBackPath(row),
    },
  })
}

function onInventoryLogSearch() {
  inventoryLogPage.value = 1
  void loadInventoryLogs()
}

function resetInventoryLogFilters() {
  inventoryLogKeyword.value = ''
  inventoryLogDateFrom.value = ''
  inventoryLogDateTo.value = ''
  inventoryLogPage.value = 1
  void loadInventoryLogs()
}

function onInventoryLogPageChange(nextPage) {
  inventoryLogPage.value = nextPage
  void loadInventoryLogs()
}

function onInventoryLogPageSizeChange(nextSize) {
  inventoryLogPageSize.value = nextSize
  inventoryLogPage.value = 1
  void loadInventoryLogs()
}

async function openQuantityEditor(targetRow) {
  const row = targetRow || editMenuTarget.value
  if (!row) {
    return
  }

  editMenuVisible.value = false
  quantityDialogVisible.value = true
  quantityLoading.value = true
  const payload = await fetchInventoryPayload(row.id)
  quantityLoading.value = false

  if (!payload?.success) {
    ElMessage.error(payload?.message || '商品数量加载失败')
    return
  }

  primeQuantityState(payload)
}

function openQuantityEditorFromMenu() {
  void openQuantityEditor(editMenuTarget.value)
}

function buildBasePayload() {
  const safePrice = Number(form.price || 0)
  const safeBarcode = cleanText(form.barcode)

  return {
    name: displayName.value,
    productCode: null,
    brand: cleanText(form.brand),
    series: cleanText(form.series),
    model: cleanText(form.model),
    modelAttribute: cleanText(form.modelAttribute) || '-',
    barcode: safeBarcode,
    price: safePrice,
    originalPrice: safePrice,
    salePrice: safePrice,
    stock: 0,
    saleNum: 0,
    sort: 0,
    putaway: 1,
    status: 3,
    goodsType: 0,
  }
}

function buildCreatePayload() {
  return {
    ...buildBasePayload(),
    quantities: createInventoryLocations.value.map((entry) => ({
      shopId: entry.shopId,
      quantity: getCreateDraftQuantity(entry.shopId),
    })),
  }
}

async function completeCreateFlow() {
  if (!isPropertyFormValid()) {
    ElMessage.warning('请先完整填写品牌、系列、型号和价格')
    createStep.value = 1
    return
  }

  const payloadBody = buildCreatePayload()
  if (!payloadBody.barcode) {
    ElMessage.warning('请填写商品条码')
    return
  }

  createSubmitting.value = true
  const payload = await apiPost('/goods/items', payloadBody, { token: authStore.token })
  createSubmitting.value = false

  if (!payload?.success) {
    ElMessage.error(payload?.message || '创建失败')
    return
  }

  ElMessage.success(payload.message || '商品创建成功')
  createFlowVisible.value = false
  resetCreateFlowState()
  await reloadAll()
}

async function onSubmit() {
  if (!isPropertyFormValid()) {
    ElMessage.warning('请填写品牌、系列、型号和正确的商品价格')
    return
  }

  const payloadBody = buildBasePayload()
  if (!payloadBody.barcode) {
    ElMessage.warning('请填写商品条码')
    return
  }

  submitting.value = true
  const payload = await apiPut('/goods/items/' + editingId.value, payloadBody, { token: authStore.token })
  submitting.value = false

  if (!payload?.success) {
    ElMessage.error(payload?.message || '保存失败')
    return
  }

  ElMessage.success(payload.message || '保存成功')
  dialogVisible.value = false
  await reloadAll()
}

function getDraftQuantity(shopId) {
  return Number(quantityDraftMap.value[shopId] || 0)
}

function adjustQuantity(shopId, delta) {
  const nextQuantity = getDraftQuantity(shopId) + Number(delta || 0)
  quantityDraftMap.value = {
    ...quantityDraftMap.value,
    [shopId]: nextQuantity,
  }
}

function resetQuantityDraft() {
  quantityDraftMap.value = { ...quantityInitialMap.value }
}

async function saveQuantityDraft() {
  const itemId = Number(quantityItem.value?.id || 0)
  if (!itemId) {
    return
  }

  quantitySubmitting.value = true
  const payload = await apiPut('/goods/items/' + itemId + '/inventory', {
    quantities: quantityInventories.value.map((entry) => ({
      shopId: entry.shopId,
      quantity: getDraftQuantity(entry.shopId),
    })),
  }, {
    token: authStore.token,
  })
  quantitySubmitting.value = false

  if (!payload?.success) {
    ElMessage.error(payload?.message || '商品数量保存失败')
    return
  }

  primeQuantityState(payload)
  ElMessage.success(payload.message || '商品数量已更新')
  await loadGoods()
}

async function onDelete(itemId) {
  try {
    await confirmDestructiveAction('确认删除这个商品吗？删除后无法恢复。')
  } catch (error) {
    return
  }
  const payload = await apiDelete('/goods/items/' + itemId, {
    token: authStore.token,
  })
  if (!payload?.success) {
    ElMessage.error(payload?.message || '删除失败')
    return
  }
  ElMessage.success(payload.message || '删除成功')
  await reloadAll()
}

watch([dialogVisible, createFlowVisible], ([editVisible, createVisible]) => {
  if (!editVisible && !createVisible) {
    void closeDialogScannerDialog()
    void stopDialogScanner()
  }
})

onMounted(() => {
  void (async () => {
    persistInventoryCompareSettings(readInventoryCompareSettings())
    await loadInventoryCompareLocations()
    await reloadAll()
    await applyGoodsSpotlightFromRoute()
  })()
})

watch(
  () => [route.query.spotlight_goods, route.query.spotlight_distribution],
  ([goodsId, distributionId]) => {
    if (!goodsId && !distributionId) {
      return
    }
    void applyGoodsSpotlightFromRoute()
  },
)

onBeforeUnmount(() => {
  isUnmounted = true
  goodsFetchSeq += 1
  metaFetchSeq += 1
  dialogMetaFetchSeq += 1

  if (goodsAbortController) {
    goodsAbortController.abort()
  }
  if (metaAbortController) {
    metaAbortController.abort()
  }
  if (dialogMetaAbortController) {
    dialogMetaAbortController.abort()
  }

  void stopCatalogScanner()
  void stopDialogScanner()
})
</script>
