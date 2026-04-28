<template>
  <section class="work-order-page">
    <section class="catalog-controls card-surface motion-fade-slide work-order-controls" style="--motion-delay: 0.08s">
      <div class="goods-search-shell work-order-search-shell">
        <el-input
          v-model.trim="keyword"
          clearable
          placeholder="搜索工单编号 / 事由 / 申请人 / 负责人 / 点位 / 单位"
          class="goods-search-input work-order-search-input"
          @keyup.enter="onSearch"
        />

        <div class="toolbar-actions goods-search-actions work-order-search-actions">
          <el-button type="primary" :loading="loading" @click="onSearch">查询</el-button>
          <el-button @click="onResetFilters">重置</el-button>
          <el-button v-if="canWrite" @click="openGroupDialog">群组管理</el-button>
          <el-button v-if="canManageScheduledOrders" @click="openWorkOrderSettingsDialog">工单设置</el-button>
          <el-button @click="openLogDialog">工单日志</el-button>
          <el-button v-if="canWrite" type="primary" @click="openCreateDialog()">新建工单</el-button>
        </div>
      </div>

      <section class="sales-filter-shell goods-filter-shell work-order-filter-shell">
        <div class="sales-filter-trigger-row">
          <button type="button" class="sales-filter-trigger" :class="{ active: filterPanelOpen }" @click="filterPanelOpen = !filterPanelOpen">
            <div class="sales-filter-trigger-copy">
              <span>筛选</span>
              <strong>{{ filterPanelOpen ? '收起工单筛选' : '展开工单筛选' }}</strong>
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
            <section class="sales-filter-panel goods-filter-panel work-order-filter-panel">
              <header class="sales-filter-head">
              <div class="sales-filter-head-copy">
                <h2>筛选</h2>
                <span>{{ activeScopeLabel }} · {{ total }} 条工单</span>
              </div>
              <div class="toolbar-actions sales-filter-head-actions">
                <el-button type="primary" :loading="loading" @click="onSearch">查询</el-button>
                <el-button class="sales-filter-reset-btn" :disabled="!activeFilterCount" @click="onResetFilters">清空筛选</el-button>
              </div>
            </header>

              <div class="sales-filter-grid work-order-filter-grid">
              <div class="sales-filter-field sales-filter-field-wide">
                <label class="sales-filter-label">工单时间</label>
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

              <div class="sales-filter-field">
                <label class="sales-filter-label">工单类型</label>
                <el-select v-model="orderTypeFilter" clearable class="full-width" placeholder="全部类型">
                  <el-option
                    v-for="item in meta.types"
                    :key="item.value"
                    :label="item.label"
                    :value="item.value"
                  />
                </el-select>
              </div>

              <div class="sales-filter-field">
                <label class="sales-filter-label">状态</label>
                <el-select
                  v-model="statusFilter"
                  clearable
                  class="full-width"
                  placeholder="全部状态"
                  :disabled="statusFilterLocked"
                >
                  <el-option
                    v-for="item in meta.statuses"
                    :key="item.value"
                    :label="item.label"
                    :value="item.value"
                  />
                </el-select>
              </div>

              <div class="sales-filter-field">
                <label class="sales-filter-label">申请人</label>
                <el-select
                  v-model="applicantFilter"
                  clearable
                  filterable
                  class="full-width"
                  placeholder="搜索申请人"
                >
                  <el-option
                    v-for="item in meta.applicantOptions"
                    :key="item.id"
                    :label="item.displayName || item.username"
                    :value="item.id"
                  />
                </el-select>
              </div>

              <div v-if="canFilterApprover" class="sales-filter-field">
                <label class="sales-filter-label">负责人</label>
                <el-select
                  v-model="approverFilter"
                  clearable
                  filterable
                  class="full-width"
                  placeholder="搜索负责人"
                >
                  <el-option
                    v-for="item in meta.approverOptions"
                    :key="item.id"
                    :label="item.displayName || item.username"
                    :value="item.id"
                  />
                </el-select>
              </div>
              </div>
            </section>
          </div>
        </CollapsePanelTransition>
      </section>
    </section>

    <section class="catalog-table card-surface motion-fade-slide work-order-table-card" style="--motion-delay: 0.12s">
      <div class="work-order-table-topbar">
        <div class="work-order-tab-row work-order-scope-row work-order-scope-row-large">
          <button
            v-for="item in scopeOptions"
            :key="item.value"
            type="button"
            class="work-order-tab work-order-tab-large"
            :class="{ active: scope === item.value }"
            @click="setScope(item.value)"
          >
            <span>{{ item.label }}</span>
            <small v-if="item.badge !== undefined">{{ item.badge }}</small>
          </button>
        </div>

        <div v-if="dashboard.pendingApprovals.length && canApprove" class="work-order-approval-strip work-order-approval-strip-inline">
          <span class="sales-filter-label">待我审核</span>
          <div class="work-order-chip-row">
            <button
              v-for="item in dashboard.pendingApprovals"
              :key="item.id"
              type="button"
              class="work-order-approval-chip"
              @click="openDetail(item.id, true)"
            >
              <strong>{{ item.orderTypeLabel }}</strong>
              <span>{{ replaceShopNameAliases(item.reason) || item.orderNum }}</span>
              <small>{{ item.orderNum }}</small>
            </button>
          </div>
        </div>
      </div>

      <div class="table-shell open-table-shell">
        <el-table :data="orders" border stripe v-loading="loading" empty-text="暂无工单记录">
          <el-table-column prop="orderCategoryLabel" label="工单大类" min-width="120" />
          <el-table-column prop="orderTypeLabel" label="工单类型" min-width="120" />
          <el-table-column label="工单事由" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">{{ replaceShopNameAliases(row.reason) || '-' }}</template>
          </el-table-column>
          <el-table-column prop="statusLabel" label="状态" min-width="100" />
          <el-table-column prop="formDate" label="工单日期" min-width="170" show-overflow-tooltip />
          <el-table-column prop="orderNum" label="工单编号" min-width="180" show-overflow-tooltip />
          <el-table-column prop="applicantName" label="申请人" min-width="120" show-overflow-tooltip />
          <el-table-column prop="approverName" label="负责人" min-width="120" show-overflow-tooltip />
          <el-table-column label="操作" :width="tableActionWidth" fixed="right">
            <template #default="{ row }">
              <ResponsiveTableActions :menu-width="168">
                <el-button text type="primary" @click="openDetail(row.id)">查看</el-button>
                <el-button v-if="canAllocateRow(row)" text type="primary" @click="openAllocationDialog(row.id)">分配</el-button>
                <el-button v-if="canEditRow(row)" text type="primary" @click="openEditDialog(row.id)">编辑</el-button>
                <el-button v-if="canWithdrawRow(row)" text type="warning" @click="confirmWithdrawOrder(row)">转草稿</el-button>
                <el-button v-if="canDeleteRow(row)" text type="danger" @click="confirmDeleteOrder(row)">删除</el-button>
                <el-button v-if="canReviewRow(row)" text type="success" @click="openDetail(row.id, true)">审批</el-button>
                <el-button text @click="printById(row.id)">打印</el-button>
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
          :page-sizes="[20, 50, 100]"
          @current-change="onPageChange"
          @size-change="onPageSizeChange"
        />
      </div>
    </section>

    <el-dialog
      v-model="categoryDialogVisible"
      title="新建工单"
      width="min(820px, 94vw)"
      append-to-body
      align-center
      destroy-on-close
      class="aqc-app-dialog work-order-category-dialog"
    >
      <section class="work-order-category-chooser">
        <button
          v-for="item in categoryOptions"
          :key="item.value"
          type="button"
          class="work-order-category-card"
          @click="openCreateDialogByCategory(item.value)"
        >
          <strong>{{ item.label }}</strong>
          <small>{{ describeCategoryTypes(item.value) }}</small>
        </button>
      </section>
    </el-dialog>

    <ResponsiveDialog
      v-model="editorVisible"
      :title="editorTitle"
      width="min(1320px, 98vw)"
      :before-close="handleEditorDialogBeforeClose"
      class="aqc-app-dialog work-order-editor-dialog"
      mobile-subtitle="工单管理"
      :initial-snap="0.66"
      :expanded-snap="0.96"
      :mobile-base-z-index="2400"
    >
      <div class="work-order-editor-shell">
        <div class="goods-step-strip work-order-step-strip">
          <button
            v-for="step in editorStepOptions"
            :key="step.value"
            type="button"
            class="goods-step-button"
            :class="{ active: editorStep === step.value, completed: editorStep > step.value }"
            :disabled="step.value === 2 && !editorAllItems.length"
            @click="goToEditorStep(step.value)"
          >
            <span class="step-number">{{ step.value }}</span>
            <span>{{ step.label }}</span>
          </button>
        </div>

        <section v-show="editorStep === 1" class="card-surface work-order-editor-panel">
          <div class="panel-head-simple">
            <div>
              <h3>工单信息</h3>
            </div>
          </div>

          <div class="work-order-category-strip">
            <button
              v-for="item in categoryOptions"
              :key="item.value"
              type="button"
              class="work-order-category-pill"
              :class="{ active: currentCategory === item.value }"
              @click="changeOrderType(defaultTypeForCategory(item.value))"
            >
              <span>{{ item.label }}</span>
            </button>
          </div>

          <div class="work-order-type-strip">
            <button
              v-for="item in visibleTypeOptions"
              :key="item.value"
              type="button"
              class="work-order-type-card"
              :class="{ active: form.orderType === item.value }"
              @click="changeOrderType(item.value)"
            >
              <span>{{ item.prefix }}</span>
              <strong>{{ item.label }}</strong>
            </button>
          </div>

          <el-form label-position="top" class="dialog-form">
            <div class="sales-filter-grid work-order-header-grid">
              <div class="sales-filter-field sales-filter-field-wide">
                <label class="sales-filter-label">事由</label>
                <el-input
                  v-model.trim="form.reason"
                  maxlength="255"
                  :placeholder="defaultReason"
                />
              </div>

              <div v-if="showSourceSelector" class="sales-filter-field">
                <label class="sales-filter-label">{{ sourceLabel }}</label>
                <el-select
                  v-model="form.sourceShopId"
                  clearable
                  filterable
                  class="full-width"
                  :placeholder="`请选择${sourceLabel}`"
                >
                  <el-option
                    v-for="item in sourceOptions"
                    :key="item.id"
                    :label="displayShopName(item.name)"
                    :value="item.id"
                  />
                </el-select>
              </div>

              <div v-if="form.orderType === 'sale'" class="sales-filter-field">
                <label class="sales-filter-label">变动库存</label>
                <el-switch
                  v-model="form.saleAffectsInventory"
                  @change="onSaleAffectsInventoryChange"
                />
              </div>

              <div v-if="form.orderType === 'sale' && form.saleAffectsInventory" class="sales-filter-field">
                <label class="sales-filter-label">发货店铺/仓库</label>
                <el-select
                  v-model="saleShipShopId"
                  clearable
                  filterable
                  class="full-width"
                  placeholder="请选择发货店铺/仓库"
                  @change="onSaleHeaderShipShopChange"
                >
                  <el-option
                    v-for="item in stockLocationOptions"
                    :key="`sale-header-ship-${item.id}`"
                    :label="displayShopName(item.name)"
                    :value="item.id"
                  />
                </el-select>
              </div>

              <div v-if="showTargetSelector" class="sales-filter-field">
                <label class="sales-filter-label">{{ targetLabel }}</label>
                <el-select
                  v-model="form.targetShopId"
                  clearable
                  filterable
                  class="full-width"
                  :placeholder="`请选择${targetLabel}`"
                >
                  <el-option
                    v-for="item in targetOptions"
                    :key="item.id"
                    :label="displayShopName(item.name)"
                    :value="item.id"
                  />
                </el-select>
              </div>

              <div v-if="form.orderType === 'purchase'" class="sales-filter-field">
                <label class="sales-filter-label">供货单位</label>
                <el-autocomplete
                  v-model="form.supplierName"
                  class="full-width"
                  :fetch-suggestions="fetchOtherWarehouseSuggestions"
                  clearable
                  maxlength="255"
                  placeholder="请输入供货单位"
                />
              </div>

              <div v-if="form.orderType === 'return'" class="sales-filter-field">
                <label class="sales-filter-label">收货单位</label>
                <el-autocomplete
                  v-model="form.partnerName"
                  class="full-width"
                  :fetch-suggestions="fetchOtherWarehouseSuggestions"
                  clearable
                  maxlength="255"
                  placeholder="请输入收货单位"
                />
              </div>

              <div class="sales-filter-field">
                <label class="sales-filter-label">申请人</label>
                <el-input :model-value="applicantName" readonly />
              </div>

              <div class="sales-filter-field">
                <label class="sales-filter-label">负责人</label>
                <el-select
                  v-model="form.approverId"
                  clearable
                  filterable
                  class="full-width"
                  :placeholder="approverPlaceholder"
                >
                  <el-option
                    v-for="item in meta.approverOptions"
                    :key="item.id"
                    :label="item.displayName ? `${item.displayName} · ${item.username}` : item.username"
                    :value="item.id"
                  />
                </el-select>
              </div>

              <div class="sales-filter-field">
                <label class="sales-filter-label">共享群组</label>
                <el-select
                  v-model="form.groupId"
                  filterable
                  class="full-width"
                  placeholder="请选择共享群组"
                >
                  <el-option
                    v-for="item in meta.groups"
                    :key="item.id"
                    :label="`${item.name}${item.isDefault ? ' · 默认' : ''} · ${item.memberCount} 人`"
                    :value="item.id"
                  />
                </el-select>
              </div>

              <div class="sales-filter-field">
                <label class="sales-filter-label">日期</label>
                <el-input v-model="form.formDate" type="datetime-local" />
              </div>
            </div>
          </el-form>
        </section>

        <section v-show="editorStep === 2" class="work-order-editor-shell">
          <section class="card-surface work-order-editor-summary">
            <div class="work-order-detail-title">
              <div>
                <span class="work-order-category-caption">{{ currentCategoryLabel }}</span>
                <h3>{{ currentTypeLabel }}</h3>
              </div>
              <div class="selected-goods-meta">
                <span>申请人 {{ applicantName }}</span>
                <span v-if="form.orderNum">编号 {{ form.orderNum }}</span>
                <span>总数量 {{ totalQuantity }}</span>
                <span v-if="isSalesOrderType">总实付 ¥ {{ formatMoney(totalReceivedAmount) }}</span>
                <span>总金额 ¥ {{ formatMoney(totalAmount) }}</span>
              </div>
            </div>

            <div class="work-order-detail-grid">
              <div class="work-order-detail-item">
                <span>事由</span>
                <strong>{{ replaceShopNameAliases(effectiveReason) }}</strong>
              </div>
              <div class="work-order-detail-item">
                <span>日期</span>
                <strong>{{ formatDateLabel(form.formDate) }}</strong>
              </div>
              <div class="work-order-detail-item">
                <span>负责人</span>
                <strong>{{ approverDisplayName || '-' }}</strong>
              </div>
              <div v-if="form.orderType === 'sale'" class="work-order-detail-item">
                <span>变动库存</span>
                <strong>{{ form.saleAffectsInventory ? '是' : '否' }}</strong>
              </div>
              <div v-if="currentGroupLabel" class="work-order-detail-item">
                <span>共享群组</span>
                <strong>{{ currentGroupLabel }}</strong>
              </div>
              <div v-if="showSourceSelector" class="work-order-detail-item">
                <span>{{ sourceLabel }}</span>
                <strong>{{ sourceDisplayName || '-' }}</strong>
              </div>
              <div v-if="showTargetSelector" class="work-order-detail-item">
                <span>{{ targetLabel }}</span>
                <strong>{{ targetDisplayName || '-' }}</strong>
              </div>
              <div v-if="form.orderType === 'purchase'" class="work-order-detail-item">
                <span>供货单位</span>
                <strong>{{ displayShopName(form.supplierName) || '-' }}</strong>
              </div>
              <div v-if="form.orderType === 'return'" class="work-order-detail-item">
                <span>收货单位</span>
                <strong>{{ displayShopName(form.partnerName) || '-' }}</strong>
              </div>
            </div>
          </section>

          <section class="card-surface work-order-items-panel">
            <div class="panel-head-simple">
              <div>
                <h3>工单明细</h3>
              </div>
            </div>

            <template v-if="!isSaleExchangeType">
            <div
              v-if="showQuickAddBar && !isMobileViewport"
              ref="quickAddBarRef"
              class="work-order-quick-add-bar work-order-quick-add-bar--desktop card-surface"
            >
              <div class="work-order-quick-add-copy">
                <strong>连续新增栏</strong>
                <span>输入条码或商品名称后回车，商品会优先插入到表格第一行，输入焦点会留在这里继续录入。</span>
              </div>
              <div class="work-order-quick-add-controls">
                <div
                  ref="quickAddFieldRef"
                  class="work-order-quick-add-input"
                >
                  <el-autocomplete
                    v-model="quickAddQuery"
                    class="full-width"
                    :fetch-suggestions="(queryString, cb) => fetchGoodsSuggestions(queryString, cb)"
                    select-when-unmatched
                    clearable
                    placeholder="条码 / 商品名称"
                    @input="handleQuickAddInput"
                    @select="handleQuickAddSuggestionSelect"
                    @keyup.enter="handleQuickAddEnter"
                  />
                </div>
                <div class="work-order-quick-add-result" :class="{ matched: quickAddMatchedLabel }">
                  <span v-if="quickAddMatchedLabel">{{ quickAddMatchedLabel }}</span>
                  <span v-else-if="quickAddLoading">正在匹配商品...</span>
                  <span v-else>匹配成功后会在这里显示商品名称</span>
                </div>
                <el-button type="primary" :loading="quickAddLoading" @click="commitQuickAddInput()">
                  添加到表格
                </el-button>
              </div>
            </div>

            <div class="table-shell open-table-shell" @keydown.capture="handleEditorDirectionalKeydown">
              <el-table
                :key="`work-order-items-${form.orderType}`"
                :data="editorPagedItems"
                border
                stripe
                row-key="localId"
                :empty-text="editorEmptyText"
                show-summary
                :summary-method="editorTableSummary"
                @sort-change="onEditorTableSortChange"
              >
                <el-table-column
                  v-if="isSaleAffectingInventory"
                  prop="goodsName"
                  label="商品名称"
                  min-width="230"
                  fixed="left"
                  sortable="custom"
                >
                  <template #default="{ row }">
                    <div
                      class="work-order-goods-cell"
                      :data-editor-field="buildEditorFieldMarker(row.localId, 'goodsName')"
                      :ref="(el) => registerEditorFieldRef(row.localId, 'goodsName', el)"
                      @dblclick="openGoodsPicker(row.localId)"
                    >
                      <el-autocomplete
                        v-model="row.goodsName"
                        class="full-width"
                        :fetch-suggestions="(queryString, cb) => fetchGoodsSuggestions(queryString, cb)"
                        select-when-unmatched
                        clearable
                        placeholder="输入商品名称或型号，双击打开选品弹窗"
                        @select="(item) => handleGoodsSuggestionSelect(row.localId, item)"
                        @keyup.enter="(event) => handleRowGoodsEnter(row, event)"
                        @change="() => onRowGoodsCommit(row)"
                        @input="() => onRowGoodsInput(row)"
                      />
                    </div>
                  </template>
                </el-table-column>

                <el-table-column
                  v-if="usesSalesRecordBinding"
                  prop="orderNum"
                  label="订单号"
                  min-width="180"
                  sortable="custom"
                >
                  <template #default="{ row }">
                    <div
                      class="work-order-goods-cell"
                      :data-editor-field="buildEditorFieldMarker(row.localId, 'orderNum')"
                      :ref="(el) => registerEditorFieldRef(row.localId, 'orderNum', el)"
                      @dblclick="openSalesPicker(row.localId)"
                    >
                      <el-input
                        v-model.trim="row.orderNum"
                        placeholder="双击选择销售记录"
                        @keyup.enter="() => onRowOrderNumCommit(row, { allowAdvanceResolved: true })"
                        @change="() => onRowOrderNumCommit(row)"
                      />
                    </div>
                  </template>
                </el-table-column>

                <el-table-column
                  v-if="isSalesOrderType"
                  prop="saleShopName"
                  label="销售店铺"
                  min-width="170"
                  sortable="custom"
                >
                  <template v-if="isSaleAffectingInventory" #header>
                    <div class="work-order-salesperson-header">
                      <span>销售店铺</span>
                      <el-popover trigger="click" placement="bottom" width="260" @show="prepareLocationBulk('sale')">
                        <template #reference>
                          <el-button text class="work-order-salesperson-bulk-trigger">全列</el-button>
                        </template>
                        <div class="work-order-salesperson-bulk-panel">
                          <el-select
                            v-model="locationBulkValue.defaultSale"
                            filterable
                            class="full-width"
                            placeholder="统一设置销售店铺"
                          >
                            <el-option
                              v-for="item in sourceOptions"
                              :key="`sale-shop-bulk-${item.id}`"
                              :label="displayShopName(item.name)"
                              :value="item.id"
                            />
                          </el-select>
                          <div class="work-order-salesperson-bulk-actions">
                            <el-button size="small" @click="clearLocationBulk('sale')">清空</el-button>
                            <el-button size="small" type="primary" @click="applyLocationToTarget('sale')">应用</el-button>
                          </div>
                        </div>
                      </el-popover>
                    </div>
                  </template>
                  <template #default="{ row }">
                    <el-input
                      v-if="!isSaleAffectingInventory"
                      :model-value="row.saleShopName"
                      readonly
                      placeholder="随销售记录带入"
                    />
                    <el-select
                      v-else
                      v-model="row.saleShopId"
                      filterable
                      class="full-width"
                      placeholder="请选择销售店铺"
                      @change="handleSaleInventoryLocationChange(row, 'sale')"
                    >
                      <el-option
                        v-for="item in sourceOptions"
                        :key="item.id"
                        :label="displayShopName(item.name)"
                        :value="item.id"
                      />
                    </el-select>
                  </template>
                </el-table-column>

                <el-table-column
                  v-if="usesReceiveShopColumn"
                  prop="receiveShopName"
                  label="收货店铺/仓库"
                  min-width="180"
                  sortable="custom"
                >
                  <template #default="{ row }">
                    <el-select
                      v-model="row.receiveShopId"
                      filterable
                      class="full-width"
                      placeholder="请选择收货店铺/仓库"
                      @change="handleSaleInventoryLocationChange(row, 'receive')"
                    >
                      <el-option
                        v-for="item in stockLocationOptions"
                        :key="`receive-${item.id}`"
                        :label="displayShopName(item.name)"
                        :value="item.id"
                      />
                    </el-select>
                  </template>
                </el-table-column>

                <el-table-column
                  v-if="isSalesOrderType && isSaleAffectingInventory"
                  prop="shipShopName"
                  label="发货店铺/仓库"
                  min-width="180"
                  sortable="custom"
                >
                  <template #header>
                    <div class="work-order-salesperson-header">
                      <span>发货店铺/仓库</span>
                      <el-popover trigger="click" placement="bottom" width="260" @show="prepareLocationBulk('ship')">
                        <template #reference>
                          <el-button text class="work-order-salesperson-bulk-trigger">全列</el-button>
                        </template>
                        <div class="work-order-salesperson-bulk-panel">
                          <el-select
                            v-model="locationBulkValue.defaultShip"
                            filterable
                            class="full-width"
                            placeholder="统一设置发货店铺/仓库"
                          >
                            <el-option
                              v-for="item in stockLocationOptions"
                              :key="`ship-shop-bulk-${item.id}`"
                              :label="displayShopName(item.name)"
                              :value="item.id"
                            />
                          </el-select>
                          <div class="work-order-salesperson-bulk-actions">
                            <el-button size="small" @click="clearLocationBulk('ship')">清空</el-button>
                            <el-button size="small" type="primary" @click="applyLocationToTarget('ship')">应用</el-button>
                          </div>
                        </div>
                      </el-popover>
                    </div>
                  </template>
                  <template #default="{ row }">
                    <el-select
                      v-model="row.shipShopId"
                      filterable
                      class="full-width"
                      placeholder="请选择发货店铺/仓库"
                      @change="handleSaleInventoryLocationChange(row, 'ship')"
                    >
                      <el-option
                        v-for="item in stockLocationOptions"
                        :key="item.id"
                        :label="displayShopName(item.name)"
                        :value="item.id"
                      />
                    </el-select>
                  </template>
                </el-table-column>

                <el-table-column
                  v-if="isSalesOrderType"
                  prop="salesperson"
                  min-width="160"
                  sortable="custom"
                >
                  <template #header>
                    <div class="work-order-salesperson-header">
                      <span>销售员</span>
                      <el-popover trigger="click" placement="bottom" width="240" @show="prepareSalespersonBulk('default')">
                        <template #reference>
                          <el-button text class="work-order-salesperson-bulk-trigger">全列</el-button>
                        </template>
                        <div class="work-order-salesperson-bulk-panel">
                          <el-select
                            v-model="salespersonBulkValue.default"
                            filterable
                            class="full-width"
                            placeholder="统一设置销售员"
                          >
                            <el-option
                              v-for="item in getSalespersonOptionsForTarget('default')"
                              :key="`salesperson-bulk-default-${item.id}`"
                              :label="formatSalespersonLabel(item)"
                              :value="formatSalespersonValue(item)"
                            />
                          </el-select>
                          <div class="work-order-salesperson-bulk-actions">
                            <el-button size="small" @click="clearSalespersonBulk('default')">清空</el-button>
                            <el-button size="small" type="primary" @click="applySalespersonToTarget('default')">应用</el-button>
                          </div>
                        </div>
                      </el-popover>
                    </div>
                  </template>
                  <template #default="{ row }">
                    <el-select
                      v-model="row.salesperson"
                      filterable
                      class="full-width"
                      placeholder="销售员"
                    >
                      <el-option
                        v-for="item in getSalespersonOptionsForRow(row)"
                        :key="`salesperson-default-${row.localId}-${item.id}`"
                        :label="formatSalespersonLabel(item)"
                        :value="formatSalespersonValue(item)"
                      />
                    </el-select>
                  </template>
                </el-table-column>

                <el-table-column
                  v-if="isSalesOrderType"
                  prop="receivedAmount"
                  label="实付金额"
                  min-width="120"
                  sortable="custom"
                >
                  <template #default="{ row }">
                    <el-input-number
                      v-model="row.receivedAmount"
                      :min="0"
                      :step="0.01"
                      :precision="2"
                      :controls="false"
                      class="full-width"
                      @input="syncRowAmount(row)"
                      @change="syncRowAmount(row)"
                    />
                  </template>
                </el-table-column>

                <el-table-column
                  v-if="!isSaleAffectingInventory"
                  prop="goodsName"
                  label="商品名称"
                  min-width="230"
                  :fixed="form.orderType === 'purchase' ? 'left' : undefined"
                  class-name="aqc-fixed-left-column"
                  label-class-name="aqc-fixed-left-column"
                  sortable="custom"
                >
                  <template #default="{ row, $index }">
                    <div
                      v-if="!isSalesOrderType || isSaleAffectingInventory"
                      class="work-order-goods-cell"
                      :data-editor-field="buildEditorFieldMarker(row.localId, 'goodsName')"
                      :ref="(el) => registerEditorFieldRef(row.localId, 'goodsName', el)"
                      @dblclick="openGoodsPicker(row.localId)"
                    >
                      <el-autocomplete
                        v-model="row.goodsName"
                        class="full-width"
                        :fetch-suggestions="(queryString, cb) => fetchGoodsSuggestions(queryString, cb)"
                        select-when-unmatched
                        clearable
                        :placeholder="form.orderType === 'purchase' ? '输入商品名称或型号，双击打开选品弹窗' : '输入商品名称，双击打开选品弹窗'"
                        @select="(item) => handleGoodsSuggestionSelect(row.localId, item)"
                        @keyup.enter="(event) => handleRowGoodsEnter(row, event)"
                        @change="() => onRowGoodsCommit(row)"
                        @input="() => onRowGoodsInput(row)"
                      />
                    </div>
                    <el-input v-else :model-value="row.goodsName" readonly placeholder="双击订单号选择销售记录" />
                  </template>
                </el-table-column>

                <el-table-column prop="unitPrice" label="单价" min-width="110" sortable="custom">
                  <template #default="{ row }">
                    <el-input-number
                      v-model="row.unitPrice"
                      :min="0"
                      :step="0.01"
                      :precision="2"
                      :controls="false"
                      class="full-width"
                      @change="syncRowAmount(row)"
                    />
                  </template>
                </el-table-column>

                <el-table-column prop="quantity" label="数量" min-width="116" align="center" sortable="custom">
                  <template #default="{ row }">
                    <el-input-number
                      v-model="row.quantity"
                      :min="1"
                      :step="1"
                      :controls="false"
                      class="full-width work-order-number-input work-order-qty-input"
                      @change="syncRowAmount(row)"
                    />
                  </template>
                </el-table-column>

                <el-table-column label="单位" width="80" align="center">
                  <template #default>只</template>
                </el-table-column>

                <el-table-column
                  v-if="isSaleAffectingInventory"
                  prop="couponAmount"
                  label="优惠券"
                  min-width="110"
                  sortable="custom"
                >
                  <template #default="{ row }">
                    <el-input-number
                      v-model="row.couponAmount"
                      :min="0"
                      :step="0.01"
                      :precision="2"
                      :controls="false"
                      class="full-width"
                    />
                  </template>
                </el-table-column>

                <el-table-column
                  v-if="isSaleAffectingInventory"
                  prop="discountRate"
                  label="折扣"
                  min-width="96"
                  sortable="custom"
                >
                  <template #header>
                    <div class="work-order-salesperson-header">
                      <span>折扣</span>
                      <el-popover trigger="click" placement="bottom" width="220" @show="prepareDiscountBulk()">
                        <template #reference>
                          <el-button text class="work-order-salesperson-bulk-trigger">整单折扣</el-button>
                        </template>
                        <div class="work-order-salesperson-bulk-panel">
                          <el-input-number
                            v-model="discountBulkValue.default"
                            :min="0"
                            :max="99.99"
                            :step="0.01"
                            :precision="2"
                            :controls="false"
                            class="full-width"
                            placeholder="统一设置整单折扣"
                          />
                          <div class="work-order-salesperson-bulk-actions">
                            <el-button size="small" @click="clearDiscountBulk">重置</el-button>
                            <el-button size="small" type="primary" @click="applyDiscountToAll">应用</el-button>
                          </div>
                        </div>
                      </el-popover>
                    </div>
                  </template>
                  <template #default="{ row }">
                    <el-input-number
                      v-model="row.discountRate"
                      :min="0"
                      :max="99.99"
                      :step="0.01"
                      :precision="2"
                      :controls="false"
                      class="full-width"
                      @input="syncRowDiscount(row)"
                      @change="syncRowDiscount(row)"
                    />
                  </template>
                </el-table-column>

                <el-table-column v-if="form.orderType === 'transfer'" prop="sourceStock" label="发货库存" min-width="110" align="center" sortable="custom">
                  <template #default="{ row }">{{ row.sourceStock ?? 0 }}</template>
                </el-table-column>

                <el-table-column v-if="form.orderType === 'transfer'" prop="targetStock" label="收货库存" min-width="110" align="center" sortable="custom">
                  <template #default="{ row }">{{ row.targetStock ?? 0 }}</template>
                </el-table-column>

                <el-table-column
                  prop="totalAmount"
                  :label="isSalesOrderType ? '应付金额' : '金额'"
                  min-width="120"
                  sortable="custom"
                >
                  <template #default="{ row }">
                    <el-input
                      v-if="!isSalesOrderType"
                      :model-value="formatMoney(row.totalAmount)"
                      readonly
                    />
                    <el-input-number
                      v-else
                      v-model="row.receivableAmount"
                      :min="0"
                      :step="0.01"
                      :precision="2"
                      :controls="false"
                      class="full-width"
                      @input="syncRowAmount(row)"
                      @change="syncRowAmount(row)"
                    />
                  </template>
                </el-table-column>

                <el-table-column v-if="form.orderType === 'purchase'" prop="brand" label="品牌" min-width="140" sortable="custom">
                  <template #default="{ row }">
                    <el-autocomplete
                      v-model="row.brand"
                      class="full-width"
                      :fetch-suggestions="fetchBrandSuggestions"
                      clearable
                      placeholder="输入品牌，支持联想"
                      @select="(item) => { row.brand = item.value }"
                    />
                  </template>
                </el-table-column>

                <el-table-column v-if="form.orderType === 'purchase'" prop="series" label="系列" min-width="140" sortable="custom">
                  <template #default="{ row }">
                    <el-autocomplete
                      v-model="row.series"
                      class="full-width"
                      :fetch-suggestions="fetchSeriesSuggestions"
                      clearable
                      placeholder="输入系列，支持联想"
                      @select="(item) => { row.series = item.value }"
                    />
                  </template>
                </el-table-column>

                <el-table-column prop="barcode" label="条码" min-width="160" sortable="custom">
                  <template #default="{ row }">
                    <div
                      :data-editor-field="buildEditorFieldMarker(row.localId, 'barcode')"
                      :ref="(el) => registerEditorFieldRef(row.localId, 'barcode', el)"
                    >
                      <el-input
                        v-model.trim="row.barcode"
                        placeholder="条码"
                        :readonly="isSalesOrderType && !isSaleAffectingInventory"
                        @keyup.enter="() => onRowBarcodeChange(row, { allowAdvanceResolved: true })"
                        @change="() => onRowBarcodeChange(row)"
                      />
                    </div>
                  </template>
                </el-table-column>

                <el-table-column
                  v-if="isSaleAffectingInventory"
                  prop="channel"
                  label="渠道"
                  min-width="110"
                  sortable="custom"
                >
                  <template #default="{ row }">
                    <el-input v-model.trim="row.channel" placeholder="渠道" />
                  </template>
                </el-table-column>

                <el-table-column
                  v-if="isSaleAffectingInventory"
                  prop="customerName"
                  label="客户姓名"
                  min-width="120"
                  sortable="custom"
                >
                  <template #default="{ row }">
                    <el-input v-model.trim="row.customerName" placeholder="可选" />
                  </template>
                </el-table-column>

                <el-table-column prop="remark" label="备注" min-width="180" sortable="custom">
                  <template #default="{ row }">
                    <el-input v-model.trim="row.remark" placeholder="可选备注" />
                  </template>
                </el-table-column>

                <el-table-column label="操作" :width="itemActionWidth" fixed="right">
                  <template #header>
                    <div class="work-order-action-header">
                      <span>操作</span>
                      <el-button text class="work-order-action-header-trigger" @click.stop="removeBlankRowsOnCurrentPage('default')">删空白</el-button>
                    </div>
                  </template>
                  <template #default="{ row, $index }">
                    <ResponsiveTableActions :menu-width="148">
                      <el-button text @click="clearRowGoods(row)">清空</el-button>
                      <el-button text type="danger" @click="confirmRemoveItemRow(row.localId)">删除本行</el-button>
                    </ResponsiveTableActions>
                  </template>
                </el-table-column>
              </el-table>
            </div>

            <div v-if="form.items.length > editorItemsPageSize" class="pager-wrap work-order-items-pager">
              <el-pagination
                background
                layout="total, sizes, prev, pager, next, jumper"
                :total="form.items.length"
                :current-page="editorItemsPage"
                :page-size="editorItemsPageSize"
                :page-sizes="[20, 50, 100]"
                @current-change="onEditorItemsPageChange"
                @size-change="onEditorItemsPageSizeChange"
              />
            </div>

            <div class="selected-goods-meta work-order-grand-summary">
              <span>总合计</span>
              <span>总数量 {{ editorGrandTotals.quantity }}</span>
              <span v-if="isSalesOrderType">总折扣 {{ formatMoney(editorGrandTotals.discount) }}</span>
              <span v-if="isSalesOrderType">总实付 ¥ {{ formatMoney(editorGrandTotals.received) }}</span>
              <span>总金额 ¥ {{ formatMoney(editorGrandTotals.amount) }}</span>
            </div>

            <div
              v-if="showQuickAddBar && isMobileViewport"
              ref="quickAddBarRef"
              class="work-order-quick-add-bar card-surface"
            >
              <div class="work-order-quick-add-copy">
                <strong>连续新增栏</strong>
                <span>输入条码或商品名称后回车，商品会优先插入到表格第一行，输入焦点会留在这里继续录入。</span>
              </div>
              <div class="work-order-quick-add-controls">
                <div
                  ref="quickAddFieldRef"
                  class="work-order-quick-add-input"
                >
                  <el-autocomplete
                    v-model="quickAddQuery"
                    class="full-width"
                    :fetch-suggestions="(queryString, cb) => fetchGoodsSuggestions(queryString, cb)"
                    select-when-unmatched
                    clearable
                    placeholder="条码 / 商品名称"
                    @input="handleQuickAddInput"
                    @select="handleQuickAddSuggestionSelect"
                    @keyup.enter="handleQuickAddEnter"
                  />
                </div>
                <div class="work-order-quick-add-result" :class="{ matched: quickAddMatchedLabel }">
                  <span v-if="quickAddMatchedLabel">{{ quickAddMatchedLabel }}</span>
                  <span v-else-if="quickAddLoading">正在匹配商品...</span>
                  <span v-else>匹配成功后会在这里显示商品名称</span>
                </div>
                <el-button type="primary" :loading="quickAddLoading" @click="commitQuickAddInput()">
                  添加到表格
                </el-button>
              </div>
            </div>

            <div class="work-order-add-row-bar">
              <el-button @click="openBatchEntryDialog">{{ usesSalesRecordBinding ? '批量录入订单' : '批量录入商品' }}</el-button>
              <el-popover trigger="hover" placement="top" width="220">
                <template #reference>
                  <el-button @click="addItemRows(1)">新增一行</el-button>
                </template>
                <div class="work-order-batch-popover">
                  <span>新增多行</span>
                  <el-input-number
                    v-model="batchRowCount"
                    :min="1"
                    :max="50"
                    :controls="false"
                    class="full-width"
                  />
                  <el-button type="primary" size="small" @click="addBatchRows">确认</el-button>
                </div>
              </el-popover>
            </div>

            <p class="scan-hint work-order-hint">
              <template v-if="usesSalesRecordBinding">
                销售类工单请双击订单号选择销售记录，也可使用批量录入订单。提交审批前，每一行都需要绑定已有销售记录。
              </template>
              <template v-else-if="isSaleAffectingInventory">
                变动库存销售单请填写商品、销售店铺与发货店铺/仓库；审批通过后会自动生成订单号、写入销售记录并同步扣减库存。
              </template>
              <template v-else>
                商品名称/型号和系列支持联想补全；双击可弹出商品选择弹窗。进货单允许保留未匹配商品，并会在审批通过时按确认结果自动新增商品。
              </template>
            </p>
            </template>

            <template v-else>
              <div class="panel-head-simple work-order-section-head">
                <div>
                  <h3>换入明细</h3>
                  <p>双击订单号选择原销售记录，审批后会退回库存并生成退货冲销记录。</p>
                </div>
              </div>
              <div class="table-shell open-table-shell" @keydown.capture="handleEditorDirectionalKeydown">
                <el-table
                  :data="sortedExchangeIncomingItems"
                  border
                  stripe
                  row-key="localId"
                  empty-text="请新增换入明细"
                  show-summary
                  :summary-method="editorTableSummary"
                  @sort-change="onEditorTableSortChange"
                >
                  <el-table-column prop="orderNum" label="订单号" min-width="180" sortable="custom">
                    <template #default="{ row }">
                      <div
                        class="work-order-goods-cell"
                        :data-editor-field="buildEditorFieldMarker(row.localId, 'orderNum')"
                        :ref="(el) => registerEditorFieldRef(row.localId, 'orderNum', el)"
                        @dblclick="openSalesPicker(row.localId)"
                      >
                        <el-input
                          v-model.trim="row.orderNum"
                          placeholder="双击选择销售记录"
                          @keyup.enter="() => onRowOrderNumCommit(row, { allowAdvanceResolved: true })"
                          @change="() => onRowOrderNumCommit(row)"
                        />
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column prop="saleShopName" label="销售店铺" min-width="170" sortable="custom">
                    <template #default="{ row }">
                      <el-input :model-value="row.saleShopName" readonly />
                    </template>
                  </el-table-column>
                  <el-table-column prop="salesperson" min-width="160" sortable="custom">
                    <template #header>
                      <div class="work-order-salesperson-header">
                        <span>销售员</span>
                        <el-popover trigger="click" placement="bottom" width="240" @show="prepareSalespersonBulk('incoming')">
                          <template #reference>
                            <el-button text class="work-order-salesperson-bulk-trigger">全列</el-button>
                          </template>
                          <div class="work-order-salesperson-bulk-panel">
                            <el-select
                              v-model="salespersonBulkValue.incoming"
                              filterable
                              class="full-width"
                              placeholder="统一设置销售员"
                            >
                              <el-option
                                v-for="item in getSalespersonOptionsForTarget('incoming')"
                                :key="`salesperson-bulk-incoming-${item.id}`"
                                :label="formatSalespersonLabel(item)"
                                :value="formatSalespersonValue(item)"
                              />
                            </el-select>
                            <div class="work-order-salesperson-bulk-actions">
                              <el-button size="small" @click="clearSalespersonBulk('incoming')">清空</el-button>
                              <el-button size="small" type="primary" @click="applySalespersonToTarget('incoming')">应用</el-button>
                            </div>
                          </div>
                        </el-popover>
                      </div>
                    </template>
                    <template #default="{ row }">
                      <el-select
                        v-model="row.salesperson"
                        filterable
                        class="full-width"
                        placeholder="销售员"
                      >
                        <el-option
                          v-for="item in getSalespersonOptionsForRow(row)"
                          :key="`salesperson-incoming-${row.localId}-${item.id}`"
                          :label="formatSalespersonLabel(item)"
                          :value="formatSalespersonValue(item)"
                        />
                      </el-select>
                    </template>
                  </el-table-column>
                  <el-table-column prop="receivedAmount" label="实付金额" min-width="120" sortable="custom">
                    <template #default="{ row }">
                      <el-input-number
                        v-model="row.receivedAmount"
                        :min="0"
                        :step="0.01"
                        :precision="2"
                        :controls="false"
                        class="full-width"
                        @input="syncRowAmount(row)"
                        @change="syncRowAmount(row)"
                      />
                    </template>
                  </el-table-column>
                  <el-table-column prop="goodsName" label="商品名称" min-width="220" sortable="custom">
                    <template #default="{ row }">
                      <el-input :model-value="row.goodsName" readonly placeholder="双击订单号选择销售记录" />
                    </template>
                  </el-table-column>
                  <el-table-column prop="unitPrice" label="单价" min-width="110" sortable="custom">
                    <template #default="{ row }">
                      <el-input :model-value="formatMoney(row.unitPrice)" readonly />
                    </template>
                  </el-table-column>
                  <el-table-column prop="quantity" label="数量" min-width="116" align="center" sortable="custom">
                    <template #default="{ row }">
                      <el-input-number
                        v-model="row.quantity"
                        :min="1"
                        :step="1"
                        :controls="false"
                        class="full-width work-order-number-input work-order-qty-input"
                        @change="syncRowAmount(row)"
                      />
                    </template>
                  </el-table-column>
                  <el-table-column label="单位" width="80" align="center">
                    <template #default>只</template>
                  </el-table-column>
                  <el-table-column prop="totalAmount" label="应付金额" min-width="120" sortable="custom">
                    <template #default="{ row }">
                    <el-input-number
                      v-model="row.receivableAmount"
                      :min="0"
                      :step="0.01"
                      :precision="2"
                      :controls="false"
                      class="full-width"
                      @input="syncRowAmount(row)"
                      @change="syncRowAmount(row)"
                    />
                  </template>
                </el-table-column>
                  <el-table-column prop="barcode" label="条码" min-width="160" sortable="custom">
                    <template #default="{ row }">
                      <el-input v-model.trim="row.barcode" readonly />
                    </template>
                  </el-table-column>
                  <el-table-column prop="remark" label="备注" min-width="180" sortable="custom">
                    <template #default="{ row }">
                      <el-input v-model.trim="row.remark" placeholder="可选备注" />
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" :width="itemActionWidth" fixed="right">
                    <template #header>
                      <div class="work-order-action-header">
                        <span>操作</span>
                        <el-button text class="work-order-action-header-trigger" @click.stop="removeBlankRowsOnCurrentPage('incoming')">删空白</el-button>
                      </div>
                    </template>
                    <template #default="{ row }">
                      <ResponsiveTableActions :menu-width="148">
                        <el-button text @click="clearRowGoods(row)">清空</el-button>
                        <el-button text type="danger" @click="confirmRemoveItemRow(row.localId)">删除本行</el-button>
                      </ResponsiveTableActions>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
              <div class="selected-goods-meta work-order-grand-summary">
                <span>总合计</span>
                <span>总数量 {{ exchangeIncomingGrandTotals.quantity }}</span>
                <span>总折扣 {{ formatMoney(exchangeIncomingGrandTotals.discount) }}</span>
                <span>总实付 ¥ {{ formatMoney(exchangeIncomingGrandTotals.received) }}</span>
                <span>总金额 ¥ {{ formatMoney(exchangeIncomingGrandTotals.amount) }}</span>
              </div>
              <div class="work-order-add-row-bar">
                <el-button @click="openBatchEntryDialog('incoming')">批量录入订单</el-button>
                <el-popover trigger="hover" placement="top" width="220">
                  <template #reference>
                    <el-button @click="addItemRows(1, 'incoming')">新增一行</el-button>
                  </template>
                  <div class="work-order-batch-popover">
                    <span>新增多行</span>
                    <el-input-number v-model="batchRowCount" :min="1" :max="50" :controls="false" class="full-width" />
                    <el-button type="primary" size="small" @click="addBatchRows('incoming')">确认</el-button>
                  </div>
                </el-popover>
              </div>

              <div class="panel-head-simple work-order-section-head">
                <div>
                  <h3>换出明细</h3>
                  <p>按新销售内容录入，审批后会生成新的销售记录并扣减发货店铺库存。</p>
                </div>
              </div>
              <div class="table-shell open-table-shell" @keydown.capture="handleEditorDirectionalKeydown">
                <el-table
                  :data="sortedExchangeOutgoingItems"
                  border
                  stripe
                  row-key="localId"
                  empty-text="请新增换出明细"
                  show-summary
                  :summary-method="editorTableSummary"
                  @sort-change="onEditorTableSortChange"
                >
                  <el-table-column
                    prop="goodsName"
                    label="商品名称"
                    min-width="220"
                    fixed="left"
                    class-name="aqc-fixed-left-column"
                    label-class-name="aqc-fixed-left-column"
                    sortable="custom"
                  >
                    <template #default="{ row }">
                      <div
                        class="work-order-goods-cell"
                        :data-editor-field="buildEditorFieldMarker(row.localId, 'goodsName')"
                        :ref="(el) => registerEditorFieldRef(row.localId, 'goodsName', el)"
                        @dblclick="openGoodsPicker(row.localId)"
                      >
                        <el-autocomplete
                          v-model="row.goodsName"
                          class="full-width"
                          :fetch-suggestions="(queryString, cb) => fetchGoodsSuggestions(queryString, cb)"
                          select-when-unmatched
                          clearable
                          placeholder="输入商品名称，双击打开选品弹窗"
                          @select="(item) => handleGoodsSuggestionSelect(row.localId, item)"
                          @keyup.enter="(event) => handleRowGoodsEnter(row, event)"
                          @change="() => onRowGoodsCommit(row)"
                          @input="() => onRowGoodsInput(row)"
                        />
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column prop="quantity" label="数量" min-width="110" align="center" sortable="custom">
                    <template #default="{ row }">
                      <el-input-number
                        v-model="row.quantity"
                        :min="1"
                        :step="1"
                        :controls="false"
                        class="full-width work-order-number-input work-order-qty-input"
                        @change="syncRowAmount(row)"
                      />
                    </template>
                  </el-table-column>
                  <el-table-column prop="unitPrice" label="单价" min-width="110" sortable="custom">
                    <template #default="{ row }">
                      <el-input :model-value="formatMoney(row.unitPrice)" readonly />
                    </template>
                  </el-table-column>
                  <el-table-column prop="receivableAmount" label="应收金额" min-width="120" sortable="custom">
                    <template #default="{ row }">
                      <el-input :model-value="formatMoney(row.receivableAmount)" readonly />
                    </template>
                  </el-table-column>
                  <el-table-column prop="receivedAmount" label="实付金额" min-width="120" sortable="custom">
                    <template #default="{ row }">
                      <el-input-number
                        v-model="row.receivedAmount"
                        :min="0"
                        :step="0.01"
                        :precision="2"
                        :controls="false"
                        class="full-width"
                        @input="syncRowAmount(row)"
                        @change="syncRowAmount(row)"
                      />
                    </template>
                  </el-table-column>
                  <el-table-column prop="couponAmount" label="优惠券" min-width="110" sortable="custom">
                    <template #default="{ row }">
                      <el-input-number
                        v-model="row.couponAmount"
                        :min="0"
                        :step="0.01"
                        :precision="2"
                        :controls="false"
                        class="full-width"
                      />
                    </template>
                  </el-table-column>
                  <el-table-column prop="discountRate" label="折扣" min-width="100" sortable="custom">
                    <template #default="{ row }">
                      <el-input :model-value="formatMoney(row.discountRate)" readonly />
                    </template>
                  </el-table-column>
                  <el-table-column prop="barcode" label="条码" min-width="160" sortable="custom">
                    <template #default="{ row }">
                      <div
                        :data-editor-field="buildEditorFieldMarker(row.localId, 'barcode')"
                        :ref="(el) => registerEditorFieldRef(row.localId, 'barcode', el)"
                      >
                        <el-input
                          v-model.trim="row.barcode"
                          placeholder="条码"
                          @keyup.enter="() => onRowBarcodeChange(row, { allowAdvanceResolved: true })"
                          @change="() => onRowBarcodeChange(row)"
                        />
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column prop="channel" label="渠道" min-width="100" sortable="custom">
                    <template #default="{ row }">
                      <el-select v-model="row.channel" class="full-width">
                        <el-option label="门店" value="门店" />
                        <el-option label="线上" value="线上" />
                        <el-option label="其他" value="其他" />
                      </el-select>
                    </template>
                  </el-table-column>
                  <el-table-column prop="saleShopName" label="销售店铺" min-width="170" sortable="custom">
                    <template #default="{ row }">
                      <el-select v-model="row.saleShopId" class="full-width" @change="() => syncOutgoingShopSelection(row, 'sale')">
                        <el-option
                          v-for="item in sourceOptions"
                          :key="`sale-${item.id}`"
                          :label="displayShopName(item.name)"
                          :value="item.id"
                        />
                      </el-select>
                    </template>
                  </el-table-column>
                  <el-table-column prop="receiveShopName" label="收货店铺/仓库" min-width="170" sortable="custom">
                    <template #default="{ row }">
                      <el-select v-model="row.receiveShopId" class="full-width" @change="() => syncOutgoingShopSelection(row, 'receive')">
                        <el-option
                          v-for="item in stockLocationOptions"
                          :key="`receive-${item.id}`"
                          :label="displayShopName(item.name)"
                          :value="item.id"
                        />
                      </el-select>
                    </template>
                  </el-table-column>
                  <el-table-column prop="shipShopName" label="发货店铺" min-width="170" sortable="custom">
                    <template #default="{ row }">
                      <el-select v-model="row.shipShopId" class="full-width" @change="() => syncOutgoingShopSelection(row, 'ship')">
                        <el-option
                          v-for="item in sourceOptions"
                          :key="`ship-${item.id}`"
                          :label="displayShopName(item.name)"
                          :value="item.id"
                        />
                      </el-select>
                    </template>
                  </el-table-column>
                  <el-table-column prop="salesperson" min-width="160" sortable="custom">
                    <template #header>
                      <div class="work-order-salesperson-header">
                        <span>销售员</span>
                        <el-popover trigger="click" placement="bottom" width="240" @show="prepareSalespersonBulk('outgoing')">
                          <template #reference>
                            <el-button text class="work-order-salesperson-bulk-trigger">全列</el-button>
                          </template>
                          <div class="work-order-salesperson-bulk-panel">
                            <el-select
                              v-model="salespersonBulkValue.outgoing"
                              filterable
                              class="full-width"
                              placeholder="统一设置销售员"
                            >
                              <el-option
                                v-for="item in getSalespersonOptionsForTarget('outgoing')"
                                :key="`salesperson-bulk-outgoing-${item.id}`"
                                :label="formatSalespersonLabel(item)"
                                :value="formatSalespersonValue(item)"
                              />
                            </el-select>
                            <div class="work-order-salesperson-bulk-actions">
                              <el-button size="small" @click="clearSalespersonBulk('outgoing')">清空</el-button>
                              <el-button size="small" type="primary" @click="applySalespersonToTarget('outgoing')">应用</el-button>
                            </div>
                          </div>
                        </el-popover>
                      </div>
                    </template>
                    <template #default="{ row }">
                      <el-select
                        v-model="row.salesperson"
                        filterable
                        class="full-width"
                        placeholder="销售员"
                      >
                        <el-option
                          v-for="item in getSalespersonOptionsForRow(row)"
                          :key="`salesperson-outgoing-${row.localId}-${item.id}`"
                          :label="formatSalespersonLabel(item)"
                          :value="formatSalespersonValue(item)"
                        />
                      </el-select>
                    </template>
                  </el-table-column>
                  <el-table-column prop="customerName" label="客户姓名" min-width="140" sortable="custom">
                    <template #default="{ row }">
                      <el-input v-model.trim="row.customerName" placeholder="可选" />
                    </template>
                  </el-table-column>
                  <el-table-column prop="remark" label="备注" min-width="180" sortable="custom">
                    <template #default="{ row }">
                      <el-input v-model.trim="row.remark" placeholder="可选备注" />
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" :width="itemActionWidth" fixed="right">
                    <template #header>
                      <div class="work-order-action-header">
                        <span>操作</span>
                        <el-button text class="work-order-action-header-trigger" @click.stop="removeBlankRowsOnCurrentPage('outgoing')">删空白</el-button>
                      </div>
                    </template>
                    <template #default="{ row }">
                      <ResponsiveTableActions :menu-width="148">
                        <el-button text @click="clearRowGoods(row)">清空</el-button>
                        <el-button text type="danger" @click="confirmRemoveItemRow(row.localId)">删除本行</el-button>
                      </ResponsiveTableActions>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
              <div class="selected-goods-meta work-order-grand-summary">
                <span>总合计</span>
                <span>总数量 {{ exchangeOutgoingGrandTotals.quantity }}</span>
                <span>总折扣 {{ formatMoney(exchangeOutgoingGrandTotals.discount) }}</span>
                <span>总实付 ¥ {{ formatMoney(exchangeOutgoingGrandTotals.received) }}</span>
                <span>总金额 ¥ {{ formatMoney(exchangeOutgoingGrandTotals.amount) }}</span>
              </div>
              <div class="work-order-add-row-bar">
                <el-button @click="openBatchEntryDialog('outgoing')">批量录入商品</el-button>
                <el-popover trigger="hover" placement="top" width="220">
                  <template #reference>
                    <el-button @click="addItemRows(1, 'outgoing')">新增一行</el-button>
                  </template>
                  <div class="work-order-batch-popover">
                    <span>新增多行</span>
                    <el-input-number v-model="batchRowCount" :min="1" :max="50" :controls="false" class="full-width" />
                    <el-button type="primary" size="small" @click="addBatchRows('outgoing')">确认</el-button>
                  </div>
                </el-popover>
              </div>

              <p class="scan-hint work-order-hint">
                换货单会先退回原销售记录，再生成新的销售记录。换入明细请选择原订单，换出明细请选择新的商品与销售信息。
              </p>
            </template>
          </section>
        </section>
      </div>

      <template #footer>
        <div class="form-actions">
          <el-button @click="requestCloseEditor()">取消</el-button>
          <el-button v-if="editorStep > 1" @click="prevEditorStep">上一步</el-button>
          <el-button v-if="editorStep < editorStepOptions.length" type="primary" @click="nextEditorStep">下一步</el-button>
          <template v-else>
            <el-button :loading="savingDraft" @click="saveEditor('draft')">保存草稿</el-button>
            <el-button type="primary" :loading="submitting" @click="saveEditor('pending')">提交审批</el-button>
          </template>
        </div>
      </template>
    </ResponsiveDialog>

    <ResponsiveDialog
      v-model="workOrderSettingsDialogVisible"
      title="工单设置"
      width="min(920px, 96vw)"
      class="aqc-app-dialog work-order-schedule-dialog"
      mobile-subtitle="工单管理"
      :initial-snap="0.62"
      :expanded-snap="0.94"
    >
      <div class="work-order-schedule-shell">
        <section class="work-order-schedule-section">
          <div class="panel-head-simple work-order-schedule-head">
            <div>
              <h3>默认负责人</h3>
              <p>可为每个工单类型预设默认负责人。新建工单时会自动带入，商品调拨单默认负责人已预设为柏云。</p>
            </div>
          </div>

          <div class="table-shell open-table-shell work-order-schedule-table-shell">
            <el-table :data="workOrderSettings" border stripe empty-text="暂无工单设置">
              <el-table-column prop="orderTypeLabel" label="工单类型" min-width="180" />
              <el-table-column label="默认负责人" min-width="280">
                <template #default="{ row }">
                  <el-select
                    v-model="row.approverId"
                    filterable
                    clearable
                    class="full-width"
                    placeholder="未设置时需手动选择负责人"
                    @change="handleWorkOrderSettingApproverChange(row)"
                  >
                    <el-option
                      v-for="item in meta.approverOptions"
                      :key="item.id"
                      :label="item.displayName ? `${item.displayName} · ${item.username}` : item.username"
                      :value="item.id"
                    />
                  </el-select>
                </template>
              </el-table-column>
              <el-table-column label="当前显示" min-width="180" show-overflow-tooltip>
                <template #default="{ row }">{{ row.approverName || '未设置' }}</template>
              </el-table-column>
            </el-table>
          </div>
        </section>
      </div>

      <template #footer>
        <div class="form-actions">
          <el-button @click="workOrderSettingsDialogVisible = false">关闭</el-button>
          <el-button type="primary" :loading="workOrderSettingsSaving" @click="saveWorkOrderSettings">保存工单设置</el-button>
        </div>
      </template>
    </ResponsiveDialog>

    <ResponsiveDialog
      v-model="detailVisible"
      :title="detailOrder?.orderNum || '工单详情'"
      width="min(1180px, 96vw)"
      class="aqc-app-dialog work-order-detail-dialog"
      mobile-subtitle="工单管理"
      :initial-snap="0.66"
      :expanded-snap="0.96"
    >
      <div v-loading="detailLoading" class="work-order-detail-shell">
        <template v-if="detailOrder">
          <section class="card-surface work-order-detail-head">
            <div class="work-order-detail-title">
              <div>
                <span class="work-order-category-caption">{{ detailOrder.orderCategoryLabel }}</span>
                <h3>{{ detailOrder.orderTypeLabel }}</h3>
              </div>
              <div class="selected-goods-meta">
                <span>状态 {{ detailOrder.statusLabel }}</span>
                <span>编号 {{ detailOrder.orderNum }}</span>
                <span>日期 {{ formatDateLabel(detailOrder.formDate) }}</span>
              </div>
            </div>

            <div class="work-order-detail-grid">
              <div class="work-order-detail-item">
                <span>事由</span>
                <strong>{{ replaceShopNameAliases(detailOrder.reason) || '未填写' }}</strong>
              </div>
              <div class="work-order-detail-item">
                <span>申请人</span>
                <strong>{{ detailOrder.applicantName || '-' }}</strong>
              </div>
              <div class="work-order-detail-item">
                <span>负责人</span>
                <strong>{{ detailOrder.approverName || '-' }}</strong>
              </div>
              <div v-if="detailOrder.groupName" class="work-order-detail-item">
                <span>共享群组</span>
                <strong>{{ detailOrder.groupName }}</strong>
              </div>
              <div v-if="detailOrder.sourceShopName" class="work-order-detail-item">
                <span>{{ detailSourceLabel() }}</span>
                <strong>{{ displayShopName(detailOrder.sourceShopName) }}</strong>
              </div>
              <div v-if="detailOrder.targetShopName" class="work-order-detail-item">
                <span>{{ detailTargetLabel() }}</span>
                <strong>{{ displayShopName(detailOrder.targetShopName) }}</strong>
              </div>
              <div v-if="detailOrder.supplierName" class="work-order-detail-item">
                <span>供货单位</span>
                <strong>{{ displayShopName(detailOrder.supplierName) }}</strong>
              </div>
              <div v-if="detailOrder.partnerName" class="work-order-detail-item">
                <span>收货单位</span>
                <strong>{{ displayShopName(detailOrder.partnerName) }}</strong>
              </div>
              <div v-if="detailOrder.orderType === 'sale'" class="work-order-detail-item">
                <span>变动库存</span>
                <strong>{{ detailOrder.saleAffectsInventory ? '是' : '否' }}</strong>
              </div>
              <div class="work-order-detail-item">
                <span>库存已调整</span>
                <strong>{{ detailOrder.stockApplied ? '是' : '否' }}</strong>
              </div>
            </div>
          </section>

          <section class="card-surface work-order-detail-table">
            <template v-if="detailOrder.orderType !== 'sale_exchange'">
            <div class="table-shell open-table-shell">
              <el-table :data="detailPagedItems" border stripe show-summary :summary-method="detailTableSummary" @sort-change="onDetailTableSortChange">
                <el-table-column
                  v-if="['sale', 'sale_return', 'sale_exchange'].includes(detailOrder.orderType) && !detailIsSaleAffectingInventory"
                  prop="orderNum"
                  label="订单号"
                  min-width="180"
                  show-overflow-tooltip
                  fixed="left"
                  class-name="aqc-fixed-left-column"
                  label-class-name="aqc-fixed-left-column"
                  sortable="custom"
                />
                <el-table-column
                  v-if="['sale', 'sale_return', 'sale_exchange'].includes(detailOrder.orderType)"
                  prop="salesperson"
                  label="销售员"
                  min-width="120"
                  show-overflow-tooltip
                  sortable="custom"
                />
                <el-table-column
                  v-if="['sale', 'sale_return', 'sale_exchange'].includes(detailOrder.orderType)"
                  prop="receivedAmount"
                  label="实付金额"
                  min-width="110"
                  sortable="custom"
                >
                  <template #default="{ row }">¥ {{ formatMoney(row.receivedAmount) }}</template>
                </el-table-column>
                <el-table-column
                  v-if="['sale', 'sale_return', 'sale_exchange'].includes(detailOrder.orderType)"
                  prop="saleShopName"
                  label="销售店铺"
                  min-width="170"
                  show-overflow-tooltip
                  sortable="custom"
                />
                <el-table-column
                  v-if="detailUsesReceiveShopColumn"
                  prop="receiveShopName"
                  label="收货店铺/仓库"
                  min-width="170"
                  show-overflow-tooltip
                  sortable="custom"
                />
                <el-table-column
                  prop="goodsName"
                  label="商品名称"
                  min-width="220"
                  show-overflow-tooltip
                  :fixed="['sale', 'sale_return', 'sale_exchange'].includes(detailOrder.orderType) ? undefined : 'left'"
                  class-name="aqc-fixed-left-column"
                  label-class-name="aqc-fixed-left-column"
                  sortable="custom"
                />
                <el-table-column prop="quantity" label="数量" min-width="90" sortable="custom" />
                <el-table-column label="单位" width="80" align="center">
                  <template #default>只</template>
                </el-table-column>
                <el-table-column v-if="detailIsSaleAffectingInventory" prop="couponAmount" label="优惠券" min-width="100" sortable="custom">
                  <template #default="{ row }">¥ {{ formatMoney(row.couponAmount) }}</template>
                </el-table-column>
                <el-table-column v-if="detailIsSaleAffectingInventory" prop="discountRate" label="折扣" min-width="90" sortable="custom" />
                <el-table-column v-if="detailOrder.orderType === 'transfer'" prop="sourceStock" label="发货库存" min-width="110" sortable="custom" />
                <el-table-column v-if="detailOrder.orderType === 'transfer'" prop="targetStock" label="收货库存" min-width="110" sortable="custom" />
                <el-table-column prop="unitPrice" label="单价" min-width="110" sortable="custom">
                  <template #default="{ row }">¥ {{ formatMoney(row.unitPrice) }}</template>
                </el-table-column>
                <el-table-column :prop="['sale', 'sale_return', 'sale_exchange'].includes(detailOrder.orderType) ? 'receivableAmount' : 'totalAmount'" :label="['sale', 'sale_return', 'sale_exchange'].includes(detailOrder.orderType) ? '应付金额' : '金额'" min-width="120" sortable="custom">
                  <template #default="{ row }">¥ {{ formatMoney(row.totalAmount) }}</template>
                </el-table-column>
                <el-table-column v-if="detailOrder.orderType === 'purchase'" prop="brand" label="品牌" min-width="120" sortable="custom" />
                <el-table-column v-if="detailOrder.orderType === 'purchase'" prop="series" label="系列" min-width="140" sortable="custom" />
                <el-table-column prop="barcode" label="条码" min-width="160" show-overflow-tooltip sortable="custom" />
                <el-table-column v-if="detailIsSaleAffectingInventory" prop="channel" label="渠道" min-width="110" show-overflow-tooltip sortable="custom" />
                <el-table-column v-if="detailIsSaleAffectingInventory" prop="shipShopName" label="发货店铺/仓库" min-width="170" show-overflow-tooltip sortable="custom" />
                <el-table-column v-if="detailIsSaleAffectingInventory" prop="customerName" label="客户姓名" min-width="120" show-overflow-tooltip sortable="custom" />
                <el-table-column prop="remark" label="备注" min-width="160" show-overflow-tooltip sortable="custom" />
              </el-table>
            </div>

            <div v-if="detailItemsTotal > detailItemsPageSize" class="pager-wrap work-order-items-pager">
              <el-pagination
                background
                layout="total, sizes, prev, pager, next, jumper"
                :total="detailItemsTotal"
                :current-page="detailItemsPage"
                :page-size="detailItemsPageSize"
                :page-sizes="[20, 50, 100]"
                @current-change="onDetailItemsPageChange"
                @size-change="onDetailItemsPageSizeChange"
              />
            </div>

            <div class="selected-goods-meta work-order-grand-summary">
              <span>总合计</span>
              <span>总数量 {{ detailGrandTotals.quantity }}</span>
              <span v-if="['sale', 'sale_return', 'sale_exchange'].includes(detailOrder.orderType)">总实付 ¥ {{ formatMoney(detailGrandTotals.received) }}</span>
              <span>总金额 ¥ {{ formatMoney(detailGrandTotals.amount) }}</span>
            </div>
            </template>

            <template v-else>
              <div class="panel-head-simple work-order-section-head">
                <div>
                  <h3>换入明细</h3>
                </div>
              </div>
              <div class="table-shell open-table-shell">
                <el-table :data="detailIncomingItems" border stripe show-summary :summary-method="detailTableSummary" @sort-change="onDetailTableSortChange">
                  <el-table-column prop="orderNum" label="订单号" min-width="180" show-overflow-tooltip sortable="custom" />
                  <el-table-column prop="salesperson" label="销售员" min-width="120" show-overflow-tooltip sortable="custom" />
                  <el-table-column prop="saleShopName" label="销售店铺" min-width="170" show-overflow-tooltip sortable="custom" />
                  <el-table-column prop="receiveShopName" label="收货店铺/仓库" min-width="170" show-overflow-tooltip sortable="custom" />
                  <el-table-column prop="receivedAmount" label="实付金额" min-width="110" sortable="custom">
                    <template #default="{ row }">¥ {{ formatMoney(row.receivedAmount) }}</template>
                  </el-table-column>
                  <el-table-column prop="goodsName" label="商品名称" min-width="220" show-overflow-tooltip sortable="custom" />
                  <el-table-column prop="unitPrice" label="单价" min-width="110" sortable="custom">
                    <template #default="{ row }">¥ {{ formatMoney(row.unitPrice) }}</template>
                  </el-table-column>
                  <el-table-column prop="quantity" label="数量" min-width="90" sortable="custom" />
                  <el-table-column label="单位" width="80" align="center">
                    <template #default>只</template>
                  </el-table-column>
                  <el-table-column prop="receivableAmount" label="应付金额" min-width="120" sortable="custom">
                    <template #default="{ row }">¥ {{ formatMoney(row.receivableAmount) }}</template>
                  </el-table-column>
                  <el-table-column prop="barcode" label="条码" min-width="160" show-overflow-tooltip sortable="custom" />
                  <el-table-column prop="remark" label="备注" min-width="160" show-overflow-tooltip sortable="custom" />
                </el-table>
              </div>

              <div class="selected-goods-meta work-order-grand-summary">
                <span>换入总合计</span>
                <span>总数量 {{ detailIncomingGrandTotals.quantity }}</span>
                <span>总实付 ¥ {{ formatMoney(detailIncomingGrandTotals.received) }}</span>
                <span>总金额 ¥ {{ formatMoney(detailIncomingGrandTotals.amount) }}</span>
              </div>

              <div class="panel-head-simple work-order-section-head">
                <div>
                  <h3>换出明细</h3>
                </div>
              </div>
              <div class="table-shell open-table-shell">
                <el-table :data="detailOutgoingItems" border stripe show-summary :summary-method="detailTableSummary" @sort-change="onDetailTableSortChange">
                  <el-table-column prop="goodsName" label="商品名称" min-width="220" show-overflow-tooltip sortable="custom" />
                  <el-table-column prop="quantity" label="数量" min-width="90" sortable="custom" />
                  <el-table-column prop="unitPrice" label="单价" min-width="110" sortable="custom">
                    <template #default="{ row }">¥ {{ formatMoney(row.unitPrice) }}</template>
                  </el-table-column>
                  <el-table-column prop="receivableAmount" label="应付金额" min-width="120" sortable="custom">
                    <template #default="{ row }">¥ {{ formatMoney(row.receivableAmount) }}</template>
                  </el-table-column>
                  <el-table-column prop="receivedAmount" label="实付金额" min-width="110" sortable="custom">
                    <template #default="{ row }">¥ {{ formatMoney(row.receivedAmount) }}</template>
                  </el-table-column>
                  <el-table-column prop="couponAmount" label="优惠券" min-width="100" sortable="custom">
                    <template #default="{ row }">¥ {{ formatMoney(row.couponAmount) }}</template>
                  </el-table-column>
                  <el-table-column prop="discountRate" label="折扣" min-width="90" sortable="custom" />
                  <el-table-column prop="saleShopName" label="销售店铺" min-width="170" show-overflow-tooltip sortable="custom" />
                  <el-table-column prop="shipShopName" label="发货店铺" min-width="170" show-overflow-tooltip sortable="custom" />
                  <el-table-column prop="salesperson" label="销售员" min-width="120" show-overflow-tooltip sortable="custom" />
                  <el-table-column prop="customerName" label="客户姓名" min-width="120" show-overflow-tooltip sortable="custom" />
                  <el-table-column prop="barcode" label="条码" min-width="160" show-overflow-tooltip sortable="custom" />
                  <el-table-column prop="remark" label="备注" min-width="160" show-overflow-tooltip sortable="custom" />
                </el-table>
              </div>

              <div class="selected-goods-meta work-order-grand-summary">
                <span>换出总合计</span>
                <span>总数量 {{ detailOutgoingGrandTotals.quantity }}</span>
                <span>总实付 ¥ {{ formatMoney(detailOutgoingGrandTotals.received) }}</span>
                <span>总金额 ¥ {{ formatMoney(detailOutgoingGrandTotals.amount) }}</span>
              </div>
            </template>
          </section>

          <section class="card-surface work-order-action-panel">
            <div class="panel-head-simple">
              <div>
                <h3>审批记录</h3>
              </div>
            </div>
            <el-timeline>
              <el-timeline-item
                v-for="item in detailOrder.actions"
                :key="item.id"
                :timestamp="formatDateLabel(item.createdAt)"
                placement="top"
              >
                <div class="work-order-action-item">
                  <strong>{{ item.actionLabel }}</strong>
                  <p>{{ item.actorName || '系统' }}</p>
                  <span v-if="item.comment">{{ item.comment }}</span>
                </div>
              </el-timeline-item>
            </el-timeline>
          </section>

          <section v-if="detailOrder.canReview" class="card-surface work-order-review-panel">
            <div class="panel-head-simple">
              <div>
                <h3>审批操作</h3>
              </div>
            </div>
            <el-input
              v-model.trim="reviewComment"
              type="textarea"
              :rows="4"
              maxlength="1000"
              show-word-limit
              placeholder="可填写审批意见"
            />
          </section>
        </template>
      </div>

      <template #footer>
        <div class="form-actions">
          <el-button v-if="detailOrder" @click="printOrder(detailOrder)">打印</el-button>
          <el-button
            v-if="detailOrder?.canEdit && canWrite && ['draft', 'rejected'].includes(String(detailOrder?.status || ''))"
            type="primary"
            :loading="submittingDetailReview"
            @click="submitDetailOrderForReview"
          >
            提交审批
          </el-button>
          <el-button v-if="detailOrder?.canEdit && canWrite" @click="openEditDialog(detailOrder.id)">编辑</el-button>
          <el-button @click="detailVisible = false">关闭</el-button>
          <el-button
            v-if="detailOrder?.canReview"
            type="danger"
            :loading="reviewing"
            @click="reviewCurrent(false)"
          >
            不通过
          </el-button>
          <el-button
            v-if="detailOrder?.canReview"
            type="primary"
            :loading="reviewing"
            @click="reviewCurrent(true)"
          >
            通过
          </el-button>
        </div>
      </template>
    </ResponsiveDialog>

    <el-dialog
      v-model="logVisible"
      title="工单日志"
      width="min(1180px, 96vw)"
      append-to-body
      align-center
      destroy-on-close
      class="aqc-app-dialog work-order-log-dialog"
    >
      <section class="card-surface work-order-log-panel">
        <div class="records-toolbar work-order-log-toolbar">
          <el-input
            v-model.trim="logKeyword"
            clearable
            placeholder="搜索工单编号 / 事由 / 备注 / 操作人员"
            class="toolbar-search toolbar-search-wide"
            @keyup.enter="onLogSearch"
          />

          <el-select v-model="logScope" class="work-order-log-select">
            <el-option
              v-for="item in scopeOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>

          <el-select v-model="logOrderTypeFilter" clearable placeholder="全部工单类型" class="work-order-log-select">
            <el-option
              v-for="item in meta.types"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>

          <el-date-picker
            v-model="logDateFrom"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="开始日期"
            style="width: 160px"
          />

          <el-date-picker
            v-model="logDateTo"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="结束日期"
            style="width: 160px"
          />

          <div class="toolbar-actions">
            <el-button :loading="logLoading" @click="onLogSearch">查询</el-button>
            <el-button @click="resetLogFilters">重置</el-button>
          </div>
        </div>

        <div class="table-shell open-table-shell">
          <el-table :data="logRows" border stripe v-loading="logLoading" empty-text="暂无工单日志">
            <el-table-column prop="createdAt" label="变更时间" min-width="170" show-overflow-tooltip />
            <el-table-column prop="orderNum" label="工单编号" min-width="180" show-overflow-tooltip />
            <el-table-column prop="orderTypeLabel" label="工单类型" min-width="120" />
            <el-table-column prop="actionLabel" label="操作" min-width="110" />
            <el-table-column prop="reason" label="工单事由" min-width="220" show-overflow-tooltip>
              <template #default="{ row }">{{ replaceShopNameAliases(row.reason) || '-' }}</template>
            </el-table-column>
            <el-table-column prop="applicantName" label="申请人" min-width="110" show-overflow-tooltip />
            <el-table-column prop="approverName" label="负责人" min-width="110" show-overflow-tooltip />
            <el-table-column prop="actorName" label="操作人员" min-width="110" show-overflow-tooltip />
            <el-table-column prop="comment" label="备注" min-width="180" show-overflow-tooltip />
          </el-table>
        </div>

        <div class="pager-wrap">
          <el-pagination
            background
            layout="total, prev, pager, next, sizes"
            :total="logTotal"
            :current-page="logPage"
            :page-size="logPageSize"
            :page-sizes="[20, 50, 100]"
            @current-change="onLogPageChange"
            @size-change="onLogPageSizeChange"
          />
        </div>
      </section>
    </el-dialog>

    <ResponsiveDialog
      v-model="allocationVisible"
      :title="allocationTitle"
      width="min(1480px, 98vw)"
      class="aqc-app-dialog work-order-allocation-dialog"
      mobile-subtitle="工单管理"
      :initial-snap="0.72"
      :expanded-snap="0.96"
      :before-close="handleAllocationDialogBeforeClose"
    >
      <div class="work-order-allocation-shell" v-loading="allocationLoading">
        <div class="goods-step-strip work-order-step-strip">
          <button
            v-for="step in allocationStepOptions"
            :key="step.value"
            type="button"
            class="goods-step-button"
            :class="{ active: allocationStep === step.value, completed: allocationStep > step.value }"
            @click="goToAllocationStep(step.value)"
          >
            <span class="step-number">{{ step.value }}</span>
            <span>{{ step.label }}</span>
          </button>
        </div>

        <section class="card-surface work-order-editor-summary">
          <div class="work-order-detail-title">
            <div>
              <span class="work-order-category-caption">已审批工单分配</span>
              <h3>{{ allocationSourceOrder?.orderTypeLabel || '工单分配' }}</h3>
            </div>
            <div class="selected-goods-meta">
              <span>来源单号 {{ allocationForm.orderNum || '-' }}</span>
              <span>发货仓库 {{ displayShopName(allocationForm.sourceShopName) || '-' }}</span>
              <span>目标点位 {{ allocationForm.targetShopIds.length }}</span>
              <span>商品 {{ allocationRows.length }}</span>
            </div>
          </div>

          <div class="work-order-detail-grid">
            <div class="work-order-detail-item">
              <span>来源工单</span>
              <strong>{{ allocationSourceOrder?.reason ? replaceShopNameAliases(allocationSourceOrder.reason) : (allocationForm.orderNum || '-') }}</strong>
            </div>
            <div class="work-order-detail-item">
              <span>分配发货仓库</span>
              <strong>{{ displayShopName(allocationForm.sourceShopName) || '-' }}</strong>
            </div>
            <div class="work-order-detail-item">
              <span>负责人</span>
              <strong>{{ allocationApproverDisplayName || '-' }}</strong>
            </div>
            <div class="work-order-detail-item">
              <span>共享群组</span>
              <strong>{{ allocationForm.groupName || '-' }}</strong>
            </div>
          </div>
        </section>

        <section v-show="allocationStep === 1" class="card-surface work-order-allocation-settings-panel">
          <div class="panel-head-simple">
            <div>
              <h3>分配设置</h3>
              <p>先确定分配顺序、收货店铺/仓库与负责人，再进入分配编辑。</p>
            </div>
          </div>

          <div class="sales-filter-grid work-order-allocation-settings-grid">
            <div class="sales-filter-field">
              <label class="sales-filter-label">发货仓库/店铺</label>
              <el-input :model-value="displayShopName(allocationForm.sourceShopName)" readonly />
            </div>

            <div class="sales-filter-field">
              <label class="sales-filter-label">负责人</label>
              <el-select
                v-model="allocationForm.approverId"
                clearable
                filterable
                class="full-width"
                placeholder="请选择负责人"
              >
                <el-option
                  v-for="item in allocationApproverOptions"
                  :key="item.id"
                  :label="item.displayName ? `${item.displayName} · ${item.username}` : item.username"
                  :value="item.id"
                />
              </el-select>
            </div>

            <div class="sales-filter-field">
              <label class="sales-filter-label">共享群组</label>
              <el-input :model-value="allocationForm.groupName || '无'" readonly />
            </div>
          </div>

          <section class="goods-compare-panel">
            <div class="goods-compare-selection-summary work-order-allocation-target-summary">
              <div class="export-columns-copy">
                <strong>选择收货店铺 / 仓库</strong>
                <span>点位的选择顺序会直接决定后续分配编辑表格的列顺序。</span>
              </div>
              <strong>{{ allocationForm.targetShopIds.length }} 个已选择</strong>
            </div>

            <div class="inventory-button-grid goods-compare-location-grid">
              <div
                v-for="item in allocationTargetOptions"
                :key="item.id"
                class="inventory-button-row goods-compare-location-row"
              >
                <button
                  type="button"
                  class="inventory-button-main goods-compare-location-button"
                  :class="{ active: allocationForm.targetShopIds.includes(item.id) }"
                  @click="toggleAllocationTarget(item.id)"
                >
                  <span v-if="resolveAllocationTargetOrder(item.id) > 0" class="goods-compare-location-order">
                    {{ resolveAllocationTargetOrder(item.id) }}
                  </span>
                  <span>{{ displayShopName(item.name) }}</span>
                </button>
              </div>
            </div>
          </section>
        </section>

        <section v-show="allocationStep === 2" class="card-surface work-order-items-panel work-order-allocation-editor-panel">
          <div class="panel-head-simple">
            <div>
              <h3>分配编辑</h3>
              <p>保存后可再次进入继续编辑；确认后会按点位自动生成商品调拨单草稿。</p>
            </div>
          </div>

          <div class="work-order-allocation-summary-grid">
            <article class="work-order-allocation-summary-card">
              <span>已选点位</span>
              <strong>{{ allocationForm.targetShopIds.length }}</strong>
            </article>
            <article class="work-order-allocation-summary-card">
              <span>商品行数</span>
              <strong>{{ allocationRows.length }}</strong>
            </article>
            <article class="work-order-allocation-summary-card">
              <span>待确认异常</span>
              <strong>{{ allocationWarningCount }}</strong>
            </article>
          </div>

          <div v-if="allocationWarningLines.length" class="work-order-allocation-warning-strip">
            <strong>当前分配存在待确认项</strong>
            <span>{{ allocationWarningLines.slice(0, 3).join('；') }}</span>
          </div>

          <div class="table-shell open-table-shell work-order-allocation-table-shell">
            <el-table
              class="work-order-allocation-table"
              :data="allocationPagedRows"
              border
              stripe
              row-key="workOrderItemId"
              :max-height="allocationTableMaxHeight"
              empty-text="暂无可分配商品"
              @sort-change="onAllocationTableSortChange"
            >
              <el-table-column prop="goodsName" label="商品名称" min-width="220" fixed="left" sortable="custom">
                <template #default="{ row }">
                  <div class="work-order-allocation-goods-cell">
                    <strong>{{ row.goodsName || row.barcode || '-' }}</strong>
                    <span v-if="row.brand || row.series">{{ [row.brand, row.series].filter(Boolean).join(' / ') }}</span>
                    <small>单价 ¥ {{ formatMoney(row.unitPrice) }}</small>
                    <small>原单/库存数量 {{ formatAllocationOriginalStockQuantity(row) }}，已分配 {{ allocationRowAssignedQuantity(row) }}</small>
                  </div>
                </template>
              </el-table-column>

              <el-table-column
                v-for="target in selectedAllocationTargets"
                :key="`allocation-target-${target.id}`"
                :label="displayShopName(target.shortName || target.name)"
                min-width="196"
              >
                <el-table-column label="变动库存" min-width="120" align="center">
                  <template #default="{ row }">
                    <input
                      :value="String(getAllocationQuantity(row, target.id))"
                      type="number"
                      min="0"
                      step="1"
                      inputmode="numeric"
                      class="allocation-qty-input"
                      @input="onAllocationQuantityInput(row, target.id, $event)"
                    />
                  </template>
                </el-table-column>
                <el-table-column label="库存" min-width="92" align="center">
                  <template #default="{ row }">{{ getAllocationCurrentStock(row, target.id) }}</template>
                </el-table-column>
              </el-table-column>
            </el-table>
          </div>

          <div class="pager-wrap work-order-allocation-pager">
            <el-pagination
              background
              layout="total, prev, pager, next, sizes"
              :total="allocationRows.length"
              :current-page="allocationItemsPage"
              :page-size="allocationItemsPageSize"
              :page-sizes="allocationPageSizeOptions"
              @current-change="allocationItemsPage = $event"
              @size-change="(value) => { allocationItemsPageSize = value; allocationItemsPage = 1 }"
            />
          </div>
        </section>
      </div>

      <template #footer>
        <div class="form-actions">
          <template v-if="allocationStep === 1">
            <el-button @click="requestCloseAllocation()">退出</el-button>
            <el-button type="primary" :loading="allocationSaving" @click="enterAllocationEdit">确认并进入分配编辑</el-button>
          </template>
          <template v-else>
            <el-button @click="goToAllocationStep(1)">返回设置</el-button>
            <el-button :loading="allocationSaving" @click="saveAllocationDraft">保存</el-button>
            <el-button type="primary" :loading="allocationConfirming" @click="confirmAllocationDraft">确认</el-button>
          </template>
        </div>
      </template>
    </ResponsiveDialog>

    <ResponsiveDialog
      v-model="groupDialogVisible"
      title="群组管理"
      width="min(960px, 96vw)"
      class="aqc-app-dialog work-order-group-dialog"
      mobile-subtitle="工单管理"
      :initial-snap="0.6"
      :expanded-snap="0.92"
    >
      <section class="work-order-group-panel">
        <div v-if="meta.groups.length" class="work-order-group-list">
          <article
            v-for="item in meta.groups"
            :key="item.id"
            class="work-order-group-card"
          >
            <div class="work-order-group-card-copy">
              <strong>{{ item.name }}</strong>
              <span>{{ item.description || '暂无群组说明' }}</span>
              <small>{{ item.memberCount }} 人 · {{ resolveGroupRoleLabel(item.memberRole) }}</small>
            </div>
            <div class="work-order-group-card-actions">
              <el-button
                v-if="item.isDefault"
                type="primary"
                plain
                disabled
              >
                默认
              </el-button>
              <el-button
                v-else
                @click="setDefaultGroup(item)"
              >
                默认
              </el-button>
              <el-button
                v-if="canManageGroup(item)"
                @click="openEditGroupDialog(item)"
              >
                编辑
              </el-button>
              <el-button
                v-if="canManageGroup(item)"
                @click="openInviteGroupDialog(item)"
              >
                邀请成员
              </el-button>
              <el-button
                v-if="canManageGroup(item)"
                type="danger"
                @click="confirmDeleteGroup(item)"
              >
                删除
              </el-button>
            </div>
          </article>
        </div>
        <div v-else class="empty-state-inline">
          <span>当前还没有可用群组，先创建一个多人协作群组吧。</span>
        </div>

        <div v-if="canWrite" class="work-order-group-footer">
          <el-button type="primary" @click="openCreateGroupDialog">新建群组</el-button>
        </div>
      </section>
    </ResponsiveDialog>

    <ResponsiveDialog
      v-model="groupCreateVisible"
      :title="groupFormTitle"
      width="min(720px, 94vw)"
      class="aqc-app-dialog work-order-group-form-dialog"
      mobile-subtitle="群组管理"
    >
      <el-form label-position="top" class="dialog-form">
        <div class="sales-filter-grid work-order-group-form-grid">
          <div class="sales-filter-field sales-filter-field-wide">
            <label class="sales-filter-label">群组名称</label>
            <el-input v-model.trim="groupCreateForm.name" maxlength="80" placeholder="例如：门店协作组" />
          </div>
          <div class="sales-filter-field sales-filter-field-wide">
            <label class="sales-filter-label">群组说明</label>
            <el-input v-model.trim="groupCreateForm.description" maxlength="255" placeholder="可选" />
          </div>
          <div class="sales-filter-field sales-filter-field-wide">
            <label class="sales-filter-label">邀请成员</label>
            <el-select
              v-model="groupCreateForm.inviteUserIds"
              multiple
              filterable
              class="full-width"
              placeholder="至少选择 1 名其他成员"
            >
              <el-option
                v-for="item in groupInviteOptions"
                :key="item.id"
                :label="item.displayName ? `${item.displayName} · ${item.username}` : item.username"
                :value="item.id"
              />
            </el-select>
          </div>
        </div>
      </el-form>

      <template #footer>
        <div class="form-actions">
          <el-button @click="groupCreateVisible = false">取消</el-button>
          <el-button type="primary" :loading="groupSaving" @click="submitCreateGroup">{{ groupFormActionText }}</el-button>
        </div>
      </template>
    </ResponsiveDialog>

    <ResponsiveDialog
      v-model="groupInviteVisible"
      :title="`邀请加入 · ${inviteTargetGroup?.name || '群组'}`"
      width="min(720px, 94vw)"
      class="aqc-app-dialog work-order-group-form-dialog"
      mobile-subtitle="群组管理"
    >
      <el-form label-position="top" class="dialog-form">
        <div class="sales-filter-grid work-order-group-form-grid">
          <div class="sales-filter-field sales-filter-field-wide">
            <label class="sales-filter-label">邀请成员</label>
            <el-select
              v-model="groupInviteForm.inviteUserIds"
              multiple
              filterable
              class="full-width"
              placeholder="选择要邀请的成员"
            >
              <el-option
                v-for="item in groupInviteOptions"
                :key="item.id"
                :label="item.displayName ? `${item.displayName} · ${item.username}` : item.username"
                :value="item.id"
              />
            </el-select>
          </div>
        </div>
      </el-form>

      <template #footer>
        <div class="form-actions">
          <el-button @click="groupInviteVisible = false">取消</el-button>
          <el-button type="primary" :loading="groupInviting" @click="submitGroupInvite">发送邀请</el-button>
        </div>
      </template>
    </ResponsiveDialog>

    <WorkOrderGoodsPickerDialog
      v-model="goodsPickerVisible"
      title="选择商品"
      :z-index="98040"
      :distribution-shop-id="goodsPickerDistributionShopId"
      :quantity-label="goodsPickerQuantityLabel"
      :secondary-distribution-shop-id="goodsPickerSecondaryDistributionShopId"
      :secondary-quantity-label="goodsPickerSecondaryQuantityLabel"
      @select="handleGoodsPicked"
    />

    <WorkOrderGoodsBatchDialog
      v-model="goodsBatchVisible"
      title="批量录入商品"
      :z-index="98040"
      :distribution-shop-id="goodsPickerDistributionShopId"
      :quantity-label="goodsPickerQuantityLabel"
      :secondary-distribution-shop-id="goodsPickerSecondaryDistributionShopId"
      :secondary-quantity-label="goodsPickerSecondaryQuantityLabel"
      @confirm="handleBatchGoodsConfirm"
    />

    <WorkOrderSalesPickerDialog
      v-model="salesPickerVisible"
      title="选择销售记录"
      :z-index="98040"
      :shop-id="Number(form.sourceShopId || 0) || null"
      :returnable-only="form.orderType === 'sale_return' || form.orderType === 'sale_exchange'"
      @select="handleSalesPicked"
    />

    <WorkOrderSalesPickerDialog
      v-model="salesBatchVisible"
      title="批量录入订单"
      :z-index="98040"
      :shop-id="Number(form.sourceShopId || 0) || null"
      :returnable-only="form.orderType === 'sale_return' || form.orderType === 'sale_exchange'"
      multiple
      @confirm="handleBatchSalesConfirm"
    />
  </section>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'

