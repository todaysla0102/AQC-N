<template>
  <section class="sales-records-workbench">
    <section class="catalog-controls card-surface motion-fade-slide sales-record-search-card" style="--motion-delay: 0.08s">
      <div class="goods-search-shell sales-record-search-shell">
        <el-input
          v-model.trim="keyword"
          clearable
          :placeholder="isRepairMode ? '搜索订单号 / 维修点 / 工程师 / 备注' : '搜索订单号 / 系列 / 型号 / 品牌 / 门店 / 销售员'"
          class="goods-search-input sales-record-search-input"
          @keyup.enter="onSearch"
        />

        <div class="toolbar-actions goods-search-actions sales-record-search-actions">
          <el-button @click="toggleRecordMode">{{ isRepairMode ? '返回销售记录' : '维修销售记录' }}</el-button>
          <el-button type="primary" :loading="loading" @click="onSearch">查询</el-button>
          <el-button @click="onResetFilters">重置</el-button>
        </div>
      </div>

      <section class="sales-filter-shell sales-record-filter-shell">
        <div class="sales-filter-trigger-row">
          <button type="button" class="sales-filter-trigger" :class="{ active: filterPanelOpen }" @click="filterPanelOpen = !filterPanelOpen">
            <div class="sales-filter-trigger-copy">
              <span>筛选</span>
              <strong>{{ filterPanelOpen ? '收起筛选面板' : '展开筛选面板' }}</strong>
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
            <section class="sales-filter-panel sales-record-filter-panel">
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

              <div class="sales-filter-hero-grid">
              <div class="sales-filter-field sales-filter-field-emphasis">
                <label class="sales-filter-label">店铺</label>
                <el-select
                  v-model="shopFilter"
                  clearable
                  filterable
                  placeholder="筛选门店"
                  class="full-width"
                  @change="onSearch"
                >
                  <el-option
                    v-for="option in meta.shopOptions"
                    :key="option.value"
                    :label="`${option.label} (${option.count})`"
                    :value="option.value"
                  />
                </el-select>
              </div>

              <div class="sales-filter-field sales-filter-field-emphasis">
                <label class="sales-filter-label">销售员</label>
                <el-select
                  v-model="salespersonFilter"
                  clearable
                  filterable
                  placeholder="筛选销售员"
                  class="full-width"
                  @change="onSearch"
                >
                  <el-option
                    v-for="option in meta.salespersonOptions"
                    :key="option.value"
                    :label="`${option.label} (${option.count})`"
                    :value="option.value"
                  />
                </el-select>
              </div>
            </div>

              <div class="sales-filter-grid">
              <div class="sales-filter-field">
                <label class="sales-filter-label">订单号</label>
                <el-input
                  v-model.trim="orderNumFilter"
                  clearable
                  placeholder="输入订单号"
                  class="full-width"
                  @keyup.enter="onSearch"
                />
              </div>

              <div v-if="!isRepairMode" class="sales-filter-field">
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
                    :label="`${option.label} (${option.count})`"
                    :value="option.value"
                  />
                </el-select>
              </div>

              <div v-if="!isRepairMode" class="sales-filter-field">
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
                    :label="`${option.label} (${option.count})`"
                    :value="option.value"
                  />
                </el-select>
              </div>

              <div class="sales-filter-field sales-filter-field-wide">
                <label class="sales-filter-label">日期范围</label>
                <el-date-picker
                  v-model="dateRange"
                  type="daterange"
                  unlink-panels
                  range-separator="至"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                  value-format="YYYY-MM-DD"
                  class="full-width"
                />
              </div>
            </div>

              <div class="sales-filter-footer">
              <div class="sales-filter-recommend-shell">
                <div class="sales-filter-recommend-head">
                  <div class="sales-filter-recommend-copy">
                    <span class="sales-filter-subtitle">推荐筛选</span>
                    <p class="sales-filter-recommend-caption">前三项会按当前筛选范围内最常用的时间区间自动推荐</p>
                  </div>
                  <span v-if="activeRecommendedPeriod" class="sales-filter-recommend-active">当前：{{ activeRecommendedPeriod.label }}</span>
                </div>
                <div class="sales-filter-recommend-bar">
                  <button
                    v-for="option in meta.recommendedPeriodOptions"
                    :key="option.key"
                    type="button"
                    class="sales-filter-recommend-chip"
                    :class="{
                      active: activeRecommendedPeriod?.key === option.key,
                      'is-recommended': option.recommended,
                    }"
                    @click="setRecommendedPeriod(option)"
                  >
                    <span class="sales-filter-recommend-chip-head">
                      <span class="sales-filter-recommend-chip-title">{{ option.label }}</span>
                      <span v-if="option.recommended" class="sales-filter-recommend-badge">推荐</span>
                    </span>
                    <small class="sales-filter-recommend-chip-count">{{ option.count }} 条</small>
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
              </div>
              </div>
            </section>
          </div>
        </CollapsePanelTransition>
      </section>
    </section>

    <div class="sales-records-overview-grid">
      <SalesSummaryPanel
        ref="summaryPanelRef"
        class="sales-records-summary-panel"
        :panel-tag="isRepairMode ? '维修销售统计' : '销售统计'"
        :display-title="isRepairMode ? '维修销售额' : '销售额'"
        :panel-tag-suffix="summaryFilterLabel"
        :allow-toggle-chart="false"
        :chart-initially-hidden="false"
        :query="summaryQuery"
        :auto-refresh-ms="15000"
      />

      <section class="card-surface sales-calendar-card motion-fade-slide" style="--motion-delay: 0.16s">
        <header class="panel-head sales-calendar-head">
          <div>
            <h2>{{ isRepairMode ? '维修销售日历' : '销售日历' }}</h2>
          </div>
          <div class="sales-summary-head-actions sales-calendar-summary-head">
            <div class="sales-kpi">
              <strong>¥ {{ formatMoney(calendar.totalAmount) }}</strong>
              <span>{{ calendar.activeDays }} 天有销售 · {{ calendar.totalQuantity }} 件商品</span>
            </div>
          </div>
        </header>

        <div class="sales-calendar-nav">
          <el-button circle :disabled="calendarLoading" @click="shiftCalendarMonth(-1)" aria-label="上一月">
            <span class="calendar-nav-arrow">‹</span>
          </el-button>
          <el-popover
            v-model:visible="calendarPickerVisible"
            trigger="click"
            placement="bottom"
            :width="340"
            popper-class="sales-calendar-picker-popper"
            @show="syncCalendarPickerState"
          >
            <template #reference>
              <button type="button" class="sales-calendar-month-trigger">
                <span class="sales-calendar-month-part">{{ calendarDisplayYear }}</span>
                <span class="sales-calendar-month-part">{{ calendarDisplayMonth }}</span>
              </button>
            </template>

            <div class="sales-calendar-picker">
              <div class="sales-calendar-picker-head">
                <span>快速跳转</span>
              </div>
              <el-select v-model="calendarPickerYear" class="full-width sales-calendar-year-select">
                <el-option
                  v-for="year in calendarYearOptions"
                  :key="year"
                  :label="`${year}年`"
                  :value="year"
                />
              </el-select>
              <div class="sales-calendar-picker-months">
                <button
                  v-for="monthOption in calendarMonthOptions"
                  :key="monthOption.value"
                  type="button"
                  class="sales-calendar-picker-month-chip"
                  :class="{ active: monthOption.value === calendarPickerMonth }"
                  @click="jumpCalendarMonth(monthOption.value)"
                >
                  {{ monthOption.label }}
                </button>
              </div>
            </div>
          </el-popover>
          <el-button circle :disabled="calendarLoading" @click="shiftCalendarMonth(1)" aria-label="下一月">
            <span class="calendar-nav-arrow">›</span>
          </el-button>
        </div>

        <transition :name="calendarTransitionName" mode="out-in">
          <div :key="calendarMonth" class="sales-calendar-board" :class="{ 'is-loading': calendarLoading }">
            <div class="sales-calendar-weekdays">
              <span v-for="weekday in weekdayLabels" :key="weekday">{{ weekday }}</span>
            </div>
            <div class="sales-calendar-grid">
              <el-popover
                v-for="day in calendar.days"
                :key="day.date"
                trigger="hover"
                placement="top"
                :width="220"
                popper-class="sales-calendar-popover"
                :show-after="70"
              >
                <div class="sales-calendar-tooltip">
                  <span>{{ formatCalendarTooltipDate(day.date) }}</span>
                  <strong>{{ formatCalendarTooltipAmount(day.amount) }}</strong>
                  <small>销量 {{ day.quantity }} · 客单价 {{ formatCalendarTicketValue(day.averageTicketValue) }}</small>
                </div>
                <template #reference>
                  <article
                    class="sales-calendar-day"
                    :class="{
                      'is-outside': !day.isCurrentMonth,
                      'is-today': day.isToday,
                      'has-sales': day.amount !== 0 || day.quantity !== 0,
                      'has-negative-sales': day.amount < 0,
                    }"
                    role="button"
                    tabindex="0"
                    @click.stop="openCalendarDetail(day)"
                    @keyup.enter.stop="openCalendarDetail(day)"
                  >
                    <div class="sales-calendar-day-number">{{ day.day }}</div>
                    <div class="sales-calendar-day-amount">{{ formatCalendarAmount(day.amount) }}</div>
                  </article>
                </template>
              </el-popover>
            </div>
          </div>
        </transition>
      </section>
    </div>

    <section ref="recordsSectionRef" class="card-surface sales-record-table motion-fade-slide" style="--motion-delay: 0.32s">
      <div class="table-shell open-table-shell">
        <el-table
          :data="records"
          border
          stripe
          v-loading="loading"
          show-summary
          :summary-method="salesTableSummary"
          :row-class-name="saleRowClassName"
          @sort-change="onSortChange"
        >
          <el-table-column v-if="!isRepairMode" prop="goodsModel" label="型号" min-width="190" sortable="custom" show-overflow-tooltip />
          <el-table-column prop="receivedAmount" label="实收金额" min-width="120" sortable="custom">
            <template #default="{ row }">¥ {{ formatMoney(row.receivedAmount) }}</template>
          </el-table-column>
          <el-table-column prop="shopName" :label="isRepairMode ? '维修点' : '销售店铺'" min-width="180" sortable="custom" show-overflow-tooltip />
          <el-table-column prop="salesperson" :label="isRepairMode ? '工程师' : '销售员'" min-width="120" sortable="custom" />
          <el-table-column v-if="!isRepairMode" prop="goodsSeries" label="系列" min-width="140" sortable="custom" show-overflow-tooltip />
          <el-table-column v-if="!isRepairMode" prop="goodsBrand" label="品牌" min-width="120" sortable="custom" />
          <el-table-column v-if="!isRepairMode" prop="unitPrice" label="单价" min-width="110" sortable="custom">
            <template #default="{ row }">¥ {{ formatMoney(row.unitPrice) }}</template>
          </el-table-column>
          <el-table-column v-if="!isRepairMode" prop="quantity" label="数量" min-width="88" sortable="custom" />
          <el-table-column v-if="!isRepairMode" prop="receivableAmount" label="应收金额" min-width="120" sortable="custom">
            <template #default="{ row }">¥ {{ formatMoney(row.receivableAmount) }}</template>
          </el-table-column>
          <el-table-column v-if="!isRepairMode" prop="discountRate" label="折扣" min-width="92" sortable="custom">
            <template #default="{ row }">{{ row.discountDisplay || '/' }}</template>
          </el-table-column>
          <el-table-column v-if="!isRepairMode" prop="couponAmount" label="优惠券" min-width="110" sortable="custom">
            <template #default="{ row }">¥ {{ formatMoney(row.couponAmount) }}</template>
          </el-table-column>
          <el-table-column prop="soldAt" label="下单时间" min-width="170" sortable="custom" />
          <el-table-column v-if="!isRepairMode" prop="shipShopName" label="发货店铺" min-width="180" sortable="custom" show-overflow-tooltip />
          <el-table-column prop="orderNum" label="订单号" min-width="210" sortable="custom" show-overflow-tooltip />
          <el-table-column v-if="isRepairMode" prop="note" label="备注" min-width="220" show-overflow-tooltip />
          <el-table-column v-if="canEditSalesRecords || authStore.can('sales.manage')" label="操作" :width="actionColumnWidth" fixed="right">
            <template #default="{ row }">
              <ResponsiveTableActions :menu-width="160">
                <el-button v-if="canEditSalesRecords" type="primary" text @click="openEdit(row)">编辑</el-button>
                <el-button v-if="authStore.can('sales.manage')" type="danger" text @click="onDelete(row.id)">删除</el-button>
              </ResponsiveTableActions>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="pager-wrap">
        <div class="toolbar-actions sales-record-export-actions">
          <el-button :loading="salesExportPending" @click="openSalesExportDialog">导出表格</el-button>
        </div>
        <el-pagination
          background
          :layout="pagerLayout"
          :total="total"
          :current-page="page"
          :page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          @current-change="onPageChange"
          @size-change="onPageSizeChange"
        />
      </div>
    </section>

    <Teleport to="body">
      <transition name="calendar-detail-pop">
        <div v-if="calendarDetailVisible" class="sales-calendar-modal-layer" @click.self="closeCalendarDetail">
          <section class="card-surface sales-calendar-modal">
            <header class="sales-calendar-modal-head">
              <div class="sales-calendar-modal-copy">
                <span>{{ formatCalendarTooltipDate(calendarDetailDay?.date || '') }}</span>
                <h3>{{ calendarDetailShop ? calendarDetailShop.label : '销售详情' }}</h3>
              </div>
              <button type="button" class="sales-calendar-modal-close" @click="closeCalendarDetail">×</button>
            </header>

            <transition name="calendar-drill-panel" mode="out-in">
              <div
                :key="calendarDetailPerson ? `person-${calendarDetailShop?.label}-${calendarDetailPerson.label}` : calendarDetailShop ? `shop-${calendarDetailShop.label}` : 'day-overview'"
                class="sales-calendar-modal-stage"
                v-loading="calendarPersonDetailLoading"
              >
                <template v-if="!calendarDetailShop">
                  <div class="sales-calendar-detail-stats sales-calendar-detail-stats-lg">
                    <article class="sales-calendar-detail-stat">
                      <span>销售额</span>
                      <strong>{{ formatCalendarTooltipAmount(calendarDetailDay?.amount || 0) }}</strong>
                    </article>
                    <article class="sales-calendar-detail-stat">
                      <span>销售数量</span>
                      <strong>{{ calendarDetailDay?.quantity || 0 }}</strong>
                    </article>
                    <article class="sales-calendar-detail-stat">
                      <span>客单价</span>
                      <strong>{{ formatCalendarTicketValue(calendarDetailDay?.averageTicketValue || 0) }}</strong>
                    </article>
                  </div>

                  <div v-if="calendarDetailDay?.breakdowns?.length" class="sales-calendar-breakdown sales-calendar-breakdown-modal">
                    <div class="sales-calendar-breakdown-head">
                      <span>{{ calendarDetailDay?.breakdownTitle || '详细统计' }}</span>
                      <small v-if="calendarDetailDay?.breakdownMode === 'shop'">点击店铺销售额查看店铺内统计</small>
                    </div>
                    <div class="sales-calendar-breakdown-list">
                      <button
                        v-for="item in calendarDetailDay?.breakdowns || []"
                        :key="`${calendarDetailDay?.date}-${item.label}`"
                        type="button"
                        class="sales-calendar-breakdown-item sales-calendar-breakdown-button"
                        :class="{ clickable: canOpenCalendarBreakdown(item) }"
                        @click="canOpenCalendarBreakdown(item) ? openCalendarShopDetail(item.label) : null"
                      >
                        <div class="sales-calendar-breakdown-main">
                          <span>{{ item.label }}</span>
                          <small>销量 {{ item.quantity }} · 客单价 {{ formatCalendarTicketValue(item.averageTicketValue) }}</small>
                        </div>
                        <div class="sales-calendar-breakdown-side">
                          <strong>{{ formatCalendarTooltipAmount(item.amount) }}</strong>
                          <el-icon v-if="canOpenCalendarBreakdown(item)" class="sales-calendar-breakdown-arrow"><ArrowRight /></el-icon>
                        </div>
                      </button>
                    </div>
                  </div>

                  <div v-else class="sales-calendar-empty-state">
                    <span>当天暂无销售明细</span>
                  </div>
                </template>

                <template v-else-if="!calendarDetailPerson">
                  <button type="button" class="sales-calendar-detail-back" @click="closeCalendarShopDetail">
                    <el-icon><ArrowLeft /></el-icon>
                    <span>返回当日总览</span>
                  </button>

                  <div class="sales-calendar-detail-stats sales-calendar-detail-stats-lg">
                    <article class="sales-calendar-detail-stat">
                      <span>店铺销售额</span>
                      <strong>{{ formatCalendarTooltipAmount(calendarDetailShop.amount) }}</strong>
                    </article>
                    <article class="sales-calendar-detail-stat">
                      <span>销售数量</span>
                      <strong>{{ calendarDetailShop.quantity }}</strong>
                    </article>
                    <article class="sales-calendar-detail-stat">
                      <span>客单价</span>
                      <strong>{{ formatCalendarTicketValue(calendarDetailShop.averageTicketValue) }}</strong>
                    </article>
                    <article class="sales-calendar-detail-stat">
                      <span>订单数</span>
                      <strong>{{ calendarDetailShop.orderCount || 0 }}</strong>
                    </article>
                  </div>

                  <div v-if="calendarDetailShop.drilldowns?.length" class="sales-calendar-breakdown sales-calendar-breakdown-modal">
                    <div class="sales-calendar-breakdown-head">
                      <span>{{ calendarDetailShop.drilldownTitle || '店铺内统计' }}</span>
                      <small>点击人员查看当日商品销售情况</small>
                    </div>
                    <div class="sales-calendar-breakdown-list">
                      <button
                        v-for="item in calendarDetailShop.drilldowns || []"
                        :key="`${calendarDetailDay?.date}-${calendarDetailShop.label}-${item.label}`"
                        type="button"
                        class="sales-calendar-breakdown-item sales-calendar-breakdown-button"
                        @click="openCalendarPersonDetail(item)"
                      >
                        <div class="sales-calendar-breakdown-main">
                          <span>{{ item.label }}</span>
                          <small>销量 {{ item.quantity }} · 客单价 {{ formatCalendarTicketValue(item.averageTicketValue) }}</small>
                        </div>
                        <div class="sales-calendar-breakdown-side">
                          <strong>{{ formatCalendarTooltipAmount(item.amount) }}</strong>
                          <el-icon class="sales-calendar-breakdown-arrow"><ArrowRight /></el-icon>
                        </div>
                      </button>
                    </div>
                  </div>

                  <div v-else class="sales-calendar-empty-state">
                    <span>店铺内暂无人员销售明细</span>
                  </div>
                </template>

                <template v-else>
                  <button type="button" class="sales-calendar-detail-back" @click="closeCalendarPersonDetail">
                    <el-icon><ArrowLeft /></el-icon>
                    <span>返回店铺详情</span>
                  </button>

                  <div class="sales-calendar-detail-stats sales-calendar-detail-stats-lg">
                    <article class="sales-calendar-detail-stat">
                      <span>{{ isRepairMode ? '工程师销售额' : '人员销售额' }}</span>
                      <strong>{{ formatCalendarTooltipAmount(calendarDetailPerson.amount) }}</strong>
                    </article>
                    <article class="sales-calendar-detail-stat">
                      <span>销售数量</span>
                      <strong>{{ calendarDetailPerson.quantity }}</strong>
                    </article>
                    <article class="sales-calendar-detail-stat">
                      <span>客单价</span>
                      <strong>{{ formatCalendarTicketValue(calendarDetailPerson.averageTicketValue) }}</strong>
                    </article>
                    <article class="sales-calendar-detail-stat">
                      <span>订单数</span>
                      <strong>{{ calendarDetailPerson.orderCount || 0 }}</strong>
                    </article>
                  </div>

                  <div class="sales-calendar-breakdown sales-calendar-breakdown-modal">
                    <div class="sales-calendar-breakdown-head">
                      <span>{{ isRepairMode ? '当日维修明细' : '当日商品销售明细' }}</span>
                    </div>
                    <div v-if="calendarDetailPersonEntries.length" class="sales-calendar-breakdown-list">
                      <div
                        v-for="item in calendarDetailPersonEntries"
                        :key="`${calendarDetailDay?.date}-${calendarDetailShop?.label}-${calendarDetailPerson.label}-${item.label}`"
                        class="sales-calendar-breakdown-item"
                      >
                        <div class="sales-calendar-breakdown-main">
                          <span>{{ item.label }}</span>
                          <small>{{ item.meta }}</small>
                        </div>
                        <div class="sales-calendar-breakdown-side">
                          <strong>{{ formatCalendarTooltipAmount(item.amount) }}</strong>
                        </div>
                      </div>
                    </div>

                    <div v-else class="sales-calendar-empty-state sales-calendar-detail-inline-empty">
                      <span>当天暂无更细的商品销售明细</span>
                    </div>
                  </div>
                </template>
              </div>
            </transition>
          </section>
        </div>
      </transition>
    </Teleport>

    <ResponsiveDialog
      v-model="dialogVisible"
      title="编辑销售记录"
      width="min(860px, 96vw)"
      class="aqc-app-dialog"
      :mobile-subtitle="isRepairMode ? '维修销售记录' : '销售记录'"
    >
      <div class="goods-editor-shell" v-loading="dialogLoading">
        <section class="goods-editor-hero sales-record-editor-hero">
          <div class="goods-code-card">
            <span>{{ isRepairMode ? '当前维修单' : '当前型号' }}</span>
            <strong>{{ isRepairMode ? (dialogForm.shopName || '未填写维修点') : (dialogForm.goodsModel || '未填写型号') }}</strong>
            <div class="goods-preview-meta">
              <span>{{ isRepairMode ? `工程师 ${dialogForm.salesperson || '-'}` : `品牌 ${dialogForm.goodsBrand || '-'}` }}</span>
              <span v-if="!isRepairMode">系列 {{ dialogForm.goodsSeries || '-' }}</span>
              <span>订单号 {{ dialogForm.orderNum || '-' }}</span>
            </div>
          </div>
        </section>

        <el-form label-position="top" class="dialog-form goods-editor-form">
          <div class="goods-editor-grid">
            <el-form-item label="销售时间">
              <el-input v-model="dialogForm.soldAt" type="datetime-local" />
            </el-form-item>

            <el-form-item :label="isRepairMode ? '工程师' : '销售员'">
              <el-select v-model="dialogForm.salesperson" filterable clearable class="full-width" placeholder="请选择销售员">
                <el-option
                  v-for="option in dialogSelectableSalespersonOptions"
                  :key="option.username"
                  :label="option.displayName ? `${option.username} · ${option.displayName}` : option.username"
                  :value="option.username"
                />
              </el-select>
            </el-form-item>

            <el-form-item v-if="!isRepairMode" label="商品条码">
              <el-input v-model.trim="dialogForm.goodsBarcode" maxlength="64" placeholder="请输入商品条码" />
            </el-form-item>

            <el-form-item v-if="!isRepairMode" label="品牌">
              <el-select
                v-model="dialogForm.goodsBrand"
                filterable
                allow-create
                default-first-option
                clearable
                class="full-width"
                placeholder="选择或输入品牌"
                @change="onDialogBrandChange"
              >
                <el-option
                  v-for="option in meta.brandOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
            </el-form-item>

            <el-form-item v-if="!isRepairMode" label="系列">
              <el-select
                v-model="dialogForm.goodsSeries"
                filterable
                allow-create
                default-first-option
                clearable
                class="full-width"
                placeholder="选择或输入系列"
              >
                <el-option
                  v-for="option in filteredDialogSeriesOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
            </el-form-item>

            <el-form-item v-if="!isRepairMode" label="型号">
              <el-input v-model.trim="dialogForm.goodsModel" maxlength="191" placeholder="请输入商品型号" />
            </el-form-item>

            <el-form-item v-if="!isRepairMode" label="渠道">
              <el-select
                v-model="dialogForm.channel"
                filterable
                allow-create
                default-first-option
                class="full-width"
                placeholder="请选择销售渠道"
                @change="onDialogChannelChange"
              >
                <el-option
                  v-for="option in channelOptions"
                  :key="option"
                  :label="option"
                  :value="option"
                />
              </el-select>
            </el-form-item>

            <el-form-item v-if="showDialogShopSelector" :label="isRepairMode ? '维修点' : '销售店铺'">
              <el-select v-model="dialogForm.shopId" filterable clearable class="full-width" placeholder="请选择销售店铺" @change="onDialogShopChange">
                <el-option
                  v-for="option in dialogSalesShopOptions"
                  :key="option.id"
                  :label="option.name"
                  :value="option.id"
                />
              </el-select>
            </el-form-item>

            <el-form-item v-if="showDialogShipShopSelector" label="发货店铺/仓库">
              <el-select v-model="dialogForm.shipShopId" filterable clearable class="full-width" placeholder="请选择发货店铺/仓库" @change="onDialogShipShopChange">
                <el-option
                  v-for="option in dialogShipShopOptions"
                  :key="`ship-${option.id}`"
                  :label="option.name"
                  :value="option.id"
                />
              </el-select>
            </el-form-item>

            <el-form-item v-if="!isRepairMode" label="客户姓名">
              <el-input v-model.trim="dialogForm.customerName" maxlength="120" placeholder="可选" />
            </el-form-item>

            <el-form-item v-if="!isRepairMode" label="数量">
              <el-input-number v-model="dialogForm.quantity" :min="1" :max="1000000" class="full-width" />
            </el-form-item>

            <el-form-item v-if="!isRepairMode" label="单价（元）">
              <el-input-number v-model="dialogForm.unitPrice" :min="0" :step="0.01" :precision="2" :max="99999999" class="full-width" />
            </el-form-item>

            <el-form-item v-if="!isRepairMode" label="应收金额（元）">
              <el-input-number v-model="dialogForm.receivableAmount" :min="0.01" :step="0.01" :precision="2" :max="99999999" class="full-width" />
            </el-form-item>

            <el-form-item label="实收金额（元）">
              <el-input-number v-model="dialogForm.receivedAmount" :min="0.01" :step="0.01" :precision="2" :max="99999999" class="full-width" />
            </el-form-item>

            <el-form-item v-if="!isRepairMode" label="优惠券（元）">
              <el-input-number v-model="dialogForm.couponAmount" :min="0" :step="0.01" :precision="2" :max="99999999" class="full-width" />
            </el-form-item>

            <el-form-item v-if="!isRepairMode" label="折扣">
              <el-input :model-value="dialogDiscountDisplay" readonly />
            </el-form-item>

            <el-form-item class="dialog-span-full" label="备注">
              <el-input
                v-model.trim="dialogForm.note"
                type="textarea"
                :rows="4"
                maxlength="5000"
                show-word-limit
                placeholder="可记录活动、售后说明或特殊备注"
              />
            </el-form-item>
          </div>
        </el-form>
      </div>

      <template #footer>
        <div class="form-actions">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="submitEdit">保存修改</el-button>
        </div>
      </template>
    </ResponsiveDialog>

    <ExportColumnsDialog
      v-model="salesExportDialogVisible"
      title="导出销售记录"
      :options="salesExportColumnOptions"
      :selected-keys="salesExportColumnKeys"
      :presets="salesExportPresets"
      :allow-presets="true"
      confirm-text="确认导出"
      @update:selected-keys="salesExportColumnKeys = $event"
      @save-preset="saveSalesExportPreset"
      @confirm="confirmSalesExport"
    />
  </section>
