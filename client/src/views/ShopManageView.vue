<template>
  <section class="shop-manage-page shop-warehouse-page">
    <section class="catalog-controls card-surface motion-fade-slide shop-manage-search-card" style="--motion-delay: 0.06s">
      <div class="goods-search-shell shop-manage-search-shell">
        <el-input
          v-model.trim="keyword"
          clearable
          placeholder="搜索店铺 / 仓库名称、地址、联系人、销售员"
          class="goods-search-input shop-manage-search-input"
          @keyup.enter="onSearch"
        />

        <div class="toolbar-actions goods-search-actions shop-manage-search-actions">
          <el-button :loading="loading" @click="onSearch">查询</el-button>
          <el-button @click="onResetFilters">重置</el-button>
          <el-button v-if="authStore.can('sales.read')" @click="openReportCenter">报告中心</el-button>
          <el-button v-if="authStore.can('shops.write')" type="primary" @click="openCreate">新增地点</el-button>
        </div>
      </div>

      <section class="sales-filter-shell goods-filter-shell shop-manage-filter-shell">
        <div class="sales-filter-trigger-row">
          <button type="button" class="sales-filter-trigger" :class="{ active: filterPanelOpen }" @click="filterPanelOpen = !filterPanelOpen">
            <div class="sales-filter-trigger-copy">
              <span>筛选</span>
              <strong>{{ filterPanelOpen ? '收起店铺筛选' : '展开店铺筛选' }}</strong>
            </div>
            <div class="sales-filter-trigger-meta">
              <div class="sales-filter-trigger-stats">
                <span>已筛选 {{ activeShopFilterCount }} 项</span>
                <strong>{{ storeRows.length + warehouseRows.length + otherWarehouseRows.length + repairRows.length }} 条结果</strong>
              </div>
            </div>
          </button>
        </div>

        <CollapsePanelTransition>
          <div v-if="filterPanelOpen" class="sales-filter-collapse-shell">
            <section class="sales-filter-panel goods-filter-panel shop-manage-filter-panel">
              <header class="sales-filter-head">
              <div class="sales-filter-head-copy">
                <h2>筛选</h2>
                <span>按类别快速收束店铺 / 仓库结果</span>
              </div>
              <div class="toolbar-actions sales-filter-head-actions">
                <el-button type="primary" :loading="loading" @click="onSearch">查询</el-button>
                <el-button class="sales-filter-reset-btn" :disabled="!activeShopFilterCount" @click="onResetFilters">清空筛选</el-button>
              </div>
            </header>

              <div class="sales-filter-grid shop-manage-filter-grid">
              <div class="sales-filter-field">
                <label class="sales-filter-label">查看范围</label>
                <el-select v-model="shopRangeFilter" class="full-width" placeholder="全部类别">
                  <el-option label="全部" value="all" />
                  <el-option label="仅店铺" value="store" />
                  <el-option label="仅仓库" value="warehouse" />
                  <el-option label="仅其他仓库" value="other" />
                  <el-option label="仅维修点" value="repair" />
                </el-select>
              </div>
              </div>
            </section>
          </div>
        </CollapsePanelTransition>
      </section>
    </section>

    <article class="card-surface shop-warehouse-panel shop-warehouse-card motion-fade-slide" style="--motion-delay: 0.08s">
      <header class="shop-warehouse-panel-head">
        <div>
          <h3>店铺</h3>
        </div>
        <span>{{ storeRows.length }} 条</span>
      </header>

      <div class="table-shell open-table-shell">
        <el-table :data="storeRows" border stripe v-loading="loading" empty-text="暂无店铺">
          <el-table-column prop="id" label="ID" width="88" />
          <el-table-column prop="name" label="店铺名称" min-width="180" show-overflow-tooltip />
          <el-table-column prop="goodsQuantity" label="商品数量" min-width="110" />
          <el-table-column prop="phone" label="联系电话" min-width="120" />
          <el-table-column prop="address" label="地址" min-width="220" show-overflow-tooltip />
          <el-table-column prop="managerName" label="店长" min-width="120" show-overflow-tooltip />
          <el-table-column prop="businessHours" label="营业时间" min-width="120" />
          <el-table-column prop="salespeople" label="销售员" min-width="260" show-overflow-tooltip />
          <el-table-column label="排班" min-width="150">
            <template #default="{ row }">
              <div class="shop-manage-schedule-cell">
                <strong>{{ row.scheduleEnabled ? '已开启' : '未开启' }}</strong>
                <span>{{ row.scheduleEnabled ? `排班成员 ${row.scheduleMemberCount || 0} 人` : '当前店铺未启用排班' }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="目标" min-width="150">
            <template #default="{ row }">
              <div class="shop-manage-schedule-cell">
                <strong>{{ row.targetEnabled ? '已开启' : '未开启' }}</strong>
                <span>{{ row.targetEnabled ? '当前店铺可查看目标页' : '当前店铺未启用目标功能' }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="报告" min-width="150">
            <template #default="{ row }">
              <div class="shop-manage-schedule-cell">
                <strong>{{ row.reportEnabled ? '已开启' : '未开启' }}</strong>
                <span>{{ row.reportEnabled ? '当前店铺会参与报告生成' : '当前店铺不会进入报告统计' }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column v-if="canShowRowActions" label="操作" :width="storeActionColumnWidth" fixed="right">
            <template #default="{ row }">
              <ResponsiveTableActions :menu-width="180">
                <el-button v-if="authStore.can('goods.read')" type="primary" text @click="openGoodsDialog(row)">商品</el-button>
                <el-button v-if="canOpenSchedule(row)" type="primary" text @click="openSchedule(row)">排班</el-button>
                <el-button v-if="canOpenTarget(row)" type="primary" text @click="openTarget(row)">目标</el-button>
                <el-button v-if="authStore.can('shops.write')" type="primary" text @click="openEdit(row)">编辑</el-button>
                <el-button v-if="authStore.can('shops.manage')" type="danger" text @click="onDelete(row.id, row.shopType)">删除</el-button>
              </ResponsiveTableActions>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </article>

    <article class="card-surface shop-warehouse-panel shop-warehouse-card motion-fade-slide" style="--motion-delay: 0.16s">
      <header class="shop-warehouse-panel-head">
        <div>
          <h3>仓库</h3>
        </div>
        <span>{{ warehouseRows.length }} 条</span>
      </header>

      <div class="table-shell open-table-shell">
        <el-table :data="warehouseRows" border stripe v-loading="loading" empty-text="暂无仓库">
          <el-table-column prop="id" label="ID" width="88" />
          <el-table-column prop="name" label="仓库名称" min-width="220" show-overflow-tooltip />
          <el-table-column prop="goodsQuantity" label="商品数量" min-width="110" />
          <el-table-column prop="managerName" label="库管" min-width="160" show-overflow-tooltip />
          <el-table-column v-if="canShowRowActions" label="操作" :width="warehouseActionColumnWidth" fixed="right">
            <template #default="{ row }">
              <ResponsiveTableActions :menu-width="180">
                <el-button v-if="authStore.can('goods.read')" type="primary" text @click="openGoodsDialog(row)">商品</el-button>
                <el-button v-if="authStore.can('shops.write')" type="primary" text @click="openEdit(row)">编辑</el-button>
                <el-button v-if="authStore.can('shops.manage')" type="danger" text @click="onDelete(row.id, row.shopType)">删除</el-button>
              </ResponsiveTableActions>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </article>

    <article class="card-surface shop-warehouse-panel shop-warehouse-card motion-fade-slide" style="--motion-delay: 0.24s">
      <header class="shop-warehouse-panel-head">
        <div>
          <h3>其他仓库</h3>
        </div>
        <span>{{ otherWarehouseRows.length }} 条</span>
      </header>

      <div class="table-shell open-table-shell">
        <el-table :data="otherWarehouseRows" border stripe v-loading="loading" empty-text="暂无其他仓库">
          <el-table-column prop="name" label="名称" min-width="260" show-overflow-tooltip />
          <el-table-column v-if="authStore.can('shops.read') || authStore.can('shops.write') || authStore.can('shops.manage')" label="操作" :width="otherWarehouseActionColumnWidth" fixed="right">
            <template #default="{ row }">
              <ResponsiveTableActions :menu-width="180">
                <el-button v-if="authStore.can('goods.read')" type="primary" text @click="openGoodsDialog(row)">商品</el-button>
                <el-button v-if="authStore.can('shops.write')" type="primary" text @click="openEdit(row)">编辑</el-button>
                <el-button v-if="authStore.can('shops.manage')" type="danger" text @click="onDelete(row.id, row.shopType)">删除</el-button>
              </ResponsiveTableActions>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </article>

    <article class="card-surface shop-warehouse-panel shop-warehouse-card motion-fade-slide" style="--motion-delay: 0.32s">
      <header class="shop-warehouse-panel-head">
        <div>
          <h3>维修点</h3>
        </div>
        <span>{{ repairRows.length }} 条</span>
      </header>

      <div class="table-shell open-table-shell">
        <el-table :data="repairRows" border stripe v-loading="loading" empty-text="暂无维修点">
          <el-table-column prop="id" label="ID" width="88" />
          <el-table-column prop="name" label="维修点名称" min-width="180" show-overflow-tooltip />
          <el-table-column prop="phone" label="联系电话" min-width="140" />
          <el-table-column prop="address" label="地址" min-width="220" show-overflow-tooltip />
          <el-table-column prop="businessHours" label="营业时间" min-width="140" />
          <el-table-column prop="salespeople" label="工程师" min-width="260" show-overflow-tooltip />
          <el-table-column v-if="authStore.can('shops.read') || authStore.can('shops.write') || authStore.can('shops.manage')" label="操作" :width="repairActionColumnWidth" fixed="right">
            <template #default="{ row }">
              <ResponsiveTableActions :menu-width="180">
                <el-button v-if="authStore.can('shops.write')" type="primary" text @click="openEdit(row)">编辑</el-button>
                <el-button v-if="authStore.can('shops.manage')" type="danger" text @click="onDelete(row.id, row.shopType)">删除</el-button>
              </ResponsiveTableActions>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </article>

    <ResponsiveDialog
      v-model="dialogVisible"
      width="min(900px, 96vw)"
      class="aqc-app-dialog shop-editor-dialog"
      :title="dialogTitle"
      mobile-subtitle="店铺 / 仓库管理"
    >
      <div class="goods-editor-shell shop-editor-shell">
        <section class="goods-editor-hero shop-editor-hero">
          <div class="goods-code-card shop-editor-hero-card">
            <span>{{ editingId ? '当前编辑' : '即将新增' }}</span>
            <strong>{{ form.name || dialogTitle }}</strong>
            <div class="goods-preview-meta">
              <span>类别 {{ activeTypeLabel }}</span>
              <span v-if="showManagerSelector">{{ activeManagerLabel }} {{ activeManagerName || '未选择' }}</span>
              <span v-if="isStoreType">排班 {{ form.scheduleEnabled ? '已开启' : '未开启' }}</span>
              <span v-if="isStoreType">目标 {{ form.targetEnabled ? '已开启' : '未开启' }}</span>
              <span v-if="isStoreType">报告 {{ form.reportEnabled ? '已开启' : '未开启' }}</span>
              <span v-if="isStoreType">销售员 {{ form.salespersonIds.length }} 人</span>
              <span v-else-if="isRepairType">工程师 {{ form.salespersonIds.length }} 人</span>
            </div>
          </div>
        </section>

        <el-form label-position="top" class="dialog-form goods-editor-form">
          <div class="shop-editor-grid">
            <div class="shop-editor-field shop-editor-field-emphasis">
              <label class="shop-editor-label">类别</label>
              <el-segmented v-model="form.shopType" :options="typeOptions" class="shop-editor-segmented" />
            </div>

            <div class="shop-editor-field shop-editor-field-emphasis">
              <label class="shop-editor-label">{{ activeNameLabel }}</label>
              <el-input v-model.trim="form.name" maxlength="255" :placeholder="'请输入' + activeNameLabel" />
            </div>

            <div v-if="showManagerSelector" class="shop-editor-field">
              <label class="shop-editor-label">{{ activeManagerLabel }}</label>
              <el-select
                v-model="form.managerUserId"
                clearable
                filterable
                class="full-width"
                :placeholder="'请选择' + activeManagerLabel"
                @change="onManagerChange"
              >
                <el-option
                  v-for="item in userOptions"
                  :key="item.id"
                  :label="formatUserOption(item)"
                  :value="item.id"
                />
              </el-select>
            </div>

            <template v-if="isStoreType">
              <div class="shop-editor-field">
                <label class="shop-editor-label">联系电话</label>
                <el-input v-model.trim="form.phone" maxlength="40" placeholder="请输入联系电话" />
              </div>

              <div class="shop-editor-field">
                <label class="shop-editor-label">营业时间</label>
                <el-input v-model.trim="form.businessHours" maxlength="100" placeholder="如 10:00-22:00" />
              </div>

              <div class="shop-editor-field">
                <label class="shop-editor-label">收款渠道</label>
                <el-select v-model="form.channel" class="full-width">
                  <el-option label="门店收银" :value="1" />
                  <el-option label="商场收银" :value="2" />
                </el-select>
              </div>

              <div class="shop-editor-field">
                <label class="shop-editor-label">排班功能</label>
                <el-switch
                  v-model="form.scheduleEnabled"
                  inline-prompt
                  active-text="开启"
                  inactive-text="关闭"
                />
              </div>

              <div class="shop-editor-field">
                <label class="shop-editor-label">目标功能</label>
                <el-switch
                  v-model="form.targetEnabled"
                  inline-prompt
                  active-text="开启"
                  inactive-text="关闭"
                />
              </div>

              <div class="shop-editor-field">
                <label class="shop-editor-label">报告功能</label>
                <el-switch
                  v-model="form.reportEnabled"
                  :disabled="reportToggleLocked"
                  inline-prompt
                  active-text="开启"
                  inactive-text="关闭"
                />
                <div v-if="reportToggleHint" style="margin-top: 8px; color: var(--text-light); font-size: 12px; line-height: 1.6;">
                  {{ reportToggleHint }}
                </div>
              </div>

              <div class="shop-editor-field shop-editor-field-wide">
                <label class="shop-editor-label">销售员</label>
                <el-select
                  v-model="form.salespersonIds"
                  multiple
                  filterable
                  clearable
                  collapse-tags
                  collapse-tags-tooltip
                  class="full-width"
                  placeholder="请选择销售员账户"
                >
                  <el-option
                    v-for="item in userOptions"
                    :key="item.id"
                    :label="formatUserOption(item)"
                    :value="item.id"
                  />
                </el-select>
              </div>

              <div class="shop-editor-field shop-editor-field-full">
                <label class="shop-editor-label">店铺地址</label>
                <el-input v-model.trim="form.address" maxlength="255" placeholder="请输入店铺地址" />
              </div>
            </template>

            <template v-else-if="isRepairType">
              <div class="shop-editor-field">
                <label class="shop-editor-label">联系电话</label>
                <el-input v-model.trim="form.phone" maxlength="40" placeholder="请输入联系电话" />
              </div>

              <div class="shop-editor-field">
                <label class="shop-editor-label">营业时间</label>
                <el-input v-model.trim="form.businessHours" maxlength="100" placeholder="如 10:00-22:00" />
              </div>

              <div class="shop-editor-field shop-editor-field-wide">
                <label class="shop-editor-label">工程师</label>
                <el-select
                  v-model="form.salespersonIds"
                  multiple
                  filterable
                  clearable
                  collapse-tags
                  collapse-tags-tooltip
                  class="full-width"
                  placeholder="请选择工程师账户"
                >
                  <el-option
                    v-for="item in engineerOptions"
                    :key="item.id"
                    :label="formatUserOption(item)"
                    :value="item.id"
                  />
                </el-select>
              </div>

              <div class="shop-editor-field shop-editor-field-full">
                <label class="shop-editor-label">地址</label>
                <el-input v-model.trim="form.address" maxlength="255" placeholder="请输入地址" />
              </div>
            </template>
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

    <ResponsiveDialog
      v-model="goodsDialogVisible"
      :title="activeGoodsShopName || '商品分布'"
      width="min(1240px, 96vw)"
      class="aqc-app-dialog shop-goods-dialog"
      mobile-subtitle="店铺 / 仓库管理"
      :initial-snap="0.64"
      :expanded-snap="0.94"
    >
      <div class="goods-editor-shell shop-goods-shell" v-loading="goodsDialogLoading || goodsMetaLoading">
        <section class="catalog-controls card-surface shop-goods-panel">
          <div class="records-toolbar catalog-toolbar">
            <el-input
              v-model.trim="goodsKeyword"
              clearable
              placeholder="搜索品牌 / 系列 / 型号 / 条码"
              class="toolbar-search toolbar-search-wide"
              @keyup.enter="onGoodsSearch"
            />

            <el-select
              v-model="goodsBrandFilter"
              clearable
              filterable
              placeholder="品牌"
              style="width: 180px"
              @change="onGoodsBrandChange"
            >
              <el-option
                v-for="option in goodsMeta.brandOptions"
                :key="option.value"
                :label="option.label + ' (' + option.count + ')'"
                :value="option.value"
              />
            </el-select>

            <el-select
              v-model="goodsSeriesFilter"
              clearable
              filterable
              placeholder="系列"
              style="width: 200px"
              @change="onGoodsSearch"
            >
              <el-option
                v-for="option in goodsMeta.seriesOptions"
                :key="option.value"
                :label="option.label + ' (' + option.count + ')'"
                :value="option.value"
              />
            </el-select>

            <el-input
              v-model.trim="goodsModelFilter"
              clearable
              placeholder="型号"
              style="width: 180px"
              @keyup.enter="onGoodsSearch"
            />

            <el-select
              v-model="goodsAttributeFilter"
              clearable
              placeholder="属性"
              style="width: 110px"
              @change="onGoodsSearch"
            >
              <el-option
                v-for="option in goodsMeta.attributeOptions"
                :key="option.value"
                :label="option.label + ' (' + option.count + ')'"
                :value="option.value"
              />
            </el-select>

            <el-input
              v-model.trim="goodsBarcodeFilter"
              clearable
              placeholder="条码"
              style="width: 180px"
              @keyup.enter="onGoodsSearch"
            />

            <el-select
              v-model="goodsHasStockFilter"
              clearable
              placeholder="库存"
              style="width: 132px"
              @change="onGoodsSearch"
            >
              <el-option label="库存不为0" :value="'nonzero'" />
              <el-option label="库存异常（小于0）" :value="'negative'" />
            </el-select>

            <div class="toolbar-actions">
              <el-button :loading="goodsDialogLoading" @click="onGoodsSearch">查询</el-button>
              <el-button @click="resetGoodsFilters">重置</el-button>
            </div>
          </div>

          <div class="catalog-index-bar compact">
            <button
              type="button"
              class="index-chip"
              :class="{ active: !goodsIndexFilter }"
              @click="setGoodsIndexFilter('')"
            >
              全部
            </button>
            <button
              v-for="option in goodsMeta.indexOptions"
              :key="option.key"
              type="button"
              class="index-chip"
              :class="{ active: goodsIndexFilter === option.key }"
              @click="setGoodsIndexFilter(option.key)"
            >
              <span>{{ option.key }}</span>
              <small>{{ option.count }}</small>
            </button>
          </div>

          <div class="catalog-meta-row shop-goods-meta-row">
            <div class="catalog-meta-copy">
              <span>筛选结果</span>
              <strong>{{ shopGoodsTotal }} 条</strong>
            </div>
            <div class="catalog-meta-copy">
              <span>库存数量</span>
              <strong>{{ shopGoodsQuantityTotal }}</strong>
            </div>
            <div class="catalog-meta-copy">
              <span>库存金额</span>
              <strong>¥ {{ formatMoney(shopGoodsAmountTotal) }}</strong>
            </div>
            <div class="toolbar-actions shop-goods-card-actions">
              <el-button :loading="goodsExportPending" @click="openGoodsExportDialog">导出表格</el-button>
              <el-button @click="openInventoryLogDialog(goodsDialogShop)">库存日志</el-button>
            </div>
          </div>
        </section>

        <section class="catalog-table card-surface shop-goods-panel">
          <div class="table-shell open-table-shell">
            <el-table
              :data="shopGoodsItems"
              border
              stripe
              v-loading="goodsDialogLoading"
              show-summary
              :summary-method="shopGoodsTableSummary"
              @sort-change="onGoodsSortChange"
            >
              <el-table-column prop="brand" label="品牌" min-width="140" sortable="custom" />
              <el-table-column prop="series" label="系列" min-width="180" sortable="custom" show-overflow-tooltip />
              <el-table-column prop="model" label="型号" min-width="220" sortable="custom" show-overflow-tooltip />
              <el-table-column prop="modelAttribute" label="属性" width="82" />
              <el-table-column prop="price" label="价格" min-width="120" sortable="custom">
                <template #default="{ row }">¥ {{ formatMoney(row.price) }}</template>
              </el-table-column>
              <el-table-column prop="shopQuantity" label="数量" min-width="100" />
              <el-table-column prop="lineAmount" label="金额" min-width="140">
                <template #default="{ row }">¥ {{ formatMoney(Number(row.price || 0) * Number(row.shopQuantity || 0)) }}</template>
              </el-table-column>
              <el-table-column prop="barcode" label="条码" min-width="170" sortable="custom" show-overflow-tooltip />
              <el-table-column v-if="authStore.can('goods.read')" label="操作" :width="shopGoodsActionColumnWidth" fixed="right">
                <template #default="{ row }">
                  <ResponsiveTableActions :menu-width="160">
                    <el-button type="primary" text @click="openShopGoodsDistribution(row)">分布</el-button>
                  </ResponsiveTableActions>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <div class="pager-wrap">
            <el-pagination
              background
              layout="total, prev, pager, next, sizes"
              :total="shopGoodsTotal"
              :current-page="goodsPage"
              :page-size="goodsPageSize"
              :page-sizes="[20, 50, 100, 200]"
              @current-change="onGoodsPageChange"
              @size-change="onGoodsPageSizeChange"
            />
          </div>
        </section>
      </div>

      <template #footer>
        <div class="form-actions">
          <el-button @click="goodsDialogVisible = false">关闭</el-button>
        </div>
      </template>
    </ResponsiveDialog>

    <MobileBottomSheet
      v-if="isMobileViewport"
      v-model="distributionDialogVisible"
      title="商品分布"
      subtitle="店铺/仓库管理"
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
            <el-button @click="openDistributionInventoryLogCenter">库存日志</el-button>
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
            <el-button @click="openDistributionInventoryLogCenter">库存日志</el-button>
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
      destroy-on-close
      append-to-body
      align-center
      class="aqc-app-dialog shop-inventory-log-dialog"
    >
      <div class="goods-editor-shell inventory-log-shell" v-loading="inventoryLogLoading">
        <section class="inventory-hero-card inventory-hero-card-strong">
          <span>库存数量</span>
          <strong>{{ inventoryLogCurrentTotal }}</strong>
          <h3>{{ activeInventoryLogShopName || '当前店铺 / 仓库' }}</h3>
          <p>按店铺 / 仓库查看所有商品库存变更记录。</p>
          <div class="inventory-hero-meta">共 {{ inventoryLogTotal }} 条日志</div>
        </section>

        <section class="catalog-controls card-surface inventory-log-panel">
          <div class="records-toolbar catalog-toolbar inventory-log-toolbar">
            <el-input
              v-model.trim="inventoryLogKeyword"
              clearable
              placeholder="搜索型号 / 变更内容 / 操作人员"
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

    <ExportColumnsDialog
      v-model="goodsExportDialogVisible"
      title="导出商品分布"
      :options="goodsExportColumnOptions"
      :selected-keys="goodsExportColumnKeys"
      confirm-text="确认导出"
      @update:selected-keys="goodsExportColumnKeys = $event"
      @confirm="confirmGoodsExport"
    />
  </section>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import CollapsePanelTransition from '../components/CollapsePanelTransition.vue'
import ExportColumnsDialog from '../components/ExportColumnsDialog.vue'
import MobileBottomSheet from '../components/MobileBottomSheet.vue'
import ResponsiveDialog from '../components/ResponsiveDialog.vue'
import ResponsiveTableActions from '../components/ResponsiveTableActions.vue'
import { useMobileViewport } from '../composables/useMobileViewport'
import { apiDelete, apiGet, apiPost, apiPut } from '../services/api'
import { useAuthStore } from '../stores/auth'
import { confirmAction, confirmDestructiveAction } from '../utils/confirm'
import { downloadCsvFile, escapeCsvCell } from '../utils/csv'
import { buildLogCenterQuery } from '../utils/logCenter'
import { getShanghaiParts } from '../utils/shanghaiTime'
import { resolveTableActionWidth } from '../utils/tableActions'
import { displayShopName, normalizeLocationRow, SHOP_TYPE_OTHER_WAREHOUSE, SHOP_TYPE_REPAIR, SHOP_TYPE_STORE, SHOP_TYPE_WAREHOUSE } from '../utils/shops'

const authStore = useAuthStore()
const { isMobileViewport } = useMobileViewport()
const route = useRoute()
const router = useRouter()

const loading = ref(false)
const submitting = ref(false)
const keyword = ref('')
const filterPanelOpen = ref(false)
const shopRangeFilter = ref('all')
const storeRows = ref([])
const warehouseRows = ref([])
const otherWarehouseRows = ref([])
const repairRows = ref([])
const userOptions = ref([])

const dialogVisible = ref(false)
const editingId = ref(0)
let shopsFetchSeq = 0
let shopsAbortController = null

const goodsDialogVisible = ref(false)
const goodsDialogLoading = ref(false)
const goodsExportPending = ref(false)
const goodsExportDialogVisible = ref(false)
const goodsExportColumnKeys = ref([])
const goodsMetaLoading = ref(false)
const goodsDialogShop = ref(null)
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
const shopGoodsItems = ref([])
const shopGoodsTotal = ref(0)
const shopGoodsQuantityTotal = ref(0)
const shopGoodsAmountTotal = ref(0)
const goodsPage = ref(1)
const goodsPageSize = ref(20)
const goodsKeyword = ref('')
const goodsBrandFilter = ref('')
const goodsSeriesFilter = ref('')
const goodsModelFilter = ref('')
const goodsAttributeFilter = ref('')
const goodsBarcodeFilter = ref('')
const goodsHasStockFilter = ref('nonzero')
const goodsIndexFilter = ref('')
const goodsSortField = ref('updated_at')
const goodsSortOrder = ref('desc')
let goodsFetchSeq = 0
let goodsAbortController = null
let goodsMetaFetchSeq = 0
let goodsMetaAbortController = null

const goodsMeta = reactive({
  brandOptions: [],
  seriesOptions: [],
  attributeOptions: [],
  indexOptions: [],
})

const typeOptions = [
  { label: '店铺', value: SHOP_TYPE_STORE },
  { label: '仓库', value: SHOP_TYPE_WAREHOUSE },
  { label: '其他仓库', value: SHOP_TYPE_OTHER_WAREHOUSE },
  { label: '维修点', value: SHOP_TYPE_REPAIR },
]

const form = reactive({
  shopType: SHOP_TYPE_STORE,
  name: '',
  phone: '',
  address: '',
  businessHours: '',
  channel: 1,
  scheduleEnabled: false,
  targetEnabled: false,
  reportEnabled: true,
  managerUserId: null,
  salespersonIds: [],
})

const currentUserShopIds = computed(() => {
  const ids = Array.isArray(authStore.user?.shopIds) ? authStore.user.shopIds : []
  const fallback = Number(authStore.user?.shopId || 0)
  const normalized = ids
    .map((item) => Number(item || 0))
    .filter((item) => Number.isInteger(item) && item > 0)
  if (fallback > 0 && !normalized.includes(fallback)) {
    normalized.unshift(fallback)
  }
  return new Set(normalized)
})

function canOpenSchedule(row) {
  if (!authStore.can('shops.read')) {
    return false
  }
  if (!row?.scheduleEnabled) {
    return false
  }
  if (authStore.isAdmin) {
    return true
  }
  return currentUserShopIds.value.has(Number(row?.id || 0))
}

const canShowStoreScheduleAction = computed(() => storeRows.value.some((row) => canOpenSchedule(row)))
function canOpenTarget(row) {
  if (!authStore.can('shops.read')) {
    return false
  }
  if (!row?.targetEnabled) {
    return false
  }
  if (authStore.isAdmin) {
    return true
  }
  return currentUserShopIds.value.has(Number(row?.id || 0))
}

const canShowStoreTargetAction = computed(() => storeRows.value.some((row) => canOpenTarget(row)))

const storeActionColumnWidth = computed(() => resolveTableActionWidth([[
  authStore.can('goods.read') ? '商品' : '',
  canShowStoreScheduleAction.value ? '排班' : '',
  canShowStoreTargetAction.value ? '目标' : '',
  authStore.can('shops.write') ? '编辑' : '',
  authStore.can('shops.manage') ? '删除' : '',
]], {
  compact: isMobileViewport.value,
  minWidth: 112,
  maxWidth: 320,
}))
const warehouseActionColumnWidth = computed(() => resolveTableActionWidth([[
  authStore.can('goods.read') ? '商品' : '',
  authStore.can('shops.write') ? '编辑' : '',
  authStore.can('shops.manage') ? '删除' : '',
]], {
  compact: isMobileViewport.value,
  minWidth: 112,
  maxWidth: 248,
}))
const otherWarehouseActionColumnWidth = computed(() => resolveTableActionWidth([[
  authStore.can('goods.read') ? '商品' : '',
  authStore.can('shops.write') ? '编辑' : '',
  authStore.can('shops.manage') ? '删除' : '',
]], {
  compact: isMobileViewport.value,
  minWidth: 112,
  maxWidth: 248,
}))
const repairActionColumnWidth = computed(() => resolveTableActionWidth([[
  authStore.can('shops.write') ? '编辑' : '',
  authStore.can('shops.manage') ? '删除' : '',
]], {
  compact: isMobileViewport.value,
  minWidth: 112,
  maxWidth: 180,
}))
const canShowRowActions = computed(() => authStore.can('goods.read') || authStore.can('shops.read') || authStore.can('shops.write') || authStore.can('shops.manage'))
const isStoreType = computed(() => Number(form.shopType) === SHOP_TYPE_STORE)
const isRepairType = computed(() => Number(form.shopType) === SHOP_TYPE_REPAIR)
const isOtherWarehouseType = computed(() => Number(form.shopType) === SHOP_TYPE_OTHER_WAREHOUSE)
const showManagerSelector = computed(() => !isOtherWarehouseType.value && !isRepairType.value)
const dialogTitle = computed(() => (editingId.value ? '编辑' : '新增') + activeTypeLabel.value)
const activeTypeLabel = computed(() => (isStoreType.value ? '店铺' : isOtherWarehouseType.value ? '其他仓库' : isRepairType.value ? '维修点' : '仓库'))
const activeNameLabel = computed(() => (isStoreType.value ? '店铺名称' : isOtherWarehouseType.value ? '其他仓库名称' : isRepairType.value ? '维修点名称' : '仓库名称'))
const activeManagerLabel = computed(() => (isStoreType.value ? '店长' : '库管'))
const normalizedShopName = computed(() => cleanText(form.name).toLowerCase())
const reportToggleLocked = computed(() => isStoreType.value && normalizedShopName.value === 'aqc flow')
const reportToggleHint = computed(() => {
  if (reportToggleLocked.value) {
    return 'AQC Flow 不作为正常门店参与报告生成。'
  }
  return ''
})
function isRepairEngineerEligible(option) {
  const roleKey = String(option?.aqcRoleKey || '').trim()
  return roleKey === 'aqc_engineer' || roleKey === 'aqc_admin'
}
const engineerOptions = computed(() => userOptions.value.filter((item) => isRepairEngineerEligible(item)))
const activeManagerName = computed(() => {
  const matched = userOptions.value.find((item) => item.id === Number(form.managerUserId || 0))
  return matched?.displayName || matched?.username || ''
})
const activeGoodsShopName = computed(() => cleanText(goodsDialogShop.value?.name))
const activeInventoryLogShopName = computed(() => cleanText(inventoryLogTarget.value?.name))
const distributionModelTitle = computed(() => buildItemName(distributionItem.value) || '当前商品')
const distributionPositiveCount = computed(() => distributionInventories.value.filter((item) => Number(item.quantity || 0) > 0).length)
const distributionHeroSubtitle = computed(() => buildInventorySubtitle(distributionItem.value, distributionPositiveCount.value))
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
const shopGoodsActionColumnWidth = computed(() => resolveTableActionWidth([['分布']], {
  compact: isMobileViewport.value,
  minWidth: 112,
  maxWidth: 148,
}))
const goodsExportColumnOptions = computed(() => ([
  { key: 'shopName', label: '店铺/仓库' },
  { key: 'brand', label: '品牌' },
  { key: 'series', label: '系列' },
  { key: 'model', label: '型号' },
  { key: 'modelAttribute', label: '属性' },
  { key: 'price', label: '单价' },
  { key: 'shopQuantity', label: '数量' },
  { key: 'lineAmount', label: '金额' },
  { key: 'barcode', label: '条码' },
]))
const activeShopFilterCount = computed(() => {
  let count = 0
  if (shopRangeFilter.value && shopRangeFilter.value !== 'all') count += 1
  return count
})

const priceFormatter = new Intl.NumberFormat('zh-CN', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

function cleanText(value) {
  return String(value || '').trim()
}

function formatMoney(value) {
  return priceFormatter.format(Number(value || 0))
}

function formatExportMoney(value) {
  const amount = Number(value || 0)
  if (!Number.isFinite(amount)) {
    return '0'
  }
  return amount.toFixed(2).replace(/\.?0+$/, '')
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

function formatShopType(shopType) {
  return Number(shopType || 0) === SHOP_TYPE_WAREHOUSE
    ? '仓库'
    : Number(shopType || 0) === SHOP_TYPE_OTHER_WAREHOUSE
      ? '其他仓库'
      : Number(shopType || 0) === SHOP_TYPE_REPAIR
        ? '维修点'
        : '店铺'
}

function shopGoodsTableSummary({ columns, data }) {
  const totalQuantity = data.reduce((sum, item) => sum + Number(item.shopQuantity || 0), 0)
  const totalAmount = data.reduce((sum, item) => (
    sum + Number(item.price || 0) * Number(item.shopQuantity || 0)
  ), 0)
  return columns.map((column, index) => {
    if (index === 0) {
      return '合计'
    }
    if (column.property === 'shopQuantity') {
      return String(totalQuantity)
    }
    if (column.property === 'lineAmount') {
      return `¥ ${formatMoney(totalAmount)}`
    }
    return ''
  })
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

function buildShopGoodsExportFilename() {
  const parts = getShanghaiParts(new Date())
  const shopName = cleanText(goodsDialogShop.value?.name || '店铺仓库')
  return `${shopName}-商品分布-${parts.year}${parts.month}${parts.day}-${parts.hour}${parts.minute}${parts.second}.csv`
}

function resetForm() {
  form.shopType = SHOP_TYPE_STORE
  form.name = ''
  form.phone = ''
  form.address = ''
  form.businessHours = ''
  form.channel = 1
  form.scheduleEnabled = false
  form.targetEnabled = false
  form.reportEnabled = true
  form.managerUserId = null
  form.salespersonIds = []
}

function formatUserOption(item) {
  const name = cleanText(item.displayName || item.username)
  const phone = cleanText(item.username)
  return name && name !== phone ? name + '（' + phone + '）' : phone || name
}

function normalizeUserIds(ids) {
  return [...new Set((ids || []).map((item) => Number(item)).filter((item) => Number.isInteger(item) && item > 0))]
}

function onManagerChange(value) {
  if (!isStoreType.value) {
    return
  }
  const nextManagerId = Number(value || 0)
  if (!nextManagerId) {
    return
  }
  if (!form.salespersonIds.includes(nextManagerId)) {
    form.salespersonIds = normalizeUserIds([...form.salespersonIds, nextManagerId])
  }
}

function openReportCenter() {
  void router.push({
    name: 'reports',
    query: {
      back: route.fullPath,
    },
  })
}

async function loadUsers() {
  const payload = await apiGet('/users/options', {
    token: authStore.token,
    query: { limit: '300' },
  })
  if (!payload?.success) {
    userOptions.value = []
    ElMessage.error(payload?.message || '账户列表加载失败')
    return
  }
  userOptions.value = payload.options || []
}

async function loadLists() {
  const seq = ++shopsFetchSeq
  if (shopsAbortController) {
    shopsAbortController.abort()
  }
  const controller = new AbortController()
  shopsAbortController = controller
  loading.value = true

  try {
    const [storesPayload, warehousesPayload, otherWarehousesPayload, repairPayload] = await Promise.all([
      apiGet('/shops', {
        token: authStore.token,
        signal: controller.signal,
        query: {
          page: '1',
          page_size: '100',
          shop_type: String(SHOP_TYPE_STORE),
          ...(keyword.value ? { q: keyword.value } : {}),
        },
      }),
      apiGet('/shops', {
        token: authStore.token,
        signal: controller.signal,
        query: {
          page: '1',
          page_size: '100',
          shop_type: String(SHOP_TYPE_WAREHOUSE),
          ...(keyword.value ? { q: keyword.value } : {}),
        },
      }),
      apiGet('/shops', {
        token: authStore.token,
        signal: controller.signal,
        query: {
          page: '1',
          page_size: '100',
          shop_type: String(SHOP_TYPE_OTHER_WAREHOUSE),
          ...(keyword.value ? { q: keyword.value } : {}),
        },
      }),
      apiGet('/shops', {
        token: authStore.token,
        signal: controller.signal,
        query: {
          page: '1',
          page_size: '100',
          shop_type: String(SHOP_TYPE_REPAIR),
          ...(keyword.value ? { q: keyword.value } : {}),
        },
      }),
    ])

    if (seq !== shopsFetchSeq) {
      return
    }
    if (!storesPayload?.success || !warehousesPayload?.success || !otherWarehousesPayload?.success || !repairPayload?.success) {
      ElMessage.error(storesPayload?.message || warehousesPayload?.message || otherWarehousesPayload?.message || repairPayload?.message || '店铺/仓库数据加载失败')
      return
    }

    storeRows.value = storesPayload.shops || []
    warehouseRows.value = warehousesPayload.shops || []
    otherWarehouseRows.value = otherWarehousesPayload.shops || []
    repairRows.value = repairPayload.shops || []

    if (shopRangeFilter.value === 'store') {
      warehouseRows.value = []
      otherWarehouseRows.value = []
      repairRows.value = []
    } else if (shopRangeFilter.value === 'warehouse') {
      storeRows.value = []
      otherWarehouseRows.value = []
      repairRows.value = []
    } else if (shopRangeFilter.value === 'other') {
      storeRows.value = []
      warehouseRows.value = []
      repairRows.value = []
    } else if (shopRangeFilter.value === 'repair') {
      storeRows.value = []
      warehouseRows.value = []
      otherWarehouseRows.value = []
    }
  } finally {
    if (shopsAbortController === controller) {
      shopsAbortController = null
    }
    if (seq === shopsFetchSeq) {
      loading.value = false
    }
  }
}

function onSearch() {
  void loadLists()
}

function onResetFilters() {
  keyword.value = ''
  shopRangeFilter.value = 'all'
  filterPanelOpen.value = false
  void loadLists()
}

function buildGoodsQuery() {
  const shopId = Number(goodsDialogShop.value?.id || 0)
  return {
    page: String(goodsPage.value),
    page_size: String(goodsPageSize.value),
    catalog_only: 'true',
    distribution_shop_id: String(shopId),
    sort_field: goodsSortField.value,
    sort_order: goodsSortOrder.value,
    ...(goodsKeyword.value ? { q: goodsKeyword.value } : {}),
    ...(goodsBrandFilter.value ? { brand: goodsBrandFilter.value } : {}),
    ...(goodsSeriesFilter.value ? { series: goodsSeriesFilter.value } : {}),
    ...(goodsModelFilter.value ? { model: goodsModelFilter.value } : {}),
    ...(goodsAttributeFilter.value ? { model_attribute: goodsAttributeFilter.value } : {}),
    ...(goodsBarcodeFilter.value ? { barcode: goodsBarcodeFilter.value } : {}),
    ...(goodsHasStockFilter.value ? { has_stock: goodsHasStockFilter.value } : {}),
    ...(goodsIndexFilter.value ? { index_key: goodsIndexFilter.value } : {}),
  }
}

function buildGoodsMetaQuery() {
  const query = buildGoodsQuery()
  delete query.page
  delete query.page_size
  delete query.sort_field
  delete query.sort_order
  return query
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

async function loadGoodsMeta() {
  const seq = ++goodsMetaFetchSeq
  if (goodsMetaAbortController) {
    goodsMetaAbortController.abort()
  }
  const controller = new AbortController()
  goodsMetaAbortController = controller
  goodsMetaLoading.value = true

  try {
    const payload = await apiGet('/goods/catalog/meta', {
      token: authStore.token,
      timeoutMs: 12000,
      signal: controller.signal,
      query: buildGoodsMetaQuery(),
    })
    if (seq !== goodsMetaFetchSeq || !payload?.success) {
      return
    }
    goodsMeta.brandOptions = payload.brandOptions || []
    goodsMeta.seriesOptions = payload.seriesOptions || []
    goodsMeta.attributeOptions = payload.attributeOptions || []
    goodsMeta.indexOptions = payload.indexOptions || []
  } finally {
    if (goodsMetaAbortController === controller) {
      goodsMetaAbortController = null
    }
    if (seq === goodsMetaFetchSeq) {
      goodsMetaLoading.value = false
    }
  }
}

async function loadShopGoods() {
  const shopId = Number(goodsDialogShop.value?.id || 0)
  if (!shopId) {
    shopGoodsItems.value = []
    shopGoodsTotal.value = 0
    shopGoodsQuantityTotal.value = 0
    shopGoodsAmountTotal.value = 0
    return
  }

  const seq = ++goodsFetchSeq
  if (goodsAbortController) {
    goodsAbortController.abort()
  }
  const controller = new AbortController()
  goodsAbortController = controller
  goodsDialogLoading.value = true

  try {
    const payload = await apiGet('/goods/items', {
      token: authStore.token,
      timeoutMs: 12000,
      signal: controller.signal,
      query: buildGoodsQuery(),
    })
    if (seq !== goodsFetchSeq) {
      return
    }
    if (!payload?.success) {
      ElMessage.error(payload?.message || '商品目录加载失败')
      return
    }
    shopGoodsItems.value = payload.items || []
    shopGoodsTotal.value = Number(payload.total || 0)
    shopGoodsQuantityTotal.value = Number(payload.shopQuantityTotal || 0)
    shopGoodsAmountTotal.value = Number(payload.shopAmountTotal || 0)
  } finally {
    if (goodsAbortController === controller) {
      goodsAbortController = null
    }
    if (seq === goodsFetchSeq) {
      goodsDialogLoading.value = false
    }
  }
}

async function fetchDistributionPayload(itemId) {
  return apiGet('/goods/items/' + itemId + '/inventory', {
    token: authStore.token,
    timeoutMs: 12000,
  })
}

function primeDistributionState(payload) {
  distributionItem.value = payload?.item || null
  distributionInventories.value = (payload?.inventories || []).map((item) => normalizeLocationRow(item, item.shopType))
  distributionTotalStock.value = Number(payload?.totalStock || 0)
}

async function fetchAllShopGoodsForExport() {
  const pageSize = 200
  let currentPage = 1
  let totalCount = 0
  const rows = []

  while (true) {
    const payload = await apiGet('/goods/items', {
      token: authStore.token,
      timeoutMs: 20000,
      query: {
        ...buildGoodsQuery(),
        page: String(currentPage),
        page_size: String(pageSize),
      },
    })
    if (!payload?.success) {
      throw new Error(payload?.message || '商品分布导出失败')
    }
    const items = payload.items || []
    totalCount = Number(payload.total || items.length || 0)
    rows.push(...items)
    if (!items.length || rows.length >= totalCount) {
      break
    }
    currentPage += 1
  }

  return rows
}

async function exportShopGoodsTable() {
  return confirmGoodsExport(goodsExportColumnKeys.value)
}

function ensureGoodsExportSelection() {
  const validKeys = new Set(goodsExportColumnOptions.value.map((item) => item.key))
  const nextKeys = (goodsExportColumnKeys.value || []).filter((key) => validKeys.has(key))
  goodsExportColumnKeys.value = nextKeys.length ? nextKeys : goodsExportColumnOptions.value.map((item) => item.key)
}

function openGoodsExportDialog() {
  if (!goodsDialogShop.value?.id) {
    ElMessage.warning('请先打开一个店铺 / 仓库的商品分布')
    return
  }
  ensureGoodsExportSelection()
  goodsExportDialogVisible.value = true
}

function formatGoodsExportCell(item, key, shopName) {
  if (key === 'shopName') {
    return shopName
  }
  if (key === 'price') {
    return formatExportMoney(item.price)
  }
  if (key === 'shopQuantity') {
    return String(Number(item.shopQuantity || 0))
  }
  if (key === 'lineAmount') {
    return formatExportMoney(Number(item.price || 0) * Number(item.shopQuantity || 0))
  }
  return cleanText(item?.[key])
}

async function confirmGoodsExport(selectedKeys) {
  if (!goodsDialogShop.value?.id) {
    ElMessage.warning('请先打开一个店铺 / 仓库的商品分布')
    return
  }
  const keys = Array.isArray(selectedKeys) ? selectedKeys.filter(Boolean) : []
  if (!keys.length) {
    ElMessage.warning('请至少选择一列')
    return
  }
  try {
    await confirmAction('确认导出当前商品分布吗？导出内容会遵循当前筛选条件和排序。', '导出确认', '确认导出')
  } catch (_error) {
    return
  }
  goodsExportPending.value = true
  try {
    const rows = await fetchAllShopGoodsForExport()
    if (!rows.length) {
      ElMessage.warning('当前筛选条件下没有可导出的数据')
      return
    }
    const optionMap = new Map(goodsExportColumnOptions.value.map((item) => [item.key, item.label]))
    const shopName = cleanText(goodsDialogShop.value?.name)
    const totalQuantity = rows.reduce((sum, item) => sum + Number(item.shopQuantity || 0), 0)
    const totalAmount = rows.reduce((sum, item) => sum + Number(item.price || 0) * Number(item.shopQuantity || 0), 0)
    const header = ['序号', ...keys.map((key) => optionMap.get(key) || key)]
    const dataLines = rows.map((item, index) => [String(index + 1), ...keys.map((key) => formatGoodsExportCell(item, key, shopName))])
    const summaryLine = ['', ...keys.map((key, index) => {
      if (index === 0) {
        return '合计'
      }
      if (key === 'shopQuantity') {
        return String(totalQuantity)
      }
      if (key === 'lineAmount') {
        return formatExportMoney(totalAmount)
      }
      return ''
    })]
    const csvContent = [header, ...dataLines, summaryLine]
      .map((line) => line.map(escapeCsvCell).join(','))
      .join('\n')
    downloadCsvFile(buildShopGoodsExportFilename(), csvContent)
    goodsExportDialogVisible.value = false
    ElMessage.success(`已导出 ${rows.length} 条商品分布`)
  } catch (error) {
    ElMessage.error(error?.message || '商品分布导出失败')
  } finally {
    goodsExportPending.value = false
  }
}

function resetGoodsFilters() {
  goodsKeyword.value = ''
  goodsBrandFilter.value = ''
  goodsSeriesFilter.value = ''
  goodsModelFilter.value = ''
  goodsAttributeFilter.value = ''
  goodsBarcodeFilter.value = ''
  goodsHasStockFilter.value = 'nonzero'
  goodsIndexFilter.value = ''
  goodsSortField.value = 'updated_at'
  goodsSortOrder.value = 'desc'
  goodsPage.value = 1
  void Promise.all([loadGoodsMeta(), loadShopGoods()])
}

function onGoodsBrandChange() {
  if (goodsSeriesFilter.value && !goodsMeta.seriesOptions.some((item) => item.value === goodsSeriesFilter.value)) {
    goodsSeriesFilter.value = ''
  }
  goodsPage.value = 1
  void Promise.all([loadGoodsMeta(), loadShopGoods()])
}

function setGoodsIndexFilter(value) {
  goodsIndexFilter.value = value
  goodsPage.value = 1
  void Promise.all([loadGoodsMeta(), loadShopGoods()])
}

function onGoodsSearch() {
  goodsPage.value = 1
  void Promise.all([loadGoodsMeta(), loadShopGoods()])
}

function onGoodsSortChange({ prop, order }) {
  if (!prop || !order) {
    goodsSortField.value = 'updated_at'
    goodsSortOrder.value = 'desc'
  } else {
    const map = {
      brand: 'brand',
      series: 'series',
      model: 'model',
      price: 'price',
      barcode: 'barcode',
    }
    goodsSortField.value = map[prop] || 'updated_at'
    goodsSortOrder.value = order === 'ascending' ? 'asc' : 'desc'
  }
  goodsPage.value = 1
  void loadShopGoods()
}

function onGoodsPageChange(nextPage) {
  goodsPage.value = nextPage
  void loadShopGoods()
}

function onGoodsPageSizeChange(nextSize) {
  goodsPageSize.value = nextSize
  goodsPage.value = 1
  void loadShopGoods()
}

async function openGoodsDialog(row) {
  goodsDialogShop.value = row
  goodsDialogVisible.value = true
  goodsKeyword.value = ''
  goodsBrandFilter.value = ''
  goodsSeriesFilter.value = ''
  goodsModelFilter.value = ''
  goodsAttributeFilter.value = ''
  goodsBarcodeFilter.value = ''
  goodsHasStockFilter.value = 'nonzero'
  goodsIndexFilter.value = ''
  goodsSortField.value = 'updated_at'
  goodsSortOrder.value = 'desc'
  goodsPage.value = 1
  goodsPageSize.value = 20
  await Promise.all([loadGoodsMeta(), loadShopGoods()])
}

async function openShopGoodsDistribution(row) {
  const goodsId = Number(row?.id || 0)
  if (!goodsId) {
    ElMessage.warning('当前商品信息未准备完成')
    return
  }
  distributionDialogVisible.value = true
  distributionLoading.value = true
  const payload = await fetchDistributionPayload(goodsId)
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

async function openDistributionInventoryLogCenter() {
  const goodsId = Number(distributionItem.value?.id || 0)
  if (!goodsId) {
    ElMessage.warning('当前商品信息未准备完成')
    return
  }
  distributionActionMenuVisible.value = false
  distributionDialogVisible.value = false
  await router.push({
    name: 'log-center',
    query: buildLogCenterQuery({
      type: 'goods_inventory',
      item_id: String(goodsId),
      subject_name: buildItemName(distributionItem.value),
      back: router.resolve({
        name: 'shops-manage',
        query: {
          ...route.query,
          spotlight_shop: String(goodsDialogShop.value?.id || ''),
        },
      }).fullPath,
    }),
  })
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
      back: router.resolve({
        name: 'shops-manage',
        query: {
          ...route.query,
          spotlight_shop: String(goodsDialogShop.value?.id || ''),
        },
      }).fullPath,
    }),
  })
}

function openSchedule(row) {
  if (!row?.scheduleEnabled) {
    ElMessage.warning('当前店铺未开启排班功能')
    return
  }
  if (!canOpenSchedule(row)) {
    ElMessage.warning('当前账号仅可查看本人所在店铺的排班')
    return
  }
  router.push({
    name: 'shop-schedule',
    params: { shopId: row.id },
  })
}

function openTarget(row) {
  if (!row?.targetEnabled) {
    ElMessage.warning('当前店铺未开启目标功能')
    return
  }
  if (!canOpenTarget(row)) {
    ElMessage.warning('当前账号仅可查看本人所在店铺的目标页')
    return
  }
  router.push({
    name: 'shop-target',
    params: { shopId: row.id },
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

async function applyShopSpotlightFromRoute() {
  const shopId = Number(route.query.spotlight_shop || 0)
  if (!shopId) {
    return
  }

  const matchedRow = [...storeRows.value, ...warehouseRows.value, ...otherWarehouseRows.value, ...repairRows.value]
    .find((item) => Number(item.id || 0) === shopId)
  if (matchedRow) {
    await openGoodsDialog(matchedRow)
  }
  await consumeSpotlightQuery(['spotlight_shop'])
}

async function loadInventoryLogs() {
  const shopId = Number(inventoryLogTarget.value?.id || 0)
  if (!shopId) {
    inventoryLogRows.value = []
    inventoryLogTotal.value = 0
    inventoryLogCurrentTotal.value = 0
    return
  }

  inventoryLogLoading.value = true
  const payload = await apiGet('/shops/' + shopId + '/inventory-logs', {
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

async function openInventoryLogDialog(row) {
  if (!row?.id) {
    ElMessage.warning('请先选择一个店铺 / 仓库')
    return
  }
  await router.push({
    name: 'log-center',
    query: {
      type: 'shop_inventory',
      shop_id: String(row.id),
      subject_name: row.name || '当前店铺 / 仓库',
      back: router.resolve({
        name: 'shops-manage',
        query: {
          ...route.query,
          spotlight_shop: String(row.id),
        },
      }).fullPath,
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

async function openCreate() {
  editingId.value = 0
  resetForm()
  await loadUsers()
  dialogVisible.value = true
}

async function openEdit(row) {
  editingId.value = row.id
  form.shopType = Number(row.shopType || SHOP_TYPE_STORE)
  form.name = row.name || ''
  form.phone = row.phone || ''
  form.address = row.address || ''
  form.businessHours = row.businessHours || ''
  form.channel = Number(row.channel || 1)
  form.scheduleEnabled = Boolean(row.scheduleEnabled)
  form.targetEnabled = Boolean(row.targetEnabled)
  form.reportEnabled = Boolean(row.reportEnabled)
  form.managerUserId = row.managerUserId || null
  form.salespersonIds = normalizeUserIds(row.salespersonIds || [])
  await loadUsers()
  dialogVisible.value = true
}

function buildPayload() {
  const isExternal = isOtherWarehouseType.value
  const salespersonIds = isStoreType.value
    ? normalizeUserIds([
      ...form.salespersonIds,
      ...(form.managerUserId ? [form.managerUserId] : []),
    ])
    : (isRepairType.value ? normalizeUserIds(form.salespersonIds) : [])

  return {
    name: form.name,
    phone: isStoreType.value || isRepairType.value ? form.phone : null,
    address: isStoreType.value || isRepairType.value ? form.address : null,
    businessHours: isStoreType.value || isRepairType.value ? form.businessHours : null,
    channel: isStoreType.value ? Number(form.channel || 1) : 1,
    scheduleEnabled: isStoreType.value ? Boolean(form.scheduleEnabled) : false,
    targetEnabled: isStoreType.value ? Boolean(form.targetEnabled) : false,
    reportEnabled: isStoreType.value ? Boolean(form.reportEnabled) : false,
    shopType: Number(form.shopType || SHOP_TYPE_STORE),
    managerUserId: isExternal || isRepairType.value ? null : (form.managerUserId || null),
    managerName: '',
    salespersonIds,
  }
}

async function onSubmit() {
  if (!form.name.trim()) {
    ElMessage.warning('请输入' + activeTypeLabel.value + '名称')
    return
  }

  submitting.value = true
  const payload = editingId.value
    ? await apiPut('/shops/' + editingId.value, buildPayload(), { token: authStore.token })
    : await apiPost('/shops', buildPayload(), { token: authStore.token })
  submitting.value = false

  if (!payload?.success) {
    ElMessage.error(payload?.message || '保存失败')
    return
  }

  ElMessage.success(payload.message || '保存成功')
  dialogVisible.value = false
  await loadLists()
}

async function onDelete(shopId, shopType) {
  const typeLabel = Number(shopType) === SHOP_TYPE_WAREHOUSE ? '仓库' : Number(shopType) === SHOP_TYPE_OTHER_WAREHOUSE ? '其他仓库' : Number(shopType) === SHOP_TYPE_REPAIR ? '维修点' : '店铺'
  try {
    await confirmDestructiveAction('确认删除这个' + typeLabel + '吗？删除后关联商品会失去归属。')
  } catch (error) {
    return
  }
  const payload = await apiDelete('/shops/' + shopId, {
    token: authStore.token,
  })
  if (!payload?.success) {
    ElMessage.error(payload?.message || '删除失败')
    return
  }
  ElMessage.success(payload.message || '删除成功')
  await loadLists()
}

onMounted(async () => {
  await Promise.all([loadLists(), loadUsers()])
  await applyShopSpotlightFromRoute()
})

watch(
  () => route.query.spotlight_shop,
  (shopId) => {
    if (!shopId) {
      return
    }
    void applyShopSpotlightFromRoute()
  },
)

onBeforeUnmount(() => {
  shopsFetchSeq += 1
  goodsFetchSeq += 1
  goodsMetaFetchSeq += 1

  if (shopsAbortController) {
    shopsAbortController.abort()
  }
  if (goodsAbortController) {
    goodsAbortController.abort()
  }
  if (goodsMetaAbortController) {
    goodsMetaAbortController.abort()
  }
})
</script>