import CollapsePanelTransition from '../components/CollapsePanelTransition.vue'
import ResponsiveDialog from '../components/ResponsiveDialog.vue'
import ResponsiveTableActions from '../components/ResponsiveTableActions.vue'
import WorkOrderGoodsBatchDialog from '../components/WorkOrderGoodsBatchDialog.vue'
import WorkOrderGoodsPickerDialog from '../components/WorkOrderGoodsPickerDialog.vue'
import WorkOrderSalesPickerDialog from '../components/WorkOrderSalesPickerDialog.vue'
import { useMobileViewport } from '../composables/useMobileViewport'
import { apiDelete, apiGet, apiPost, apiPut } from '../services/api'
import { useAuthStore } from '../stores/auth'
import { confirmAction, confirmDestructiveAction } from '../utils/confirm'
import { getShanghaiDateTimeLocalValue, getShanghaiTimestamp } from '../utils/shanghaiTime'
import { resolveTableActionWidth } from '../utils/tableActions'
import { displayShopName, replaceShopNameAliases, SHOP_TYPE_OTHER_WAREHOUSE } from '../utils/shops'

const authStore = useAuthStore()
const { isMobileViewport } = useMobileViewport()
const route = useRoute()
const router = useRouter()
const ALLOCATION_TARGET_MEMORY_KEY = 'aqc_n_allocation_target_memory_v1'