</template>

<script setup>
import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import CollapsePanelTransition from '../components/CollapsePanelTransition.vue'
import ExportColumnsDialog from '../components/ExportColumnsDialog.vue'
import ResponsiveDialog from '../components/ResponsiveDialog.vue'
import ResponsiveTableActions from '../components/ResponsiveTableActions.vue'
import SalesSummaryPanel from '../components/SalesSummaryPanel.vue'
import { useMobileViewport } from '../composables/useMobileViewport'
import { apiDelete, apiGet, apiPut } from '../services/api'
import { useAuthStore } from '../stores/auth'
import { confirmAction, confirmDestructiveAction } from '../utils/confirm'
import { downloadCsvFile, escapeCsvCell } from '../utils/csv'
import { getShanghaiParts } from '../utils/shanghaiTime'
import { SHOP_TYPE_REPAIR, SHOP_TYPE_STORE, SHOP_TYPE_WAREHOUSE } from '../utils/shops'
import { resolveTableActionWidth } from '../utils/tableActions'

const authStore = useAuthStore()
const { isMobileViewport } = useMobileViewport()
const route = useRoute()
const router = useRouter()
const isRepairMode = computed(() => route.name === 'repair-sales-records')

const loading = ref(false)
const metaLoading = ref(false)
const calendarLoading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const keyword = ref('')
const recordIdFilter = ref('')
const orderNumFilter = ref('')
const brandFilter = ref('')
const seriesFilter = ref('')
const shopFilter = ref(authStore.user?.shopName || '')
const salespersonFilter = ref('')
const dateRange = ref([])
const sortField = ref('sold_at')
const sortOrder = ref('desc')
const records = ref([])
const calendarMonth = ref(getCurrentMonthToken())
const calendarTransitionName = ref('calendar-slide-next')
const calendarPickerVisible = ref(false)
const calendarPickerYear = ref(Number(getCurrentMonthToken().slice(0, 4)))
const calendarPickerMonth = ref(Number(getCurrentMonthToken().slice(5, 7)))
const weekdayLabels = ['S', 'M', 'T', 'W', 'T', 'F', 'S']
const channelOptions = ['门店', '小程序', '企业微信', '私域', '团购', '其他']
const filterPanelOpen = ref(false)
const calendarDetailVisible = ref(false)
const calendarDetailDay = ref(null)
const calendarDetailShopLabel = ref('')
const calendarDetailPersonLabel = ref('')
const calendarPersonDetailLoading = ref(false)
const calendarDetailPersonEntries = ref([])
const dialogVisible = ref(false)
const dialogLoading = ref(false)
const saving = ref(false)
const editingId = ref(null)
const dialogSalesShopOptions = ref([])
const dialogShipShopOptions = ref([])
const dialogSalespersonOptions = ref([])
const originalDialogRecord = ref(null)
const dialogLastSelectedSalesShopId = ref(null)
const canEditSalesRecords = computed(() => authStore.aqcRoleKey === 'aqc_admin' || authStore.can('sales.manage'))
const SALES_EXPORT_PRESET_STORAGE_KEY = 'aqc-sales-record-export-presets-v1'
const salesExportDialogVisible = ref(false)
const salesExportPending = ref(false)
const salesExportColumnKeys = ref([])
const salesExportPresets = ref(loadSalesExportPresets())
const actionColumnWidth = computed(() => resolveTableActionWidth([[
  canEditSalesRecords.value ? '编辑' : '',
  authStore.can('sales.manage') ? '删除' : '',
]], {
  compact: isMobileViewport.value,
  minWidth: 112,
  maxWidth: 170,
}))
const pagerLayout = computed(() => (isMobileViewport.value ? 'prev, pager, next' : 'total, prev, pager, next, sizes'))
const recordsSectionRef = ref(null)
const summaryPanelRef = ref(null)
let searchDebounceTimer = null
let autoRefreshTimer = null
let autoRefreshPending = false