const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const orders = ref([])
const keyword = ref('')
const dateRange = ref([])
const orderTypeFilter = ref('')
const statusFilter = ref('')
const applicantFilter = ref(null)
const approverFilter = ref(null)
const scope = ref('mine')
const filterPanelOpen = ref(false)
const editorVisible = ref(false)
const categoryDialogVisible = ref(false)
const editorStep = ref(1)
const detailVisible = ref(false)
const detailLoading = ref(false)
const submittingDetailReview = ref(false)
const allocationVisible = ref(false)
const allocationLoading = ref(false)
const allocationSaving = ref(false)
const allocationConfirming = ref(false)
const allocationStep = ref(1)
const allocationSnapshot = ref('')
const allocationSourceOrder = ref(null)
const allocationTargetOptions = ref([])
const allocationApproverOptions = ref([])
const allocationItemsPage = ref(1)
const allocationItemsPageSize = ref(20)
const savingDraft = ref(false)
const submitting = ref(false)
const reviewing = ref(false)
const detailOrder = ref(null)
const editorItemsPage = ref(1)
const detailItemsPage = ref(1)
const editorItemsPageSize = ref(20)
const detailItemsPageSize = ref(20)
const editorSortState = reactive({ prop: '', order: '' })
const detailSortState = reactive({ prop: '', order: '' })
const allocationSortState = reactive({ prop: '', order: '' })
const reviewComment = ref('')
const goodsPickerVisible = ref(false)
const goodsBatchVisible = ref(false)
const salesPickerVisible = ref(false)
const salesBatchVisible = ref(false)
const currentGoodsPickerRowKey = ref('')
const currentSalesPickerRowKey = ref('')
const currentBatchTarget = ref('default')
const batchRowCount = ref(3)
const quickAddQuery = ref('')
const quickAddMatchedLabel = ref('')
const quickAddLoading = ref(false)
const quickAddFieldRef = ref(null)
const quickAddBarRef = ref(null)
const goodsInventorySnapshots = reactive({})
const editorSnapshot = ref('')
const groupDialogVisible = ref(false)
const workOrderSettingsDialogVisible = ref(false)
const groupCreateVisible = ref(false)
const groupInviteVisible = ref(false)
const groupSaving = ref(false)
const groupInviting = ref(false)
const workOrderSettingsSaving = ref(false)
const inviteTargetGroup = ref(null)
const editingGroupId = ref(null)
const logVisible = ref(false)
const logLoading = ref(false)
const logTotal = ref(0)
const logPage = ref(1)
const logPageSize = ref(20)
const logRows = ref([])
const logScope = ref('mine')
const logOrderTypeFilter = ref('')
const logKeyword = ref('')
const logDateFrom = ref('')
const logDateTo = ref('')
const tableActionWidth = computed(() => resolveTableActionWidth(
  (orders.value.length ? orders.value : [{ id: 0 }]).map((row) => [
    '查看',
    row.id ? (canAllocateRow(row) ? '分配' : '') : '分配',
    row.id ? (canEditRow(row) ? '编辑' : '') : '编辑',
    row.id ? (canWithdrawRow(row) ? '转草稿' : '') : '转草稿',
    row.id ? (canDeleteRow(row) ? '删除' : '') : '删除',
    row.id ? (canReviewRow(row) ? '审批' : '') : '审批',
    '打印',
  ]),
  {
    compact: isMobileViewport.value,
    minWidth: 132,
    maxWidth: 468,
  },
))
const itemActionWidth = computed(() => resolveTableActionWidth([['清空', '删除本行']], {
  compact: isMobileViewport.value,
  minWidth: 128,
  maxWidth: 208,
}))
const showQuickAddBar = computed(() => !isSaleExchangeType.value && !usesSalesRecordBinding.value)

const meta = reactive({
  types: [],
  categories: [],
  statuses: [],
  shopOptions: [],
  storeOptions: [],
  warehouseOptions: [],
  otherWarehouseOptions: [],
  applicantOptions: [],
  approverOptions: [],
  groups: [],
  goodsBrandOptions: [],
  goodsSeriesOptions: [],
  defaultApproverSettings: [],
})
const salespersonBulkValue = reactive({
  default: '',
  incoming: '',
  outgoing: '',
})
const discountBulkValue = reactive({
  default: 10,
})
const locationBulkValue = reactive({
  defaultSale: null,
  defaultShip: null,
})
const workOrderSettings = ref([])
const saleShipShopId = ref(null)

const dashboard = reactive({
  draftCount: 0,
  pendingCount: 0,
  approvalCount: 0,
  recentMine: [],
  pendingApprovals: [],
})

let rowSeed = 1
let editorFocusRetryTimers = []
let editorFocusRequestToken = 0
const editorFieldElementRegistry = new Map()
const goodsSelectionLocks = new Set()
const goodsLookupTokens = new Map()
const barcodeLookupTokens = new Map()
const salesRecordLookupTokens = new Map()
const resolvedBarcodeByRow = new Map()
let quickAddLookupToken = null

const editorStepOptions = [
  { value: 1, label: '工单信息' },
  { value: 2, label: '工单明细' },
]
const allocationStepOptions = [
  { value: 1, label: '分配设置' },
  { value: 2, label: '分配编辑' },
]
const allocationPageSizeOptions = [10, 20, 50, 100]

const form = reactive({
  id: null,
  orderNum: '',
  orderType: 'transfer',
  saleAffectsInventory: false,
  reason: '',
  formDate: defaultDateTimeLocal(),
  sourceShopId: null,
  targetShopId: null,
  supplierName: '',
  partnerName: '',
  approverId: null,
  groupId: null,
  items: [],
  exchangeIncomingItems: [],
  exchangeOutgoingItems: [],
})

const categoryDraft = reactive({
  category: 'goods',
})

const groupCreateForm = reactive({
  name: '',
  description: '',
  inviteUserIds: [],
})

const groupInviteForm = reactive({
  inviteUserIds: [],
})
const allocationForm = reactive({
  orderId: null,
  orderNum: '',
  orderType: '',
  sourceShopId: null,
  sourceShopName: '',
  approverId: null,
  groupId: null,
  groupName: '',
  targetShopIds: [],
})
const allocationRows = ref([])

const canApprove = computed(() => authStore.can('workorders.approve'))
const canWrite = computed(() => authStore.can('workorders.write'))
const canManageScheduledOrders = computed(() => canWrite.value && authStore.isAdmin)
const canFilterApprover = computed(() => authStore.isAdmin)
const groupInviteOptions = computed(() => (
  meta.applicantOptions.filter((item) => Number(item.id) !== Number(authStore.user?.id || 0))
))
const accessibleGroupIds = computed(() => (
  new Set(meta.groups.map((item) => Number(item.id || 0)).filter((id) => id > 0))
))
const applicantName = computed(() => authStore.displayName || authStore.user?.username || '当前账户')
const approverPlaceholder = computed(() => (authStore.isAdmin ? '请选择管理员负责人，可为本人' : '请选择负责人'))
const approverDisplayName = computed(() => {
  const matched = meta.approverOptions.find((item) => Number(item.id) === Number(form.approverId || 0))
  return matched?.displayName || matched?.username || ''
})
const defaultGroupId = computed(() => {
  const preferred = meta.groups.find((item) => item.isDefault)
  return preferred?.id || meta.groups[0]?.id || null
})
const currentGroupLabel = computed(() => {
  const matched = meta.groups.find((item) => Number(item.id) === Number(form.groupId || 0))
  return matched?.name || ''
})
const groupFormTitle = computed(() => (editingGroupId.value ? '编辑群组' : '新建群组'))
const groupFormActionText = computed(() => (editingGroupId.value ? '保存修改' : '创建并邀请'))
const allocationTitle = computed(() => (
  allocationForm.orderNum
    ? `工单分配 · ${allocationForm.orderNum}`
    : '工单分配'
))
const allocationApproverDisplayName = computed(() => {
  const matched = allocationApproverOptions.value.find((item) => Number(item.id) === Number(allocationForm.approverId || 0))
  return matched?.displayName || matched?.username || ''
})
const sourceDisplayName = computed(() => {
  const matched = sourceOptions.value.find((item) => Number(item.id) === Number(form.sourceShopId || 0))
  return displayShopName(matched?.name) || ''
})
const targetDisplayName = computed(() => {
  const matched = targetOptions.value.find((item) => Number(item.id) === Number(form.targetShopId || 0))
  return displayShopName(matched?.name) || ''
})
const saleShipDisplayName = computed(() => {
  const matched = stockLocationOptions.value.find((item) => Number(item.id) === Number(saleShipShopId.value || 0))
  return displayShopName(matched?.name) || ''
})
const currentTypeLabel = computed(() => findTypeLabel(form.orderType))
const currentCategory = computed(() => resolveOrderCategory(form.orderType))
const categoryOptions = computed(() => meta.categories || [])
const currentCategoryLabel = computed(() => resolveCategoryLabel(currentCategory.value))
const currentApplicantOption = computed(() => (
  meta.applicantOptions.find((item) => Number(item.id) === Number(authStore.user?.id || 0)) || null
))
const visibleTypeOptions = computed(() => (
  meta.types.filter((item) => resolveOrderCategory(item.value) === currentCategory.value)
))
const defaultReason = computed(() => buildDefaultReason())
const effectiveReason = computed(() => cleanReasonText(form.reason) || defaultReason.value)
const editorTitle = computed(() => (form.id ? `编辑工单 · ${form.orderNum}` : '新建工单'))
const showSourceSelector = computed(() => form.orderType !== 'purchase')
const showTargetSelector = computed(() => form.orderType === 'transfer' || form.orderType === 'purchase')
const isSaleExchangeType = computed(() => form.orderType === 'sale_exchange')
const isSalesOrderType = computed(() => ['sale', 'sale_return', 'sale_exchange'].includes(form.orderType))
const isSaleAffectingInventory = computed(() => form.orderType === 'sale' && form.saleAffectsInventory)
const usesReceiveShopColumn = computed(() => form.orderType === 'sale_return')
const usesSalesRecordBinding = computed(() => isSalesOrderType.value && !isSaleExchangeType.value && !isSaleAffectingInventory.value)
const sourceLabel = computed(() => (isSalesOrderType.value ? '销售店铺' : '发货仓库/店铺'))
const targetLabel = computed(() => '收货仓库/店铺')
const stockLocationOptions = computed(() => (
  meta.shopOptions.filter((item) => Number(item.shopType) !== SHOP_TYPE_OTHER_WAREHOUSE)
))
const sourceOptions = computed(() => {
  if (!isSalesOrderType.value) {
    return stockLocationOptions.value
  }
  return meta.storeOptions
})
const targetOptions = computed(() => stockLocationOptions.value)
const shopOptionMap = computed(() => {
  const entries = (meta.shopOptions || []).map((item) => [Number(item.id || 0), item])
  return new Map(entries)
})
const editorAllItems = computed(() => (
  isSaleExchangeType.value
    ? [...form.exchangeIncomingItems, ...form.exchangeOutgoingItems]
    : form.items
))
const totalQuantity = computed(() => editorAllItems.value.reduce((sum, item) => sum + Number(item.quantity || 0), 0))
const exchangeIncomingItems = computed(() => form.exchangeIncomingItems)
const exchangeOutgoingItems = computed(() => form.exchangeOutgoingItems)
const sortedExchangeIncomingItems = computed(() => sortWorkOrderRows(exchangeIncomingItems.value, editorSortState))
const sortedExchangeOutgoingItems = computed(() => sortWorkOrderRows(exchangeOutgoingItems.value, editorSortState))
const totalAmount = computed(() => editorAllItems.value.reduce((sum, item) => sum + Number(item.totalAmount || 0), 0))
const totalReceivedAmount = computed(() => editorAllItems.value.reduce((sum, item) => sum + Number(item.receivedAmount || 0), 0))
const editorGrandTotals = computed(() => buildWorkOrderTotals(form.items))
const exchangeIncomingGrandTotals = computed(() => buildWorkOrderTotals(form.exchangeIncomingItems))
const exchangeOutgoingGrandTotals = computed(() => buildWorkOrderTotals(form.exchangeOutgoingItems))
const editorItemsPageCount = computed(() => Math.max(1, Math.ceil(form.items.length / editorItemsPageSize.value)))
const editorItemStartIndex = computed(() => (editorItemsPage.value - 1) * editorItemsPageSize.value)
const sortedEditorItems = computed(() => sortWorkOrderRows(form.items, editorSortState))
const editorEmptyText = computed(() => (
  showQuickAddBar.value
    ? '点击新增一行、批量录入，或使用连续新增栏开始录入'
    : '点击新增一行或批量录入开始录入'
))
const editorPagedItems = computed(() => (
  sortedEditorItems.value.slice(editorItemStartIndex.value, editorItemStartIndex.value + editorItemsPageSize.value)
))
const detailItemsTotal = computed(() => Array.isArray(detailOrder.value?.items) ? detailOrder.value.items.length : 0)
const detailItemsPageCount = computed(() => Math.max(1, Math.ceil(detailItemsTotal.value / detailItemsPageSize.value)))
const detailItemStartIndex = computed(() => (detailItemsPage.value - 1) * detailItemsPageSize.value)
const sortedDetailItems = computed(() => sortWorkOrderRows(Array.isArray(detailOrder.value?.items) ? detailOrder.value.items : [], detailSortState))
const detailIncomingItems = computed(() => (
  sortedDetailItems.value.filter((item) => String(item.lineType || 'default') !== 'outgoing')
))
const detailOutgoingItems = computed(() => (
  sortedDetailItems.value.filter((item) => String(item.lineType || 'default') === 'outgoing')
))
const detailIsSaleAffectingInventory = computed(() => (
  detailOrder.value?.orderType === 'sale' && Boolean(detailOrder.value?.saleAffectsInventory)
))
const detailUsesReceiveShopColumn = computed(() => detailOrder.value?.orderType === 'sale_return')
const detailPagedItems = computed(() => (
  sortedDetailItems.value.slice(detailItemStartIndex.value, detailItemStartIndex.value + detailItemsPageSize.value)
))
const detailGrandTotals = computed(() => buildWorkOrderTotals(sortedDetailItems.value))
const detailIncomingGrandTotals = computed(() => buildWorkOrderTotals(detailIncomingItems.value))
const detailOutgoingGrandTotals = computed(() => buildWorkOrderTotals(detailOutgoingItems.value))
const hasEditorUnsavedChanges = computed(() => (
  editorVisible.value &&
  editorSnapshot.value &&
  editorSnapshot.value !== serializeEditorState()
))
const selectedAllocationTargets = computed(() => {
  const targetMap = new Map((allocationTargetOptions.value || []).map((item) => [Number(item.id || 0), item]))
  return allocationForm.targetShopIds
    .map((shopId) => targetMap.get(Number(shopId || 0)))
    .filter(Boolean)
})
const hasAllocationUnsavedChanges = computed(() => (
  allocationVisible.value &&
  allocationSnapshot.value &&
  allocationSnapshot.value !== serializeAllocationState()
))
const allocationWarningLines = computed(() => buildAllocationWarnings())
const allocationWarningCount = computed(() => allocationWarningLines.value.length)
const allocationItemsPageCount = computed(() => Math.max(1, Math.ceil(allocationRows.value.length / allocationItemsPageSize.value)))
const allocationItemStartIndex = computed(() => (allocationItemsPage.value - 1) * allocationItemsPageSize.value)
const allocationTableMaxHeight = computed(() => (isMobileViewport.value ? '52vh' : '56vh'))
const sortedAllocationRows = computed(() => sortWorkOrderRows(allocationRows.value, allocationSortState))
const allocationPagedRows = computed(() => (
  sortedAllocationRows.value.slice(allocationItemStartIndex.value, allocationItemStartIndex.value + allocationItemsPageSize.value)
))
const goodsPickerDistributionShopId = computed(() => {
  if (form.orderType === 'transfer' || form.orderType === 'return' || form.orderType === 'damage') {
    return Number(form.sourceShopId || 0) || null
  }
  if (form.orderType === 'purchase') {
    return Number(form.targetShopId || 0) || null
  }
  if (isSaleAffectingInventory.value) {
    const currentRow = findAnyEditorRow(currentGoodsPickerRowKey.value)
    return Number(currentRow?.shipShopId || saleShipShopId.value || form.sourceShopId || 0) || null
  }
  if (form.orderType === 'sale_exchange') {
    return Number(form.sourceShopId || 0) || null
  }
  return null
})
const goodsPickerQuantityLabel = computed(() => {
  if (form.orderType === 'transfer') {
    return '发货库存'
  }
  if (form.orderType === 'purchase') {
    return '收货库存'
  }
  if (form.orderType === 'return' || form.orderType === 'damage') {
    return '发货库存'
  }
  if (form.orderType === 'sale_exchange') {
    return '发货库存'
  }
  if (isSaleAffectingInventory.value) {
    return '发货库存'
  }
  return '商品数量'
})
const goodsPickerSecondaryDistributionShopId = computed(() => (
  form.orderType === 'transfer' ? Number(form.targetShopId || 0) || null : null
))
const goodsPickerSecondaryQuantityLabel = computed(() => (
  form.orderType === 'transfer' ? '收货库存' : ''
))
const statusFilterLocked = computed(() => ['draft', 'pending', 'approver'].includes(scope.value))
const activeScopeLabel = computed(() => {
  const matched = scopeOptions.value.find((item) => item.value === scope.value)
  return matched?.label || '我的工单'
})

function resetGroupCreateForm() {
  editingGroupId.value = null
  groupCreateForm.name = ''
  groupCreateForm.description = ''
  groupCreateForm.inviteUserIds = []
}

function resetGroupInviteForm() {
  groupInviteForm.inviteUserIds = []
  inviteTargetGroup.value = null
}

function buildWorkOrderSettingsRows(source = meta.defaultApproverSettings) {
  const settingsMap = new Map(
    (Array.isArray(source) ? source : []).map((item) => [String(item?.orderType || '').trim(), item]),
  )
  return (meta.types || []).map((item) => {
    const matched = settingsMap.get(String(item?.value || '').trim()) || null
    return {
      orderType: String(item?.value || '').trim(),
      orderTypeLabel: item?.label || '',
      approverId: matched?.approverId || null,
      approverName: matched?.approverName || '',
    }
  })
}

function syncWorkOrderSettingsRows(source = meta.defaultApproverSettings) {
  workOrderSettings.value = buildWorkOrderSettingsRows(source)
}

function resolveDefaultApproverId(orderType) {
  const matched = (meta.defaultApproverSettings || []).find((item) => String(item?.orderType || '').trim() === String(orderType || '').trim())
  return Number(matched?.approverId || 0) || null
}

function applyDefaultApproverToForm(orderType, { force = false } = {}) {
  const defaultApproverId = resolveDefaultApproverId(orderType)
  if (!force && Number(form.approverId || 0)) {
    return
  }
  form.approverId = defaultApproverId
}

function handleWorkOrderSettingApproverChange(row) {
  const matched = meta.approverOptions.find((item) => Number(item.id || 0) === Number(row?.approverId || 0))
  row.approverName = matched?.displayName || matched?.username || ''
}
const activeFilterCount = computed(() => {
  let count = 0
  if (Array.isArray(dateRange.value) && (dateRange.value[0] || dateRange.value[1])) count += 1
  if (orderTypeFilter.value) count += 1
  if (statusFilter.value) count += 1
  if (applicantFilter.value) count += 1
  if (approverFilter.value) count += 1
  return count
})
const scopeOptions = computed(() => {
  const items = [
    { value: 'mine', label: '我的工单' },
    { value: 'pending', label: '待审批', badge: dashboard.pendingCount },
    { value: 'draft', label: '草稿箱', badge: dashboard.draftCount },
  ]
  if (canApprove.value) {
    items.push({ value: 'approver', label: '待我审核', badge: dashboard.approvalCount })
  }
  if (authStore.isAdmin) {
    items.push({ value: 'all', label: '全部记录' })
  }
  return items
})

function defaultDateTimeLocal() {
  return getShanghaiDateTimeLocalValue()
}

function formatDateLabel(value) {
  const text = String(value || '').trim()
  if (!text) {
    return '-'
  }
  return text.replace('T', ' ')
}

function formatMoney(value) {
  return Number(value || 0).toFixed(2)
}

function toFiniteNumber(value, fallback = 0) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

function compareTextValue(left, right) {
  return String(left || '').localeCompare(String(right || ''), 'zh-CN', {
    numeric: true,
    sensitivity: 'base',
  })
}

function formatSalespersonValue(item) {
  return String(item?.displayName || item?.username || '').trim()
}

function formatSalespersonLabel(item) {
  const name = formatSalespersonValue(item)
  const username = String(item?.username || '').trim()
  return username && username !== name ? `${name} · ${username}` : name
}

function dedupeSalespersonOptions(items) {
  const result = []
  const seen = new Set()
  for (const item of items || []) {
    const key = formatSalespersonValue(item)
    if (!key || seen.has(key)) {
      continue
    }
    seen.add(key)
    result.push(item)
  }
  return result
}

function getSalespersonOptionsForShop(shopId) {
  const normalizedShopId = Number(shopId || 0)
  const fallbackOptions = dedupeSalespersonOptions([
    currentApplicantOption.value,
    ...meta.applicantOptions,
  ])
  if (!normalizedShopId) {
    return fallbackOptions
  }
  const matchedShop = shopOptionMap.value.get(normalizedShopId)
  const selectedIds = Array.isArray(matchedShop?.salespersonIds)
    ? matchedShop.salespersonIds.map((item) => Number(item || 0)).filter((item) => item > 0)
    : []
  if (!selectedIds.length) {
    return fallbackOptions
  }
  const optionMap = new Map(meta.applicantOptions.map((item) => [Number(item.id), item]))
  const scopedOptions = selectedIds
    .map((item) => optionMap.get(item))
    .filter(Boolean)
  return dedupeSalespersonOptions([
    currentApplicantOption.value,
    ...scopedOptions,
  ])
}

function getSalespersonOptionsForRow(row) {
  return getSalespersonOptionsForShop(Number(row?.saleShopId || form.sourceShopId || 0) || null)
}

function getSalespersonOptionsForTarget(target = 'default') {
  const rows = target === 'incoming'
    ? form.exchangeIncomingItems
    : target === 'outgoing'
      ? form.exchangeOutgoingItems
      : form.items
  const uniqueShopIds = [...new Set(
    rows
      .map((item) => Number(item?.saleShopId || form.sourceShopId || 0))
      .filter((item) => item > 0),
  )]
  if (!uniqueShopIds.length) {
    return getSalespersonOptionsForShop(Number(form.sourceShopId || 0) || null)
  }
  return dedupeSalespersonOptions(uniqueShopIds.flatMap((shopId) => getSalespersonOptionsForShop(shopId)))
}

function getLocationOptionsForBulk(field) {
  return field === 'sale' ? sourceOptions.value : stockLocationOptions.value
}

function updateRowSaleShop(row, shopId) {
  const normalizedId = Number(shopId || 0) || null
  row.saleShopId = normalizedId
  syncOutgoingShopSelection(row, 'sale')
}

async function updateRowShipShop(row, shopId) {
  const normalizedId = Number(shopId || 0) || null
  row.shipShopId = normalizedId
  await handleSaleInventoryLocationChange(row, 'ship')
}

function prepareLocationBulk(field) {
  const firstRow = form.items[0] || null
  if (field === 'sale') {
    locationBulkValue.defaultSale = Number(firstRow?.saleShopId || 0) || null
    return
  }
  locationBulkValue.defaultShip = Number(firstRow?.shipShopId || saleShipShopId.value || 0) || null
}

function clearLocationBulk(field) {
  if (field === 'sale') {
    locationBulkValue.defaultSale = null
    return
  }
  locationBulkValue.defaultShip = null
}

async function applyLocationToTarget(field) {
  const nextId = field === 'sale'
    ? Number(locationBulkValue.defaultSale || 0) || null
    : Number(locationBulkValue.defaultShip || 0) || null
  if (!nextId) {
    ElMessage.warning(field === 'sale' ? '请先选择销售店铺' : '请先选择发货店铺/仓库')
    return
  }
  if (field === 'sale') {
    form.items.forEach((row) => {
      updateRowSaleShop(row, nextId)
    })
    return
  }
  saleShipShopId.value = nextId
  await Promise.all(form.items.map((row) => updateRowShipShop(row, nextId)))
}

function ensureRowSalespersonByShop(row, { force = false } = {}) {
  if (!row) {
    return
  }
  const options = getSalespersonOptionsForRow(row)
  const currentValue = String(row.salesperson || '').trim()
  const hasCurrent = options.some((item) => formatSalespersonValue(item) === currentValue)
  if (currentValue && hasCurrent && !force) {
    return
  }
  const preferredValue = formatSalespersonValue(currentApplicantOption.value)
  if (preferredValue && options.some((item) => formatSalespersonValue(item) === preferredValue)) {
    row.salesperson = preferredValue
    return
  }
  row.salesperson = formatSalespersonValue(options[0]) || preferredValue || currentValue || ''
}

function prepareSalespersonBulk(target = 'default') {
  const rows = target === 'incoming'
    ? form.exchangeIncomingItems
    : target === 'outgoing'
      ? form.exchangeOutgoingItems
      : form.items
  salespersonBulkValue[target] = String(rows[0]?.salesperson || formatSalespersonValue(currentApplicantOption.value) || '')
}

function clearSalespersonBulk(target = 'default') {
  salespersonBulkValue[target] = ''
}

function applySalespersonToTarget(target = 'default') {
  const nextValue = String(salespersonBulkValue[target] || '').trim()
  if (!nextValue) {
    ElMessage.warning('请先选择销售员')
    return
  }
  const rows = target === 'incoming'
    ? form.exchangeIncomingItems
    : target === 'outgoing'
      ? form.exchangeOutgoingItems
      : form.items
  rows.forEach((row) => {
    row.salesperson = nextValue
    ensureRowSalespersonByShop(row)
  })
}

function prepareDiscountBulk() {
  discountBulkValue.default = Number(form.items[0]?.discountRate || 10)
}

function clearDiscountBulk() {
  discountBulkValue.default = 10
}

function applyDiscountToAll() {
  const nextValue = Number(discountBulkValue.default || 0)
  if (!Number.isFinite(nextValue) || nextValue < 0) {
    ElMessage.warning('请先输入正确的折扣')
    return
  }
  form.items.forEach((row) => {
    row.discountRate = Number(nextValue.toFixed(2))
    syncRowDiscount(row)
  })
}

function normalizeSortMetric(row, prop) {
  if (!row || !prop) {
    return ''
  }
  const value = row[prop]
  if (['unitPrice', 'quantity', 'totalAmount', 'sourceStock', 'targetStock', 'receivedAmount', 'receivableAmount'].includes(prop)) {
    return Number(value || 0)
  }
  return String(value || '').trim()
}

function sortWorkOrderRows(items, sortState) {
  const source = Array.isArray(items) ? [...items] : []
  if (!sortState?.prop || !sortState?.order) {
    return source
  }
  const direction = sortState.order === 'ascending' ? 1 : -1
  source.sort((left, right) => {
    const leftValue = normalizeSortMetric(left, sortState.prop)
    const rightValue = normalizeSortMetric(right, sortState.prop)
    if (typeof leftValue === 'number' || typeof rightValue === 'number') {
      return (Number(leftValue || 0) - Number(rightValue || 0)) * direction
    }
    return compareTextValue(leftValue, rightValue) * direction
  })
  return source
}

function normalizePersistedWorkOrderItems(items) {
  return (Array.isArray(items) ? [...items] : []).sort((left, right) => {
    const leftSortIndex = Number(left?.sortIndex ?? left?.sort ?? 0)
    const rightSortIndex = Number(right?.sortIndex ?? right?.sort ?? 0)
    if (leftSortIndex !== rightSortIndex) {
      return leftSortIndex - rightSortIndex
    }
    return Number(left?.id || 0) - Number(right?.id || 0)
  })
}

function normalizePersistedOrderDetail(order) {
  if (!order || typeof order !== 'object') {
    return order
  }
  return {
    ...order,
    items: normalizePersistedWorkOrderItems(order.items),
  }
}

function serializeEditorState() {
  const serializeItem = (item) => ({
    lineType: String(item.lineType || 'default').trim(),
    saleRecordId: item.saleRecordId || null,
    orderNum: String(item.orderNum || '').trim(),
    salesperson: String(item.salesperson || '').trim(),
    saleShopId: item.saleShopId || null,
    saleShopName: String(item.saleShopName || '').trim(),
    receiveShopId: item.receiveShopId || null,
    receiveShopName: String(item.receiveShopName || '').trim(),
    shipShopId: item.shipShopId || null,
    shipShopName: String(item.shipShopName || '').trim(),
    goodsId: item.goodsId || null,
    goodsName: String(item.goodsName || '').trim(),
    productCode: String(item.productCode || '').trim(),
    brand: String(item.brand || '').trim(),
    series: String(item.series || '').trim(),
    barcode: String(item.barcode || '').trim(),
    unitPrice: Number(item.unitPrice || 0),
    quantity: Number(item.quantity || 0),
    receivedAmount: Number(item.receivedAmount || 0),
    receivableAmount: Number(item.receivableAmount || 0),
    couponAmount: Number(item.couponAmount || 0),
    discountRate: Number(item.discountRate || 0),
    totalAmount: Number(item.totalAmount || 0),
    channel: String(item.channel || '').trim(),
    customerName: String(item.customerName || '').trim(),
    remark: String(item.remark || '').trim(),
  })
  return JSON.stringify({
    id: form.id || null,
    orderType: form.orderType || '',
    saleAffectsInventory: Boolean(form.saleAffectsInventory),
    reason: cleanReasonText(form.reason),
    formDate: String(form.formDate || '').trim(),
    sourceShopId: form.sourceShopId || null,
    targetShopId: form.targetShopId || null,
    supplierName: String(form.supplierName || '').trim(),
    partnerName: String(form.partnerName || '').trim(),
    approverId: form.approverId || null,
    groupId: form.groupId || null,
    items: form.items.map(serializeItem),
    exchangeIncomingItems: form.exchangeIncomingItems.map(serializeItem),
    exchangeOutgoingItems: form.exchangeOutgoingItems.map(serializeItem),
  })
}

function serializeEditorPayloadItem(item) {
  return {
    lineType: item.lineType || 'default',
    saleRecordId: item.saleRecordId || null,
    orderNum: item.orderNum || '',
    salesperson: item.salesperson || '',
    saleShopId: item.saleShopId || null,
    saleShopName: item.saleShopName || '',
    receiveShopId: item.receiveShopId || null,
    receiveShopName: item.receiveShopName || '',
    shipShopId: item.shipShopId || null,
    shipShopName: item.shipShopName || '',
    goodsId: item.goodsId || null,
    goodsName: item.goodsName || '',
    productCode: item.productCode || '',
    brand: item.brand || '',
    series: item.series || '',
    barcode: item.barcode || '',
    unitPrice: toFiniteNumber(item.unitPrice, 0),
    quantity: toFiniteNumber(item.quantity, 1),
    receivedAmount: toFiniteNumber(item.receivedAmount, 0),
    receivableAmount: toFiniteNumber(item.receivableAmount ?? item.totalAmount, 0),
    couponAmount: toFiniteNumber(item.couponAmount, 0),
    discountRate: toFiniteNumber(item.discountRate, 10),
    totalAmount: toFiniteNumber(item.totalAmount, 0),
    channel: item.channel || '',
    customerName: item.customerName || '',
    remark: item.remark || '',
    isNewGoods: false,
  }
}

function buildSortedEditorPayloadItems() {
  if (isSaleExchangeType.value) {
    return [...sortedExchangeIncomingItems.value, ...sortedExchangeOutgoingItems.value]
  }
  return sortedEditorItems.value
}

function persistCurrentEditorSortOrder() {
  if (isSaleExchangeType.value) {
    form.exchangeIncomingItems = [...sortedExchangeIncomingItems.value]
    form.exchangeOutgoingItems = [...sortedExchangeOutgoingItems.value]
    return
  }
  form.items = [...sortedEditorItems.value]
}

function captureEditorSnapshot() {
  editorSnapshot.value = serializeEditorState()
}

function resetAllocationState() {
  allocationSourceOrder.value = null
  allocationTargetOptions.value = []
  allocationApproverOptions.value = []
  allocationItemsPage.value = 1
  allocationItemsPageSize.value = 20
  allocationSortState.prop = ''
  allocationSortState.order = ''
  allocationForm.orderId = null
  allocationForm.orderNum = ''
  allocationForm.orderType = ''
  allocationForm.sourceShopId = null
  allocationForm.sourceShopName = ''
  allocationForm.approverId = null
  allocationForm.groupId = null
  allocationForm.groupName = ''
  allocationForm.targetShopIds = []
  allocationRows.value = []
  allocationStep.value = 1
  allocationSnapshot.value = ''
}

function resolveStoredAllocationTargets() {
  if (typeof window === 'undefined') {
    return []
  }
  try {
    const raw = String(window.localStorage.getItem(ALLOCATION_TARGET_MEMORY_KEY) || '').trim()
    if (!raw) {
      return []
    }
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed?.targetShopIds)
      ? parsed.targetShopIds.map((item) => Number(item || 0)).filter((item) => item > 0)
      : []
  } catch (error) {
    console.warn('Failed to read allocation target memory', error)
    return []
  }
}

function persistStoredAllocationTargets(targetShopIds = []) {
  if (typeof window === 'undefined') {
    return
  }
  try {
    window.localStorage.setItem(ALLOCATION_TARGET_MEMORY_KEY, JSON.stringify({
      targetShopIds: targetShopIds.map((item) => Number(item || 0)).filter((item) => item > 0),
    }))
  } catch (error) {
    console.warn('Failed to persist allocation target memory', error)
  }
}

function applyRememberedAllocationTargets() {
  if (allocationForm.targetShopIds.length) {
    return
  }
  const availableIds = new Set((allocationTargetOptions.value || []).map((item) => Number(item.id || 0)).filter((item) => item > 0))
  const rememberedIds = resolveStoredAllocationTargets()
    .filter((item) => availableIds.has(Number(item || 0)))
  if (!rememberedIds.length) {
    return
  }
  allocationForm.targetShopIds = rememberedIds
}

function serializeAllocationState() {
  return JSON.stringify({
    orderId: allocationForm.orderId || null,
    approverId: allocationForm.approverId || null,
    targetShopIds: [...allocationForm.targetShopIds],
    rows: (allocationRows.value || []).map((row) => ({
      workOrderItemId: Number(row.workOrderItemId || 0),
      targets: (row.targets || []).map((target) => ({
        shopId: Number(target.shopId || 0),
        quantity: Number(target.quantity || 0),
      })),
    })),
  })
}

function captureAllocationSnapshot() {
  allocationSnapshot.value = serializeAllocationState()
}

function cloneAllocationSnapshotState() {
  try {
    return JSON.parse(allocationSnapshot.value || '{}')
  } catch {
    return {}
  }
}

function applyAllocationSnapshot(snapshot) {
  if (!snapshot || typeof snapshot !== 'object') {
    return
  }
  allocationForm.approverId = snapshot.approverId || null
  allocationForm.targetShopIds = Array.isArray(snapshot.targetShopIds) ? snapshot.targetShopIds.map((item) => Number(item || 0)).filter((item) => item > 0) : []
  const rowMap = new Map((allocationRows.value || []).map((row) => [Number(row.workOrderItemId || 0), row]))
  for (const row of allocationRows.value || []) {
    for (const target of row.targets || []) {
      target.quantity = 0
    }
  }
  for (const rowState of Array.isArray(snapshot.rows) ? snapshot.rows : []) {
    const row = rowMap.get(Number(rowState.workOrderItemId || 0))
    if (!row) {
      continue
    }
    const targetMap = new Map((row.targets || []).map((target) => [Number(target.shopId || 0), target]))
    for (const targetState of Array.isArray(rowState.targets) ? rowState.targets : []) {
      const target = targetMap.get(Number(targetState.shopId || 0))
      if (!target) {
        continue
      }
      target.quantity = Math.max(0, Number(targetState.quantity || 0))
    }
  }
}

function normalizeAllocationTarget(target, optionMap) {
  const normalizedShopId = Number(target?.shopId || 0)
  const option = optionMap.get(normalizedShopId)
  return {
    shopId: normalizedShopId,
    shopName: target?.shopName || option?.name || '',
    shortName: target?.shortName || option?.shortName || '',
    shopType: Number(target?.shopType ?? option?.shopType ?? 0),
    currentStock: Number(target?.currentStock || 0),
    quantity: Math.max(0, Number(target?.quantity || 0)),
  }
}

function applyAllocationResponse(payload) {
  const draft = payload?.draft || null
  allocationItemsPage.value = 1
  allocationSortState.prop = ''
  allocationSortState.order = ''
  allocationSourceOrder.value = payload?.order || null
  allocationTargetOptions.value = payload?.targetOptions || []
  allocationApproverOptions.value = payload?.approverOptions || meta.approverOptions || []
  const optionMap = new Map((allocationTargetOptions.value || []).map((item) => [Number(item.id || 0), item]))
  allocationForm.orderId = Number(draft?.orderId || 0) || null
  allocationForm.orderNum = String(draft?.orderNum || '')
  allocationForm.orderType = String(draft?.orderType || '')
  allocationForm.sourceShopId = Number(draft?.sourceShopId || 0) || null
  allocationForm.sourceShopName = String(draft?.sourceShopName || '')
  allocationForm.approverId = draft?.approverId || null
  allocationForm.groupId = draft?.groupId || null
  allocationForm.groupName = String(draft?.groupName || '')
  allocationForm.targetShopIds = Array.isArray(draft?.targetShopIds)
    ? draft.targetShopIds.map((item) => Number(item || 0)).filter((item) => item > 0)
    : []
  allocationRows.value = Array.isArray(draft?.rows)
    ? draft.rows.map((row) => ({
      ...row,
      workOrderItemId: Number(row.workOrderItemId || 0),
      plannedQuantity: Number(row.plannedQuantity || 0),
      sourceStock: Number(row.sourceStock || 0),
      unitPrice: Number(row.unitPrice || 0),
      lineAmount: Number(row.lineAmount || 0),
      allocatedQuantity: Number(row.allocatedQuantity || 0),
      targets: (row.targets || []).map((target) => normalizeAllocationTarget(target, optionMap)),
    }))
    : []
  applyRememberedAllocationTargets()
  captureAllocationSnapshot()
}

function buildAllocationPayload() {
  return {
    approverId: allocationForm.approverId || null,
    targetShopIds: [...allocationForm.targetShopIds],
    rows: (allocationRows.value || []).map((row) => ({
      workOrderItemId: Number(row.workOrderItemId || 0),
      targets: (row.targets || []).map((target) => ({
        shopId: Number(target.shopId || 0),
        quantity: Math.max(0, Number(target.quantity || 0)),
      })),
    })),
  }
}

function resolveAllocationTargetOrder(shopId) {
  const index = allocationForm.targetShopIds.findIndex((item) => Number(item || 0) === Number(shopId || 0))
  return index >= 0 ? index + 1 : 0
}

function toggleAllocationTarget(shopId) {
  const normalizedId = Number(shopId || 0)
  if (!normalizedId) {
    return
  }
  const currentIndex = allocationForm.targetShopIds.findIndex((item) => Number(item || 0) === normalizedId)
  if (currentIndex >= 0) {
    allocationForm.targetShopIds.splice(currentIndex, 1)
    persistStoredAllocationTargets(allocationForm.targetShopIds)
    return
  }
  allocationForm.targetShopIds.push(normalizedId)
  persistStoredAllocationTargets(allocationForm.targetShopIds)
}