const RECOMMENDED_PERIOD_PRESET_KEYS = ['today', 'yesterday', 'this_week', 'last_week', 'this_month', 'last_month', 'this_year', 'last_year']
const RECOMMENDED_PERIOD_PRESET_LABELS = {
  today: '本日',
  yesterday: '昨日',
  this_week: '本周',
  last_week: '上周',
  this_month: '本月',
  last_month: '上月',
  this_year: '本年',
  last_year: '去年',
}

const meta = reactive({
  totalItems: 0,
  brandOptions: [],
  seriesOptions: [],
  shopOptions: [],
  salespersonOptions: [],
  recommendedPeriodOptions: createDefaultRecommendedPeriodOptions(),
})

const calendar = reactive({
  month: '',
  monthLabel: '',
  totalAmount: 0,
  totalQuantity: 0,
  activeDays: 0,
  days: [],
})
const calendarMonthOptions = Array.from({ length: 12 }, (_, index) => ({
  value: index + 1,
  label: `${String(index + 1).padStart(2, '0')}月`,
}))
const calendarYearOptions = computed(() => {
  const currentYear = Number(getCurrentMonthToken().slice(0, 4))
  const activeYear = parseCalendarMonthToken(calendarMonth.value).year || currentYear
  const startYear = Math.min(currentYear, activeYear) - 5
  const endYear = Math.max(currentYear, activeYear) + 2
  return Array.from({ length: endYear - startYear + 1 }, (_, index) => endYear - index)
})
const calendarDisplayYear = computed(() => `${parseCalendarMonthToken(calendarMonth.value).year}年`)
const calendarDisplayMonth = computed(() => `${String(parseCalendarMonthToken(calendarMonth.value).month).padStart(2, '0')}月`)