async function goToAllocationStep(nextStep) {
  const normalizedStep = Math.min(Math.max(Number(nextStep || 1), 1), allocationStepOptions.length)
  if (normalizedStep === 2 && allocationStep.value !== 2) {
    await enterAllocationEdit()
    return
  }
  allocationStep.value = normalizedStep
}

function getAllocationTarget(row, shopId) {
  return (row?.targets || []).find((target) => Number(target.shopId || 0) === Number(shopId || 0)) || null
}

function getAllocationQuantity(row, shopId) {
  return Math.max(0, Number(getAllocationTarget(row, shopId)?.quantity || 0))
}

function getAllocationCurrentStock(row, shopId) {
  return Number(getAllocationTarget(row, shopId)?.currentStock || 0)
}

function formatAllocationOriginalStockQuantity(row) {
  return `${Number(row?.plannedQuantity || 0)}/${Number(row?.sourceStock || 0)}`
}

function setAllocationQuantity(row, shopId, nextValue) {
  const target = getAllocationTarget(row, shopId)
  if (!target) {
    return
  }
  const parsed = Number.parseInt(String(nextValue ?? '').trim(), 10)
  target.quantity = Math.max(0, Number.isFinite(parsed) ? parsed : 0)
}

function onAllocationQuantityInput(row, shopId, event) {
  setAllocationQuantity(row, shopId, event?.target?.value)
}

function allocationRowAssignedQuantity(row) {
  return (row?.targets || []).reduce((sum, target) => sum + Number(target.quantity || 0), 0)
}

function buildAllocationWarnings() {
  const warnings = []
  for (const row of allocationRows.value || []) {
    const goodsLabel = String(row?.goodsName || row?.barcode || '当前商品').trim()
    const assignedQuantity = allocationRowAssignedQuantity(row)
    const plannedQuantity = Number(row?.plannedQuantity || 0)
    const sourceStock = Number(row?.sourceStock || 0)
    if (assignedQuantity < plannedQuantity) {
      warnings.push(`${goodsLabel} 仍有 ${plannedQuantity - assignedQuantity} 件未分配`)
    }
    if (assignedQuantity > plannedQuantity) {
      warnings.push(`${goodsLabel} 分配数量超出原单 ${assignedQuantity - plannedQuantity} 件`)
    }
    if (assignedQuantity > sourceStock) {
      warnings.push(`${goodsLabel} 分配数量超出库存 ${assignedQuantity - sourceStock} 件`)
    }
  }
  return warnings
}

function confirmableAllocationTargetCount() {
  const shopCounts = new Set()
  for (const row of allocationRows.value || []) {
    for (const target of row.targets || []) {
      if (Number(target.quantity || 0) > 0) {
        shopCounts.add(Number(target.shopId || 0))
      }
    }
  }
  return shopCounts.size
}

function findEditorRowIndex(rowKey) {
  return form.items.findIndex((item) => item.localId === rowKey)
}

function findAnyEditorRow(rowKey) {
  for (const rows of [form.items, form.exchangeIncomingItems, form.exchangeOutgoingItems]) {
    const matched = rows.find((item) => item.localId === rowKey)
    if (matched) {
      return matched
    }
  }
  return null
}

function resetQuickAddBar({ keepMatchedLabel = false } = {}) {
  quickAddQuery.value = ''
  quickAddLoading.value = false
  quickAddLookupToken = null
  if (!keepMatchedLabel) {
    quickAddMatchedLabel.value = ''
  }
}

function buildMatchedGoodsLabel(goods) {
  return [goods?.brand, goods?.series, goods?.model || goods?.name]
    .map((value) => String(value || '').trim())
    .filter(Boolean)
    .join(' ') || String(goods?.barcode || '').trim() || '未命名商品'
}

function resolveQuickAddInputElement() {
  const root = quickAddFieldRef.value?.$el || quickAddFieldRef.value
  if (!(root instanceof HTMLElement)) {
    return null
  }
  const matched = root.querySelector('input:not([readonly]):not([disabled]), textarea:not([readonly]):not([disabled])')
  if (matched instanceof HTMLInputElement || matched instanceof HTMLTextAreaElement) {
    return matched
  }
  return null
}

function focusQuickAddField() {
  nextTick(() => {
    const schedule = () => {
      const target = resolveQuickAddInputElement()
      if (!(target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement)) {
        return
      }
      try {
        target.focus({ preventScroll: true })
      } catch {
        target.focus()
      }
      const cursorAt = String(target.value || '').length
      target.setSelectionRange?.(cursorAt, cursorAt)
    }
    if (typeof window !== 'undefined' && typeof window.requestAnimationFrame === 'function') {
      window.requestAnimationFrame(() => {
        window.requestAnimationFrame(schedule)
      })
      return
    }
    schedule()
  })
}

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function nextRowKey() {
  rowSeed += 1
  return `wo-row-${Date.now()}-${rowSeed}`
}

function buildEditorFieldMarker(rowKey, field) {
  return `work-order-editor-${String(rowKey || '').trim()}-${String(field || '').trim()}`
}

function registerEditorFieldRef(rowKey, field, element) {
  const marker = buildEditorFieldMarker(rowKey, field)
  const currentElements = editorFieldElementRegistry.get(marker) || new Set()
  if (element instanceof HTMLElement) {
    currentElements.add(element)
    editorFieldElementRegistry.set(marker, currentElements)
    return
  }
  const nextElements = new Set(
    Array.from(currentElements).filter((item) => item instanceof HTMLElement && item.isConnected),
  )
  if (nextElements.size) {
    editorFieldElementRegistry.set(marker, nextElements)
  } else {
    editorFieldElementRegistry.delete(marker)
  }
}

function clearEditorFocusRetryTimers() {
  editorFocusRetryTimers.forEach((timerId) => window.clearTimeout(timerId))
  editorFocusRetryTimers = []
}

function isVisibleEditorFieldElement(element) {
  if (!(element instanceof HTMLElement) || !element.isConnected) {
    return false
  }
  const rect = element.getBoundingClientRect()
  if (rect.width <= 0 || rect.height <= 0) {
    return false
  }
  const style = window.getComputedStyle(element)
  return style.display !== 'none' && style.visibility !== 'hidden'
}

function isFocusableEditorFieldInput(element) {
  return (
    (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement)
    && isVisibleEditorFieldElement(element)
    && !element.disabled
    && !element.readOnly
  )
}

function resolveEditorFieldInput(marker) {
  const registeredWrappers = Array.from(editorFieldElementRegistry.get(marker) || [])
    .filter((item) => item instanceof HTMLElement && item.isConnected)
  if (registeredWrappers.length) {
    editorFieldElementRegistry.set(marker, new Set(registeredWrappers))
  } else {
    editorFieldElementRegistry.delete(marker)
  }
  const wrapperCandidates = registeredWrappers.length
    ? registeredWrappers
    : Array.from(document.querySelectorAll(`[data-editor-field="${marker}"]`)).filter((item) => item instanceof HTMLElement)
  const inputCandidates = wrapperCandidates
    .flatMap((wrapper) => {
      if (wrapper instanceof HTMLInputElement || wrapper instanceof HTMLTextAreaElement) {
        return [wrapper]
      }
      return Array.from(wrapper.querySelectorAll('input, textarea'))
    })
    .filter((item) => item instanceof HTMLInputElement || item instanceof HTMLTextAreaElement)
  const focusableInput = inputCandidates.find((item) => isFocusableEditorFieldInput(item))
  if (focusableInput) {
    return focusableInput
  }
  const visibleInput = inputCandidates.find((item) => isVisibleEditorFieldElement(item))
  return visibleInput || inputCandidates[0] || null
}

function findTypeLabel(value) {
  const matched = meta.types.find((item) => item.value === value)
  return matched?.label || value || '工单'
}

function resolveOrderCategory(value) {
  const matched = meta.types.find((item) => item.value === value)
  return matched?.category || 'goods'
}

function resolveCategoryLabel(value) {
  const matched = meta.categories.find((item) => item.value === value)
  return matched?.label || '商品类工单'
}

function defaultTypeForCategory(category) {
  return meta.types.find((item) => resolveOrderCategory(item.value) === category)?.value || 'transfer'
}

function describeCategoryTypes(category) {
  const labels = meta.types
    .filter((item) => resolveOrderCategory(item.value) === category)
    .map((item) => item.label)
  return labels.join(' / ')
}

function detailSourceLabel() {
  return ['sale', 'sale_return', 'sale_exchange'].includes(detailOrder.value?.orderType || '') ? '销售店铺' : '发货仓库/店铺'
}

function detailTargetLabel() {
  return '收货仓库/店铺'
}

function cleanReasonText(value) {
  return String(value || '').trim()
}

function formatReasonDate() {
  const source = String(form.formDate || '').slice(0, 10)
  if (!source) {
    return '今日'
  }
  const [year, month, day] = source.split('-')
  return `${Number(year)}年${Number(month)}月${Number(day)}日`
}

function buildDefaultReason() {
  const sourceName = sourceDisplayName.value || (isSalesOrderType.value ? '未选择销售店铺' : '未选择发货店铺/仓库')
  const targetName = targetDisplayName.value || '未选择收货店铺/仓库'
  if (form.orderType === 'transfer') {
    return `${sourceName}-调往-${targetName}-调拨单`
  }
  if (form.orderType === 'purchase') {
    return `${targetName}-进货单`
  }
  if (form.orderType === 'return') {
    return `${sourceName}-退货单`
  }
  if (form.orderType === 'damage') {
    return `${sourceName}-报损单`
  }
  if (form.orderType === 'sale') {
    return `${sourceName}-${findTypeLabel(form.orderType)}`
  }
  if (form.orderType === 'sale_return') {
    return `${sourceName}-${findTypeLabel(form.orderType)}`
  }
  if (form.orderType === 'sale_exchange') {
    return `${sourceName}-${findTypeLabel(form.orderType)}`
  }
  return `${findTypeLabel(form.orderType)}`
}

function createRow(preset = {}) {
  const row = {
    localId: nextRowKey(),
    id: null,
    lineType: 'default',
    saleRecordId: null,
    orderNum: '',
    salesperson: applicantName.value,
    saleShopId: null,
    saleShopName: '',
    receiveShopId: null,
    receiveShopName: '',
    shipShopId: null,
    shipShopName: '',
    goodsId: null,
    goodsName: '',
    productCode: '',
    brand: '',
    series: '',
    barcode: '',
    unitPrice: 0,
    quantity: 1,
    receivedAmount: 0,
    receivableAmount: 0,
    couponAmount: 0,
    discountRate: 10,
    totalAmount: 0,
    channel: '',
    customerName: '',
    remark: '',
    sourceStock: 0,
    targetStock: 0,
    isNewGoods: false,
    ...preset,
  }
  row.saleShopId = row.saleShopId || null
  row.saleShopName = row.saleShopName || ''
  row.receiveShopId = row.receiveShopId || null
  row.receiveShopName = row.receiveShopName || ''
  row.shipShopId = row.shipShopId || null
  row.shipShopName = row.shipShopName || ''
  if (row.lineType === 'outgoing' || isSaleAffectingInventory.value) {
    const currentStoreId = Number(form.sourceShopId || 0) || null
    const currentStoreName = sourceDisplayName.value || ''
    const currentShipId = Number(saleShipShopId.value || form.sourceShopId || 0) || null
    const currentShipName = saleShipDisplayName.value || currentStoreName
    row.saleShopId = row.saleShopId || currentStoreId
    row.saleShopName = row.saleShopName || currentStoreName
    row.receiveShopId = row.receiveShopId || row.saleShopId || currentStoreId
    row.receiveShopName = row.receiveShopName || row.saleShopName || currentStoreName
    row.shipShopId = row.shipShopId || currentShipId
    row.shipShopName = row.shipShopName || currentShipName
    row.salesperson = row.salesperson || String(form.exchangeIncomingItems[0]?.salesperson || applicantName.value || '')
    row.channel = row.channel || '门店'
  }
  ensureRowSalespersonByShop(row)
  syncRowAmount(row)
  return row
}

function resolveEditorTargetByRow(row) {
  if (String(row?.lineType || 'default') === 'incoming') {
    return 'incoming'
  }
  if (String(row?.lineType || 'default') === 'outgoing') {
    return 'outgoing'
  }
  return 'default'
}

function focusEditorField(rowKey, field) {
  clearEditorFocusRetryTimers()
  editorFocusRequestToken += 1
  const requestToken = editorFocusRequestToken
  const marker = buildEditorFieldMarker(rowKey, field)
  const attemptFocus = (retry = 0) => {
    if (requestToken !== editorFocusRequestToken) {
      return
    }
    const target = resolveEditorFieldInput(marker)
    if (!(target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement)) {
      if (retry < 14) {
        const timerId = window.setTimeout(() => attemptFocus(retry + 1), Math.min(90 + retry * 45, 320))
        editorFocusRetryTimers.push(timerId)
      }
      return
    }
    target.scrollIntoView?.({
      block: 'nearest',
      inline: 'nearest',
    })
    try {
      target.focus({ preventScroll: true })
    } catch {
      target.focus()
    }
    const cursorAt = String(target.value || '').length
    target.setSelectionRange?.(cursorAt, cursorAt)
    if (document.activeElement !== target && retry < 14) {
      const timerId = window.setTimeout(() => attemptFocus(retry + 1), Math.min(90 + retry * 45, 320))
      editorFocusRetryTimers.push(timerId)
    }
  }
  const scheduleInitialFocus = () => {
    attemptFocus(0)
    const timerId = window.setTimeout(() => attemptFocus(0), 60)
    editorFocusRetryTimers.push(timerId)
    ;[140, 260, 420].forEach((delay) => {
      const guardTimerId = window.setTimeout(() => {
        if (requestToken !== editorFocusRequestToken) {
          return
        }
        const target = resolveEditorFieldInput(marker)
        if (!(target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement)) {
          return
        }
        if (document.activeElement !== target) {
          attemptFocus(0)
        }
      }, delay)
      editorFocusRetryTimers.push(guardTimerId)
    })
  }
  nextTick(() => {
    if (typeof window !== 'undefined' && typeof window.requestAnimationFrame === 'function') {
      window.requestAnimationFrame(() => {
        window.requestAnimationFrame(() => {
          scheduleInitialFocus()
        })
      })
      return
    }
    scheduleInitialFocus()
  })
}

function focusEditorFieldAfterUiSettles(rowKey, field) {
  nextTick(() => {
    const activeElement = typeof document !== 'undefined' ? document.activeElement : null
    if (activeElement instanceof HTMLInputElement || activeElement instanceof HTMLTextAreaElement) {
      activeElement.blur?.()
    }
    if (typeof window !== 'undefined' && typeof window.requestAnimationFrame === 'function') {
      window.requestAnimationFrame(() => {
        window.setTimeout(() => {
          focusEditorField(rowKey, field)
        }, 40)
      })
      return
    }
    window.setTimeout(() => {
      focusEditorField(rowKey, field)
    }, 40)
  })
}

function isVisibleFloatingPanel(selector) {
  return Array.from(document.querySelectorAll(selector)).some((element) => isVisibleEditorFieldElement(element))
}

function shouldKeepNativeHorizontalCaret(target, key) {
  if (!(target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement)) {
    return false
  }
  const start = Number(target.selectionStart ?? 0)
  const end = Number(target.selectionEnd ?? start)
  if (start !== end) {
    return true
  }
  if (key === 'ArrowLeft') {
    return start > 0
  }
  if (key === 'ArrowRight') {
    return end < String(target.value || '').length
  }
  return false
}

function resolveDirectionalFocusableInput(container) {
  if (!(container instanceof HTMLElement)) {
    return null
  }
  if (isFocusableEditorFieldInput(container)) {
    return container
  }
  const candidateSelectors = [
    'input:not([readonly]):not([disabled])',
    'textarea:not([readonly]):not([disabled])',
    'input',
    'textarea',
  ]
  for (const selector of candidateSelectors) {
    const matched = Array.from(container.querySelectorAll(selector)).find((item) => (
      item instanceof HTMLInputElement || item instanceof HTMLTextAreaElement
    ) && isFocusableEditorFieldInput(item))
    if (matched) {
      return matched
    }
  }
  return null
}

function getDirectionalEditableCells(row) {
  if (!(row instanceof HTMLTableRowElement)) {
    return []
  }
  return Array.from(row.cells).filter((cell) => resolveDirectionalFocusableInput(cell))
}

function focusDirectionalCell(cell) {
  const target = resolveDirectionalFocusableInput(cell)
  if (!target) {
    return false
  }
  target.scrollIntoView?.({
    block: 'nearest',
    inline: 'nearest',
  })
  try {
    target.focus({ preventScroll: true })
  } catch {
    target.focus()
  }
  const cursorAt = String(target.value || '').length
  target.setSelectionRange?.(cursorAt, cursorAt)
  return document.activeElement === target
}

function handleEditorDirectionalKeydown(event) {
  const key = String(event?.key || '')
  if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(key)) {
    return
  }
  if (event.altKey || event.ctrlKey || event.metaKey) {
    return
  }
  const target = event.target
  if (!(target instanceof HTMLElement)) {
    return
  }
  const insideAutocomplete = target.closest('.el-autocomplete')
  const insideSelect = target.closest('.el-select')
  if (
    (insideAutocomplete && isVisibleFloatingPanel('.el-autocomplete-suggestion'))
    || (insideSelect && isVisibleFloatingPanel('.el-select__popper'))
    || target.closest('[aria-expanded="true"]')
  ) {
    return
  }
  if ((key === 'ArrowLeft' || key === 'ArrowRight') && shouldKeepNativeHorizontalCaret(target, key)) {
    return
  }
  const sourceCell = target.closest('td')
  const sourceRow = sourceCell?.closest('tr')
  const sourceTable = sourceRow?.closest('table')
  if (!(sourceCell instanceof HTMLTableCellElement) || !(sourceRow instanceof HTMLTableRowElement) || !(sourceTable instanceof HTMLTableElement)) {
    return
  }
  const rowCells = getDirectionalEditableCells(sourceRow)
  const cellIndex = rowCells.findIndex((cell) => cell === sourceCell)
  if (cellIndex < 0) {
    return
  }
  let nextCell = null
  if (key === 'ArrowLeft' || key === 'ArrowRight') {
    const offset = key === 'ArrowLeft' ? -1 : 1
    nextCell = rowCells[cellIndex + offset] || null
  } else {
    const rowList = Array.from(sourceTable.querySelectorAll('tbody tr'))
      .filter((row) => row instanceof HTMLTableRowElement && getDirectionalEditableCells(row).length)
    const rowIndex = rowList.findIndex((row) => row === sourceRow)
    if (rowIndex < 0) {
      return
    }
    const offset = key === 'ArrowUp' ? -1 : 1
    const nextRow = rowList[rowIndex + offset] || null
    if (nextRow instanceof HTMLTableRowElement) {
      const nextRowCells = getDirectionalEditableCells(nextRow)
      nextCell = nextRowCells[cellIndex] || nextRowCells[nextRowCells.length - 1] || null
    }
  }
  if (!nextCell) {
    return
  }
  event.preventDefault()
  event.stopPropagation()
  focusDirectionalCell(nextCell)
}

function ensureEditorFocusRow(target, index) {
  const rows = editorRowsForTarget(target)
  let focusIndex = Math.max(0, Number(index || 0))
  while (!rows[focusIndex]) {
    rows.push(createRow({ lineType: target === 'default' ? 'default' : target }))
  }
  if (target === 'default') {
    editorItemsPage.value = Math.floor(focusIndex / editorItemsPageSize.value) + 1
    normalizeEditorItemsPage()
  }
  return rows[focusIndex]
}

function canAutoMergeFilledGoodsRow(row, target) {
  if (!row || Number(row.goodsId || 0) <= 0) {
    return false
  }
  if (Number(row.saleRecordId || 0) > 0) {
    return false
  }
  return target !== 'incoming'
}

function mergeDuplicateFilledGoodsRow(row, target = 'default') {
  const rows = editorRowsForTarget(target)
  const currentIndex = rows.findIndex((item) => item.localId === row?.localId)
  if (currentIndex < 0 || !canAutoMergeFilledGoodsRow(row, target)) {
    return { merged: false, targetIndex: currentIndex, targetRow: row }
  }
  const duplicateIndex = rows.findIndex((item, index) => (
    index !== currentIndex &&
    canAutoMergeFilledGoodsRow(item, target) &&
    Number(item.goodsId || 0) === Number(row.goodsId || 0)
  ))
  if (duplicateIndex < 0) {
    return { merged: false, targetIndex: currentIndex, targetRow: row }
  }
  const duplicateRow = rows[duplicateIndex]
  duplicateRow.quantity = Math.max(Number(duplicateRow.quantity || 1), 1) + Math.max(Number(row.quantity || 1), 1)
  if (isSalesOrderType.value) {
    duplicateRow.receivableAmount = Number((Number(duplicateRow.unitPrice || row.unitPrice || 0) * duplicateRow.quantity).toFixed(2))
    duplicateRow.receivedAmount = Number(((duplicateRow.receivableAmount * Number(duplicateRow.discountRate || row.discountRate || 10)) / 10).toFixed(2))
    duplicateRow.totalAmount = Number(duplicateRow.receivableAmount || 0)
  } else {
    syncRowAmount(duplicateRow)
  }
  clearRowGoods(row)
  normalizeEditorItemsPage()
  return {
    merged: true,
    targetIndex: currentIndex,
    targetRow: row,
  }
}

function mergeDuplicateGoodsRowsInTarget(target = 'default') {
  const rows = editorRowsForTarget(target)
  for (let index = 0; index < rows.length; index += 1) {
    const currentRow = rows[index]
    const result = mergeDuplicateFilledGoodsRow(currentRow, target)
    if (result.merged) {
      index = Math.max(-1, Number(result.targetIndex || 0) - 1)
    }
  }
}

function advanceToNextEditorRow(row, field, { deferFocus = false } = {}) {
  const target = resolveEditorTargetByRow(row)
  const mergeResult = mergeDuplicateFilledGoodsRow(row, target)
  if (mergeResult.merged) {
    if (deferFocus) {
      focusEditorFieldAfterUiSettles(mergeResult.targetRow.localId, field)
    } else {
      focusEditorField(mergeResult.targetRow.localId, field)
    }
    return
  }
  const nextIndex = Math.max(0, Number(mergeResult.targetIndex || 0) + 1)
  const nextRow = ensureEditorFocusRow(target, nextIndex)
  if (deferFocus) {
    focusEditorFieldAfterUiSettles(nextRow.localId, field)
  } else {
    focusEditorField(nextRow.localId, field)
  }
}

function collectBlankEditorRowKeys(target = 'default') {
  return editorRowsForTarget(target)
    .filter((row) => isEditorBlankRow(row))
    .map((row) => row.localId)
}

function removeBlankRowsForTarget(target = 'default') {
  const blankRowKeys = collectBlankEditorRowKeys(target)
  blankRowKeys.forEach((rowKey) => removeRowByKey(rowKey))
  return blankRowKeys.length
}

async function maybeRemoveBlankRowsBeforeDraftSave() {
  const targets = isSaleExchangeType.value ? ['incoming', 'outgoing'] : ['default']
  const blankCount = targets.reduce((sum, target) => sum + collectBlankEditorRowKeys(target).length, 0)
  if (!blankCount) {
    return
  }
  try {
    await confirmAction(
      `检测到 ${blankCount} 条空白行，是否在保存草稿前自动删除？`,
      '空白行处理',
      '删除空白行',
    )
  } catch {
    return
  }
  targets.forEach((target) => {
    removeBlankRowsForTarget(target)
  })
  ensureAtLeastOneRow()
  normalizeEditorItemsPage()
  ElMessage.success(`已自动删除 ${blankCount} 条空白行`)
}

function normalizeEditorItemsPage() {
  editorItemsPage.value = Math.min(Math.max(editorItemsPage.value, 1), editorItemsPageCount.value)
}

function normalizeDetailItemsPage() {
  detailItemsPage.value = Math.min(Math.max(detailItemsPage.value, 1), detailItemsPageCount.value)
}

function ensureAtLeastOneRow() {
  if (isSaleExchangeType.value) {
    if (!form.exchangeIncomingItems.length) {
      form.exchangeIncomingItems.push(createRow({ lineType: 'incoming' }))
    }
    if (!form.exchangeOutgoingItems.length) {
      form.exchangeOutgoingItems.push(createRow({ lineType: 'outgoing' }))
    }
    return
  }
}

function syncRowAmount(row) {
  row.quantity = Math.max(Number(row.quantity || 1), 1)
  row.unitPrice = Number(row.unitPrice || 0)
  if (isSalesOrderType.value) {
    const fallbackAmount = Number((row.unitPrice * row.quantity).toFixed(2))
    const rawReceivableAmount = row.receivableAmount
    const rawReceivedAmount = row.receivedAmount
    const rawCouponAmount = row.couponAmount
    row.receivableAmount = rawReceivableAmount === '' || rawReceivableAmount === null || rawReceivableAmount === undefined
      ? fallbackAmount
      : Number(rawReceivableAmount || 0)
    row.receivedAmount = rawReceivedAmount === '' || rawReceivedAmount === null || rawReceivedAmount === undefined
      ? row.receivableAmount
      : Number(rawReceivedAmount || 0)
    row.couponAmount = rawCouponAmount === '' || rawCouponAmount === null || rawCouponAmount === undefined
      ? 0
      : Number(rawCouponAmount || 0)
    row.discountRate = row.receivableAmount > 0
      ? Number(((row.receivedAmount / row.receivableAmount) * 10).toFixed(2))
      : 10
    row.totalAmount = Number(row.receivableAmount)
    return
  }
  row.totalAmount = Number((row.unitPrice * row.quantity).toFixed(2))
}

function syncRowDiscount(row) {
  row.quantity = Math.max(Number(row.quantity || 1), 1)
  row.unitPrice = Number(row.unitPrice || 0)
  const fallbackAmount = Number((row.unitPrice * row.quantity).toFixed(2))
  const rawReceivableAmount = row.receivableAmount
  const rawCouponAmount = row.couponAmount
  row.receivableAmount = rawReceivableAmount === '' || rawReceivableAmount === null || rawReceivableAmount === undefined
    ? fallbackAmount
    : Number(rawReceivableAmount || 0)
  row.couponAmount = rawCouponAmount === '' || rawCouponAmount === null || rawCouponAmount === undefined
    ? 0
    : Number(rawCouponAmount || 0)
  row.discountRate = Number(Number(row.discountRate || 0).toFixed(2))
  row.receivedAmount = row.receivableAmount > 0
    ? Number(((row.receivableAmount * row.discountRate) / 10).toFixed(2))
    : 0
  row.totalAmount = Number(row.receivableAmount)
}

function validatePendingSalesItemsForRows(rows, requiresBoundOrder = false) {
  const sourceRows = Array.isArray(rows) ? rows : []
  const incompleteIndex = sourceRows.findIndex((item) => {
    if (!String(item.salesperson || '').trim()) {
      return true
    }
    return requiresBoundOrder && !String(item.orderNum || '').trim()
  })
  if (incompleteIndex < 0) {
    return ''
  }
  const rowLabel = `第 ${incompleteIndex + 1} 行`
  if (!String(sourceRows[incompleteIndex]?.salesperson || '').trim()) {
    return `${rowLabel} 销售员未填写完整，不能提交审批`
  }
  return `${rowLabel} 销售记录信息不完整，不能提交审批`
}

function validatePendingSalesItems() {
  if (!isSalesOrderType.value) {
    return ''
  }
  const salesValidationItems = isSaleExchangeType.value ? form.exchangeIncomingItems : form.items
  const requiresBoundOrder = usesSalesRecordBinding.value || isSaleExchangeType.value
  return validatePendingSalesItemsForRows(salesValidationItems, requiresBoundOrder)
}

function syncOutgoingShopSelection(row, field) {
  const targetId = Number(
    field === 'ship'
      ? row.shipShopId
      : field === 'receive'
        ? row.receiveShopId
        : row.saleShopId || 0,
  ) || null
  const optionPool = field === 'sale' ? sourceOptions.value : stockLocationOptions.value
  const matched = optionPool.find((item) => Number(item.id) === Number(targetId || 0))
  if (field === 'ship') {
    row.shipShopName = matched?.name || ''
  } else if (field === 'receive') {
    row.receiveShopName = matched?.name || ''
  } else {
    row.saleShopName = matched?.name || ''
    if (!row.receiveShopId || !row.receiveShopName) {
      row.receiveShopId = row.saleShopId || null
      row.receiveShopName = row.saleShopName || ''
    }
    ensureRowSalespersonByShop(row)
  }
}

async function handleSaleInventoryLocationChange(row, field) {
  syncOutgoingShopSelection(row, field)
  if (field === 'ship' && Number(row?.goodsId || 0)) {
    const snapshot = await loadGoodsInventorySnapshot(row.goodsId, { force: true })
    row.sourceStock = Number(snapshot[Number(row.shipShopId || 0)] || 0)
  }
}

function clearRowGoods(row) {
  const localId = row?.localId || nextRowKey()
  const lineType = String(row?.lineType || 'default')
  Object.assign(row, createRow({
    localId,
    lineType,
  }))
  row.id = null
  row.remark = ''
  row.isNewGoods = false
  goodsSelectionLocks.delete(localId)
  goodsLookupTokens.delete(localId)
  resolvedBarcodeByRow.delete(localId)
  barcodeLookupTokens.delete(localId)
  salesRecordLookupTokens.delete(localId)
}

function fillRowFromGoods(row, goods) {
  const primaryStock = Number(goods.shopQuantity ?? goods.sourceStock ?? 0)
  const secondaryStock = Number(goods.secondaryShopQuantity ?? goods.targetStock ?? primaryStock)
  row.goodsId = goods.id
  row.goodsName = goods.model || goods.name || ''
  row.productCode = goods.productCode || ''
  row.brand = goods.brand || ''
  row.series = goods.series || ''
  row.barcode = goods.barcode || ''
  row.unitPrice = Number(goods.price || 0)
  if (isSalesOrderType.value) {
    row.receivableAmount = null
    row.receivedAmount = null
  }
  row.sourceStock = primaryStock
  row.targetStock = secondaryStock
  row.isNewGoods = false
  ensureRowSalespersonByShop(row)
  syncRowAmount(row)
}

async function loadGoodsInventorySnapshot(goodsId, { force = false } = {}) {
  const normalizedId = Number(goodsId || 0)
  if (!normalizedId) {
    return {}
  }
  if (!force && goodsInventorySnapshots[normalizedId]) {
    return goodsInventorySnapshots[normalizedId]
  }
  const payload = await apiGet(`/goods/items/${normalizedId}/inventory`, {
    token: authStore.token,
  })
  const snapshot = {}
  if (payload?.success) {
    for (const item of payload.inventories || []) {
      snapshot[Number(item.shopId || 0)] = Number(item.quantity || 0)
    }
  }
  goodsInventorySnapshots[normalizedId] = snapshot
  return snapshot
}

async function enrichGoodsWithStocks(goods) {
  const sourceId = isSaleAffectingInventory.value
    ? Number(saleShipShopId.value || form.sourceShopId || 0)
    : Number(form.sourceShopId || 0)
  const targetId = Number(form.targetShopId || 0)
  const sourceStock = Number(goods.sourceStock ?? goods.shopQuantity ?? 0)
  const targetStock = Number(goods.targetStock ?? goods.secondaryShopQuantity ?? goods.shopQuantity ?? 0)
  if ((sourceId || targetId) && goods.id) {
    const snapshot = await loadGoodsInventorySnapshot(goods.id, { force: true })
    return {
      ...goods,
      sourceStock: sourceId ? Number(snapshot[sourceId] || 0) : sourceStock,
      targetStock: targetId ? Number(snapshot[targetId] || 0) : targetStock,
    }
  }
  return {
    ...goods,
    sourceStock,
    targetStock,
  }
}

function fillRowFromSaleRecord(row, record, quantityOverride = null) {
  const baseQuantity = Math.max(Number(record.quantity || 1), 1)
  const nextQuantity = Math.max(Number(quantityOverride ?? record.quantity ?? 1), 1)
  const receivableAmount = Number(record.receivableAmount || 0)
  const receivedAmount = Number(record.receivedAmount || 0)
  const quantityRatio = nextQuantity / baseQuantity
  row.saleRecordId = Number(record.id || 0) || null
  row.orderNum = record.orderNum || ''
  row.salesperson = record.salesperson || ''
  row.saleShopId = record.shopId || null
  row.saleShopName = record.shopName || ''
  row.receiveShopId = record.shopId || null
  row.receiveShopName = record.shopName || ''
  row.shipShopId = record.shipShopId || null
  row.shipShopName = record.shipShopName || row.saleShopName || ''
  row.goodsId = record.goodsId || null
  row.goodsName = record.goodsModel || record.goodsDisplayName || ''
  row.productCode = record.goodsCode || ''
  row.brand = record.goodsBrand || ''
  row.series = record.goodsSeries || ''
  row.barcode = record.goodsBarcode || ''
  row.unitPrice = Number(record.unitPrice || 0)
  row.quantity = nextQuantity
  row.receivedAmount = Number((receivedAmount * quantityRatio).toFixed(2))
  row.receivableAmount = Number((receivableAmount * quantityRatio).toFixed(2))
  row.couponAmount = Number(record.couponAmount || 0)
  row.discountRate = Number(record.discountRate || 10)
  row.channel = record.channel || '门店'
  row.customerName = record.customerName || ''
  row.sourceStock = 0
  row.targetStock = 0
  row.isNewGoods = false
  ensureRowSalespersonByShop(row)
  syncRowAmount(row)
}