const dialogForm = reactive({
  soldAt: '',
  orderNum: '',
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
  salesperson: '',
  customerName: '',
  note: '',
})

const currentSortLabel = computed(() => {
  const labelMap = {
    sold_at: '下单时间',
    goods_series: '系列',
    goods_model: '型号',
    goods_brand: '品牌',
    unit_price: '单价',
    quantity: '数量',
    receivable_amount: '应收金额',
    discount_rate: '折扣',
    coupon_amount: '优惠券',
    received_amount: '实收金额',
    shop_name: '销售店铺',
    ship_shop_name: '发货店铺',
    salesperson: '销售员',
    order_num: '订单号',
  }
  return `${labelMap[sortField.value] || '下单时间'} ${sortOrder.value === 'asc' ? '正序' : '倒序'}`
})

const activeFilterEntries = computed(() => ([
  ['关键词', keyword.value],
  ['订单号', orderNumFilter.value],
  ...(!isRepairMode.value ? [['品牌', brandFilter.value], ['系列', seriesFilter.value]] : []),
  [isRepairMode.value ? '维修点' : '销售店铺', shopFilter.value],
  [isRepairMode.value ? '工程师' : '销售员', salespersonFilter.value],
  ['推荐筛选', activeRecommendedPeriod.value?.label || ''],
  ['时间', activeRecommendedPeriod.value ? '' : dateRangeDisplayLabel.value],
]).filter(([, value]) => String(value || '').trim()))

const activeFilterCount = computed(() => activeFilterEntries.value.length)
const hasCustomDateRange = computed(() => Boolean(dateRange.value?.[0] && dateRange.value?.[1]))
const dateRangeDisplayLabel = computed(() => dateRange.value?.filter(Boolean)?.join(' 至 ') || '')
const activeRecommendedPeriod = computed(() => {
  const [dateFrom, dateTo] = dateRange.value || []
  if (!dateFrom || !dateTo) {
    return null
  }
  return meta.recommendedPeriodOptions.find((item) => item.dateFrom === dateFrom && item.dateTo === dateTo) || null
})

const summaryQuery = computed(() => ({
  sale_kind: isRepairMode.value ? 'repair' : 'goods',
  ...(keyword.value ? { q: keyword.value } : {}),
  ...(orderNumFilter.value ? { order_num: orderNumFilter.value } : {}),
  ...(brandFilter.value ? { brand: brandFilter.value } : {}),
  ...(seriesFilter.value ? { series: seriesFilter.value } : {}),
  ...(shopFilter.value ? { shop_name: shopFilter.value } : {}),
  ...(salespersonFilter.value ? { salesperson: salespersonFilter.value } : {}),
  ...(dateRange.value?.[0] ? { date_from: dateRange.value[0] } : {}),
  ...(dateRange.value?.[1] ? { date_to: dateRange.value[1] } : {}),
}))

const summaryFilterLabel = computed(() => {
  const labels = [
    activeRecommendedPeriod.value?.label || '',
    activeRecommendedPeriod.value ? '' : (hasCustomDateRange.value ? `${dateRange.value[0]} 至 ${dateRange.value[1]}` : ''),
    salespersonFilter.value,
    shopFilter.value,
    brandFilter.value,
    seriesFilter.value,
    orderNumFilter.value,
    keyword.value,
  ]
    .map((item) => String(item || '').trim())
    .filter(Boolean)
  return labels.join(' · ')
})

const salesExportColumnOptions = computed(() => ([
  ...(isRepairMode.value
    ? [
      { key: 'soldAt', label: '下单时间' },
      { key: 'orderNum', label: '订单号' },
      { key: 'shopName', label: '维修点' },
      { key: 'salesperson', label: '工程师' },
      { key: 'receivedAmount', label: '实收金额' },
      { key: 'note', label: '备注' },
    ]
    : [
      { key: 'soldAt', label: '下单时间' },
      { key: 'orderNum', label: '订单号' },
      { key: 'goodsModel', label: '型号' },
      { key: 'goodsBrand', label: '品牌' },
      { key: 'goodsSeries', label: '系列' },
      { key: 'shopName', label: '销售店铺' },
      { key: 'shipShopName', label: '发货店铺' },
      { key: 'salesperson', label: '销售员' },
      { key: 'unitPrice', label: '单价' },
      { key: 'quantity', label: '数量' },
      { key: 'receivableAmount', label: '应收金额' },
      { key: 'receivedAmount', label: '实收金额' },
      { key: 'discountDisplay', label: '折扣' },
      { key: 'couponAmount', label: '优惠券' },
      { key: 'channel', label: '渠道' },
      { key: 'customerName', label: '客户姓名' },
      { key: 'goodsBarcode', label: '条码' },
      { key: 'note', label: '备注' },
    ]),
]))

const showDialogShopSelector = computed(() => (isRepairMode.value ? true : dialogForm.channel === '门店'))
const showDialogShipShopSelector = computed(() => !isRepairMode.value && showDialogShopSelector.value)
function isRepairEngineerEligible(option) {
  const roleKey = String(option?.aqcRoleKey || '').trim()
  return roleKey === 'aqc_engineer' || roleKey === 'aqc_admin'
}

const dialogSelectableSalespersonOptions = computed(() => {
  if (!isRepairMode.value) {
    return dialogSalespersonOptions.value
  }
  return dialogSalespersonOptions.value.filter((item) => isRepairEngineerEligible(item))
})

const filteredDialogSeriesOptions = computed(() => {
  if (!dialogForm.goodsBrand) {
    return meta.seriesOptions
  }
  return meta.seriesOptions.filter((item) => String(item.value || '').trim())
})

const dialogDiscountDisplay = computed(() => {
  const receivable = Number(dialogForm.receivableAmount || 0)
  const received = Number(dialogForm.receivedAmount || 0)
  if (receivable <= 0) {
    return '/'
  }
  const rate = received >= receivable ? 10 : Number(((received / receivable) * 10).toFixed(2))
  if (Math.abs(receivable - received) < 0.005 && rate >= 9.99) {
    return '/'
  }
  return rate.toFixed(2)
})

function formatMoney(value) {
  return new Intl.NumberFormat('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value || 0)
}

function salesTableSummary({ columns, data }) {
  const pageReceivedTotal = data.reduce((sum, item) => sum + Number(item.receivedAmount || 0), 0)
  const pageQuantityTotal = data.reduce((sum, item) => sum + Number(item.quantity || 0), 0)
  const pageReceivableTotal = data.reduce((sum, item) => sum + Number(item.receivableAmount || 0), 0)
  return columns.map((column, index) => {
    if (index === 0) {
      return '合计'
    }
    if (column.property === 'receivedAmount') {
      return `¥ ${formatMoney(pageReceivedTotal)}`
    }
    if (column.property === 'quantity') {
      return String(pageQuantityTotal)
    }
    if (column.property === 'receivableAmount') {
      return `¥ ${formatMoney(pageReceivableTotal)}`
    }
    return ''
  })
}

function getDefaultSalesExportColumnKeys() {
  return salesExportColumnOptions.value.map((item) => item.key)
}

function loadSalesExportPresets() {
  if (typeof window === 'undefined') {
    return []
  }
  try {
    const raw = window.localStorage.getItem(SALES_EXPORT_PRESET_STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed : []
  } catch (_error) {
    return []
  }
}

function persistSalesExportPresets() {
  if (typeof window === 'undefined') {
    return
  }
  try {
    window.localStorage.setItem(SALES_EXPORT_PRESET_STORAGE_KEY, JSON.stringify(salesExportPresets.value || []))
  } catch (_error) {
    // ignore preset persistence failures
  }
}

function ensureSalesExportSelection() {
  const validKeys = new Set(salesExportColumnOptions.value.map((item) => item.key))
  const nextKeys = (salesExportColumnKeys.value || []).filter((key) => validKeys.has(key))
  salesExportColumnKeys.value = nextKeys.length ? nextKeys : getDefaultSalesExportColumnKeys()
}

function openSalesExportDialog() {
  ensureSalesExportSelection()
  salesExportDialogVisible.value = true
}

function saveSalesExportPreset(preset) {
  const name = String(preset?.name || '').trim()
  const keys = Array.isArray(preset?.keys) ? preset.keys.filter((item) => salesExportColumnOptions.value.some((option) => option.key === item)) : []
  if (!name || !keys.length) {
    return
  }
  salesExportPresets.value = [
    { id: String(preset.id || Date.now()), name, keys },
    ...salesExportPresets.value.filter((item) => item.name !== name),
  ].slice(0, 12)
  persistSalesExportPresets()
  ElMessage.success('导出预设已保存')
}

function buildSalesExportFilename() {
  const parts = getShanghaiParts(new Date())
  return `销售记录-${parts.year}${parts.month}${parts.day}-${parts.hour}${parts.minute}${parts.second}.csv`
}

function formatSalesExportCell(row, key) {
  if (key === 'unitPrice' || key === 'receivableAmount' || key === 'receivedAmount' || key === 'couponAmount') {
    return formatMoney(row?.[key] || 0)
  }
  return String(row?.[key] ?? '').trim()
}

async function fetchAllSalesRecordsForExport() {
  const pageSizeLimit = 200
  let currentPage = 1
  let totalCount = 0
  const rows = []

  while (true) {
    const payload = await apiGet('/sales/records', {
      token: authStore.token,
      timeoutMs: 20000,
      query: {
        ...buildQuery(false),
        page: String(currentPage),
        page_size: String(pageSizeLimit),
      },
    })
    if (!payload?.success) {
      throw new Error(payload?.message || '销售记录导出失败')
    }
    const batch = payload.records || []
    totalCount = Number(payload.total || batch.length || 0)
    rows.push(...batch)
    if (!batch.length || rows.length >= totalCount) {
      break
    }
    currentPage += 1
  }

  return rows
}

async function confirmSalesExport(selectedKeys) {
  const keys = Array.isArray(selectedKeys) ? selectedKeys.filter(Boolean) : []
  if (!keys.length) {
    ElMessage.warning('请至少选择一列')
    return
  }
  try {
    await confirmAction('确认导出当前筛选结果吗？导出内容会遵循当前筛选条件和排序。', '导出确认', '确认导出')
  } catch (_error) {
    return
  }
  salesExportPending.value = true
  try {
    const rows = await fetchAllSalesRecordsForExport()
    if (!rows.length) {
      ElMessage.warning('当前筛选条件下没有可导出的销售记录')
      return
    }
    const optionMap = new Map(salesExportColumnOptions.value.map((item) => [item.key, item.label]))
    const header = ['序号', ...keys.map((key) => optionMap.get(key) || key)]
    const dataLines = rows.map((row, index) => [String(index + 1), ...keys.map((key) => formatSalesExportCell(row, key))])
    const csvContent = [header, ...dataLines]
      .map((line) => line.map(escapeCsvCell).join(','))
      .join('\n')
    downloadCsvFile(buildSalesExportFilename(), csvContent)
    salesExportDialogVisible.value = false
    ElMessage.success(`已导出 ${rows.length} 条销售记录`)
  } catch (error) {
    ElMessage.error(error?.message || '销售记录导出失败')
  } finally {
    salesExportPending.value = false
  }
}

function saleRowClassName({ row }) {
  const status = String(row?.saleStatus || 'normal')
  if (status === 'returned') {
    return 'sales-record-row-returned'
  }
  if (status === 'return_entry') {
    return 'sales-record-row-return-entry'
  }
  return ''
}

function truncateDecimal(value, digits = 2) {
  const factor = 10 ** digits
  return Math.floor(Number(value || 0) * factor) / factor
}

function getCurrentMonthToken() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

function formatDateToken(date) {
  return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, '0')}-${String(date.getUTCDate()).padStart(2, '0')}`
}

function parseDateToken(token) {
  const [year, month, day] = String(token || '').split('-').map((item) => Number(item || 0))
  return new Date(Date.UTC(year, Math.max(month - 1, 0), day || 1))
}

function shiftDateToken(token, diffDays) {
  const next = parseDateToken(token)
  next.setUTCDate(next.getUTCDate() + Number(diffDays || 0))
  return formatDateToken(next)
}

function getShanghaiTodayToken() {
  const parts = getShanghaiParts(new Date())
  return `${parts.year}-${parts.month}-${parts.day}`
}

function resolveRecommendedPeriodDateRange(key, todayToken = getShanghaiTodayToken()) {
  const currentWeekStart = shiftDateToken(todayToken, -((parseDateToken(todayToken).getUTCDay() + 6) % 7))
  const currentMonthStart = `${todayToken.slice(0, 7)}-01`
  const currentYearStart = `${todayToken.slice(0, 4)}-01-01`
  const currentWeekEnd = shiftDateToken(currentWeekStart, 6)
  const currentMonthEnd = shiftDateToken(`${todayToken.slice(0, 7)}-01`, new Date(Date.UTC(Number(todayToken.slice(0, 4)), Number(todayToken.slice(5, 7)), 0)).getUTCDate() - 1)

  if (key === 'today') {
    return [todayToken, todayToken]
  }
  if (key === 'yesterday') {
    const yesterday = shiftDateToken(todayToken, -1)
    return [yesterday, yesterday]
  }
  if (key === 'this_week') {
    return [currentWeekStart, currentWeekEnd]
  }
  if (key === 'last_week') {
    return [shiftDateToken(currentWeekStart, -7), shiftDateToken(currentWeekStart, -1)]
  }
  if (key === 'this_month') {
    return [currentMonthStart, currentMonthEnd]
  }
  if (key === 'last_month') {
    const previousMonthLastDay = shiftDateToken(currentMonthStart, -1)
    return [`${previousMonthLastDay.slice(0, 7)}-01`, previousMonthLastDay]
  }
  if (key === 'this_year') {
    return [currentYearStart, `${todayToken.slice(0, 4)}-12-31`]
  }
  if (key === 'last_year') {
    const lastYear = String(Number(todayToken.slice(0, 4)) - 1)
    return [`${lastYear}-01-01`, `${lastYear}-12-31`]
  }
  return [todayToken, todayToken]
}

function createDefaultRecommendedPeriodOptions() {
  const todayToken = getShanghaiTodayToken()
  return RECOMMENDED_PERIOD_PRESET_KEYS.map((key, index) => {
    const [dateFrom, dateTo] = resolveRecommendedPeriodDateRange(key, todayToken)
    return {
      key,
      label: RECOMMENDED_PERIOD_PRESET_LABELS[key] || key,
      count: 0,
      dateFrom,
      dateTo,
      recommended: index < 3,
    }
  })
}

function normalizeRecommendedPeriodOptions(options) {
  const fallbackMap = new Map(createDefaultRecommendedPeriodOptions().map((item) => [item.key, item]))
  const incoming = Array.isArray(options) ? options : []
  if (!incoming.length) {
    return Array.from(fallbackMap.values())
  }

  const normalized = incoming
    .map((item) => {
      const key = String(item?.key || '').trim()
      if (!fallbackMap.has(key)) {
        return null
      }
      const fallback = fallbackMap.get(key)
      return {
        ...fallback,
        ...item,
        key,
        label: RECOMMENDED_PERIOD_PRESET_LABELS[key] || item?.label || fallback?.label || key,
        count: Number(item?.count || 0),
        dateFrom: String(item?.dateFrom || fallback?.dateFrom || '').trim(),
        dateTo: String(item?.dateTo || fallback?.dateTo || '').trim(),
        recommended: Boolean(item?.recommended),
      }
    })
    .filter(Boolean)

  for (const key of RECOMMENDED_PERIOD_PRESET_KEYS) {
    if (!normalized.some((item) => item.key === key)) {
      normalized.push(fallbackMap.get(key))
    }
  }

  return normalized
}

function parseCalendarMonthToken(token) {
  const [yearText, monthText] = String(token || getCurrentMonthToken()).split('-')
  return {
    year: Number(yearText || 0),
    month: Number(monthText || 1),
  }
}

function buildCalendarMonthToken(year, month) {
  return `${Number(year || 0)}-${String(Number(month || 1)).padStart(2, '0')}`
}

function syncCalendarPickerState() {
  const parsed = parseCalendarMonthToken(calendarMonth.value)
  calendarPickerYear.value = parsed.year
  calendarPickerMonth.value = parsed.month
}

function formatCalendarAmount(value) {
  const amount = Number(value || 0)
  if (amount === 0) {
    return '0'
  }
  const sign = amount < 0 ? '-' : ''
  const absolute = Math.abs(amount)
  if (absolute >= 10000) {
    return `${sign}${truncateDecimal(absolute / 10000).toFixed(2)}w`
  }
  if (absolute >= 1000) {
    return `${sign}${truncateDecimal(absolute / 1000).toFixed(2)}k`
  }
  return `${sign}${Math.floor(absolute)}`
}

function formatCalendarTooltipAmount(value) {
  const amount = Number(value || 0)
  if (amount === 0) {
    return '¥ 0.00'
  }
  return `${amount > 0 ? '+' : '-'}¥ ${formatMoney(Math.abs(amount))}`
}

function formatCalendarTicketValue(value) {
  return `¥ ${formatMoney(value || 0)}`
}

function formatCalendarTooltipDate(value) {
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  const weekday = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][date.getDay()]
  return `${value} ${weekday}`
}

function canOpenCalendarBreakdown(item) {
  return Array.isArray(item?.drilldowns) && item.drilldowns.length > 0
}

const calendarDetailShop = computed(() => {
  if (!calendarDetailDay.value || !calendarDetailShopLabel.value) {
    return null
  }
  return (calendarDetailDay.value.breakdowns || []).find((item) => item.label === calendarDetailShopLabel.value) || null
})

const calendarDetailPerson = computed(() => {
  if (!calendarDetailShop.value || !calendarDetailPersonLabel.value) {
    return null
  }
  return (calendarDetailShop.value.drilldowns || []).find((item) => item.label === calendarDetailPersonLabel.value) || null
})

function openCalendarDetail(day) {
  calendarDetailDay.value = day
  calendarDetailShopLabel.value = ''
  calendarDetailPersonLabel.value = ''
  calendarDetailPersonEntries.value = []
  calendarPersonDetailLoading.value = false
  calendarDetailVisible.value = true
}

function closeCalendarDetail() {
  calendarDetailVisible.value = false
  calendarDetailDay.value = null
  calendarDetailShopLabel.value = ''
  calendarDetailPersonLabel.value = ''
  calendarDetailPersonEntries.value = []
  calendarPersonDetailLoading.value = false
}

function openCalendarShopDetail(label) {
  if (!calendarDetailVisible.value) {
    return
  }
  calendarDetailShopLabel.value = label
  calendarDetailPersonLabel.value = ''
  calendarDetailPersonEntries.value = []
}

function closeCalendarShopDetail() {
  calendarDetailShopLabel.value = ''
  calendarDetailPersonLabel.value = ''
  calendarDetailPersonEntries.value = []
  calendarPersonDetailLoading.value = false
}

function buildCalendarPersonQuery({ date, shopName, salesperson }) {
  return {
    ...buildFilterQuery(),
    shop_name: shopName,
    salesperson,
    date_from: date,
    date_to: date,
    page: 1,
    page_size: 200,
    sort_field: 'sold_at',
    sort_order: 'asc',
  }
}

function resolveCalendarPersonEntryLabel(record) {
  if (isRepairMode.value) {
    return String(record.note || '').trim() || String(record.orderNum || '').trim() || '维修项目'
  }
  return String(record.goodsModel || record.goodsDisplayName || '').trim()
    || [record.goodsBrand, record.goodsSeries].filter(Boolean).join(' ')
    || String(record.orderNum || '').trim()
    || '未命名商品'
}

function buildCalendarPersonEntries(records) {
  const grouped = new Map()
  for (const item of Array.isArray(records) ? records : []) {
    const label = resolveCalendarPersonEntryLabel(item)
    const current = grouped.get(label) || {
      label,
      amount: 0,
      quantity: 0,
      orderNums: new Set(),
    }
    current.amount = Number((current.amount + Number(item.receivedAmount || 0)).toFixed(2))
    current.quantity += Number(item.quantity || 0)
    if (item.orderNum) {
      current.orderNums.add(item.orderNum)
    }
    grouped.set(label, current)
  }
  return [...grouped.values()]
    .sort((left, right) => {
      if (right.amount !== left.amount) {
        return right.amount - left.amount
      }
      return String(left.label || '').localeCompare(String(right.label || ''), 'zh-CN')
    })
    .map((item) => ({
      label: item.label,
      amount: Number(item.amount || 0),
      meta: `${isRepairMode.value ? '单数' : '销量'} ${item.quantity || 0} · 订单 ${item.orderNums.size}`,
    }))
}

async function openCalendarPersonDetail(item) {
  if (!calendarDetailDay.value || !calendarDetailShop.value || !item?.label) {
    return
  }
  calendarDetailPersonLabel.value = ''
  calendarDetailPersonEntries.value = []
  if (Array.isArray(item.entries) && item.entries.length) {
    calendarDetailPersonEntries.value = item.entries
    calendarDetailPersonLabel.value = item.label
    return
  }
  calendarPersonDetailLoading.value = true
  const payload = await apiGet('/sales/records', {
    token: authStore.token,
    query: buildCalendarPersonQuery({
      date: calendarDetailDay.value.date,
      shopName: calendarDetailShop.value.label,
      salesperson: item.label,
    }),
  })
  calendarPersonDetailLoading.value = false
  if (!payload?.success) {
    ElMessage.error(payload?.message || '人员销售明细加载失败')
    return
  }
  calendarDetailPersonEntries.value = buildCalendarPersonEntries(payload.records || [])
  calendarDetailPersonLabel.value = item.label
}

function closeCalendarPersonDetail() {
  calendarDetailPersonLabel.value = ''
  calendarDetailPersonEntries.value = []
  calendarPersonDetailLoading.value = false
}

function buildFilterQuery() {
  return {
    sale_kind: isRepairMode.value ? 'repair' : 'goods',
    ...(recordIdFilter.value ? { record_id: recordIdFilter.value } : {}),
    ...(keyword.value ? { q: keyword.value } : {}),
    ...(orderNumFilter.value ? { order_num: orderNumFilter.value } : {}),
    ...(brandFilter.value ? { brand: brandFilter.value } : {}),
    ...(seriesFilter.value ? { series: seriesFilter.value } : {}),
    ...(shopFilter.value ? { shop_name: shopFilter.value } : {}),
    ...(salespersonFilter.value ? { salesperson: salespersonFilter.value } : {}),
    ...(dateRange.value?.[0] ? { date_from: dateRange.value[0] } : {}),
    ...(dateRange.value?.[1] ? { date_to: dateRange.value[1] } : {}),
  }
}

function toDateTimeLocalValue(value) {
  const text = String(value || '').trim()
  if (!text) {
    return ''
  }
  return text.slice(0, 16)
}

function resolveSalespersonPayload(selectedValue) {
  const cleanValue = String(selectedValue || '').trim()
  if (!cleanValue) {
    return ''
  }
  const matched = dialogSelectableSalespersonOptions.value.find((item) => item.username === cleanValue || item.displayName === cleanValue)
  return matched?.displayName || matched?.username || cleanValue
}

function syncDialogSalespersonValue(rawValue) {
  const cleanValue = String(rawValue || '').trim()
  const matched = dialogSelectableSalespersonOptions.value.find((item) => item.username === cleanValue || item.displayName === cleanValue)
  dialogForm.salesperson = matched?.username || cleanValue
}

function syncDialogShopValue(rawShopId, rawShopName) {
  if (rawShopId) {
    dialogForm.shopId = Number(rawShopId)
    dialogLastSelectedSalesShopId.value = Number(rawShopId)
    return
  }
  const cleanName = String(rawShopName || '').trim()
  const matched = dialogSalesShopOptions.value.find((item) => item.name === cleanName)
  dialogForm.shopId = matched?.id || null
  dialogLastSelectedSalesShopId.value = matched?.id || null
}

function syncDialogShipShopValue(rawShopId, rawShopName) {
  if (rawShopId) {
    dialogForm.shipShopId = Number(rawShopId)
    return
  }
  const cleanName = String(rawShopName || '').trim()
  const matched = dialogShipShopOptions.value.find((item) => item.name === cleanName)
  dialogForm.shipShopId = matched?.id || null
}

function resetDialogForm() {
  dialogForm.soldAt = ''
  dialogForm.orderNum = ''
  dialogForm.goodsId = null
  dialogForm.goodsCode = ''
  dialogForm.goodsBrand = ''
  dialogForm.goodsSeries = ''
  dialogForm.goodsModel = ''
  dialogForm.goodsBarcode = ''
  dialogForm.unitPrice = 0
  dialogForm.receivableAmount = 0
  dialogForm.receivedAmount = 0
  dialogForm.couponAmount = 0
  dialogForm.quantity = 1
  dialogForm.channel = '门店'
  dialogForm.shopId = null
  dialogForm.shopName = ''
  dialogForm.shipShopId = null
  dialogForm.shipShopName = ''
  dialogForm.salesperson = ''
  dialogForm.customerName = ''
  dialogForm.note = ''
  originalDialogRecord.value = null
  dialogLastSelectedSalesShopId.value = null
}

async function loadDialogOptions() {
  dialogLoading.value = true
  const [salesShopsPayload, shipWarehousesPayload, usersPayload] = await Promise.all([
    apiGet('/shops', {
      token: authStore.token,
      query: {
        page: '1',
        page_size: '100',
        shop_type: String(isRepairMode.value ? SHOP_TYPE_REPAIR : SHOP_TYPE_STORE),
      },
    }),
    isRepairMode.value
      ? Promise.resolve(null)
      : apiGet('/shops', {
        token: authStore.token,
        query: {
          page: '1',
          page_size: '100',
          shop_type: String(SHOP_TYPE_WAREHOUSE),
        },
      }),
    apiGet('/users/options', { token: authStore.token, query: { limit: '200' } }),
  ])
  dialogLoading.value = false
  dialogSalesShopOptions.value = salesShopsPayload?.success
    ? (salesShopsPayload.shops || []).map((item) => ({
      id: item.id,
      name: item.name,
    }))
    : []
  dialogShipShopOptions.value = isRepairMode.value
    ? []
    : [
      ...dialogSalesShopOptions.value,
      ...((shipWarehousesPayload?.success ? (shipWarehousesPayload.shops || []) : []).map((item) => ({
        id: item.id,
        name: item.name,
      }))),
    ].sort((left, right) => Number(left.id || 0) - Number(right.id || 0))
  dialogSalespersonOptions.value = usersPayload?.success ? (usersPayload.options || []) : []
}

function buildQuery(includePaging = true) {
  const query = {
    ...buildFilterQuery(),
    sort_field: sortField.value,
    sort_order: sortOrder.value,
  }
  if (includePaging) {
    query.page = String(page.value)
    query.page_size = String(pageSize.value)
  }
  return query
}

async function loadMeta(options = {}) {
  const { silent = false } = options
  if (!silent) {
    metaLoading.value = true
  }
  const payload = await apiGet('/sales/meta', {
    token: authStore.token,
    query: buildQuery(false),
  })
  if (!silent) {
    metaLoading.value = false
  }
  if (!payload?.success) {
    if (!silent) {
      ElMessage.error(payload?.message || '销售筛选元数据加载失败')
    }
    return
  }

  meta.totalItems = Number(payload.totalItems || 0)
  meta.brandOptions = payload.brandOptions || []
  meta.seriesOptions = payload.seriesOptions || []
  meta.shopOptions = payload.shopOptions || []
  meta.salespersonOptions = payload.salespersonOptions || []
  meta.recommendedPeriodOptions = normalizeRecommendedPeriodOptions(payload.recommendedPeriodOptions)
}

async function loadCalendar(options = {}) {
  const { silent = false, preserveDetail = false } = options
  if (!silent) {
    calendarLoading.value = true
  }
  if (!preserveDetail) {
    closeCalendarDetail()
  }
  const payload = await apiGet('/sales/calendar', {
    token: authStore.token,
    query: {
      ...buildFilterQuery(),
      month: calendarMonth.value,
    },
  })
  if (!silent) {
    calendarLoading.value = false
  }

  if (!payload?.success) {
    if (!silent) {
      ElMessage.error(payload?.message || '销售日历加载失败')
    }
    return
  }

  calendar.month = payload.month || calendarMonth.value
  calendar.monthLabel = payload.monthLabel || calendarMonth.value
  calendar.totalAmount = Number(payload.totalAmount || 0)
  calendar.totalQuantity = Number(payload.totalQuantity || 0)
  calendar.activeDays = Number(payload.activeDays || 0)
  calendar.days = payload.days || []
}

async function loadRecords(options = {}) {
  const { silent = false } = options
  if (!silent) {
    loading.value = true
  }
  const payload = await apiGet('/sales/records', {
    token: authStore.token,
    query: buildQuery(true),
  })
  if (!silent) {
    loading.value = false
  }

  if (!payload?.success) {
    if (!silent) {
      ElMessage.error(payload?.message || '销售记录加载失败')
    }
    return
  }

  records.value = payload.records || []
  total.value = Number(payload.total || 0)
}

async function reloadAll(options = {}) {
  await Promise.all([loadMeta(options), loadRecords(options), loadCalendar(options)])
}

function clearAutoRefreshTimer() {
  if (autoRefreshTimer !== null) {
    clearInterval(autoRefreshTimer)
    autoRefreshTimer = null
  }
}

async function runAutoRefresh() {
  if (
    autoRefreshPending
    || dialogVisible.value
    || dialogLoading.value
    || salesExportDialogVisible.value
    || calendarDetailVisible.value
    || (typeof document !== 'undefined' && document.visibilityState === 'hidden')
  ) {
    return
  }
  autoRefreshPending = true
  try {
    await Promise.all([
      reloadAll({ silent: true, preserveDetail: true }),
      summaryPanelRef.value?.reload?.({ animate: false }) || Promise.resolve(),
    ])
  } finally {
    autoRefreshPending = false
  }
}

function startAutoRefreshTimer() {
  clearAutoRefreshTimer()
  if (typeof window === 'undefined') {
    return
  }
  autoRefreshTimer = window.setInterval(() => {
    void runAutoRefresh()
  }, 15000)
}

function onDialogBrandChange() {
  if (dialogForm.goodsSeries && !meta.seriesOptions.some((item) => item.value === dialogForm.goodsSeries)) {
    dialogForm.goodsSeries = ''
  }
}

function onDialogChannelChange() {
  if (isRepairMode.value) {
    return
  }
  if (dialogForm.channel !== '门店') {
    dialogForm.shopId = null
    dialogForm.shopName = ''
    dialogForm.shipShopId = null
    dialogForm.shipShopName = ''
  }
}

function onDialogShopChange(value) {
  const previousSalesShopId = Number(dialogLastSelectedSalesShopId.value || 0)
  const matched = dialogSalesShopOptions.value.find((item) => item.id === value)
  dialogForm.shopName = matched?.name || ''
  if (isRepairMode.value) {
    dialogLastSelectedSalesShopId.value = matched?.id || null
    return
  }
  if (
    !dialogForm.shipShopId
    || Number(dialogForm.shipShopId || 0) === previousSalesShopId
    || !dialogForm.shipShopName
  ) {
    dialogForm.shipShopId = matched?.id || null
    dialogForm.shipShopName = matched?.name || ''
  }
  dialogLastSelectedSalesShopId.value = matched?.id || null
}

function onDialogShipShopChange(value) {
  const matched = dialogShipShopOptions.value.find((item) => item.id === value)
  dialogForm.shipShopName = matched?.name || ''
}

function onBrandChange() {
  if (seriesFilter.value && !meta.seriesOptions.some((item) => item.value === seriesFilter.value)) {
    seriesFilter.value = ''
  }
  page.value = 1
  void reloadAll()
}

function onSearch() {
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
    searchDebounceTimer = null
  }
  page.value = 1
  void reloadAll()
}

function onResetFilters() {
  recordIdFilter.value = ''
  keyword.value = ''
  orderNumFilter.value = ''
  brandFilter.value = ''
  seriesFilter.value = ''
  shopFilter.value = ''
  salespersonFilter.value = ''
  dateRange.value = []
  sortField.value = 'sold_at'
  sortOrder.value = 'desc'
  page.value = 1
  closeCalendarDetail()
  void reloadAll()
}

function setRecommendedPeriod(option) {
  const [nextDateFrom, nextDateTo] = [String(option?.dateFrom || '').trim(), String(option?.dateTo || '').trim()]
  if (!nextDateFrom || !nextDateTo) {
    return
  }
  page.value = 1
  if (dateRange.value?.[0] === nextDateFrom && dateRange.value?.[1] === nextDateTo) {
    void reloadAll()
    return
  }
  dateRange.value = [nextDateFrom, nextDateTo]
}

function onSortChange({ prop, order }) {
  if (!prop || !order) {
    sortField.value = 'sold_at'
    sortOrder.value = 'desc'
  } else {
    const map = {
      soldAt: 'sold_at',
      goodsSeries: 'goods_series',
      goodsModel: 'goods_model',
      goodsBrand: 'goods_brand',
      unitPrice: 'unit_price',
      quantity: 'quantity',
      receivableAmount: 'receivable_amount',
      discountRate: 'discount_rate',
      couponAmount: 'coupon_amount',
      receivedAmount: 'received_amount',
      shopName: 'shop_name',
      shipShopName: 'ship_shop_name',
      salesperson: 'salesperson',
      orderNum: 'order_num',
    }
    sortField.value = map[prop] || 'sold_at'
    sortOrder.value = order === 'ascending' ? 'asc' : 'desc'
  }
  page.value = 1
  void loadRecords()
}

async function onDelete(recordId) {
  try {
    await confirmDestructiveAction('确认删除这条销售记录吗？删除后统计会同步变化。')
  } catch (error) {
    return
  }
  const payload = await apiDelete(`/sales/records/${recordId}`, {
    token: authStore.token,
  })
  if (!payload?.success) {
    ElMessage.error(payload?.message || '删除失败')
    return
  }
  ElMessage.success(payload.message || '删除成功')
  await reloadAll()
}

async function openEdit(row) {
  if (!canEditSalesRecords.value) {
    ElMessage.warning('当前账号无权编辑销售记录')
    return
  }
  editingId.value = row.id
  resetDialogForm()
  originalDialogRecord.value = { ...row }
  dialogForm.soldAt = toDateTimeLocalValue(row.soldAt)
  dialogForm.orderNum = row.orderNum || ''
  dialogForm.goodsId = row.goodsId || null
  dialogForm.goodsCode = row.goodsCode || ''
  dialogForm.goodsBrand = row.goodsBrand || ''
  dialogForm.goodsSeries = row.goodsSeries || ''
  dialogForm.goodsModel = row.goodsModel || ''
  dialogForm.goodsBarcode = row.goodsBarcode || ''
  dialogForm.unitPrice = Number(row.unitPrice || 0)
  dialogForm.receivableAmount = Number(row.receivableAmount || 0)
  dialogForm.receivedAmount = Number(row.receivedAmount || 0)
  dialogForm.couponAmount = Number(row.couponAmount || 0)
  dialogForm.quantity = Number(row.quantity || 1)
  dialogForm.channel = row.channel || '门店'
  dialogForm.shopId = row.shopId || null
  dialogForm.shopName = row.shopName || ''
  dialogForm.shipShopId = row.shipShopId || null
  dialogForm.shipShopName = row.shipShopName || ''
  dialogForm.salesperson = row.salesperson || ''
  dialogForm.customerName = row.customerName || ''
  dialogForm.note = row.note || ''
  dialogVisible.value = true
  await loadDialogOptions()
  syncDialogShopValue(row.shopId, row.shopName)
  syncDialogShipShopValue(row.shipShopId, row.shipShopName)
  syncDialogSalespersonValue(row.salesperson)
}

function buildEditPayload() {
  const original = originalDialogRecord.value || {}
  const goodsFieldsChanged = [
    ['goodsCode', dialogForm.goodsCode],
    ['goodsBrand', dialogForm.goodsBrand],
    ['goodsSeries', dialogForm.goodsSeries],
    ['goodsModel', dialogForm.goodsModel],
    ['goodsBarcode', dialogForm.goodsBarcode],
  ].some(([key, value]) => String(value || '').trim() !== String(original[key] || '').trim())
  return {
    saleKind: isRepairMode.value ? 'repair' : 'goods',
    soldAt: dialogForm.soldAt ? `${dialogForm.soldAt}:00` : null,
    orderNum: dialogForm.orderNum,
    goodsId: isRepairMode.value ? null : (goodsFieldsChanged ? null : (dialogForm.goodsId || null)),
    goodsCode: isRepairMode.value ? '' : dialogForm.goodsCode,
    goodsBrand: isRepairMode.value ? '' : dialogForm.goodsBrand,
    goodsSeries: isRepairMode.value ? '' : dialogForm.goodsSeries,
    goodsModel: isRepairMode.value ? '' : dialogForm.goodsModel,
    goodsBarcode: isRepairMode.value ? '' : dialogForm.goodsBarcode,
    unitPrice: Number(isRepairMode.value ? (dialogForm.receivedAmount || 0) : (dialogForm.unitPrice || 0)),
    receivableAmount: Number(isRepairMode.value ? (dialogForm.receivedAmount || 0) : (dialogForm.receivableAmount || 0)),
    receivedAmount: Number(dialogForm.receivedAmount || 0),
    couponAmount: Number(isRepairMode.value ? 0 : (dialogForm.couponAmount || 0)),
    quantity: Number(isRepairMode.value ? 1 : (dialogForm.quantity || 1)),
    channel: isRepairMode.value ? '维修' : dialogForm.channel,
    shopId: showDialogShopSelector.value ? (dialogForm.shopId || null) : null,
    shopName: showDialogShopSelector.value ? dialogForm.shopName : '',
    shipShopId: showDialogShipShopSelector.value ? (dialogForm.shipShopId || dialogForm.shopId || null) : null,
    shipShopName: showDialogShipShopSelector.value ? (dialogForm.shipShopName || dialogForm.shopName) : '',
    salesperson: resolveSalespersonPayload(dialogForm.salesperson),
    customerName: isRepairMode.value ? '' : dialogForm.customerName,
    note: dialogForm.note,
  }
}

async function submitEdit() {
  if (!editingId.value) {
    return
  }
  if (!isRepairMode.value && (!dialogForm.receivableAmount || Number(dialogForm.receivableAmount) <= 0)) {
    ElMessage.error('请输入正确的应收金额')
    return
  }
  if (!dialogForm.receivedAmount || Number(dialogForm.receivedAmount) <= 0) {
    ElMessage.error('请输入正确的实收金额')
    return
  }
  if (showDialogShopSelector.value && !dialogForm.shopId) {
    ElMessage.error(isRepairMode.value ? '请选择维修点' : '门店销售请选择销售店铺')
    return
  }
  if (showDialogShipShopSelector.value && !dialogForm.shipShopId) {
    ElMessage.error('门店销售请选择发货店铺')
    return
  }
  saving.value = true
  const payload = await apiPut(`/sales/records/${editingId.value}`, buildEditPayload(), {
    token: authStore.token,
  })
  saving.value = false
  if (!payload?.success) {
    ElMessage.error(payload?.message || '更新失败')
    return
  }
  ElMessage.success(payload.message || '更新成功')
  dialogVisible.value = false
  await reloadAll()
}

function toggleRecordMode() {
  router.push({ name: isRepairMode.value ? 'sales-records' : 'repair-sales-records' })
}

function onPageChange(nextPage) {
  page.value = nextPage
  void loadRecords()
}

function onPageSizeChange(nextSize) {
  pageSize.value = nextSize
  page.value = 1
  void loadRecords()
}

function shiftCalendarMonth(step) {
  closeCalendarDetail()
  calendarPickerVisible.value = false
  calendarTransitionName.value = step >= 0 ? 'calendar-slide-next' : 'calendar-slide-prev'
  const { year, month } = parseCalendarMonthToken(calendarMonth.value)
  const nextDate = new Date(year, month - 1 + step, 1)
  calendarMonth.value = `${nextDate.getFullYear()}-${String(nextDate.getMonth() + 1).padStart(2, '0')}`
  syncCalendarPickerState()
  void loadCalendar()
}

function jumpCalendarMonth(monthValue) {
  const nextToken = buildCalendarMonthToken(calendarPickerYear.value, monthValue)
  if (nextToken === calendarMonth.value) {
    calendarPickerVisible.value = false
    return
  }
  closeCalendarDetail()
  calendarTransitionName.value = nextToken > calendarMonth.value ? 'calendar-slide-next' : 'calendar-slide-prev'
  calendarPickerMonth.value = Number(monthValue || 1)
  calendarMonth.value = nextToken
  calendarPickerVisible.value = false
  void loadCalendar()
}

function scrollRecordsIntoView() {
  nextTick(() => {
    recordsSectionRef.value?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
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

async function applySalesSpotlightFromRoute() {
  const spotlightRecordId = String(route.query.spotlight_sale_record || '').trim()
  const spotlightOrderNum = String(route.query.spotlight_order_num || '').trim()
  if (!spotlightRecordId && !spotlightOrderNum) {
    return
  }

  recordIdFilter.value = spotlightRecordId
  keyword.value = ''
  orderNumFilter.value = spotlightRecordId ? '' : spotlightOrderNum
  brandFilter.value = ''
  seriesFilter.value = ''
  shopFilter.value = ''
  salespersonFilter.value = ''
  dateRange.value = []
  sortField.value = 'sold_at'
  sortOrder.value = 'desc'
  page.value = 1
  filterPanelOpen.value = false
  closeCalendarDetail()

  await reloadAll()
  scrollRecordsIntoView()
  await consumeSpotlightQuery(['spotlight_sale_record', 'spotlight_order_num'])
}

async function applyAccountFiltersFromRoute() {
  const accountSalesperson = String(route.query.account_salesperson || '').trim()
  const accountDateFrom = String(route.query.account_date_from || '').trim()
  const accountDateTo = String(route.query.account_date_to || '').trim()
  if (!accountSalesperson && !accountDateFrom && !accountDateTo) {
    return
  }

  recordIdFilter.value = ''
  keyword.value = ''
  orderNumFilter.value = ''
  brandFilter.value = ''
  seriesFilter.value = ''
  shopFilter.value = ''
  salespersonFilter.value = accountSalesperson
  dateRange.value = accountDateFrom || accountDateTo ? [accountDateFrom, accountDateTo].filter(Boolean) : []
  sortField.value = 'sold_at'
  sortOrder.value = 'desc'
  page.value = 1
  filterPanelOpen.value = false
  closeCalendarDetail()

  await reloadAll()
  scrollRecordsIntoView()
  await consumeSpotlightQuery(['account_salesperson', 'account_date_from', 'account_date_to'])
}

function scheduleAutoSearch() {
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
  }
  searchDebounceTimer = setTimeout(() => {
    onSearch()
  }, 280)
}

watch([keyword, orderNumFilter], () => {
  scheduleAutoSearch()
})

watch(
  () => [route.query.spotlight_sale_record, route.query.spotlight_order_num, route.query.account_salesperson, route.query.account_date_from, route.query.account_date_to],
  ([recordId, orderNum, accountSalesperson, accountDateFrom, accountDateTo]) => {
    if (accountSalesperson || accountDateFrom || accountDateTo) {
      void applyAccountFiltersFromRoute()
      return
    }
    if (!recordId && !orderNum) {
      return
    }
    void applySalesSpotlightFromRoute()
  },
)

watch(dateRange, () => {
  onSearch()
}, { deep: true })

onBeforeUnmount(() => {
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
  }
  clearAutoRefreshTimer()
})

void (async () => {
  await reloadAll()
  startAutoRefreshTimer()
  await applyAccountFiltersFromRoute()
  await applySalesSpotlightFromRoute()
})()
</script>