async function hydrateItemsWithLiveStocks(items, sourceShopId, targetShopId) {
  const sourceId = Number(sourceShopId || 0)
  const targetId = Number(targetShopId || 0)
  return Promise.all((items || []).map(async (item) => {
    if (!item?.goodsId) {
      return {
        ...item,
        sourceStock: 0,
        targetStock: 0,
      }
    }
    const snapshot = await loadGoodsInventorySnapshot(item.goodsId, { force: true })
    return {
      ...item,
      sourceStock: sourceId ? Number(snapshot[sourceId] || 0) : 0,
      targetStock: targetId ? Number(snapshot[targetId] || 0) : 0,
    }
  }))
}

async function refreshSelectedItemStocks() {
  const rows = editorAllItems.value.filter((item) => item.goodsId)
  if (!rows.length) {
    return
  }
  if (isSaleAffectingInventory.value) {
    await Promise.all(rows.map(async (row) => {
      const snapshot = await loadGoodsInventorySnapshot(row.goodsId, { force: true })
      row.sourceStock = Number(snapshot[Number(row.shipShopId || form.sourceShopId || 0)] || 0)
      row.targetStock = 0
    }))
    return
  }
  const hydratedRows = await hydrateItemsWithLiveStocks(rows, form.sourceShopId, form.targetShopId)
  const rowMap = new Map(hydratedRows.map((item) => [Number(item.goodsId || 0), item]))
  editorAllItems.value.forEach((row) => {
    if (!row.goodsId) {
      return
    }
    const matched = rowMap.get(Number(row.goodsId || 0))
    if (!matched) {
      return
    }
    row.sourceStock = Number(matched.sourceStock || 0)
    row.targetStock = Number(matched.targetStock || 0)
  })
}

function normalizeSuggestionText(value) {
  return String(value || '').trim().toLowerCase()
}

function normalizeSuggestionOption(item) {
  const value = String(item?.value ?? item?.name ?? item?.label ?? '').trim()
  if (!value) {
    return null
  }
  return {
    value,
    label: String(item?.label ?? item?.name ?? value).trim() || value,
    count: Number(item?.count || 0),
  }
}

function buildTextSuggestions(options, queryString) {
  const normalizedQuery = normalizeSuggestionText(queryString)
  return (options || [])
    .map((item) => normalizeSuggestionOption(item))
    .filter((item) => item && (!normalizedQuery || normalizeSuggestionText(item.value).includes(normalizedQuery)))
    .slice(0, 12)
}

async function ensureOtherWarehouseOptionsLoaded() {
  if (meta.otherWarehouseOptions.length) {
    return
  }
  const payload = await apiGet('/shops', {
    token: authStore.token,
    query: {
      page: 1,
      page_size: 100,
      shop_type: String(SHOP_TYPE_OTHER_WAREHOUSE),
    },
  })
  if (payload?.success) {
    meta.otherWarehouseOptions = payload.shops || []
  }
}

async function fetchOtherWarehouseSuggestions(queryString, callback) {
  await ensureOtherWarehouseOptionsLoaded()
  callback(buildTextSuggestions(meta.otherWarehouseOptions, queryString))
}

async function fetchGoodsSuggestions(queryString, callback) {
  const baseQuery = {
    page: 1,
    page_size: 10,
    q: queryString || undefined,
    catalog_only: 'false',
    sort_field: 'updated_at',
    sort_order: 'desc',
  }
  if (form.orderType === 'transfer') {
    const [sourcePayload, targetPayload] = await Promise.all([
      apiGet('/goods/items', {
        token: authStore.token,
        query: {
          ...baseQuery,
          distribution_shop_id: form.sourceShopId || undefined,
        },
      }),
      apiGet('/goods/items', {
        token: authStore.token,
        query: {
          ...baseQuery,
          distribution_shop_id: form.targetShopId || undefined,
        },
      }),
    ])
    if (!sourcePayload?.success && !targetPayload?.success) {
      callback([])
      return
    }
    const targetMap = new Map((targetPayload?.items || []).map((item) => [Number(item.id), item]))
    callback(
      (sourcePayload?.items || targetPayload?.items || []).map((item) => {
        const goodsName = [item.brand, item.series, item.model].filter(Boolean).join(' ') || item.name || item.barcode
        const targetItem = targetMap.get(Number(item.id))
        return {
          ...item,
          sourceStock: Number(item.shopQuantity || 0),
          targetStock: Number(targetItem?.shopQuantity || 0),
          value: `${goodsName}（${Number(item.shopQuantity || 0)}）`,
        }
      }),
    )
    return
  }

  const payload = await apiGet('/goods/items', {
    token: authStore.token,
    query: {
      ...baseQuery,
      distribution_shop_id: goodsPickerDistributionShopId.value || undefined,
    },
  })
  if (!payload?.success) {
    callback([])
    return
  }
  callback(
    (payload.items || []).map((item) => ({
      ...item,
      sourceStock: Number(item.shopQuantity || 0),
      targetStock: Number(item.shopQuantity || 0),
      value: [item.brand, item.series, item.model].filter(Boolean).join(' ') || item.name || item.barcode,
    })),
  )
}

function fetchBrandSuggestions(queryString, callback) {
  callback(buildTextSuggestions(meta.goodsBrandOptions, queryString))
}

function fetchSeriesSuggestions(queryString, callback) {
  callback(buildTextSuggestions(meta.goodsSeriesOptions, queryString))
}

function normalizeLookupText(value) {
  return String(value || '').trim().toLowerCase().replace(/\s+/g, ' ')
}

function normalizeCompactLookupText(value) {
  return normalizeLookupText(value).replace(/\s+/g, '')
}

function matchesLookupText(source, target) {
  const normalizedSource = normalizeLookupText(source)
  const normalizedTarget = normalizeLookupText(target)
  if (!normalizedSource || !normalizedTarget) {
    return false
  }
  if (normalizedSource === normalizedTarget) {
    return true
  }
  return normalizeCompactLookupText(source) === normalizeCompactLookupText(target)
}

function resolveGoodsLookupDistributionShopId(row) {
  if (form.orderType === 'transfer' || form.orderType === 'return' || form.orderType === 'damage') {
    return Number(form.sourceShopId || 0) || null
  }
  if (form.orderType === 'purchase') {
    return Number(form.targetShopId || 0) || null
  }
  if (isSaleAffectingInventory.value) {
    return Number(row?.shipShopId || saleShipShopId.value || form.sourceShopId || 0) || null
  }
  if (form.orderType === 'sale_exchange') {
    return Number(form.sourceShopId || 0) || null
  }
  return null
}

function buildGoodsLookupCandidates(item) {
  return [
    item?.value,
    item?.model,
    item?.name,
    item?.productCode,
    item?.barcode,
    [item?.brand, item?.series, item?.model].filter(Boolean).join(' '),
    [item?.brand, item?.series, item?.name].filter(Boolean).join(' '),
  ]
    .map((value) => String(value || '').trim())
    .filter(Boolean)
}

function resolveExactGoodsMatch(items, query) {
  const sourceItems = Array.isArray(items) ? items : []
  const normalizedQuery = normalizeLookupText(query)
  const exactMatches = sourceItems.filter((item) => (
    buildGoodsLookupCandidates(item).some((candidate) => matchesLookupText(candidate, query))
  ))
  if (exactMatches.length === 1) {
    return exactMatches[0]
  }
  if (exactMatches.length > 1) {
    const exactBarcodeMatch = exactMatches.find((item) => matchesLookupText(item?.barcode, query))
    if (exactBarcodeMatch) {
      return exactBarcodeMatch
    }
    const exactProductCodeMatch = exactMatches.find((item) => matchesLookupText(item?.productCode, query))
    if (exactProductCodeMatch) {
      return exactProductCodeMatch
    }
    return null
  }
  if (sourceItems.length === 1) {
    const fallbackMatched = buildGoodsLookupCandidates(sourceItems[0]).some((candidate) => {
      const normalizedCandidate = normalizeLookupText(candidate)
      return Boolean(normalizedQuery) && Boolean(normalizedCandidate) && (
        normalizedCandidate.includes(normalizedQuery)
        || normalizedQuery.includes(normalizedCandidate)
      )
    })
    return fallbackMatched ? sourceItems[0] : null
  }
  return null
}

function resolveQuickAddDistributionShopId() {
  if (form.orderType === 'transfer' || form.orderType === 'return' || form.orderType === 'damage') {
    return Number(form.sourceShopId || 0) || null
  }
  if (form.orderType === 'purchase') {
    return Number(form.targetShopId || 0) || null
  }
  if (isSaleAffectingInventory.value) {
    return Number(saleShipShopId.value || form.sourceShopId || 0) || null
  }
  return null
}

function createQuickAddTopRow(target = 'default') {
  const rows = editorRowsForTarget(target)
  const nextRow = createRow({ lineType: target === 'default' ? 'default' : target })
  rows.unshift(nextRow)
  if (target === 'default') {
    editorItemsPage.value = 1
    normalizeEditorItemsPage()
  }
  return nextRow
}

function findDuplicateFilledGoodsRow(goodsId, target = 'default') {
  const normalizedGoodsId = Number(goodsId || 0)
  if (!normalizedGoodsId) {
    return null
  }
  return editorRowsForTarget(target).find((row) => (
    Number(row?.goodsId || 0) === normalizedGoodsId
    && !isEditorBlankRow(row)
  )) || null
}

function incrementExistingGoodsRow(row, quantityDelta = 1) {
  if (!row) {
    return
  }
  row.quantity = Math.max(Number(row.quantity || 1), 1) + Math.max(Number(quantityDelta || 1), 1)
  if (isSalesOrderType.value) {
    row.receivableAmount = Number((Number(row.unitPrice || 0) * row.quantity).toFixed(2))
    row.receivedAmount = Number(((row.receivableAmount * Number(row.discountRate || 10)) / 10).toFixed(2))
    row.totalAmount = Number(row.receivableAmount || 0)
    return
  }
  syncRowAmount(row)
}

async function resolveQuickAddGoods(query) {
  const normalizedQuery = String(query || '').trim()
  if (!normalizedQuery) {
    return null
  }
  const barcodePayload = await apiGet(`/goods/barcode/${encodeURIComponent(normalizedQuery)}`, {
    token: authStore.token,
    query: {
      catalog_only: 'false',
    },
  })
  if (barcodePayload?.success && barcodePayload.item) {
    return barcodePayload.item
  }
  const payload = await apiGet('/goods/items', {
    token: authStore.token,
    query: {
      page: 1,
      page_size: 12,
      q: normalizedQuery,
      catalog_only: 'false',
      sort_field: 'updated_at',
      sort_order: 'desc',
      distribution_shop_id: resolveQuickAddDistributionShopId() || undefined,
    },
  })
  if (!payload?.success) {
    return null
  }
  return resolveExactGoodsMatch(payload.items || [], normalizedQuery)
}

function handleQuickAddInput() {
  quickAddMatchedLabel.value = ''
  quickAddLookupToken = null
}

function handleQuickAddEnter(event) {
  const target = event?.target
  if (target instanceof HTMLElement) {
    const insideAutocomplete = target.closest('.el-autocomplete')
    if (insideAutocomplete && isVisibleFloatingPanel('.el-autocomplete-suggestion')) {
      return
    }
  }
  void commitQuickAddInput()
}

async function handleQuickAddSuggestionSelect(item) {
  await commitQuickAddInput({
    item: Number(item?.id || 0) > 0 ? item : null,
    query: Number(item?.id || 0) > 0 ? item?.value : item?.value || quickAddQuery.value,
  })
}

async function commitQuickAddInput({ item = null, query = quickAddQuery.value } = {}) {
  if (!showQuickAddBar.value || quickAddLoading.value) {
    return false
  }
  const normalizedQuery = String(query || '').trim()
  if (!normalizedQuery && !item) {
    focusQuickAddField()
    return false
  }
  quickAddLoading.value = true
  quickAddMatchedLabel.value = ''
  const lookupToken = Symbol(`quick-add-${normalizedQuery || Date.now()}`)
  quickAddLookupToken = lookupToken
  try {
    const matchedGoods = item || await resolveQuickAddGoods(normalizedQuery)
    if (quickAddLookupToken !== lookupToken) {
      return false
    }
    if (!matchedGoods) {
      ElMessage.warning('未找到匹配的商品或条码')
      return false
    }
    const enrichedGoods = await enrichGoodsWithStocks(matchedGoods)
    if (quickAddLookupToken !== lookupToken) {
      return false
    }
    const duplicateRow = findDuplicateFilledGoodsRow(enrichedGoods.id, 'default')
    if (duplicateRow) {
      incrementExistingGoodsRow(duplicateRow, 1)
    } else {
      const targetRow = createQuickAddTopRow('default')
      fillRowFromGoods(targetRow, enrichedGoods)
    }
    quickAddMatchedLabel.value = buildMatchedGoodsLabel(enrichedGoods)
    quickAddQuery.value = ''
    return true
  } finally {
    if (quickAddLookupToken === lookupToken) {
      quickAddLookupToken = null
    }
    quickAddLoading.value = false
    focusQuickAddField()
  }
}

function rowMatchesCurrentGoods(row, query) {
  if (Number(row?.goodsId || 0) <= 0) {
    return false
  }
  return [
    row?.goodsName,
    row?.productCode,
    row?.barcode,
    [row?.brand, row?.series, row?.goodsName].filter(Boolean).join(' '),
  ].some((candidate) => matchesLookupText(candidate, query))
}

async function onRowGoodsCommit(row, { allowAdvanceResolved = false } = {}) {
  const localId = String(row?.localId || '').trim()
  const goodsName = String(row?.goodsName || '').trim()
  if (!localId || !goodsName) {
    goodsLookupTokens.delete(localId)
    return false
  }
  if (goodsSelectionLocks.has(localId)) {
    return false
  }
  if (rowMatchesCurrentGoods(row, goodsName)) {
    if (allowAdvanceResolved) {
      advanceToNextEditorRow(row, 'goodsName', { deferFocus: true })
    }
    return true
  }
  const lookupToken = Symbol(`goods-${localId}`)
  goodsLookupTokens.set(localId, lookupToken)
  const payload = await apiGet('/goods/items', {
    token: authStore.token,
    query: {
      page: 1,
      page_size: 12,
      q: goodsName,
      catalog_only: 'false',
      sort_field: 'updated_at',
      sort_order: 'desc',
      distribution_shop_id: resolveGoodsLookupDistributionShopId(row) || undefined,
    },
  })
  if (goodsLookupTokens.get(localId) !== lookupToken) {
    return false
  }
  goodsLookupTokens.delete(localId)
  if (!payload?.success) {
    return false
  }
  const matched = resolveExactGoodsMatch(payload.items || [], goodsName)
  if (!matched) {
    return false
  }
  fillRowFromGoods(row, await enrichGoodsWithStocks(matched))
  advanceToNextEditorRow(row, 'goodsName', { deferFocus: true })
  return true
}

function resolveExactSaleRecord(records, orderNum) {
  const sourceRecords = Array.isArray(records) ? records : []
  const exactMatches = sourceRecords.filter((item) => matchesLookupText(item?.orderNum, orderNum))
  if (exactMatches.length === 1) {
    return exactMatches[0]
  }
  if (exactMatches.length > 1) {
    return null
  }
  if (sourceRecords.length === 1 && matchesLookupText(sourceRecords[0]?.orderNum, orderNum)) {
    return sourceRecords[0]
  }
  return null
}

async function onRowOrderNumCommit(row, { allowAdvanceResolved = false } = {}) {
  const orderNum = String(row?.orderNum || '').trim()
  if (!orderNum) {
    salesRecordLookupTokens.delete(String(row?.localId || '').trim())
    return false
  }
  if (Number(row?.saleRecordId || 0) > 0) {
    if (allowAdvanceResolved && matchesLookupText(row.orderNum, orderNum)) {
      advanceToNextEditorRow(row, 'orderNum', { deferFocus: true })
    }
    return true
  }
  if (!Number(form.sourceShopId || 0)) {
    return false
  }
  const localId = String(row?.localId || '').trim()
  if (!localId) {
    return false
  }
  const lookupToken = Symbol(`sale-record-${localId}`)
  salesRecordLookupTokens.set(localId, lookupToken)
  const payload = await apiGet('/sales/records', {
    token: authStore.token,
    query: {
      page: 1,
      page_size: 10,
      order_num: orderNum,
      shop_id: Number(form.sourceShopId || 0) || undefined,
      sale_status: (form.orderType === 'sale_return' || form.orderType === 'sale_exchange') ? 'normal' : undefined,
    },
  })
  if (salesRecordLookupTokens.get(localId) !== lookupToken) {
    return false
  }
  salesRecordLookupTokens.delete(localId)
  if (!payload?.success) {
    return false
  }
  const matched = resolveExactSaleRecord(payload.records || [], orderNum)
  if (!matched) {
    return false
  }
  fillRowFromSaleRecord(row, matched)
  if (isSaleExchangeType.value) {
    form.exchangeOutgoingItems.forEach((item) => {
      if (!String(item.salesperson || '').trim()) {
        item.salesperson = row.salesperson || applicantName.value || ''
      }
      ensureRowSalespersonByShop(item)
    })
  }
  advanceToNextEditorRow(row, 'orderNum', { deferFocus: true })
  return true
}

async function onRowBarcodeChange(row, { allowAdvanceResolved = false } = {}) {
  const localId = String(row?.localId || '').trim()
  const barcode = String(row?.barcode || '').trim()
  if (!localId || !barcode) {
    if (localId) {
      resolvedBarcodeByRow.delete(localId)
      barcodeLookupTokens.delete(localId)
    }
    return
  }
  if (resolvedBarcodeByRow.get(localId) === barcode && Number(row.goodsId || 0) > 0) {
    if (allowAdvanceResolved) {
      advanceToNextEditorRow(row, 'barcode', { deferFocus: true })
    }
    return true
  }
  const lookupToken = Symbol(`barcode-${localId}`)
  barcodeLookupTokens.set(localId, lookupToken)
  const payload = await apiGet(`/goods/barcode/${encodeURIComponent(barcode)}`, {
    token: authStore.token,
    query: {
      catalog_only: 'false',
    },
  })
  if (barcodeLookupTokens.get(localId) !== lookupToken) {
    return
  }
  if (!payload?.success || !payload.item) {
    row.goodsId = null
    row.sourceStock = 0
    row.targetStock = 0
    resolvedBarcodeByRow.delete(localId)
    barcodeLookupTokens.delete(localId)
    ElMessage.warning(payload?.message || '未找到匹配条码的商品')
    return
  }
  fillRowFromGoods(row, await enrichGoodsWithStocks(payload.item))
  resolvedBarcodeByRow.set(localId, barcode)
  barcodeLookupTokens.delete(localId)
  advanceToNextEditorRow(row, 'barcode', { deferFocus: true })
  return true
}

async function handleGoodsSuggestionSelect(rowKey, item) {
  const row = findAnyEditorRow(rowKey)
  if (!row) {
    return
  }
  if (Number(item?.id || 0) > 0) {
    const localId = String(row.localId || '').trim()
    goodsSelectionLocks.add(localId)
    try {
      fillRowFromGoods(row, await enrichGoodsWithStocks(item))
      advanceToNextEditorRow(row, 'goodsName', { deferFocus: true })
    } finally {
      goodsSelectionLocks.delete(localId)
    }
    return
  }
  row.goodsName = String(item?.value || '').trim()
  await onRowGoodsCommit(row, { allowAdvanceResolved: true })
}

function onRowGoodsInput(row) {
  const localId = String(row?.localId || '').trim()
  goodsSelectionLocks.delete(localId)
  goodsLookupTokens.delete(localId)
  resolvedBarcodeByRow.delete(localId)
  barcodeLookupTokens.delete(localId)
  salesRecordLookupTokens.delete(localId)
  row.goodsId = null
  row.sourceStock = 0
  row.targetStock = 0
  row.isNewGoods = false
  syncRowAmount(row)
}

function handleRowGoodsEnter(row, event) {
  const target = event?.target
  if (target instanceof HTMLElement) {
    const insideAutocomplete = target.closest('.el-autocomplete')
    if (insideAutocomplete && isVisibleFloatingPanel('.el-autocomplete-suggestion')) {
      return
    }
  }
  void onRowGoodsCommit(row, { allowAdvanceResolved: true })
}

function editorRowsForTarget(target = 'default') {
  if (target === 'incoming') {
    return form.exchangeIncomingItems
  }
  if (target === 'outgoing') {
    return form.exchangeOutgoingItems
  }
  return form.items
}

function addItemRows(count = 1, target = 'default') {
  const safeCount = Math.min(Math.max(Number(count || 1), 1), 50)
  const rows = editorRowsForTarget(target)
  for (let index = 0; index < safeCount; index += 1) {
    rows.push(createRow({ lineType: target === 'default' ? 'default' : target }))
  }
  editorItemsPage.value = 1
  normalizeEditorItemsPage()
}

function addBatchRows(target = 'default') {
  addItemRows(batchRowCount.value, target)
}

function removeRowByKey(rowKey) {
  for (const rows of [form.items, form.exchangeIncomingItems, form.exchangeOutgoingItems]) {
    const index = rows.findIndex((item) => item.localId === rowKey)
    if (index >= 0) {
      rows.splice(index, 1)
      return true
    }
  }
  return false
}

async function confirmRemoveItemRow(rowKey) {
  try {
    await confirmDestructiveAction('确认删除当前这一行商品明细吗？', '删除本行')
  } catch {
    return
  }
  if (!removeRowByKey(rowKey)) {
    return
  }
  ensureAtLeastOneRow()
  normalizeEditorItemsPage()
}

function normalizeFormByType(nextType) {
  if (nextType === 'transfer') {
    form.supplierName = ''
    form.partnerName = ''
    return
  }
  if (nextType === 'purchase') {
    form.sourceShopId = null
    form.partnerName = ''
    return
  }
  if (nextType === 'return') {
    form.targetShopId = null
    form.supplierName = ''
    return
  }
  if (['sale', 'sale_return', 'sale_exchange'].includes(nextType)) {
    form.targetShopId = null
    form.supplierName = ''
    form.partnerName = ''
    if (nextType !== 'sale') {
      form.saleAffectsInventory = false
    }
    return
  }
  form.targetShopId = null
  form.supplierName = ''
  form.partnerName = ''
  form.saleAffectsInventory = false
}

function rowHasMeaningfulContent(row) {
  return Boolean(
    Number(row?.goodsId || 0) ||
    Number(row?.saleRecordId || 0) ||
    String(row?.goodsName || '').trim() ||
    String(row?.orderNum || '').trim() ||
    String(row?.salesperson || '').trim() ||
    Number(row?.quantity || 0) > 1 ||
    Number(row?.receivedAmount || 0) > 0 ||
    Number(row?.receivableAmount || 0) > 0
  )
}

function isEditorBlankRow(row) {
  if (!row) {
    return true
  }
  return !Boolean(
    Number(row?.goodsId || 0)
    || Number(row?.saleRecordId || 0)
    || String(row?.goodsName || '').trim()
    || String(row?.orderNum || '').trim()
    || String(row?.salesperson || '').trim()
    || String(row?.saleShopName || '').trim()
    || String(row?.receiveShopName || '').trim()
    || String(row?.shipShopName || '').trim()
    || String(row?.brand || '').trim()
    || String(row?.series || '').trim()
    || String(row?.barcode || '').trim()
    || String(row?.channel || '').trim()
    || String(row?.customerName || '').trim()
    || String(row?.remark || '').trim()
    || Number(row?.unitPrice || 0) > 0
    || Number(row?.quantity || 0) > 1
    || Number(row?.receivedAmount || 0) > 0
    || Number(row?.receivableAmount || 0) > 0
    || Number(row?.couponAmount || 0) > 0
  )
}

function visibleEditorRowsForTarget(target = 'default') {
  if (target === 'incoming') {
    return sortedExchangeIncomingItems.value
  }
  if (target === 'outgoing') {
    return sortedExchangeOutgoingItems.value
  }
  return editorPagedItems.value
}

function removeBlankRowsOnCurrentPage(target = 'default') {
  const visibleRows = visibleEditorRowsForTarget(target)
  const blankRowIds = visibleRows
    .filter((row) => isEditorBlankRow(row))
    .map((row) => row.localId)
  if (!blankRowIds.length) {
    ElMessage.info('当前页没有空白行')
    return
  }
  blankRowIds.forEach((rowKey) => removeRowByKey(rowKey))
  ensureAtLeastOneRow()
  normalizeEditorItemsPage()
  ElMessage.success(`已删除 ${blankRowIds.length} 条空白行`)
}

function onSaleAffectsInventoryChange() {
  if (form.orderType !== 'sale') {
    form.saleAffectsInventory = false
    return
  }
  if (form.saleAffectsInventory && !Number(saleShipShopId.value || 0)) {
    saleShipShopId.value = Number(form.sourceShopId || 0) || null
  }
  if (form.items.some((item) => rowHasMeaningfulContent(item))) {
    form.items = [createRow()]
    editorItemsPage.value = 1
    normalizeEditorItemsPage()
  } else {
    ensureAtLeastOneRow()
  }
  if (form.saleAffectsInventory) {
    ElMessage.info('已切换为变动库存销售单，请重新填写销售明细')
  } else {
    saleShipShopId.value = null
    ElMessage.info('已切换为补开单模式，请重新选择销售记录')
  }
}

async function onSaleHeaderShipShopChange(value) {
  const normalizedId = Number(value || 0) || null
  saleShipShopId.value = normalizedId
  await Promise.all(form.items.map((row) => updateRowShipShop(row, normalizedId)))
}

function changeOrderType(nextType) {
  resetQuickAddBar()
  const previousType = form.orderType
  const previousDefaultApproverId = resolveDefaultApproverId(previousType)
  form.orderType = nextType
  if (nextType === 'sale') {
    form.saleAffectsInventory = true
  } else {
    saleShipShopId.value = null
  }
  categoryDraft.category = resolveOrderCategory(nextType)
  normalizeFormByType(nextType)
  if (nextType === 'sale_exchange') {
    form.items = []
    form.exchangeIncomingItems = [createRow({ lineType: 'incoming' })]
    form.exchangeOutgoingItems = [createRow({ lineType: 'outgoing', channel: '门店' })]
  } else {
    form.exchangeIncomingItems = [createRow({ lineType: 'incoming' })]
    form.exchangeOutgoingItems = [createRow({ lineType: 'outgoing', channel: '门店' })]
    if (!form.items.length) {
      form.items = []
    }
  }
  ensureAtLeastOneRow()
  if (!Number(form.approverId || 0) || Number(form.approverId || 0) === Number(previousDefaultApproverId || 0)) {
    applyDefaultApproverToForm(nextType, { force: true })
  }
  editorAllItems.value.forEach((item) => {
    item.isNewGoods = false
    syncRowAmount(item)
  })
}

function resetForm(nextType = 'transfer') {
  resetQuickAddBar()
  form.id = null
  form.orderNum = ''
  form.orderType = nextType
  form.saleAffectsInventory = nextType === 'sale'
  form.formDate = defaultDateTimeLocal()
  form.reason = ''
  form.sourceShopId = null
  form.targetShopId = null
  form.supplierName = ''
  form.partnerName = ''
  form.approverId = null
  form.groupId = null
  form.groupId = defaultGroupId.value
  saleShipShopId.value = null
  form.items = []
  form.exchangeIncomingItems = [createRow({ lineType: 'incoming' })]
  form.exchangeOutgoingItems = [createRow({ lineType: 'outgoing', channel: '门店' })]
  batchRowCount.value = 3
  editorStep.value = 1
  editorItemsPage.value = 1
  editorItemsPageSize.value = 20
  editorSortState.prop = ''
  editorSortState.order = ''
  categoryDraft.category = resolveOrderCategory(nextType)
  normalizeFormByType(nextType)
  applyDefaultApproverToForm(nextType, { force: true })
}

function buildPayload(statusValue) {
  normalizeFormByType(form.orderType)
  return {
    orderType: form.orderType,
    status: statusValue,
    saleAffectsInventory: Boolean(form.saleAffectsInventory),
    reason: effectiveReason.value,
    formDate: form.formDate || null,
    sourceShopId: form.sourceShopId || null,
    targetShopId: form.targetShopId || null,
    supplierName: form.supplierName || '',
    partnerName: form.partnerName || '',
    approverId: form.approverId || null,
    groupId: form.groupId || null,
    items: buildSortedEditorPayloadItems().map((item) => serializeEditorPayloadItem(item)),
  }
}

function buildPayloadFromOrder(order, statusValue) {
  const sourceItems = Array.isArray(order?.items) ? order.items : []
  return {
    orderType: order?.orderType || 'transfer',
    status: statusValue,
    saleAffectsInventory: Boolean(order?.saleAffectsInventory),
    reason: String(order?.reason || '').trim(),
    formDate: order?.formDate || null,
    sourceShopId: order?.sourceShopId || null,
    targetShopId: order?.targetShopId || null,
    supplierName: order?.supplierName || '',
    partnerName: order?.partnerName || '',
    approverId: order?.approverId || null,
    groupId: order?.groupId || null,
    items: sourceItems.map((item) => ({
      lineType: item.lineType || 'default',
      saleRecordId: item.saleRecordId || null,
      orderNum: item.orderNum || '',
      salesperson: item.salesperson || '',
      saleShopId: item.saleShopId || null,
      saleShopName: item.saleShopName || '',
      receiveShopId: item.receiveShopId || null,
      receiveShopName: item.receiveShopName || '',
      shipShopId: item.shipShopId || null,
      shipShopName: item.shipShopName || '',
      goodsId: item.goodsId || null,
      goodsName: item.goodsName || '',
      productCode: item.productCode || '',
      brand: item.brand || '',
      series: item.series || '',
      barcode: item.barcode || '',
      unitPrice: toFiniteNumber(item.unitPrice, 0),
      quantity: toFiniteNumber(item.quantity, 1),
      receivedAmount: toFiniteNumber(item.receivedAmount, 0),
      receivableAmount: toFiniteNumber(item.receivableAmount ?? item.totalAmount, 0),
      couponAmount: toFiniteNumber(item.couponAmount, 0),
      discountRate: toFiniteNumber(item.discountRate, 10),
      totalAmount: toFiniteNumber(item.totalAmount, 0),
      channel: item.channel || '',
      customerName: item.customerName || '',
      remark: item.remark || '',
      isNewGoods: false,
    })),
  }
}

function resolveOrderSalesValidationRows(order) {
  const items = Array.isArray(order?.items) ? order.items : []
  if (String(order?.orderType || '') === 'sale_exchange') {
    return items.filter((item) => String(item.lineType || 'default') !== 'outgoing')
  }
  return items
}

function orderRequiresBoundSalesRecord(order) {
  const orderType = String(order?.orderType || '')
  if (orderType === 'sale_exchange') {
    return true
  }
  return ['sale', 'sale_return'].includes(orderType) && !Boolean(order?.saleAffectsInventory)
}

function rowHasEditableGoodsContent(item) {
  if (!item) {
    return false
  }
  return Boolean(
    Number(item.goodsId || 0)
    || String(item.goodsName || '').trim()
    || String(item.brand || '').trim()
    || String(item.series || '').trim()
    || String(item.barcode || '').trim()
    || Number(item.unitPrice || 0)
    || String(item.remark || '').trim(),
  )
}

function getPendingPurchaseGoodsRows(items) {
  return (Array.isArray(items) ? items : []).filter((item) => rowHasEditableGoodsContent(item) && !Number(item.goodsId || 0))
}

async function confirmPurchaseGoodsCreation(rows) {
  const pendingRows = Array.isArray(rows) ? rows : []
  if (!pendingRows.length) {
    return true
  }
  const preview = pendingRows
    .slice(0, 3)
    .map((item, index) => {
      const label = [item.brand, item.series, item.goodsName].filter(Boolean).join(' ') || item.barcode || `第 ${index + 1} 行商品`
      return `- ${label}`
    })
    .join('\n')
  const suffix = pendingRows.length > 3 ? `\n- 其余 ${pendingRows.length - 3} 条未匹配商品` : ''
  try {
    await confirmAction(`本工单包含未匹配的商品，是否确认创建新商品？\n\n${preview}${suffix}`, '新商品确认', '确认创建')
    return true
  } catch {
    return false
  }
}

function applyOrderToForm(order) {
  const normalizedOrder = normalizePersistedOrderDetail(order)
  form.id = normalizedOrder.id
  form.orderNum = normalizedOrder.orderNum || ''
  form.orderType = normalizedOrder.orderType || 'transfer'
  form.saleAffectsInventory = Boolean(normalizedOrder.saleAffectsInventory)
  form.reason = normalizedOrder.reason || ''
  form.formDate = String(normalizedOrder.formDate || '').slice(0, 16) || defaultDateTimeLocal()
  form.sourceShopId = normalizedOrder.sourceShopId || null
  form.targetShopId = normalizedOrder.targetShopId || null
  form.supplierName = normalizedOrder.supplierName || ''
  form.partnerName = normalizedOrder.partnerName || ''
  form.approverId = normalizedOrder.approverId || null
  form.groupId = normalizedOrder.groupId || null
  const mappedItems = (normalizedOrder.items || []).map((item) => createRow({
    id: item.id,
    sortIndex: Number(item.sortIndex ?? item.sort ?? 0),
    lineType: item.lineType || 'default',
    saleRecordId: item.saleRecordId || null,
    orderNum: item.orderNum || '',
    salesperson: item.salesperson || '',
    saleShopId: item.saleShopId || null,
    saleShopName: item.saleShopName || '',
    receiveShopId: item.receiveShopId || null,
    receiveShopName: item.receiveShopName || '',
    shipShopId: item.shipShopId || null,
    shipShopName: item.shipShopName || '',
    goodsId: item.goodsId || null,
    goodsName: item.goodsName || '',
    productCode: item.productCode || '',
    brand: item.brand || '',
    series: item.series || '',
    barcode: item.barcode || '',
    unitPrice: Number(item.unitPrice || 0),
    quantity: Number(item.quantity || 1),
    receivedAmount: Number(item.receivedAmount || 0),
    receivableAmount: Number(item.receivableAmount || item.totalAmount || 0),
    couponAmount: Number(item.couponAmount || 0),
    discountRate: Number(item.discountRate || 10),
    totalAmount: Number(item.totalAmount || 0),
    channel: item.channel || '',
    customerName: item.customerName || '',
    remark: item.remark || '',
    sourceStock: Number(item.sourceStock || 0),
    targetStock: Number(item.targetStock || 0),
    isNewGoods: false,
  }))
  if ((normalizedOrder.orderType || '') === 'sale_exchange') {
    form.items = []
    form.exchangeIncomingItems = mappedItems.filter((item) => String(item.lineType || 'default') !== 'outgoing')
    form.exchangeOutgoingItems = mappedItems.filter((item) => String(item.lineType || 'default') === 'outgoing')
  } else {
    form.items = mappedItems
    form.exchangeIncomingItems = [createRow({ lineType: 'incoming' })]
    form.exchangeOutgoingItems = [createRow({ lineType: 'outgoing', channel: '门店' })]
  }
  saleShipShopId.value = form.orderType === 'sale' && form.saleAffectsInventory
    ? (Number(form.items[0]?.shipShopId || form.sourceShopId || 0) || null)
    : null
  ensureAtLeastOneRow()
  batchRowCount.value = 3
  editorStep.value = 1
  editorItemsPage.value = 1
  editorItemsPageSize.value = 20
  editorSortState.prop = ''
  editorSortState.order = ''
  categoryDraft.category = resolveOrderCategory(form.orderType)
  normalizeEditorItemsPage()
}

function canEditRow(row) {
  return (
    canWrite.value &&
    ['draft', 'rejected'].includes(row.status) &&
    (
      Number(row.applicantId || 0) === Number(authStore.user?.id || 0) ||
      accessibleGroupIds.value.has(Number(row.groupId || 0))
    )
  )
}

function canAllocateRow(row) {
  return (
    canWrite.value &&
    String(row?.status || '') === 'approved' &&
    ['purchase', 'transfer'].includes(String(row?.orderType || ''))
  )
}

function canReviewRow(row) {
  return (
    canApprove.value &&
    row.status === 'pending' &&
    Number(row.approverId || 0) === Number(authStore.user?.id || 0)
  )
}

function canWithdrawRow(row) {
  return (
    canWrite.value &&
    row.status === 'pending' &&
    Number(row.applicantId || 0) === Number(authStore.user?.id || 0)
  )
}

function canDeleteRow(row) {
  const isApplicant = Number(row.applicantId || 0) === Number(authStore.user?.id || 0)
  const isSharedGroupDraft = accessibleGroupIds.value.has(Number(row.groupId || 0))
  return (
    canWrite.value &&
    (
      (['draft', 'rejected'].includes(String(row.status || '')) && (isApplicant || isSharedGroupDraft)) ||
      (String(row.status || '') === 'pending' && isApplicant)
    )
  )
}

function setScope(nextScope) {
  scope.value = nextScope
  page.value = 1
  logPage.value = 1
  if (statusFilterLocked.value) {
    statusFilter.value = ''
  }
  void Promise.all([loadOrders(), loadLogs()])
}

function resolveOrderQuery() {
  return {
    scope: scope.value,
    status: statusFilterLocked.value ? undefined : (statusFilter.value || undefined),
    dateStart: Array.isArray(dateRange.value) ? dateRange.value[0] || undefined : undefined,
    dateEnd: Array.isArray(dateRange.value) ? dateRange.value[1] || undefined : undefined,
    applicantId: applicantFilter.value || undefined,
    approverId: approverFilter.value || undefined,
  }
}

async function loadMeta() {
  const payload = await apiGet('/work-orders/meta', {
    token: authStore.token,
  })
  if (!payload?.success) {
    return
  }
  meta.categories = payload.categories || []
  meta.types = payload.types || []
  meta.statuses = payload.statuses || []
  meta.shopOptions = payload.shopOptions || []
  meta.storeOptions = payload.storeOptions || []
  meta.warehouseOptions = payload.warehouseOptions || []
  meta.otherWarehouseOptions = payload.otherWarehouseOptions || []
  meta.applicantOptions = payload.applicantOptions || []
  meta.approverOptions = payload.approverOptions || []
  meta.groups = payload.groups || []
  meta.defaultApproverSettings = payload.defaultApproverSettings || []
  if (!form.groupId && defaultGroupId.value) {
    form.groupId = defaultGroupId.value
  }
  if (!Number(form.approverId || 0)) {
    applyDefaultApproverToForm(form.orderType, { force: true })
  }
  syncWorkOrderSettingsRows()
  editorAllItems.value.forEach((row) => ensureRowSalespersonByShop(row))
}

async function loadGoodsAutocompleteMeta() {
  const payload = await apiGet('/goods/catalog/meta', {
    token: authStore.token,
    query: {
      catalog_only: 'false',
    },
  })
  if (!payload?.success) {
    meta.goodsBrandOptions = []
    meta.goodsSeriesOptions = []
    return
  }
  meta.goodsBrandOptions = payload.brandOptions || []
  meta.goodsSeriesOptions = payload.seriesOptions || []
}

async function loadDashboard() {
  const payload = await apiGet('/work-orders/dashboard', {
    token: authStore.token,
  })
  if (!payload?.success) {
    return
  }
  dashboard.draftCount = Number(payload.draftCount || 0)
  dashboard.pendingCount = Number(payload.pendingCount || 0)
  dashboard.approvalCount = Number(payload.approvalCount || 0)
  dashboard.recentMine = payload.recentMine || []
  dashboard.pendingApprovals = payload.pendingApprovals || []
}

async function loadWorkOrderSettings() {
  if (!canManageScheduledOrders.value) {
    workOrderSettings.value = []
    return
  }
  const payload = await apiGet('/work-orders/settings', {
    token: authStore.token,
  })
  if (!payload?.success) {
    workOrderSettings.value = []
    return
  }
  meta.defaultApproverSettings = payload.settings || []
  syncWorkOrderSettingsRows(payload.settings || [])
}

async function loadOrders() {
  loading.value = true
  const query = resolveOrderQuery()
  const payload = await apiGet('/work-orders', {
    token: authStore.token,
    query: {
      page: page.value,
      page_size: pageSize.value,
      scope: query.scope,
      order_type: orderTypeFilter.value || undefined,
      status: query.status,
      keyword: keyword.value || undefined,
      date_start: query.dateStart,
      date_end: query.dateEnd,
      applicant_id: query.applicantId,
      approver_id: query.approverId,
    },
  })
  loading.value = false
  if (!payload?.success) {
    orders.value = []
    total.value = 0
    return
  }
  orders.value = payload.orders || []
  total.value = Number(payload.total || 0)
}

async function loadLogs() {
  if (!logVisible.value) {
    return
  }
  logLoading.value = true
  const query = resolveLogQuery()
  const payload = await apiGet('/work-orders/logs', {
    token: authStore.token,
    query: {
      page: logPage.value,
      page_size: logPageSize.value,
      scope: query.scope,
      order_type: query.orderType,
      keyword: query.keyword,
      date_start: query.dateStart,
      date_end: query.dateEnd,
    },
  })
  logLoading.value = false
  if (!payload?.success) {
    logRows.value = []
    logTotal.value = 0
    return
  }
  logRows.value = payload.logs || []
  logTotal.value = Number(payload.total || 0)
}

async function onSearch() {
  page.value = 1
  await loadOrders()
}

async function onResetFilters() {
  keyword.value = ''
  dateRange.value = []
  orderTypeFilter.value = ''
  statusFilter.value = ''
  applicantFilter.value = null
  approverFilter.value = null
  scope.value = 'mine'
  filterPanelOpen.value = false
  page.value = 1
  await loadOrders()
}

async function onPageChange(nextPage) {
  page.value = nextPage
  await loadOrders()
}

async function onPageSizeChange(nextSize) {
  pageSize.value = nextSize
  page.value = 1
  await loadOrders()
}

async function onLogPageChange(nextPage) {
  logPage.value = nextPage
  await loadLogs()
}

async function onLogPageSizeChange(nextSize) {
  logPageSize.value = nextSize
  logPage.value = 1
  await loadLogs()
}

function resolveLogQuery() {
  return {
    scope: logScope.value || 'mine',
    orderType: logOrderTypeFilter.value || undefined,
    keyword: logKeyword.value || undefined,
    dateStart: logDateFrom.value || undefined,
    dateEnd: logDateTo.value || undefined,
  }
}

async function onLogSearch() {
  logPage.value = 1
  await loadLogs()
}

async function resetLogFilters() {
  logScope.value = scope.value || 'mine'
  logOrderTypeFilter.value = orderTypeFilter.value || ''
  logKeyword.value = keyword.value || ''
  logDateFrom.value = Array.isArray(dateRange.value) ? (dateRange.value[0] || '') : ''
  logDateTo.value = Array.isArray(dateRange.value) ? (dateRange.value[1] || '') : ''
  logPage.value = 1
  await loadLogs()
}

async function openLogDialog() {
  await router.push({
    name: 'log-center',
    query: {
      type: 'work_order',
      scope: scope.value || 'mine',
      order_type: orderTypeFilter.value || '',
      keyword: keyword.value || '',
      date_start: Array.isArray(dateRange.value) ? (dateRange.value[0] || '') : '',
      date_end: Array.isArray(dateRange.value) ? (dateRange.value[1] || '') : '',
      back: route.fullPath,
    },
  })
}

function onEditorItemsPageChange(nextPage) {
  editorItemsPage.value = nextPage
}

function onEditorItemsPageSizeChange(nextSize) {
  editorItemsPageSize.value = nextSize
  editorItemsPage.value = 1
  normalizeEditorItemsPage()
}

function onDetailItemsPageChange(nextPage) {
  detailItemsPage.value = nextPage
}

function onDetailItemsPageSizeChange(nextSize) {
  detailItemsPageSize.value = nextSize
  detailItemsPage.value = 1
  normalizeDetailItemsPage()
}

function onEditorTableSortChange({ prop, order }) {
  editorSortState.prop = prop || ''
  editorSortState.order = order || ''
  editorItemsPage.value = 1
  normalizeEditorItemsPage()
}

function onAllocationTableSortChange({ prop, order }) {
  allocationSortState.prop = prop || ''
  allocationSortState.order = order || ''
  allocationItemsPage.value = 1
}

function onDetailTableSortChange({ prop, order }) {
  detailSortState.prop = prop || ''
  detailSortState.order = order || ''
  detailItemsPage.value = 1
  normalizeDetailItemsPage()
}

function buildTableSummary(columns, rows) {
  const quantityValue = (rows || []).reduce((sum, item) => sum + Number(item.quantity || 0), 0)
  const amountValue = (rows || []).reduce((sum, item) => sum + Number(item.totalAmount || item.receivableAmount || 0), 0)
  const receivedValue = (rows || []).reduce((sum, item) => sum + Number(item.receivedAmount || 0), 0)
  const discountValue = amountValue > 0 ? Number(((receivedValue / amountValue) * 10).toFixed(2)) : 10
  const hasReceivedColumn = (rows || []).some((item) => Number(item.receivedAmount || 0) !== 0 || String(item.orderNum || '').trim())
  return columns.map((column, index) => {
    const label = String(column.label || '')
    const property = String(column.property || '')
    if (index === 0 || label === '商品名称') {
      return '合计'
    }
    if (label === '实付金额' || property === 'receivedAmount') {
      return hasReceivedColumn ? `¥ ${formatMoney(receivedValue)}` : ''
    }
    if (label === '数量' || property === 'quantity') {
      return String(quantityValue)
    }
    if (label === '折扣' || property === 'discountRate') {
      return hasReceivedColumn ? formatMoney(discountValue) : ''
    }
    if (label === '金额' || label === '应付金额' || property === 'totalAmount' || property === 'receivableAmount') {
      return `¥ ${formatMoney(amountValue)}`
    }
    return ''
  })
}

function buildWorkOrderTotals(rows) {
  const source = Array.isArray(rows) ? rows : []
  const amount = source.reduce((sum, item) => sum + Number(item.totalAmount || item.receivableAmount || 0), 0)
  const received = source.reduce((sum, item) => sum + Number(item.receivedAmount || 0), 0)
  return {
    quantity: source.reduce((sum, item) => sum + Number(item.quantity || 0), 0),
    amount,
    received,
    discount: amount > 0 ? Number(((received / amount) * 10).toFixed(2)) : 10,
  }
}

function editorTableSummary({ columns, data }) {
  return buildTableSummary(columns, data)
}

function detailTableSummary({ columns, data }) {
  return buildTableSummary(columns, data)
}

function buildInventoryWarnings(rows = editorAllItems.value, orderType = form.orderType) {
  const warnings = []
  const sourceRows = Array.isArray(rows) ? rows : []
  sourceRows.forEach((item, index) => {
    if (!Number(item.goodsId || 0)) {
      return
    }
    const goodsName = String(item.goodsName || item.barcode || `第 ${index + 1} 行商品`).trim()
    const segments = []
    if (orderType === 'transfer') {
      if (Number(item.sourceStock || 0) < 0) {
        segments.push(`发货库存 ${Number(item.sourceStock || 0)}`)
      } else if (Number(item.sourceStock || 0) === 0) {
        segments.push('发货库存 0')
      }
      if (Number(item.targetStock || 0) < 0) {
        segments.push(`收货库存 ${Number(item.targetStock || 0)}`)
      }
    } else if (orderType === 'purchase') {
      if (Number(item.targetStock || 0) < 0) {
        segments.push(`收货库存 ${Number(item.targetStock || 0)}`)
      }
    } else if (Number(item.sourceStock || 0) < 0) {
      segments.push(`发货库存 ${Number(item.sourceStock || 0)}`)
    } else if (Number(item.sourceStock || 0) === 0) {
      segments.push('发货库存 0')
    }
    if (segments.length) {
      warnings.push(`${goodsName}（${segments.join(' / ')}）`)
    }
  })
  return warnings
}

function resolveInventoryWarningActionText(actionType) {
  if (actionType === 'pending') {
    return '继续提交'
  }
  if (actionType === 'approved') {
    return '继续审批'
  }
  return '继续保存'
}

async function confirmInventoryWarningsBeforeProceed(
  actionType,
  rows = editorAllItems.value,
  orderType = form.orderType,
  saleAffectsInventoryFlag = form.saleAffectsInventory,
) {
  if (orderType === 'sale' && saleAffectsInventoryFlag) {
    await refreshSelectedItemStocks()
  }
  const warnings = buildInventoryWarnings(rows, orderType)
  if (!warnings.length) {
    return true
  }
  const lines = warnings.slice(0, 6).join('\n')
  const extra = warnings.length > 6 ? `\n另有 ${warnings.length - 6} 条库存异常未展开。` : ''
  const actionText = resolveInventoryWarningActionText(actionType)
  try {
    await confirmAction(
      `当前工单存在库存异常（发货库存为 0 或库存小于 0）的商品：\n${lines}${extra}\n\n确认仍要${actionText}吗？`,
      '库存异常确认',
      actionText,
    )
    return true
  } catch {
    return false
  }
}

function openCreateDialog(nextType = 'transfer') {
  if (!canWrite.value) {
    ElMessage.warning('当前账号没有创建工单权限')
    return
  }
  const nextCategory = resolveOrderCategory(nextType)
  categoryDraft.category = nextCategory
  categoryDialogVisible.value = true
}

function openCreateDialogByCategory(categoryValue) {
  const targetCategory = categoryValue || 'goods'
  const nextType = defaultTypeForCategory(targetCategory)
  categoryDraft.category = targetCategory
  resetForm(nextType)
  categoryDialogVisible.value = false
  editorVisible.value = true
  captureEditorSnapshot()
}

function resolveGroupRoleLabel(role) {
  if (role === 'owner') return '群主'
  if (role === 'admin') return '管理员'
  return '成员'
}

function canManageGroup(group) {
  return ['owner', 'admin'].includes(String(group?.memberRole || ''))
}

function openGroupDialog() {
  groupDialogVisible.value = true
  void loadMeta()
}

function openWorkOrderSettingsDialog() {
  if (!canManageScheduledOrders.value) {
    ElMessage.warning('当前账号没有管理工单设置权限')
    return
  }
  workOrderSettingsDialogVisible.value = true
  void Promise.all([loadMeta(), loadWorkOrderSettings()])
}

function openCreateGroupDialog() {
  resetGroupCreateForm()
  groupCreateVisible.value = true
}

function openEditGroupDialog(group) {
  editingGroupId.value = Number(group?.id || 0) || null
  groupCreateForm.name = String(group?.name || '')
  groupCreateForm.description = String(group?.description || '')
  groupCreateForm.inviteUserIds = []
  groupCreateVisible.value = true
}

function openInviteGroupDialog(group) {
  inviteTargetGroup.value = group || null
  groupInviteForm.inviteUserIds = []
  groupInviteVisible.value = true
}

async function submitCreateGroup() {
  if (!cleanReasonText(groupCreateForm.name)) {
    ElMessage.warning('请填写群组名称')
    return
  }
  if (!editingGroupId.value && (!Array.isArray(groupCreateForm.inviteUserIds) || groupCreateForm.inviteUserIds.length < 1)) {
    ElMessage.warning('群组至少需要邀请 1 名其他成员')
    return
  }
  groupSaving.value = true
  const payload = editingGroupId.value
    ? await apiPut(`/groups/${editingGroupId.value}`, {
      name: groupCreateForm.name,
      description: groupCreateForm.description || '',
    }, { token: authStore.token })
    : await apiPost('/groups', {
      name: groupCreateForm.name,
      description: groupCreateForm.description || '',
      inviteUserIds: groupCreateForm.inviteUserIds,
    }, { token: authStore.token })
  groupSaving.value = false
  if (!payload?.success) {
    ElMessage.error(payload?.message || (editingGroupId.value ? '群组更新失败' : '群组创建失败'))
    return
  }
  ElMessage.success(payload.message || (editingGroupId.value ? '群组已更新' : '群组已创建'))
  groupCreateVisible.value = false
  resetGroupCreateForm()
  await loadMeta()
}

async function submitGroupInvite() {
  if (!inviteTargetGroup.value?.id) {
    ElMessage.warning('请选择要邀请的群组')
    return
  }
  if (!Array.isArray(groupInviteForm.inviteUserIds) || groupInviteForm.inviteUserIds.length < 1) {
    ElMessage.warning('请至少选择 1 名成员')
    return
  }
  groupInviting.value = true
  const payload = await apiPost(`/groups/${inviteTargetGroup.value.id}/invite`, {
    userIds: groupInviteForm.inviteUserIds,
  }, { token: authStore.token })
  groupInviting.value = false
  if (!payload?.success) {
    ElMessage.error(payload?.message || '邀请发送失败')
    return
  }
  ElMessage.success(payload.message || '邀请已发出')
  groupInviteVisible.value = false
  resetGroupInviteForm()
  await loadMeta()
}

async function setDefaultGroup(group) {
  const groupId = Number(group?.id || 0)
  if (!groupId) {
    return
  }
  const payload = await apiPost(`/groups/${groupId}/default`, {}, { token: authStore.token })
  if (!payload?.success) {
    ElMessage.error(payload?.message || '默认群组更新失败')
    return
  }
  ElMessage.success(payload.message || '默认群组已更新')
  await loadMeta()
}

async function confirmDeleteGroup(group) {
  try {
    await confirmDestructiveAction(`确认删除群组“${group?.name || ''}”吗？当前群组下共享的草稿将恢复为个人草稿。`, '删除群组')
  } catch {
    return
  }
  const payload = await apiDelete(`/groups/${group.id}`, { token: authStore.token })
  if (!payload?.success) {
    ElMessage.error(payload?.message || '群组删除失败')
    return
  }
  ElMessage.success(payload.message || '群组已删除')
  await Promise.all([loadMeta(), loadDashboard(), loadOrders()])
}

async function saveWorkOrderSettings() {
  workOrderSettingsSaving.value = true
  const payload = await apiPut('/work-orders/settings', {
    settings: workOrderSettings.value.map((item) => ({
      orderType: item.orderType,
      approverId: item.approverId || null,
    })),
  }, { token: authStore.token })
  workOrderSettingsSaving.value = false
  if (!payload?.success) {
    ElMessage.error(payload?.message || '工单设置保存失败')
    return
  }
  ElMessage.success(payload.message || '工单设置已保存')
  await Promise.all([loadMeta(), loadWorkOrderSettings()])
}

function validateStepOne() {
  if (!cleanReasonText(effectiveReason.value)) {
    ElMessage.warning('请确认工单事由')
    return false
  }
  if (!String(form.formDate || '').trim()) {
    ElMessage.warning('请选择工单日期')
    return false
  }
  if (showSourceSelector.value && !form.sourceShopId) {
    ElMessage.warning(`请选择${sourceLabel.value}`)
    return false
  }
  if (showTargetSelector.value && !form.targetShopId) {
    ElMessage.warning(`请选择${targetLabel.value}`)
    return false
  }
  if (form.orderType === 'purchase' && !String(form.supplierName || '').trim()) {
    ElMessage.warning('请填写供货单位')
    return false
  }
  if (form.orderType === 'return' && !String(form.partnerName || '').trim()) {
    ElMessage.warning('请填写收货单位')
    return false
  }
  if (!form.approverId) {
    ElMessage.warning('请选择负责人')
    return false
  }
  return true
}

function goToEditorStep(nextStep) {
  if (Number(nextStep || 1) > 1 && !validateStepOne()) {
    return
  }
  editorStep.value = Math.min(Math.max(Number(nextStep || 1), 1), editorStepOptions.length)
}

function nextEditorStep() {
  if (editorStep.value === 1 && !validateStepOne()) {
    return
  }
  goToEditorStep(editorStep.value + 1)
}

function prevEditorStep() {
  goToEditorStep(editorStep.value - 1)
}

async function openAllocationDialog(orderId) {
  if (!canWrite.value) {
    ElMessage.warning('当前账号没有分配工单权限')
    return
  }
  allocationLoading.value = true
  const payload = await apiGet(`/work-orders/${orderId}/allocation-draft`, {
    token: authStore.token,
  })
  allocationLoading.value = false
  if (!payload?.success || !payload?.draft) {
    ElMessage.error(payload?.message || '分配信息获取失败')
    return
  }
  applyAllocationResponse(payload)
  allocationStep.value = 1
  allocationVisible.value = true
}

async function persistAllocationDraft(successMessage = '分配草稿已保存') {
  if (!allocationForm.orderId) {
    ElMessage.warning('当前分配工单不存在')
    return null
  }
  if (!allocationForm.approverId) {
    ElMessage.warning('请选择负责人')
    return null
  }
  if (!allocationForm.targetShopIds.length) {
    ElMessage.warning('请至少选择一个分配店铺/仓库')
    return null
  }
  persistStoredAllocationTargets(allocationForm.targetShopIds)
  allocationSaving.value = true
  const payload = await apiPut(
    `/work-orders/${allocationForm.orderId}/allocation-draft`,
    buildAllocationPayload(),
    { token: authStore.token },
  )
  allocationSaving.value = false
  if (!payload?.success || !payload?.draft) {
    ElMessage.error(payload?.message || '分配草稿保存失败')
    return null
  }
  applyAllocationResponse(payload)
  ElMessage.success(payload.message || successMessage)
  return payload
}

async function enterAllocationEdit() {
  const payload = await persistAllocationDraft('分配设置已保存')
  if (!payload) {
    return
  }
  allocationStep.value = 2
}

async function saveAllocationDraft() {
  const warnings = allocationWarningLines.value
  if (warnings.length) {
    try {
      await confirmAction(
        `当前分配存在以下待确认项：\n${warnings.slice(0, 6).join('\n')}${warnings.length > 6 ? `\n另有 ${warnings.length - 6} 项未展开。` : ''}\n\n确认仍要保存吗？`,
        '分配保存确认',
        '继续保存',
      )
    } catch {
      return
    }
  }
  await persistAllocationDraft()
}

async function confirmAllocationDraft() {
  const createdCount = confirmableAllocationTargetCount()
  if (!createdCount) {
    ElMessage.warning('请至少为一个店铺/仓库填写分配数量')
    return
  }
  const warnings = allocationWarningLines.value
  const warningText = warnings.length
    ? `\n\n当前仍有以下待确认项：\n${warnings.slice(0, 6).join('\n')}${warnings.length > 6 ? `\n另有 ${warnings.length - 6} 项未展开。` : ''}`
    : ''
  try {
    await confirmAction(
      `确认生成 ${createdCount} 张商品调拨单草稿吗？${warningText}`,
      '确认分配',
      '确认生成',
    )
  } catch {
    return
  }
  allocationConfirming.value = true
  const payload = await apiPost(
    `/work-orders/${allocationForm.orderId}/allocation-draft/confirm`,
    buildAllocationPayload(),
    { token: authStore.token },
  )
  allocationConfirming.value = false
  if (!payload?.success) {
    ElMessage.error(payload?.message || '分配确认失败')
    return
  }
  ElMessage.success(payload.message || '商品调拨单草稿已生成')
  allocationVisible.value = false
  resetAllocationState()
  await Promise.all([loadDashboard(), loadOrders()])
}

async function requestCloseAllocation(done) {
  if (!allocationVisible.value) {
    done?.()
    return
  }
  const message = hasAllocationUnsavedChanges.value
    ? '当前分配内容尚未保存，确认退出吗？'
    : '确认退出当前分配窗口吗？'
  try {
    await confirmAction(message, '退出确认', '确认退出')
  } catch {
    return
  }
  allocationVisible.value = false
  resetAllocationState()
  done?.()
}

function handleAllocationDialogBeforeClose(done) {
  void requestCloseAllocation(done)
}

async function openEditDialog(orderId) {
  if (!canWrite.value) {
    ElMessage.warning('当前账号没有编辑工单权限')
    return
  }
  detailVisible.value = false
  detailLoading.value = true
  const payload = await apiGet(`/work-orders/${orderId}`, {
    token: authStore.token,
  })
  detailLoading.value = false
  if (!payload?.success || !payload.order) {
    ElMessage.error(payload?.message || '工单详情获取失败')
    return
  }
  applyOrderToForm(payload.order)
  editorVisible.value = true
  captureEditorSnapshot()
}

async function openDetail(orderId, focusReview = false) {
  detailLoading.value = true
  detailVisible.value = true
  detailItemsPage.value = 1
  detailItemsPageSize.value = 20
  detailSortState.prop = ''
  detailSortState.order = ''
  reviewComment.value = ''
  const payload = await apiGet(`/work-orders/${orderId}`, {
    token: authStore.token,
  })
  detailLoading.value = false
  if (!payload?.success || !payload.order) {
    detailVisible.value = false
    ElMessage.error(payload?.message || '工单详情获取失败')
    return
  }
  detailOrder.value = normalizePersistedOrderDetail(payload.order)
  normalizeDetailItemsPage()
  if (focusReview && payload.order.canReview) {
    reviewComment.value = payload.order.approvalComment || ''
  }
}

async function requestCloseEditor(done) {
  if (!editorVisible.value) {
    done?.()
    return
  }
  if (hasEditorUnsavedChanges.value) {
    try {
      await confirmAction('当前工单有未保存的修改，确认关闭吗？', '关闭确认', '确认关闭')
    } catch {
      return
    }
  }
  editorVisible.value = false
  done?.()
}

function handleEditorDialogBeforeClose(done) {
  void requestCloseEditor(done)
}

function handleWindowBeforeUnload(event) {
  if (!editorVisible.value && !allocationVisible.value) {
    return
  }
  if (!hasEditorUnsavedChanges.value && !hasAllocationUnsavedChanges.value) {
    return
  }
  event.preventDefault()
  event.returnValue = ''
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

async function applyWorkOrderSpotlightFromRoute() {
  const orderId = Number(route.query.spotlight_work_order || 0)
  if (!orderId) {
    return
  }
  await openDetail(orderId)
  await consumeSpotlightQuery(['spotlight_work_order'])
}

function normalizeScopeQueryValue(value) {
  const clean = String(value || '').trim()
  return scopeOptions.value.some((item) => item.value === clean) ? clean : ''
}

function normalizeRouteKeywordValue(value) {
  return String(value || '').trim()
}

function normalizeTypeQueryValue(value) {
  const clean = String(value || '').trim()
  return meta.types.some((item) => item.value === clean) ? clean : defaultTypeForCategory('goods')
}

function normalizeComposeShopId(value, options) {
  const normalized = Number(value || 0) || null
  if (!normalized) {
    return null
  }
  return options.some((item) => Number(item.id || 0) === normalized) ? normalized : null
}

function normalizeComposeGoodsId(value) {
  const normalized = Number(value || 0) || null
  return normalized && normalized > 0 ? normalized : null
}

async function applyComposePrefillFromRoute(composeType) {
  if (composeType !== 'transfer') {
    return
  }
  const sourceShopId = normalizeComposeShopId(route.query.prefill_source_shop_id, sourceOptions.value)
  const requestedTargetShopId = normalizeComposeShopId(route.query.prefill_target_shop_id, targetOptions.value)
  const fallbackTargetShopId = normalizeComposeShopId(authStore.shopId, targetOptions.value)
  const targetShopId = requestedTargetShopId || (
    fallbackTargetShopId && fallbackTargetShopId !== sourceShopId
      ? fallbackTargetShopId
      : null
  )
  const goodsId = normalizeComposeGoodsId(route.query.prefill_goods_id)

  if (sourceShopId) {
    form.sourceShopId = sourceShopId
  }
  form.targetShopId = targetShopId

  if (!goodsId) {
    return
  }

  const payload = await apiGet(`/goods/items/${goodsId}`, {
    token: authStore.token,
  })
  if (!payload?.success || !payload.item) {
    ElMessage.warning(payload?.message || '预填商品加载失败，请在工单中手动选择商品')
    return
  }
  const goods = await enrichGoodsWithStocks(payload.item)
  form.items = [createRow()]
  fillRowFromGoods(form.items[0], goods)
  await refreshSelectedItemStocks()
  editorItemsPage.value = 1
  normalizeEditorItemsPage()
}

async function applyWorkOrderStateFromRoute() {
  const nextScope = normalizeScopeQueryValue(route.query.scope)
  const nextKeyword = normalizeRouteKeywordValue(route.query.keyword)
  const shouldCompose = String(route.query.compose || '').trim() === '1'
  const composeType = normalizeTypeQueryValue(route.query.type)
  const hasComposePrefill = Boolean(
    route.query.prefill_source_shop_id
    || route.query.prefill_target_shop_id
    || route.query.prefill_goods_id,
  )

  if (nextScope && nextScope !== scope.value) {
    scope.value = nextScope
    page.value = 1
    logPage.value = 1
    if (statusFilterLocked.value) {
      statusFilter.value = ''
    }
  }

  if (nextKeyword !== keyword.value) {
    keyword.value = nextKeyword
    page.value = 1
  }

  if (shouldCompose) {
    const nextCategory = resolveOrderCategory(composeType)
    openCreateDialogByCategory(nextCategory)
    changeOrderType(composeType)
    await applyComposePrefillFromRoute(composeType)
    captureEditorSnapshot()
  }

  if (nextScope || nextKeyword || shouldCompose || hasComposePrefill) {
    await consumeSpotlightQuery(['scope', 'keyword', 'compose', 'type', 'prefill_source_shop_id', 'prefill_target_shop_id', 'prefill_goods_id'])
  }
}

async function saveEditor(statusValue) {
  if (!canWrite.value) {
    ElMessage.warning('当前账号没有保存工单权限')
    return
  }
  if (statusValue === 'draft') {
    await maybeRemoveBlankRowsBeforeDraftSave()
  }
  const itemsForSave = isSaleExchangeType.value
    ? [...form.exchangeIncomingItems, ...form.exchangeOutgoingItems]
    : form.items
  const pendingPurchaseGoodsRows = form.orderType === 'purchase'
    ? getPendingPurchaseGoodsRows(itemsForSave)
    : []
  if (statusValue === 'pending') {
    const unmatchedIndex = itemsForSave.findIndex((item) => !Number(item.goodsId || 0) && form.orderType !== 'purchase')
    if (unmatchedIndex >= 0) {
      ElMessage.warning(`第 ${unmatchedIndex + 1} 行商品尚未匹配到已有商品，不能提交审批`)
      return
    }
    const salesValidationMessage = validatePendingSalesItems()
    if (salesValidationMessage) {
      ElMessage.warning(salesValidationMessage)
      return
    }
  }
  if (statusValue === 'pending' && !(await confirmPurchaseGoodsCreation(pendingPurchaseGoodsRows))) {
    return
  }
  if (!(await confirmInventoryWarningsBeforeProceed(statusValue))) {
    return
  }
  persistCurrentEditorSortOrder()
  const payload = buildPayload(statusValue)
  if (statusValue === 'draft') {
    savingDraft.value = true
  } else {
    submitting.value = true
  }
  const result = form.id
    ? await apiPut(`/work-orders/${form.id}`, payload, { token: authStore.token })
    : await apiPost('/work-orders', payload, { token: authStore.token })
  if (statusValue === 'draft') {
    savingDraft.value = false
  } else {
    submitting.value = false
  }
  if (!result?.success || !result.order) {
    ElMessage.error(result?.message || '工单保存失败')
    return
  }
  ElMessage.success(result.message || '工单已保存')
  captureEditorSnapshot()
  editorVisible.value = false
  detailOrder.value = normalizePersistedOrderDetail(result.order)
  detailItemsPage.value = 1
  detailSortState.prop = ''
  detailSortState.order = ''
  normalizeDetailItemsPage()
  await Promise.all([loadDashboard(), loadOrders()])
}

async function submitDetailOrderForReview() {
  if (!detailOrder.value || !canWrite.value) {
    ElMessage.warning('当前工单无法提交审批')
    return
  }
  const order = detailOrder.value
  const itemsForSave = Array.isArray(order.items) ? order.items : []
  const pendingPurchaseGoodsRows = String(order.orderType || '') === 'purchase'
    ? getPendingPurchaseGoodsRows(itemsForSave)
    : []
  if (String(order.orderType || '') !== 'purchase') {
    const unmatchedIndex = itemsForSave.findIndex((item) => !Number(item.goodsId || 0))
    if (unmatchedIndex >= 0) {
      ElMessage.warning(`第 ${unmatchedIndex + 1} 行商品尚未匹配到已有商品，不能提交审批`)
      return
    }
  }
  const salesValidationMessage = validatePendingSalesItemsForRows(
    resolveOrderSalesValidationRows(order),
    orderRequiresBoundSalesRecord(order),
  )
  if (salesValidationMessage) {
    ElMessage.warning(salesValidationMessage)
    return
  }
  if (!(await confirmPurchaseGoodsCreation(pendingPurchaseGoodsRows))) {
    return
  }
  if (!(await confirmInventoryWarningsBeforeProceed('pending', itemsForSave, order.orderType))) {
    return
  }
  submittingDetailReview.value = true
  const payload = buildPayloadFromOrder(order, 'pending')
  const result = await apiPut(`/work-orders/${order.id}`, payload, { token: authStore.token })
  submittingDetailReview.value = false
  if (!result?.success || !result.order) {
    ElMessage.error(result?.message || '工单提交审批失败')
    return
  }
  detailOrder.value = normalizePersistedOrderDetail(result.order)
  detailItemsPage.value = 1
  detailSortState.prop = ''
  detailSortState.order = ''
  normalizeDetailItemsPage()
  ElMessage.success(result.message || '工单已提交审批')
  await Promise.all([loadDashboard(), loadOrders()])
}

async function confirmWithdrawOrder(row) {
  try {
    await confirmDestructiveAction('确认将这张待审批工单转回草稿箱吗？当前审批流程会被撤销。', '转草稿')
  } catch {
    return
  }
  const result = await apiPost(`/work-orders/${row.id}/withdraw`, {}, { token: authStore.token })
  if (!result?.success || !result.order) {
    ElMessage.error(result?.message || '工单转草稿失败')
    return
  }
  if (detailOrder.value && Number(detailOrder.value.id) === Number(row.id)) {
    detailOrder.value = normalizePersistedOrderDetail(result.order)
    detailItemsPage.value = 1
    normalizeDetailItemsPage()
  }
  ElMessage.success(result.message || '工单已转回草稿箱')
  await Promise.all([loadDashboard(), loadOrders()])
}

async function confirmDeleteOrder(row) {
  const message = row.status === 'pending'
    ? '确认删除这张待审批工单吗？删除后会撤销当前审批流程，且无法恢复。'
    : '确认删除这张草稿工单吗？删除后无法恢复。'
  try {
    await confirmDestructiveAction(message, '删除工单')
  } catch {
    return
  }
  const result = await apiDelete(`/work-orders/${row.id}`, { token: authStore.token })
  if (!result?.success) {
    ElMessage.error(result?.message || '工单删除失败')
    return
  }
  if (detailOrder.value && Number(detailOrder.value.id) === Number(row.id)) {
    detailVisible.value = false
    detailOrder.value = null
  }
  ElMessage.success(result.message || '工单已删除')
  await Promise.all([loadDashboard(), loadOrders()])
}

async function reviewCurrent(approved) {
  if (!detailOrder.value) {
    return
  }
  if (approved && detailOrder.value.orderType === 'purchase') {
    const pendingRows = getPendingPurchaseGoodsRows(detailOrder.value.items || [])
    if (!(await confirmPurchaseGoodsCreation(pendingRows))) {
      return
    }
  }
  if (approved && !(
    await confirmInventoryWarningsBeforeProceed(
      'approved',
      detailOrder.value.items || [],
      detailOrder.value.orderType,
      Boolean(detailOrder.value.saleAffectsInventory),
    )
  )) {
    return
  }
  reviewing.value = true
  const payload = await apiPost(
    `/work-orders/${detailOrder.value.id}/review`,
    {
      approved,
      comment: reviewComment.value || '',
    },
    { token: authStore.token },
  )
  reviewing.value = false
  if (!payload?.success || !payload.order) {
    ElMessage.error(payload?.message || '工单审批失败')
    return
  }
  detailOrder.value = normalizePersistedOrderDetail(payload.order)
  detailItemsPage.value = 1
  normalizeDetailItemsPage()
  ElMessage.success(payload.message || '工单已更新')
  await Promise.all([loadDashboard(), loadOrders()])
}

function openGoodsPicker(rowKey) {
  currentGoodsPickerRowKey.value = rowKey
  goodsPickerVisible.value = true
}

async function handleGoodsPicked(goods) {
  const row = findAnyEditorRow(currentGoodsPickerRowKey.value)
  if (!row) {
    return
  }
  fillRowFromGoods(row, await enrichGoodsWithStocks({
    ...goods,
    sourceStock: Number(goods.shopQuantity ?? goods.sourceStock ?? 0),
    targetStock: Number(goods.secondaryShopQuantity ?? goods.targetStock ?? goods.shopQuantity ?? 0),
  }))
  if (isSaleAffectingInventory.value) {
    row.saleShopId = row.saleShopId || Number(form.sourceShopId || 0) || null
    row.saleShopName = row.saleShopName || sourceDisplayName.value || ''
    row.receiveShopId = row.receiveShopId || row.saleShopId || Number(form.sourceShopId || 0) || null
    row.receiveShopName = row.receiveShopName || row.saleShopName || sourceDisplayName.value || ''
    row.shipShopId = row.shipShopId || Number(saleShipShopId.value || form.sourceShopId || 0) || null
    row.shipShopName = row.shipShopName || saleShipDisplayName.value || sourceDisplayName.value || ''
    row.channel = row.channel || '门店'
  }
  advanceToNextEditorRow(row, 'goodsName', { deferFocus: true })
}

function openSalesPicker(rowKey) {
  if (!Number(form.sourceShopId || 0)) {
    ElMessage.warning('请先选择销售店铺，再选择销售记录')
    return
  }
  currentSalesPickerRowKey.value = rowKey
  salesPickerVisible.value = true
}

function handleSalesPicked(record) {
  const row = findAnyEditorRow(currentSalesPickerRowKey.value)
  if (!row) {
    return
  }
  fillRowFromSaleRecord(row, record)
  if (isSaleExchangeType.value) {
    form.exchangeOutgoingItems.forEach((item) => {
      if (!String(item.salesperson || '').trim()) {
        item.salesperson = row.salesperson || applicantName.value || ''
      }
      ensureRowSalespersonByShop(item)
    })
  }
  advanceToNextEditorRow(row, 'orderNum', { deferFocus: true })
}

function removeSingleBlankRowIfPresent() {
  const rows = editorRowsForTarget(currentBatchTarget.value)
  if (
    rows.length === 1 &&
    !Number(rows[0].goodsId || 0) &&
    !String(rows[0].goodsName || '').trim() &&
    !String(rows[0].orderNum || '').trim()
  ) {
    rows.splice(0, 1)
  }
}

async function handleBatchGoodsConfirm(selectedRows) {
  const rows = Array.isArray(selectedRows) ? selectedRows : []
  if (!rows.length) {
    return
  }
  removeSingleBlankRowIfPresent()
  const enriched = await Promise.all(rows.map((item) => enrichGoodsWithStocks(item)))
  const targetRows = editorRowsForTarget(currentBatchTarget.value)
  enriched.forEach((item) => {
    targetRows.push(createRow({
      lineType: currentBatchTarget.value === 'default' ? 'default' : currentBatchTarget.value,
      quantity: Math.max(Number(item.quantity || 1), 1),
      sourceStock: Number(item.sourceStock ?? item.shopQuantity ?? 0),
      targetStock: Number(item.secondaryShopQuantity ?? item.targetStock ?? item.shopQuantity ?? 0),
      goodsId: item.id || null,
      goodsName: item.model || item.name || '',
      productCode: item.productCode || '',
      brand: item.brand || '',
      series: item.series || '',
      barcode: item.barcode || '',
      unitPrice: Number(item.price || 0),
      saleShopId: (isSaleExchangeType.value || isSaleAffectingInventory.value) ? Number(form.sourceShopId || 0) || null : null,
      saleShopName: (isSaleExchangeType.value || isSaleAffectingInventory.value) ? sourceDisplayName.value : '',
      shipShopId: (isSaleExchangeType.value || isSaleAffectingInventory.value) ? Number(saleShipShopId.value || form.sourceShopId || 0) || null : null,
      shipShopName: (isSaleExchangeType.value || isSaleAffectingInventory.value) ? (saleShipDisplayName.value || sourceDisplayName.value) : '',
      salesperson: (isSaleExchangeType.value || isSaleAffectingInventory.value)
        ? String(form.exchangeIncomingItems[0]?.salesperson || applicantName.value || '')
        : applicantName.value,
      channel: (isSaleExchangeType.value || isSaleAffectingInventory.value) ? '门店' : '',
    }))
  })
  mergeDuplicateGoodsRowsInTarget(currentBatchTarget.value)
  targetRows.forEach((row) => syncRowAmount(row))
  editorItemsPage.value = 1
  normalizeEditorItemsPage()
}

function handleBatchSalesConfirm(selectedRows) {
  const rows = Array.isArray(selectedRows) ? selectedRows : []
  if (!rows.length) {
    return
  }
  removeSingleBlankRowIfPresent()
  const targetRows = editorRowsForTarget(currentBatchTarget.value)
  rows.forEach((record) => {
    const row = createRow({ lineType: currentBatchTarget.value === 'default' ? 'default' : currentBatchTarget.value })
    fillRowFromSaleRecord(row, record, Math.max(Number(record.quantity || 1), 1))
    targetRows.push(row)
  })
  editorItemsPage.value = 1
  normalizeEditorItemsPage()
}

function openBatchEntryDialog(target = 'default') {
  currentBatchTarget.value = target
  if (usesSalesRecordBinding.value && target !== 'outgoing') {
    if (!Number(form.sourceShopId || 0)) {
      ElMessage.warning('请先选择销售店铺，再批量录入订单')
      return
    }
    salesBatchVisible.value = true
    return
  }
  goodsBatchVisible.value = true
}

async function printById(orderId) {
  detailLoading.value = true
  const payload = await apiGet(`/work-orders/${orderId}`, {
    token: authStore.token,
  })
  detailLoading.value = false
  if (!payload?.success || !payload.order) {
    ElMessage.error(payload?.message || '工单详情获取失败')
    return
  }
  await printOrder(payload.order)
}

function waitForPrintAssets(frameDocument) {
  const images = Array.from(frameDocument.images || [])
  if (!images.length) {
    return Promise.resolve()
  }
  return Promise.all(
    images.map((image) => {
      if (image.complete) {
        return Promise.resolve()
      }
      return new Promise((resolve) => {
        image.addEventListener('load', resolve, { once: true })
        image.addEventListener('error', resolve, { once: true })
      })
    }),
  )
}

function padPrintNumber(value) {
  return String(value).padStart(2, '0')
}

function formatPrintDateOnly(value) {
  const clean = String(value || '').trim().replace('T', ' ')
  if (!clean) {
    return ''
  }
  return clean.slice(0, 10)
}

function formatPrintTimestamp() {
  return getShanghaiTimestamp()
}

function buildPrintMetaItems(order) {
  const formDate = formatPrintDateOnly(order.formDate) || '-'
  const orderNum = order.orderNum || '-'
  const reason = order.reason || '-'
  const items = [
    { label: '日期', value: formDate },
    { label: '工单编号', value: orderNum },
  ]

  if (order.orderType === 'purchase') {
    items.push(
      { label: '收货仓库/店铺', value: displayShopName(order.targetShopName) || '-' },
      { label: '供货单位', value: displayShopName(order.supplierName) || '-' },
    )
  } else if (order.orderType === 'sale' || order.orderType === 'sale_return' || order.orderType === 'sale_exchange') {
    items.push(
      { label: '销售店铺', value: displayShopName(order.sourceShopName) || '-' },
    )
  } else if (order.orderType === 'return') {
    items.push(
      { label: '发货仓库/店铺', value: displayShopName(order.sourceShopName) || '-' },
      { label: '收货单位', value: displayShopName(order.partnerName) || '-' },
    )
  } else if (order.orderType === 'damage') {
    items.push(
      { label: '发货仓库/店铺', value: displayShopName(order.sourceShopName) || '-' },
    )
  } else {
    items.push(
      { label: '发货仓库/店铺', value: displayShopName(order.sourceShopName) || '-' },
      { label: '收货仓库/店铺', value: displayShopName(order.targetShopName) || '-' },
    )
  }

  items.push(
    { label: '事由', value: replaceShopNameAliases(reason) },
    { label: '页数', rawHtml: '<span class="print-page-counter">1 / 1</span>' },
  )
  return items
}

function buildPrintMetaHtml(order) {
  return buildPrintMetaItems(order)
    .map((item) => `
      <div class="print-meta-item">
        <span class="print-meta-label">${escapeHtml(item.label)}：</span>
        <span class="print-meta-value">${item.rawHtml || escapeHtml(item.value)}</span>
      </div>
    `)
    .join('')
}

function resolvePrintGoodsName(item) {
  const cleanGoodsName = String(item?.goodsName || '').trim()
  if (cleanGoodsName) {
    return cleanGoodsName
  }
  const fallback = [item?.brand, item?.series, item?.barcode]
    .map((value) => String(value || '').trim())
    .filter(Boolean)
    .join(' ')
  return fallback || '-'
}

function resolvePrintableItems(order) {
  const sourceItems = Array.isArray(order?.items) ? order.items : []
  if (detailOrder.value && Number(detailOrder.value.id || 0) === Number(order?.id || 0)) {
    return sortedDetailItems.value
  }
  return sourceItems
}

function buildPrintItemRows(order) {
  const items = resolvePrintableItems(order)
  const isPrintableInventorySale = order.orderType === 'sale' && Boolean(order.saleAffectsInventory)
  if (!items.length) {
    return `
      <tr>
        <td colspan="${isPrintableInventorySale ? 14 : (order.orderType === 'sale' || order.orderType === 'sale_return' || order.orderType === 'sale_exchange' ? 11 : 7)}" class="print-center">暂无明细</td>
      </tr>
    `
  }
  if (isPrintableInventorySale) {
    return items.map((item, index) => `
      <tr>
        <td class="print-center">${index + 1}</td>
        <td>${escapeHtml(resolvePrintGoodsName(item))}</td>
        <td class="print-center">${escapeHtml(String(item.quantity || 0))}</td>
        <td class="print-right">${escapeHtml(formatMoney(item.unitPrice))}</td>
        <td class="print-right">${escapeHtml(formatMoney(item.totalAmount))}</td>
        <td class="print-right">${escapeHtml(formatMoney(item.receivedAmount))}</td>
        <td class="print-right">${escapeHtml(formatMoney(item.couponAmount))}</td>
        <td class="print-center">${escapeHtml(formatMoney(item.discountRate))}</td>
        <td>${escapeHtml(item.channel || '-')}</td>
        <td>${escapeHtml(item.saleShopName || '-')}</td>
        <td>${escapeHtml(item.shipShopName || '-')}</td>
        <td>${escapeHtml(item.salesperson || '-')}</td>
        <td>${escapeHtml(item.customerName || '')}</td>
        <td>${escapeHtml(item.remark || '')}</td>
      </tr>
    `).join('')
  }
  if (order.orderType === 'sale' || order.orderType === 'sale_return' || order.orderType === 'sale_exchange') {
    return items.map((item, index) => `
      <tr>
        <td class="print-center">${index + 1}</td>
        <td>${escapeHtml(item.orderNum || '-')}</td>
        <td>${escapeHtml(item.salesperson || '-')}</td>
        <td>${escapeHtml(item.saleShopName || '-')}</td>
        <td class="print-right">${escapeHtml(formatMoney(item.receivedAmount))}</td>
        <td>${escapeHtml(resolvePrintGoodsName(item))}</td>
        <td class="print-right">${escapeHtml(formatMoney(item.unitPrice))}</td>
        <td class="print-center">${escapeHtml(String(item.quantity || 0))}</td>
        <td class="print-center">只</td>
        <td class="print-right">${escapeHtml(formatMoney(item.totalAmount))}</td>
        <td>${escapeHtml(item.remark || '')}</td>
      </tr>
    `).join('')
  }
  return items.map((item, index) => `
    <tr>
      <td class="print-center">${index + 1}</td>
      <td>${escapeHtml(resolvePrintGoodsName(item))}</td>
      <td class="print-center">${escapeHtml(String(item.quantity || 0))}</td>
      <td class="print-center">只</td>
      <td class="print-right">${escapeHtml(formatMoney(item.unitPrice))}</td>
      <td class="print-right">${escapeHtml(formatMoney(item.totalAmount))}</td>
      <td>${escapeHtml(item.remark || '')}</td>
    </tr>
  `).join('')
}

function buildPrintFooterMeta(order) {
  return `
    <div class="print-footer-meta">
      <div>申请人：${escapeHtml(order.applicantName || '-')}</div>
      <div>负责人：${escapeHtml(order.approverName || '-')}</div>
      <div>打印日期：${escapeHtml(formatPrintTimestamp())}</div>
    </div>
  `
}

async function printOrder(order) {
  const isPrintableInventorySale = order.orderType === 'sale' && Boolean(order.saleAffectsInventory)
  const metaHtml = buildPrintMetaHtml(order)
  const itemRows = buildPrintItemRows(order)
  const totalQuantityValue = Number(order.totalQuantity || 0)
  const totalAmountValue = formatMoney(order.totalAmount)
  const totalReceivedValue = formatMoney((order.items || []).reduce((sum, item) => sum + Number(item.receivedAmount || 0), 0))
  const titleLabel = escapeHtml(order.orderTypeLabel || findTypeLabel(order.orderType))
  const footerMeta = buildPrintFooterMeta(order)

  const html = `
    <!doctype html>
    <html lang="zh-CN">
      <head>
        <meta charset="UTF-8" />
        <title></title>
        <base href="${window.location.origin}/" />
        <style>
          @page {
            size: A4 portrait;
            margin: 10mm 8mm 12mm;
          }
          html,
          body {
            margin: 0;
            color: #000;
            font-family: "Noto Serif SC", "Songti SC", "STSong", "SimSun", serif;
            font-size: 13px;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
          }
          .print-sheet {
            width: 100%;
          }
          .print-header {
            display: grid;
            grid-template-columns: 72px 1fr 72px;
            align-items: center;
            margin-bottom: 4mm;
          }
          .print-logo {
            width: 72px;
          }
          .print-logo img {
            width: 54px;
            height: 54px;
            object-fit: contain;
            display: block;
          }
          .print-title-cell {
            text-align: center;
            font-size: 29px;
            font-weight: 700;
            letter-spacing: 0.12em;
          }
          .print-meta-list {
            display: flex;
            flex-wrap: wrap;
            gap: 6px 20px;
            margin-bottom: 6mm;
          }
          .print-meta-item {
            display: flex;
            align-items: flex-start;
            gap: 6px;
            width: calc((100% - 20px) / 2);
            min-height: 24px;
            line-height: 1.7;
            font-size: 15px;
          }
          .print-meta-label {
            white-space: nowrap;
            font-weight: 700;
          }
          .print-meta-value {
            flex: 1;
          }
          .print-page-counter {
            white-space: nowrap;
          }
          .print-form {
            width: 100%;
            border-collapse: collapse;
            table-layout: fixed;
          }
          .print-form thead {
            display: table-header-group;
          }
          .print-form th,
          .print-form td {
            border: 1px solid #111;
            padding: 8px 9px;
            vertical-align: middle;
            color: #000;
            word-break: break-all;
            font-size: 17px;
          }
          .print-head-row th {
            text-align: center;
            font-weight: 700;
            font-size: 18px;
            padding: 8px 5px;
          }
          .print-summary-row td {
            font-weight: 700;
            font-size: 17px;
          }
          .print-center {
            text-align: center;
          }
          .print-right {
            text-align: right;
          }
          .print-footer-meta {
            margin-top: 8mm;
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 12px;
            font-size: 15px;
            line-height: 1.7;
          }
          .print-footer-meta > div:nth-child(2) {
            text-align: center;
          }
          .print-footer-meta > div:last-child {
            text-align: right;
          }
        </style>
      </head>
      <body>
        <div class="print-sheet">
          <div class="print-header">
            <div class="print-logo">
              <img src="${window.location.origin}/aqc-logo.svg" alt="AQC" />
            </div>
            <div class="print-title-cell">${titleLabel}</div>
            <div></div>
          </div>
          <div class="print-meta-list">
            ${metaHtml}
          </div>
          <table class="print-form">
            ${
              isPrintableInventorySale
                ? `
            <colgroup>
              <col style="width: 6%" />
              <col style="width: 17%" />
              <col style="width: 6%" />
              <col style="width: 8%" />
              <col style="width: 9%" />
              <col style="width: 9%" />
              <col style="width: 8%" />
              <col style="width: 6%" />
              <col style="width: 7%" />
              <col style="width: 11%" />
              <col style="width: 11%" />
              <col style="width: 8%" />
              <col style="width: 10%" />
              <col style="width: 10%" />
            </colgroup>
                `
                : order.orderType === 'sale' || order.orderType === 'sale_return' || order.orderType === 'sale_exchange'
                ? `
            <colgroup>
              <col style="width: 6%" />
              <col style="width: 13%" />
              <col style="width: 10%" />
              <col style="width: 14%" />
              <col style="width: 10%" />
              <col style="width: 18%" />
              <col style="width: 9%" />
              <col style="width: 7%" />
              <col style="width: 7%" />
              <col style="width: 10%" />
              <col style="width: 6%" />
              <col style="width: 10%" />
            </colgroup>
                `
                : `
            <colgroup>
              <col style="width: 8%" />
              <col style="width: 36%" />
              <col style="width: 8%" />
              <col style="width: 8%" />
              <col style="width: 12%" />
              <col style="width: 13%" />
              <col style="width: 15%" />
            </colgroup>
                `
            }
            <thead>
              ${
                isPrintableInventorySale
                  ? `
              <tr class="print-head-row">
                <th>序号</th>
                <th>商品名称</th>
                <th>数量</th>
                <th>单价</th>
                <th>应付金额</th>
                <th>实付金额</th>
                <th>优惠券</th>
                <th>折扣</th>
                <th>渠道</th>
                <th>销售店铺</th>
                <th>发货店铺/仓库</th>
                <th>销售员</th>
                <th>客户姓名</th>
                <th>备注</th>
              </tr>
                  `
                  : order.orderType === 'sale' || order.orderType === 'sale_return' || order.orderType === 'sale_exchange'
                  ? `
              <tr class="print-head-row">
                <th>序号</th>
                <th>订单号</th>
                <th>销售员</th>
                <th>销售店铺</th>
                <th>实付金额</th>
                <th>商品名称</th>
                <th>单价</th>
                <th>数量</th>
                <th>单位</th>
                <th>应付金额</th>
                <th>备注</th>
              </tr>
                  `
                  : `
              <tr class="print-head-row">
                <th>序号</th>
                <th>${order.orderType === 'purchase' ? '商品名称' : '商品全名'}</th>
                <th>数量</th>
                <th>单位</th>
                <th>单价</th>
                <th>金额</th>
                <th>备注</th>
              </tr>
                  `
              }
            </thead>
            <tbody>
              ${itemRows}
              ${
                isPrintableInventorySale
                  ? `
              <tr class="print-summary-row">
                <td colspan="2">总计</td>
                <td class="print-center">${escapeHtml(String(totalQuantityValue))}</td>
                <td></td>
                <td class="print-right">¥ ${escapeHtml(totalAmountValue)}</td>
                <td class="print-right">¥ ${escapeHtml(totalReceivedValue)}</td>
                <td colspan="8"></td>
              </tr>
                  `
                  : order.orderType === 'sale' || order.orderType === 'sale_return' || order.orderType === 'sale_exchange'
                  ? `
              <tr class="print-summary-row">
                <td colspan="4">总计</td>
                <td class="print-right">¥ ${escapeHtml(totalReceivedValue)}</td>
                <td></td>
                <td></td>
                <td class="print-center">${escapeHtml(String(totalQuantityValue))}</td>
                <td></td>
                <td class="print-right">¥ ${escapeHtml(totalAmountValue)}</td>
                <td></td>
              </tr>
                  `
                  : `
              <tr class="print-summary-row">
                <td colspan="2">总计</td>
                <td class="print-center">${escapeHtml(String(totalQuantityValue))}</td>
                <td></td>
                <td colspan="2" class="print-right">¥ ${escapeHtml(totalAmountValue)}</td>
                <td></td>
              </tr>
                  `
              }
            </tbody>
          </table>
          ${footerMeta}
        </div>
      </body>
    </html>
  `

  const frame = document.createElement('iframe')
  frame.setAttribute('aria-hidden', 'true')
  frame.style.position = 'fixed'
  frame.style.right = '0'
  frame.style.bottom = '0'
  frame.style.width = '0'
  frame.style.height = '0'
  frame.style.border = '0'
  frame.style.opacity = '0'
  document.body.appendChild(frame)

  const frameWindow = frame.contentWindow
  const frameDocument = frame.contentDocument || frameWindow?.document
  if (!frameWindow || !frameDocument) {
    frame.remove()
    ElMessage.error('打印初始化失败，请重试')
    return
  }

  const cleanup = () => {
    window.setTimeout(() => {
      frame.remove()
    }, 600)
  }

  frameWindow.addEventListener('afterprint', cleanup, { once: true })
  frameDocument.open()
  frameDocument.write(html)
  frameDocument.close()
  frameDocument.title = ''
  await waitForPrintAssets(frameDocument)
  frameWindow.focus()
  window.setTimeout(() => {
    frameWindow.print()
  }, 180)
  window.setTimeout(cleanup, 60000)
}

watch(
  () => allocationRows.value.length,
  () => {
    const pageCount = allocationItemsPageCount.value
    if (allocationItemsPage.value > pageCount) {
      allocationItemsPage.value = pageCount
    }
  },
)

watch(
  () => allocationItemsPageSize.value,
  () => {
    allocationItemsPage.value = 1
  },
)

watch(
  () => form.sourceShopId,
  (value, previousValue) => {
    if (!isSaleAffectingInventory.value) {
      return
    }
    const currentShipId = Number(saleShipShopId.value || 0) || null
    const previousSourceId = Number(previousValue || 0) || null
    if (!currentShipId || currentShipId === previousSourceId) {
      saleShipShopId.value = Number(value || 0) || null
    }
  },
)

watch(
  () => [form.orderType, form.saleAffectsInventory, form.sourceShopId, form.targetShopId],
  () => {
    if (isSaleExchangeType.value) {
      const currentStoreId = Number(form.sourceShopId || 0) || null
      const currentStoreName = sourceDisplayName.value || ''
      form.exchangeOutgoingItems.forEach((row) => {
        if (!Number(row.saleShopId || 0)) {
          row.saleShopId = currentStoreId
          row.saleShopName = currentStoreName
        }
        if (!Number(row.receiveShopId || 0)) {
          row.receiveShopId = row.saleShopId || currentStoreId
          row.receiveShopName = row.saleShopName || currentStoreName
        }
        if (!Number(row.shipShopId || 0)) {
          row.shipShopId = currentStoreId
          row.shipShopName = currentStoreName
        }
        ensureRowSalespersonByShop(row)
        if (!String(row.channel || '').trim()) {
          row.channel = '门店'
        }
      })
      form.exchangeIncomingItems.forEach((row) => {
        if (!Number(row.receiveShopId || 0)) {
          row.receiveShopId = row.saleShopId || currentStoreId
          row.receiveShopName = row.saleShopName || currentStoreName
        }
        ensureRowSalespersonByShop(row)
      })
    }
    if (isSaleAffectingInventory.value) {
      const currentStoreId = Number(form.sourceShopId || 0) || null
      const currentStoreName = sourceDisplayName.value || ''
      const currentShipId = Number(saleShipShopId.value || form.sourceShopId || 0) || null
      const currentShipName = saleShipDisplayName.value || currentStoreName
      form.items.forEach((row) => {
        if (!Number(row.saleShopId || 0)) {
          row.saleShopId = currentStoreId
          row.saleShopName = currentStoreName
        }
        if (!Number(row.receiveShopId || 0)) {
          row.receiveShopId = row.saleShopId || currentStoreId
          row.receiveShopName = row.saleShopName || currentStoreName
        }
        if (!Number(row.shipShopId || 0)) {
          row.shipShopId = currentShipId
          row.shipShopName = currentShipName
        }
        ensureRowSalespersonByShop(row)
        if (!String(row.channel || '').trim()) {
          row.channel = '门店'
        }
      })
    }
    void refreshSelectedItemStocks()
  },
)

watch(
  () => [editorVisible.value, showQuickAddBar.value],
  ([visible, enabled]) => {
    if (!visible) {
      resetQuickAddBar()
      return
    }
    if (enabled) {
      focusQuickAddField()
    }
  },
)

onMounted(async () => {
  window.addEventListener('beforeunload', handleWindowBeforeUnload)
  await Promise.all([loadMeta(), loadDashboard(), loadGoodsAutocompleteMeta()])
  await applyWorkOrderStateFromRoute()
  await loadOrders()
  ensureAtLeastOneRow()
  await applyWorkOrderSpotlightFromRoute()
})

watch(
  () => route.query.spotlight_work_order,
  (orderId) => {
    if (!orderId) {
      return
    }
    void applyWorkOrderSpotlightFromRoute()
  },
)

watch(
  () => [
    route.query.scope,
    route.query.keyword,
    route.query.compose,
    route.query.type,
    route.query.prefill_source_shop_id,
    route.query.prefill_target_shop_id,
    route.query.prefill_goods_id,
  ],
  async ([scopeValue, keywordValue, composeValue, typeValue, prefillSourceShopId, prefillTargetShopId, prefillGoodsId]) => {
    if (!scopeValue && !keywordValue && !composeValue && !typeValue && !prefillSourceShopId && !prefillTargetShopId && !prefillGoodsId) {
      return
    }
    await applyWorkOrderStateFromRoute()
    await Promise.all([loadOrders(), loadLogs()])
  },
)

onBeforeRouteLeave(async () => {
  if (!editorVisible.value && !allocationVisible.value) {
    return true
  }
  if (!hasEditorUnsavedChanges.value && !hasAllocationUnsavedChanges.value) {
    return true
  }
  const message = hasAllocationUnsavedChanges.value
    ? '当前分配有未保存的修改，确认离开当前页面吗？'
    : '当前工单有未保存的修改，确认离开当前页面吗？'
  try {
    await confirmAction(message, '离开确认', '确认离开')
    return true
  } catch {
    return false
  }
})

onBeforeUnmount(() => {
  clearEditorFocusRetryTimers()
  editorFieldElementRegistry.clear()
  goodsSelectionLocks.clear()
  goodsLookupTokens.clear()
  barcodeLookupTokens.clear()
  salesRecordLookupTokens.clear()
  resolvedBarcodeByRow.clear()
  window.removeEventListener('beforeunload', handleWindowBeforeUnload)
})
</script>
