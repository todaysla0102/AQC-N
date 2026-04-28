<template>
  <section class="report-center-page">
    <article v-if="report" class="card-surface motion-fade-slide report-center-hero" style="--motion-delay: 0.04s">
      <div class="report-center-hero-copy">
        <h3>{{ report.title || '最新报告' }}</h3>
        <div class="report-center-meta">
          <span v-if="report.createdAt">生成于 {{ formatDateTime(report.createdAt) }}</span>
        </div>
      </div>

      <div class="toolbar-actions report-center-hero-actions">
        <el-button @click="goBack">返回</el-button>
        <el-button :loading="loading" @click="loadReport">刷新</el-button>
        <el-button @click="openReportHistory">查看历史报告</el-button>
        <el-button v-if="authStore.isAdmin" @click="openReportSettings">报告设置</el-button>
      </div>
    </article>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" show-icon />

    <section v-if="report" class="report-summary-grid motion-fade-slide" style="--motion-delay: 0.08s">
      <article class="card-surface report-summary-card">
        <span>销售额</span>
        <strong>¥ {{ formatMoney(report.summary?.salesAmount?.receivedTotal) }}</strong>
        <small>客单价 ¥ {{ formatMoney(report.summary?.salesAmount?.averageTicketValue) }}</small>
      </article>
      <article class="card-surface report-summary-card">
        <span>销量</span>
        <strong>{{ formatInteger(report.summary?.salesGoods?.salesQuantity) }}</strong>
        <small>商品数 {{ formatInteger(report.summary?.salesGoods?.productCount) }}</small>
      </article>
      <article class="card-surface report-summary-card">
        <span>库存总数</span>
        <strong>{{ formatInteger(report.summary?.inventory?.currentTotalQuantity) }}</strong>
        <small>净变动 {{ formatSignedInteger(report.summary?.inventory?.netChangeQuantity) }}</small>
      </article>
      <article class="card-surface report-summary-card">
        <span>工单</span>
        <strong>{{ formatInteger(report.summary?.workOrders?.approvedCount) }}</strong>
        <small>待审批 {{ formatInteger(report.summary?.workOrders?.pendingCount) }}</small>
      </article>
    </section>

    <section v-if="report" class="report-module-list">
      <article class="card-surface motion-fade-slide report-module-card" style="--motion-delay: 0.12s">
        <header class="report-module-head">
          <div>
            <h3>{{ report.modules?.salesAmount?.title || '销售金额报告' }}</h3>
          </div>
        </header>
        <div class="report-module-highlight-list">
          <span v-for="item in report.modules?.salesAmount?.highlights || []" :key="item">{{ item }}</span>
        </div>
        <div class="report-metric-grid">
          <article class="report-metric-item">
            <span>总销售额</span>
            <strong>¥ {{ formatMoney(report.modules?.salesAmount?.summary?.receivedTotal) }}</strong>
          </article>
          <article class="report-metric-item">
            <span>环比</span>
            <strong>{{ formatPercent(report.modules?.salesAmount?.summary?.momChangePercent) }}</strong>
          </article>
          <article class="report-metric-item">
            <span>同比</span>
            <strong>{{ formatPercent(report.modules?.salesAmount?.summary?.yoyChangePercent) }}</strong>
          </article>
          <article class="report-metric-item">
            <span>客单价</span>
            <strong>¥ {{ formatMoney(report.modules?.salesAmount?.summary?.averageTicketValue) }}</strong>
          </article>
        </div>
        <CollapsePanelTransition>
          <div v-if="isExpanded('salesAmount')" class="report-detail-grid">
            <section class="report-detail-section report-detail-section-full">
              <div class="report-detail-head">
                <strong>门店销售明细</strong>
              </div>
              <div class="report-detail-list">
                <article v-for="item in report.modules?.salesAmount?.details?.shopBreakdown || []" :key="item.shopName" class="report-detail-row">
                  <div>
                    <strong>{{ item.shopName }}</strong>
                    <span>{{ item.orderCount }} 单 · {{ item.quantity }} 件</span>
                  </div>
                  <strong>¥ {{ formatMoney(item.salesAmount) }}</strong>
                </article>
              </div>
            </section>
          </div>
        </CollapsePanelTransition>
        <div class="report-module-footer">
          <el-button @click="toggleDetails('salesAmount')">{{ isExpanded('salesAmount') ? '收起详情' : '查看详情' }}</el-button>
        </div>
      </article>

      <article class="card-surface motion-fade-slide report-module-card" style="--motion-delay: 0.16s">
        <header class="report-module-head">
          <div>
            <h3>{{ report.modules?.salesGoods?.title || '销售商品报告' }}</h3>
          </div>
        </header>
        <div class="report-module-highlight-list">
          <span v-for="item in report.modules?.salesGoods?.highlights || []" :key="item">{{ item }}</span>
        </div>
        <div class="report-metric-grid">
          <article class="report-metric-item">
            <span>销售件数</span>
            <strong>{{ formatInteger(report.modules?.salesGoods?.summary?.salesQuantity) }}</strong>
          </article>
          <article class="report-metric-item">
            <span>销量最高商品</span>
            <strong>{{ report.modules?.salesGoods?.summary?.topProduct?.goodsModel || '暂无' }}</strong>
          </article>
          <article class="report-metric-item">
            <span>进销比</span>
            <strong>{{ formatRatio(report.modules?.salesGoods?.summary?.salesToPurchaseRatio) }}</strong>
          </article>
          <article class="report-metric-item">
            <span>去化率</span>
            <strong>{{ formatRate(report.modules?.salesGoods?.summary?.sellThroughRate) }}</strong>
          </article>
        </div>
        <CollapsePanelTransition>
          <div v-if="isExpanded('salesGoods')" class="report-detail-grid">
            <section class="report-detail-section report-detail-section-full report-detail-section-scroll">
              <div class="report-detail-head">
                <strong>商品销售明细</strong>
              </div>
              <div class="report-detail-list report-detail-list-scroll">
                <article
                  v-for="item in report.modules?.salesGoods?.details?.products || []"
                  :key="`${item.goodsId || 0}-${item.goodsModel}`"
                  class="report-detail-row"
                >
                  <div>
                    <strong>{{ item.goodsModel }}</strong>
                    <span>{{ [item.goodsBrand, item.goodsSeries].filter(Boolean).join(' / ') || '未分类' }}</span>
                  </div>
                  <div class="report-detail-side">
                    <span>{{ item.quantity }} 件</span>
                    <strong>¥ {{ formatMoney(item.salesAmount) }}</strong>
                  </div>
                </article>
              </div>
            </section>
          </div>
        </CollapsePanelTransition>
        <div class="report-module-footer">
          <el-button @click="toggleDetails('salesGoods')">{{ isExpanded('salesGoods') ? '收起详情' : '查看详情' }}</el-button>
        </div>
      </article>

      <article class="card-surface motion-fade-slide report-module-card" style="--motion-delay: 0.2s">
        <header class="report-module-head">
          <div>
            <h3>{{ report.modules?.inventory?.title || '库存报告' }}</h3>
          </div>
        </header>
        <div class="report-module-highlight-list">
          <span v-for="item in report.modules?.inventory?.highlights || []" :key="item">{{ item }}</span>
        </div>
        <div class="report-metric-grid">
          <article class="report-metric-item">
            <span>库存总数</span>
            <strong>{{ formatInteger(report.modules?.inventory?.summary?.currentTotalQuantity) }}</strong>
          </article>
          <article class="report-metric-item">
            <span>入库</span>
            <strong>{{ formatInteger(report.modules?.inventory?.summary?.changeInQuantity) }}</strong>
          </article>
          <article class="report-metric-item">
            <span>出库</span>
            <strong>{{ formatInteger(report.modules?.inventory?.summary?.changeOutQuantity) }}</strong>
          </article>
          <article class="report-metric-item">
            <span>净变动</span>
            <strong>{{ formatSignedInteger(report.modules?.inventory?.summary?.netChangeQuantity) }}</strong>
          </article>
        </div>
        <CollapsePanelTransition>
          <div v-if="isExpanded('inventory')" class="report-detail-grid">
            <section class="report-detail-section report-detail-section-scroll">
              <div class="report-detail-head">
                <strong>库存分布</strong>
              </div>
              <div class="report-detail-list report-detail-list-scroll">
                <article
                  v-for="item in report.modules?.inventory?.details?.shopBreakdown || []"
                  :key="`${item.shopId || 0}-${item.shopName}`"
                  class="report-detail-row report-detail-row-actionable"
                  role="button"
                  tabindex="0"
                  @click="openInventoryLocationDetail(item)"
                  @keyup.enter="openInventoryLocationDetail(item)"
                >
                  <div>
                    <strong>{{ item.shopName }}</strong>
                    <span>{{ formatShopType(item.shopType) }} · 入库 {{ formatInteger(item.changeInQuantity) }} · 出库 {{ formatInteger(item.changeOutQuantity) }}</span>
                  </div>
                  <div class="report-detail-side report-detail-side-inline">
                    <strong>{{ formatInteger(item.quantity) }}</strong>
                    <span :class="['report-quantity-change', quantityChangeClass(item.netChangeQuantity)]">{{ quantityChangeLabel(item.netChangeQuantity) }}</span>
                  </div>
                </article>
              </div>
            </section>

            <section class="report-detail-section report-detail-section-scroll">
              <div class="report-detail-head">
                <strong>库存变动明细</strong>
              </div>
              <div class="report-detail-list report-detail-list-scroll">
                <article
                  v-for="item in report.modules?.inventory?.details?.changeLogs || []"
                  :key="`${item.createdAt}-${item.goodsId || 0}-${item.goodsModel}-${item.changeContent}`"
                  class="report-detail-row report-detail-row-actionable"
                  role="button"
                  tabindex="0"
                  @click="openInventoryChangeAction(item)"
                  @keyup.enter="openInventoryChangeAction(item)"
                >
                  <div>
                    <strong>{{ item.goodsModel || '未识别商品' }}</strong>
                    <span>{{ item.shopName || '-' }} · {{ item.changeContent || '-' }}</span>
                  </div>
                  <div class="report-detail-side">
                    <span>{{ formatDateTime(item.createdAt) }}</span>
                    <strong>{{ formatSignedInteger(item.delta) }}</strong>
                  </div>
                </article>
              </div>
            </section>
          </div>
        </CollapsePanelTransition>
        <div class="report-module-footer">
          <el-button @click="toggleDetails('inventory')">{{ isExpanded('inventory') ? '收起详情' : '查看详情' }}</el-button>
        </div>
      </article>

      <article class="card-surface motion-fade-slide report-module-card" style="--motion-delay: 0.24s">
        <header class="report-module-head">
          <div>
            <h3>{{ report.modules?.salesperson?.title || '销售员报告' }}</h3>
          </div>
        </header>
        <div class="report-module-highlight-list">
          <span v-for="item in report.modules?.salesperson?.highlights || []" :key="item">{{ item }}</span>
        </div>
        <div class="report-metric-grid">
          <article class="report-metric-item">
            <span>参与人数</span>
            <strong>{{ formatInteger(report.modules?.salesperson?.summary?.memberCount) }}</strong>
          </article>
          <article class="report-metric-item">
            <span>销冠</span>
            <strong>{{ report.modules?.salesperson?.summary?.topSalesperson?.name || '暂无' }}</strong>
          </article>
          <article class="report-metric-item">
            <span>销冠金额</span>
            <strong>¥ {{ formatMoney(report.modules?.salesperson?.summary?.topSalesperson?.salesAmount) }}</strong>
          </article>
        </div>
        <CollapsePanelTransition>
          <div v-if="isExpanded('salesperson')" class="report-detail-grid">
            <section class="report-detail-section report-detail-section-full report-detail-section-scroll">
              <div class="report-detail-head">
                <strong>销售员排行榜</strong>
              </div>
              <div class="report-detail-list report-detail-list-scroll">
                <article
                  v-for="(item, index) in report.modules?.salesperson?.details?.ranking || []"
                  :key="item.name"
                  class="report-detail-row report-detail-row-actionable"
                  role="button"
                  tabindex="0"
                  @click="openSalespersonDetail(item)"
                  @keyup.enter="openSalespersonDetail(item)"
                >
                  <div>
                    <strong>{{ index + 1 }}. {{ item.name }}</strong>
                    <span>{{ item.orderCount }} 单 · {{ item.quantity }} 件</span>
                  </div>
                  <strong>¥ {{ formatMoney(item.salesAmount) }}</strong>
                </article>
              </div>
            </section>
          </div>
        </CollapsePanelTransition>
        <div class="report-module-footer">
          <el-button @click="toggleDetails('salesperson')">{{ isExpanded('salesperson') ? '收起详情' : '查看详情' }}</el-button>
        </div>
      </article>

      <article v-if="report.modules?.target" class="card-surface motion-fade-slide report-module-card" style="--motion-delay: 0.28s">
        <header class="report-module-head">
          <div>
            <h3>{{ report.modules?.target?.title || '目标报告' }}</h3>
          </div>
        </header>
        <div class="report-module-highlight-list">
          <span v-for="item in report.modules?.target?.highlights || []" :key="item">{{ item }}</span>
        </div>
        <div class="report-metric-grid">
          <article class="report-metric-item">
            <span>启用门店</span>
            <strong>{{ formatInteger(report.modules?.target?.summary?.enabledShopCount) }}</strong>
          </article>
          <article class="report-metric-item">
            <span>平均完成度</span>
            <strong>{{ formatRate(report.modules?.target?.summary?.averageCompletionRatio) }}</strong>
          </article>
        </div>
        <CollapsePanelTransition>
          <div v-if="isExpanded('target')" class="report-detail-grid">
            <section class="report-detail-section report-detail-section-full">
              <div class="report-detail-head">
                <strong>门店目标进展</strong>
              </div>
              <div class="report-detail-list">
                <article v-for="item in report.modules?.target?.details?.shops || []" :key="item.shopId" class="report-detail-row">
                  <div>
                    <strong>{{ item.shopName }}</strong>
                    <span>目标 ¥ {{ formatMoney(item.targetAmount) }} · 实际 ¥ {{ formatMoney(item.actualAmount) }}</span>
                  </div>
                  <strong>{{ formatRate(item.completionRatio) }}</strong>
                </article>
              </div>
            </section>
          </div>
        </CollapsePanelTransition>
        <div class="report-module-footer">
          <el-button @click="toggleDetails('target')">{{ isExpanded('target') ? '收起详情' : '查看详情' }}</el-button>
        </div>
      </article>

      <article class="card-surface motion-fade-slide report-module-card" style="--motion-delay: 0.32s">
        <header class="report-module-head">
          <div>
            <h3>{{ report.modules?.workOrders?.title || '工单报告' }}</h3>
          </div>
        </header>
        <div class="report-module-highlight-list">
          <span v-for="item in report.modules?.workOrders?.highlights || []" :key="item">{{ item }}</span>
        </div>
        <div class="report-metric-grid">
          <article class="report-metric-item">
            <span>审批通过</span>
            <strong>{{ formatInteger(report.modules?.workOrders?.summary?.approvedCount) }}</strong>
          </article>
          <article class="report-metric-item">
            <span>待审批</span>
            <strong>{{ formatInteger(report.modules?.workOrders?.summary?.pendingCount) }}</strong>
          </article>
          <article class="report-metric-item">
            <span>草稿</span>
            <strong>{{ formatInteger(report.modules?.workOrders?.summary?.draftCount) }}</strong>
          </article>
        </div>
        <CollapsePanelTransition>
          <div v-if="isExpanded('workOrders')" class="report-detail-grid">
            <section class="report-detail-section report-detail-section-scroll">
              <div class="report-detail-head">
                <strong>审批通过工单</strong>
              </div>
              <div class="report-detail-list report-detail-list-scroll">
                <article v-for="item in report.modules?.workOrders?.details?.approvedOrders || []" :key="item.orderNum" class="report-detail-row">
                  <div>
                    <strong>{{ item.orderNum }}</strong>
                    <span>{{ item.orderTypeLabel }} · {{ item.applicantName || '-' }}</span>
                  </div>
                  <strong>{{ formatDateTime(item.approvedAt) }}</strong>
                </article>
              </div>
            </section>

            <section class="report-detail-section report-detail-section-scroll">
              <div class="report-detail-head">
                <strong>待审批 / 草稿</strong>
              </div>
              <div class="report-detail-list report-detail-list-scroll">
                <article
                  v-for="item in [...(report.modules?.workOrders?.details?.pendingOrders || []), ...(report.modules?.workOrders?.details?.draftOrders || [])]"
                  :key="`${item.orderNum}-${item.createdAt}`"
                  class="report-detail-row"
                >
                  <div>
                    <strong>{{ item.orderNum }}</strong>
                    <span>{{ item.orderTypeLabel }} · {{ item.reason || '-' }}</span>
                  </div>
                  <strong>{{ formatDateTime(item.createdAt) }}</strong>
                </article>
              </div>
            </section>
          </div>
        </CollapsePanelTransition>
        <div class="report-module-footer">
          <el-button @click="toggleDetails('workOrders')">{{ isExpanded('workOrders') ? '收起详情' : '查看详情' }}</el-button>
        </div>
      </article>
    </section>

    <article v-else-if="!loading" class="card-surface motion-fade-slide report-empty-card" style="--motion-delay: 0.08s">
      <strong>暂无可查看的报告</strong>
      <p>报告会在配置的推送时间生成，也可以稍后到历史报告里查看。</p>
    </article>

    <ResponsiveDialog
      v-if="authStore.isAdmin"
      v-model="reportSettingsVisible"
      title="报告设置"
      width="900px"
      class="aqc-app-dialog report-settings-dialog"
      mobile-subtitle="报告设置"
    >
      <div v-loading="reportSettingsLoading" class="report-settings-shell">
        <section class="report-settings-overview">
          <article class="report-settings-overview-card">
            <span>调度时区</span>
            <strong>北京时间</strong>
            <p>日报按每日时间生成，周报按所选周几生成上一完整周，月报按所选几号生成上一完整月。</p>
          </article>
          <article class="report-settings-overview-card">
            <span>通知清理</span>
            <strong>各周期独立执行</strong>
            <p>每张卡片都可以单独设置清理时间；到点后只撤回该周期的推送通知，不会再共用日报时间。</p>
          </article>
        </section>

        <section class="report-settings-stack">
          <article
            v-for="item in reportSettings"
            :key="item.periodKey"
            class="report-setting-card"
          >
            <div class="report-setting-head">
              <div class="report-setting-copy">
                <span class="panel-tag">{{ item.periodLabel }}</span>
                <h3>{{ item.periodLabel }}</h3>
                <p>
                  上次生成：
                  {{ item.lastRunAt ? item.lastRunAt.replace('T', ' ').slice(0, 16) : '尚未生成' }}
                  <template v-if="item.lastPeriodKey">
                    · 周期标识 {{ item.lastPeriodKey }}
                  </template>
                </p>
              </div>
              <el-switch v-model="item.enabled" inline-prompt active-text="启用" inactive-text="停用" />
            </div>

            <div class="report-setting-grid">
              <div class="report-setting-field">
                <label class="sales-filter-label">推送时间（北京时间）</label>
                <el-time-select
                  v-model="item.pushTime"
                  class="full-width"
                  start="00:00"
                  step="00:15"
                  end="23:45"
                  placeholder="选择推送时间"
                />
                <div class="report-setting-caption">{{ reportPushCaption(item) }}</div>
              </div>

              <div v-if="item.periodKey === 'week'" class="report-setting-field">
                <label class="sales-filter-label">周报推送日</label>
                <el-select v-model="item.pushWeekday" class="full-width">
                  <el-option
                    v-for="option in reportWeekdayOptions"
                    :key="`push-${item.periodKey}-${option.value}`"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
              </div>

              <div v-if="item.periodKey === 'month'" class="report-setting-field">
                <label class="sales-filter-label">月报推送日</label>
                <el-select v-model="item.pushDayOfMonth" class="full-width">
                  <el-option
                    v-for="option in reportMonthDayOptions"
                    :key="`push-day-${item.periodKey}-${option.value}`"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
                <div class="report-setting-caption">若当月没有这个日期，会在当月最后一天执行。</div>
              </div>

              <div class="report-setting-field">
                <label class="sales-filter-label">清理时间（北京时间）</label>
                <el-time-select
                  v-model="item.cleanupTime"
                  class="full-width"
                  start="00:00"
                  step="00:15"
                  end="23:45"
                  placeholder="选择清理时间"
                />
                <div class="report-setting-caption">{{ reportCleanupCaption(item) }}</div>
              </div>

              <div v-if="item.periodKey === 'week'" class="report-setting-field">
                <label class="sales-filter-label">周报清理日</label>
                <el-select v-model="item.cleanupWeekday" class="full-width">
                  <el-option
                    v-for="option in reportWeekdayOptions"
                    :key="`cleanup-${item.periodKey}-${option.value}`"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
              </div>

              <div v-if="item.periodKey === 'month'" class="report-setting-field">
                <label class="sales-filter-label">月报清理日</label>
                <el-select v-model="item.cleanupDayOfMonth" class="full-width">
                  <el-option
                    v-for="option in reportMonthDayOptions"
                    :key="`cleanup-day-${item.periodKey}-${option.value}`"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
                <div class="report-setting-caption">只撤回月报通知，不影响日报和周报。</div>
              </div>

              <div class="report-setting-field">
                <label class="sales-filter-label">接收身份</label>
                <el-checkbox-group v-model="item.recipientRoleKeys" class="report-role-group">
                  <el-checkbox
                    v-for="role in reportRoleOptions"
                    :key="role.value"
                    :label="role.value"
                  >
                    {{ role.label }}
                  </el-checkbox>
                </el-checkbox-group>
              </div>

              <div class="report-setting-field">
                <label class="sales-filter-label">额外接收成员</label>
                <el-select
                  v-model="item.recipientUserIds"
                  multiple
                  filterable
                  clearable
                  collapse-tags
                  collapse-tags-tooltip
                  class="full-width"
                  placeholder="可按成员追加接收人"
                >
                  <el-option
                    v-for="member in reportRecipientOptions"
                    :key="member.value"
                    :label="member.label"
                    :value="member.value"
                  />
                </el-select>
              </div>

              <div class="report-setting-field">
                <label class="sales-filter-label">历史保留天数</label>
                <el-input-number
                  v-model="item.retentionDays"
                  :min="0"
                  :max="3650"
                  class="full-width"
                />
                <div class="report-setting-caption">`0` 表示不自动删除，默认建议月报保留为 `0`。</div>
              </div>
            </div>
          </article>
        </section>
      </div>

      <template #footer>
        <div class="form-actions report-settings-footer">
          <el-button @click="reportSettingsVisible = false">取消</el-button>
          <el-button @click="openReportTestDialog">报告测试</el-button>
          <el-button type="primary" :loading="reportSettingsSaving" @click="saveReportSettings">保存设置</el-button>
        </div>
      </template>
    </ResponsiveDialog>

    <ResponsiveDialog
      v-if="authStore.isAdmin"
      v-model="reportTestVisible"
      title="报告测试"
      width="560px"
      class="aqc-app-dialog report-test-dialog"
      mobile-subtitle="测试推送"
      :mobile-base-z-index="2800"
    >
      <el-form label-position="top" class="dialog-form report-test-form" @submit.prevent="submitReportTest">
        <el-form-item label="报告类型">
          <el-select v-model="reportTestForm.periodKey" class="full-width">
            <el-option
              v-for="item in reportSettings"
              :key="item.periodKey"
              :label="item.periodLabel"
              :value="item.periodKey"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="推送成员">
          <el-select
            v-model="reportTestForm.userIds"
            multiple
            filterable
            clearable
            collapse-tags
            collapse-tags-tooltip
            class="full-width"
            placeholder="请选择测试接收人"
          >
            <el-option
              v-for="member in reportRecipientOptions"
              :key="member.value"
              :label="member.label"
              :value="member.value"
            />
          </el-select>
        </el-form-item>

        <div class="report-test-hint">
          会立即生成上一周期的测试报告，并推送到所选成员的页眉通知中。
        </div>
      </el-form>

      <template #footer>
        <div class="form-actions">
          <el-button @click="reportTestVisible = false">取消</el-button>
          <el-button type="primary" :loading="reportTestSubmitting" @click="submitReportTest">确认推送</el-button>
        </div>
      </template>
    </ResponsiveDialog>

    <ResponsiveDialog
      v-model="inventoryLocationDetailVisible"
      :title="inventoryLocationDetail?.shopName || '库存分布详情'"
      width="min(860px, 96vw)"
      class="aqc-app-dialog report-location-dialog"
      mobile-subtitle="库存分布"
      :z-index="8500"
      :mobile-base-z-index="8500"
    >
      <template v-if="inventoryLocationDetail">
        <section class="report-drill-summary-grid">
          <article class="report-drill-summary-card">
            <span>当前库存</span>
            <strong>{{ formatInteger(inventoryLocationDetail.quantity) }}</strong>
          </article>
          <article class="report-drill-summary-card">
            <span>净变动</span>
            <strong :class="['report-drill-value', quantityChangeClass(inventoryLocationDetail.netChangeQuantity)]">
              {{ quantityChangeLabel(inventoryLocationDetail.netChangeQuantity) }}
            </strong>
          </article>
          <article class="report-drill-summary-card">
            <span>入库</span>
            <strong>{{ formatInteger(inventoryLocationDetail.changeInQuantity) }}</strong>
          </article>
          <article class="report-drill-summary-card">
            <span>出库</span>
            <strong>{{ formatInteger(inventoryLocationDetail.changeOutQuantity) }}</strong>
          </article>
        </section>

        <section class="report-drill-card">
          <header class="report-drill-card-head">
            <div>
              <strong>变动明细</strong>
              <p>{{ formatShopType(inventoryLocationDetail.shopType) }} · 共 {{ formatInteger(inventoryLocationDetail.changeCount) }} 次变化</p>
            </div>
          </header>

          <div v-if="inventoryLocationDetail.recentLogs?.length" class="report-drill-log-list">
            <article
              v-for="item in inventoryLocationDetail.recentLogs"
              :key="`${item.createdAt}-${item.goodsId || 0}-${item.goodsModel}-${item.changeContent}`"
              class="report-drill-log-row"
            >
              <div>
                <strong>{{ item.goodsModel || '未识别商品' }}</strong>
                <span>{{ item.changeContent || '-' }}</span>
              </div>
              <div class="report-detail-side">
                <span>{{ formatDateTime(item.createdAt) }}</span>
                <strong>{{ formatSignedInteger(item.delta) }}</strong>
              </div>
            </article>
          </div>
          <div v-else class="report-drill-empty">当前点位在本周期暂无库存变动。</div>
        </section>
      </template>

      <template #footer>
        <div class="form-actions">
          <el-button @click="inventoryLocationDetailVisible = false">关闭</el-button>
        </div>
      </template>
    </ResponsiveDialog>

    <ResponsiveDialog
      v-model="salespersonDetailVisible"
      :title="salespersonDetail?.name || '销售员详情'"
      width="min(1080px, 96vw)"
      class="aqc-app-dialog report-salesperson-dialog"
      mobile-subtitle="销售员排行榜"
      :z-index="8510"
      :mobile-base-z-index="8510"
    >
      <template v-if="salespersonDetail">
        <template v-if="isMobileViewport">
          <div class="report-salesperson-mobile-panel">
            <section class="goods-distribution-mobile-summary-bar">
              <article class="goods-distribution-mobile-summary-item">
                <span>销售额</span>
                <strong>¥ {{ formatMoney(salespersonDetail.salesAmount) }}</strong>
              </article>
              <article class="goods-distribution-mobile-summary-item">
                <span>订单数</span>
                <strong>{{ formatInteger(salespersonDetail.orderCount) }}</strong>
              </article>
            </section>

            <section class="goods-distribution-mobile-title">
              <strong>{{ salespersonDetail.name || '销售员详情' }}</strong>
              <p>共 {{ formatInteger(salespersonDetail.salesDetails?.length || 0) }} 条记录，销售件数 {{ formatInteger(salespersonDetail.quantity) }}，最高点位 {{ salespersonDetail.topShop?.shopName || '-' }}</p>
            </section>

            <section class="goods-distribution-mobile-summary-bar">
              <article class="goods-distribution-mobile-summary-item">
                <span>销售件数</span>
                <strong>{{ formatInteger(salespersonDetail.quantity) }}</strong>
              </article>
              <article class="goods-distribution-mobile-summary-item">
                <span>销售最高点位</span>
                <strong>{{ salespersonDetail.topShop?.shopName || '-' }}</strong>
              </article>
            </section>

            <section v-if="salespersonDetail.salesDetails?.length" class="goods-distribution-mobile-list report-salesperson-mobile-list">
              <article
                v-for="item in salespersonDetail.salesDetails"
                :key="`${item.soldAt}-${item.orderNum}-${item.goodsId || 0}-${item.goodsModel}`"
                class="goods-distribution-mobile-row"
              >
                <div class="goods-distribution-mobile-main">
                  <strong>{{ item.goodsModel || '未识别商品' }}</strong>
                  <span>{{ item.shopName || '-' }} · {{ item.orderNum || '无订单号' }}</span>
                </div>
                <div class="goods-distribution-mobile-side report-salesperson-mobile-side">
                  <small>{{ formatDateTime(item.soldAt) }}</small>
                  <strong>¥ {{ formatMoney(item.salesAmount) }}</strong>
                  <span>{{ formatInteger(item.quantity) }} 件</span>
                </div>
              </article>
            </section>
            <div v-else class="goods-distribution-mobile-empty">
              <strong>暂无销售明细</strong>
              <p>当前销售员在本周期暂无销售明细。</p>
            </div>
          </div>
        </template>

        <template v-else>
          <section class="report-drill-summary-grid report-salesperson-summary-grid">
            <article class="report-drill-summary-card">
              <span>销售额</span>
              <strong>¥ {{ formatMoney(salespersonDetail.salesAmount) }}</strong>
            </article>
            <article class="report-drill-summary-card">
              <span>订单数</span>
              <strong>{{ formatInteger(salespersonDetail.orderCount) }}</strong>
            </article>
            <article class="report-drill-summary-card">
              <span>销售件数</span>
              <strong>{{ formatInteger(salespersonDetail.quantity) }}</strong>
            </article>
            <article class="report-drill-summary-card">
              <span>销售最高点位</span>
              <strong>{{ salespersonDetail.topShop?.shopName || '-' }}</strong>
            </article>
          </section>

          <section class="report-drill-card">
            <header class="report-drill-card-head">
              <div>
                <strong>销售明细</strong>
                <p>共 {{ formatInteger(salespersonDetail.salesDetails?.length || 0) }} 条记录</p>
              </div>
            </header>

            <div v-if="salespersonDetail.salesDetails?.length" class="report-drill-log-list">
              <article
                v-for="item in salespersonDetail.salesDetails"
                :key="`${item.soldAt}-${item.orderNum}-${item.goodsId || 0}-${item.goodsModel}`"
                class="report-drill-log-row"
              >
                <div>
                  <strong>{{ item.goodsModel || '未识别商品' }}</strong>
                  <span>{{ item.shopName || '-' }} · {{ item.orderNum || '无订单号' }}</span>
                </div>
                <div class="report-detail-side">
                  <span>{{ formatDateTime(item.soldAt) }}</span>
                  <strong>{{ formatInteger(item.quantity) }} 件 · ¥ {{ formatMoney(item.salesAmount) }}</strong>
                </div>
              </article>
            </div>
            <div v-else class="report-drill-empty">当前销售员在本周期暂无销售明细。</div>
          </section>
        </template>
      </template>

      <template #footer>
        <div class="form-actions">
          <el-button @click="salespersonDetailVisible = false">关闭</el-button>
        </div>
      </template>
    </ResponsiveDialog>

    <ResponsiveDialog
      v-model="inventoryChangeActionVisible"
      :title="inventoryChangeAction?.goodsModel || '库存变动操作'"
      width="min(360px, 92vw)"
      class="aqc-app-dialog report-inventory-action-dialog"
      mobile-subtitle="库存变动"
      :z-index="8520"
      :mobile-base-z-index="8520"
    >
      <section class="work-order-category-chooser goods-distribution-action-chooser">
        <button
          type="button"
          class="work-order-category-card goods-distribution-action-card"
          :disabled="!canOpenInventoryDistribution(inventoryChangeAction)"
          @click="openDistributionForInventoryChange()"
        >
          <strong>分布</strong>
          <small>{{ inventoryChangeAction?.shopName || '当前商品' }} · 打开这个商品的库存分布</small>
        </button>
        <button
          type="button"
          class="work-order-category-card goods-distribution-action-card"
          :disabled="!canTraceInventoryChange(inventoryChangeAction)"
          @click="traceInventoryChange()"
        >
          <strong>追溯</strong>
          <small>{{ inventoryChangeAction?.changeContent || '打开关联的销售或工单' }}</small>
        </button>
      </section>
    </ResponsiveDialog>

    <ResponsiveDialog
      v-model="reportDistributionVisible"
      title="商品分布"
      width="min(1120px, 96vw)"
      class="aqc-app-dialog goods-distribution-dialog report-distribution-dialog"
      mobile-subtitle="报告中心"
      :z-index="8540"
      :mobile-base-z-index="8540"
    >
      <div class="goods-distribution-shell" v-loading="reportDistributionLoading">
        <template v-if="isMobileViewport">
          <div class="goods-distribution-mobile-panel">
            <section class="goods-distribution-mobile-summary-bar">
              <article class="goods-distribution-mobile-summary-item">
                <span>总库存</span>
                <strong>{{ reportDistributionTotalStock }}</strong>
              </article>
              <article class="goods-distribution-mobile-summary-item">
                <span>库存金额</span>
                <strong>¥ {{ formatMoney(reportDistributionTotalAmount) }}</strong>
              </article>
            </section>

            <section class="goods-distribution-mobile-title">
              <strong>{{ reportDistributionTitle || '当前商品' }}</strong>
              <p>{{ reportDistributionSubtitle || '库存分布' }}</p>
            </section>

            <div class="goods-distribution-mobile-utility">
              <el-button @click="openReportDistributionInventoryLog">库存日志</el-button>
            </div>

            <section class="goods-distribution-mobile-summary-bar">
              <article class="goods-distribution-mobile-summary-item">
                <span>有货点位</span>
                <strong>{{ reportDistributionPositiveCount }}</strong>
              </article>
              <article class="goods-distribution-mobile-summary-item">
                <span>点位明细</span>
                <strong>{{ reportDistributionRows.length }}</strong>
              </article>
            </section>
          </div>

          <section v-if="reportDistributionRows.length" class="goods-distribution-mobile-list">
            <article
              v-for="row in reportDistributionRows"
              :key="row.shopId"
              class="goods-distribution-mobile-row goods-distribution-row-actionable"
              role="button"
              tabindex="0"
              @click="openReportDistributionActionMenu(row)"
              @keyup.enter="openReportDistributionActionMenu(row)"
            >
              <div class="goods-distribution-mobile-main">
                <strong>{{ displayShopName(row.shopName || row.shopShortName) || '-' }}</strong>
                <span>{{ formatShopType(row.shopType) }}<template v-if="row.unitPrice"> · 单价 ¥ {{ formatMoney(row.unitPrice) }}</template></span>
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
        </template>

        <template v-else>
          <section class="inventory-hero-card inventory-hero-card-strong">
            <span>总库存</span>
            <strong>{{ reportDistributionTotalStock }}</strong>
            <h3>{{ reportDistributionTitle || '当前商品' }}</h3>
            <p>{{ reportDistributionSubtitle || '库存分布' }}</p>
            <div class="toolbar-actions inventory-hero-actions">
              <el-button @click="openReportDistributionInventoryLog">库存日志</el-button>
            </div>
          </section>

          <div class="table-shell open-table-shell inventory-table-shell">
            <el-table
              :data="reportDistributionRows"
              border
              stripe
              empty-text="暂无库存分布"
              show-summary
              :summary-method="reportDistributionTableSummary"
              @row-click="openReportDistributionActionMenu"
            >
              <el-table-column label="店铺 / 仓库名称" min-width="260" show-overflow-tooltip>
                <template #default="{ row }">{{ displayShopName(row.shopName || row.shopShortName) || '-' }}</template>
              </el-table-column>
              <el-table-column prop="quantity" label="库存数量" min-width="110" />
              <el-table-column prop="unitPrice" label="单价" min-width="120">
                <template #default="{ row }">¥ {{ formatMoney(row.unitPrice) }}</template>
              </el-table-column>
              <el-table-column prop="lineAmount" label="金额" min-width="140">
                <template #default="{ row }">¥ {{ formatMoney(row.lineAmount) }}</template>
              </el-table-column>
              <el-table-column label="点位类型" min-width="120">
                <template #default="{ row }">{{ formatShopType(row.shopType) }}</template>
              </el-table-column>
            </el-table>
          </div>
        </template>
      </div>

      <template #footer>
        <div class="form-actions">
          <el-button @click="reportDistributionVisible = false">关闭</el-button>
        </div>
      </template>
    </ResponsiveDialog>

    <ResponsiveDialog
      v-model="reportDistributionActionVisible"
      :title="reportDistributionActionTitle"
      width="min(360px, 92vw)"
      class="aqc-app-dialog goods-distribution-action-dialog report-distribution-action-dialog"
      mobile-subtitle="报告中心"
      :z-index="8550"
      :mobile-base-z-index="8550"
    >
      <section class="work-order-category-chooser goods-distribution-action-chooser">
        <button
          type="button"
          class="work-order-category-card goods-distribution-action-card"
          @click="createTransferFromReportDistribution"
        >
          <strong>调拨</strong>
          <small>{{ reportDistributionActionTitle }} · 基于当前点位创建商品调拨单</small>
        </button>
        <button
          type="button"
          class="work-order-category-card goods-distribution-action-card"
          @click="viewReportDistributionInventoryLogs"
        >
          <strong>日志</strong>
          <small>{{ reportDistributionActionTitle }} · 查看这个点位的库存变化记录</small>
        </button>
      </section>
    </ResponsiveDialog>
  </section>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import { ref, reactive, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import CollapsePanelTransition from '../components/CollapsePanelTransition.vue'
import ResponsiveDialog from '../components/ResponsiveDialog.vue'
import { apiGet, apiPost, apiPut } from '../services/api'
import { useAuthStore } from '../stores/auth'
import { useMobileViewport } from '../composables/useMobileViewport'
import { buildLogCenterQuery, sanitizeLogBackPath } from '../utils/logCenter'
import { displayShopName, normalizeLocationRow } from '../utils/shops'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { isMobileViewport } = useMobileViewport()
const DEFAULT_REPORT_ROLE_OPTIONS = [
  { value: 'aqc_admin', label: '管理员' },
  { value: 'aqc_manager', label: '店长' },
  { value: 'aqc_sales', label: '销售员' },
]
const REPORT_WEEKDAY_OPTIONS = [
  { value: 0, label: '周一' },
  { value: 1, label: '周二' },
  { value: 2, label: '周三' },
  { value: 3, label: '周四' },
  { value: 4, label: '周五' },
  { value: 5, label: '周六' },
  { value: 6, label: '周日' },
]
const REPORT_MONTH_DAY_OPTIONS = Array.from({ length: 31 }, (_, index) => ({
  value: index + 1,
  label: `${index + 1} 日`,
}))

const loading = ref(false)
const errorMessage = ref('')
const report = ref(null)
const expandedKeys = ref([])

const reportSettingsVisible = ref(false)
const reportTestVisible = ref(false)
const reportSettingsLoading = ref(false)
const reportSettingsSaving = ref(false)
const reportTestSubmitting = ref(false)
const reportSettings = ref([])
const reportRoleOptions = ref([])
const reportMembers = ref([])
const inventoryLocationDetailVisible = ref(false)
const inventoryLocationDetail = ref(null)
const salespersonDetailVisible = ref(false)
const salespersonDetail = ref(null)
const inventoryChangeActionVisible = ref(false)
const inventoryChangeAction = ref(null)
const reportDistributionVisible = ref(false)
const reportDistributionLoading = ref(false)
const reportDistributionRows = ref([])
const reportDistributionItem = ref(null)
const reportDistributionActionVisible = ref(false)
const reportDistributionActionRow = ref(null)
const reportTestForm = reactive({
  periodKey: 'day',
  userIds: [],
})

const reportId = computed(() => Number(route.query.report_id || 0) || null)
const returnPath = computed(() => sanitizeLogBackPath(route.query.back, '/reports'))
const reportRecipientOptions = computed(() => reportMembers.value
  .filter((item) => item?.isActive && item?.aqcRoleKey !== 'aqc_departed')
  .map((item) => ({
    value: Number(item.id || 0),
    label: [
      item.displayName || item.phone || item.username || `成员 ${item.id || ''}`,
      reportRoleOptions.value.find((role) => role.value === item.aqcRoleKey)?.label || item.aqcRoleKey || '未设置身份',
      formatShopNames(item),
    ].filter(Boolean).join(' · '),
  }))
  .filter((item) => item.value > 0))
const reportDistributionTotalStock = computed(() => (
  reportDistributionRows.value.reduce((sum, item) => sum + Number(item.quantity || 0), 0)
))
const reportDistributionTotalAmount = computed(() => (
  reportDistributionRows.value.reduce((sum, item) => sum + Number(item.lineAmount || 0), 0)
))
const reportDistributionPositiveCount = computed(() => (
  reportDistributionRows.value.filter((item) => Number(item.quantity || 0) > 0).length
))
const reportDistributionGoodsId = computed(() => (
  Number(reportDistributionItem.value?.id || reportDistributionItem.value?.goodsId || 0)
))
const reportDistributionTitle = computed(() => {
  const item = reportDistributionItem.value
  const named = [item?.brand, item?.series, item?.model].filter(Boolean).join(' ')
  return named || item?.goodsModel || item?.name || '当前商品'
})
const reportDistributionSubtitle = computed(() => {
  return [reportDistributionItem.value?.goodsBrand, reportDistributionItem.value?.goodsSeries]
    .filter(Boolean)
    .join(' / ') || '库存分布'
})
const reportDistributionActionTitle = computed(() => (
  displayShopName(reportDistributionActionRow.value?.shopName || reportDistributionActionRow.value?.shopShortName) || '库存点位操作'
))
const reportWeekdayOptions = REPORT_WEEKDAY_OPTIONS
const reportMonthDayOptions = REPORT_MONTH_DAY_OPTIONS

function formatShopNames(row) {
  const names = Array.isArray(row?.shopNames) ? row.shopNames.filter(Boolean) : []
  if (names.length) {
    return names.join('、')
  }
  return row?.shopName || ''
}

function normalizeReportSetting(item = {}) {
  return {
    id: Number(item.id || 0) || null,
    periodKey: String(item.periodKey || '').trim(),
    periodLabel: String(item.periodLabel || '').trim() || '报告',
    enabled: Boolean(item.enabled),
    recipientRoleKeys: Array.isArray(item.recipientRoleKeys) ? [...new Set(item.recipientRoleKeys.filter(Boolean))] : [],
    recipientUserIds: Array.isArray(item.recipientUserIds)
      ? [...new Set(item.recipientUserIds.map((value) => Number(value || 0)).filter((value) => value > 0))]
      : [],
    pushTime: String(item.pushTime || '07:00').trim() || '07:00',
    pushWeekday: Number(item.pushWeekday ?? 0),
    pushDayOfMonth: Math.min(Math.max(Number(item.pushDayOfMonth ?? 1) || 1, 1), 31),
    cleanupTime: String(item.cleanupTime || '23:59').trim() || '23:59',
    cleanupWeekday: Number(item.cleanupWeekday ?? 0),
    cleanupDayOfMonth: Math.min(Math.max(Number(item.cleanupDayOfMonth ?? 1) || 1, 1), 31),
    retentionDays: Math.max(Number(item.retentionDays || 0), 0),
    lastPeriodKey: String(item.lastPeriodKey || '').trim(),
    lastRunAt: String(item.lastRunAt || '').trim(),
  }
}

function orderedReportSettings(items = []) {
  const itemMap = new Map(items.map((item) => [item.periodKey, normalizeReportSetting(item)]))
  return ['day', 'week', 'month'].map((periodKey) => itemMap.get(periodKey) || normalizeReportSetting({
    periodKey,
    periodLabel: periodKey === 'day' ? '日报' : periodKey === 'week' ? '周报' : '月报',
    enabled: true,
    recipientRoleKeys: [],
    recipientUserIds: [],
    pushTime: '07:00',
    pushWeekday: 0,
    pushDayOfMonth: 1,
    cleanupTime: '23:59',
    cleanupWeekday: 0,
    cleanupDayOfMonth: 1,
    retentionDays: periodKey === 'month' ? 0 : 35,
  }))
}

function reportWeekdayLabel(value) {
  return reportWeekdayOptions.find((item) => Number(item.value) === Number(value))?.label || '周一'
}

function reportPushCaption(item) {
  if (item?.periodKey === 'week') {
    return `会在北京时间${reportWeekdayLabel(item.pushWeekday)} ${item.pushTime || '07:00'} 生成上一完整周。`
  }
  if (item?.periodKey === 'month') {
    return `会在北京时间每月 ${Number(item.pushDayOfMonth || 1)} 日 ${item.pushTime || '07:00'} 生成上一完整月。`
  }
  return '会在北京时间每日这个时间生成上一完整日。'
}

function reportCleanupCaption(item) {
  if (item?.periodKey === 'week') {
    return `会在北京时间${reportWeekdayLabel(item.cleanupWeekday)} ${item.cleanupTime || '23:59'} 撤回周报通知。`
  }
  if (item?.periodKey === 'month') {
    return `会在北京时间每月 ${Number(item.cleanupDayOfMonth || 1)} 日 ${item.cleanupTime || '23:59'} 撤回月报通知。`
  }
  return '会在北京时间每日这个时间撤回日报通知。'
}

function resolveRecommendedReportUserIds(periodKey) {
  const matched = reportSettings.value.find((item) => item.periodKey === periodKey)
  if (!matched) {
    return []
  }
  const selectedRoleKeys = new Set(matched.recipientRoleKeys || [])
  const selectedUserIds = new Set(matched.recipientUserIds || [])
  reportMembers.value.forEach((item) => {
    if (!item?.isActive || item?.aqcRoleKey === 'aqc_departed') {
      return
    }
    if (selectedRoleKeys.has(item.aqcRoleKey)) {
      selectedUserIds.add(Number(item.id || 0))
    }
  })
  return [...selectedUserIds].filter((value) => value > 0)
}

function formatMoney(value) {
  return Number(value || 0).toFixed(2)
}

function formatInteger(value) {
  return String(Number(value || 0))
}

function formatSignedInteger(value) {
  const amount = Number(value || 0)
  if (amount > 0) return `+${amount}`
  return String(amount)
}

function quantityChangeLabel(value) {
  const amount = Number(value || 0)
  if (amount > 0) return `+${amount}`
  if (amount < 0) return String(amount)
  return '-'
}

function quantityChangeClass(value) {
  const amount = Number(value || 0)
  if (amount > 0) return 'positive'
  if (amount < 0) return 'negative'
  return 'neutral'
}

function formatShopType(shopType) {
  return Number(shopType || 0) === 1
    ? '仓库'
    : Number(shopType || 0) === 2
      ? '其他仓库'
      : Number(shopType || 0) === 3
        ? '维修点'
        : '店铺'
}

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '--'
  }
  const amount = Number(value || 0)
  return `${amount >= 0 ? '+' : ''}${amount.toFixed(2)}%`
}

function formatRate(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '--'
  }
  return `${(Number(value || 0) * 100).toFixed(2)}%`
}

function formatRatio(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '--'
  }
  return Number(value || 0).toFixed(2)
}

function formatDateTime(value) {
  const text = String(value || '').trim()
  if (!text) return '-'
  return text.replace('T', ' ').slice(0, 16)
}

function isExpanded(key) {
  return expandedKeys.value.includes(key)
}

function toggleDetails(key) {
  if (isExpanded(key)) {
    expandedKeys.value = expandedKeys.value.filter((item) => item !== key)
    return
  }
  expandedKeys.value = [...expandedKeys.value, key]
}

function openInventoryLocationDetail(item) {
  inventoryLocationDetail.value = item || null
  inventoryLocationDetailVisible.value = Boolean(item)
}

function openSalespersonDetail(item) {
  salespersonDetail.value = item || null
  salespersonDetailVisible.value = Boolean(item)
}

function parseTraceToken(text, label) {
  const source = String(text || '').trim()
  if (!source) {
    return ''
  }
  const matcher = source.match(new RegExp(`${label}\\s*[:：]?\\s*([A-Za-z0-9_-]+)`))
  return String(matcher?.[1] || '').trim()
}

function buildInventoryTraceTarget(item) {
  if (!item) {
    return null
  }
  const relatedType = String(item.relatedType || '').trim().toLowerCase()
  const relatedId = Number(item.relatedId || 0)
  const workOrderNum = parseTraceToken(item.changeContent, '工单')
  const saleOrderNum = parseTraceToken(item.changeContent, '订单')

  if ((relatedType === 'work_order' && relatedId) || workOrderNum) {
    return {
      name: 'work-orders',
      query: {
        scope: authStore.isAdmin ? 'all' : 'mine',
        ...(workOrderNum ? { keyword: workOrderNum } : {}),
        ...(relatedType === 'work_order' && relatedId ? { spotlight_work_order: String(relatedId) } : {}),
      },
    }
  }

  if (relatedType === 'sale_record' && relatedId) {
    return {
      name: 'sales-records',
      query: {
        spotlight_sale_record: String(relatedId),
      },
    }
  }

  if (saleOrderNum) {
    return {
      name: 'sales-records',
      query: {
        spotlight_order_num: saleOrderNum,
      },
    }
  }

  return null
}

function canTraceInventoryChange(item) {
  return Boolean(buildInventoryTraceTarget(item))
}

function openInventoryChangeAction(item) {
  inventoryChangeAction.value = item || null
  inventoryChangeActionVisible.value = Boolean(item)
}

function canOpenInventoryDistribution(item) {
  return Number(item?.goodsId || 0) > 0
}

function primeReportDistributionState(payload, fallbackItem = null) {
  const unitPrice = Number(payload?.item?.price || fallbackItem?.price || 0)
  reportDistributionItem.value = payload?.item || fallbackItem || null
  reportDistributionRows.value = (payload?.inventories || []).map((item) => {
    const normalized = normalizeLocationRow(item, item.shopType)
    return {
      ...normalized,
      unitPrice,
      lineAmount: unitPrice * Number(normalized.quantity || 0),
    }
  }).sort((left, right) => {
    const quantityGap = Number(right.quantity || 0) - Number(left.quantity || 0)
    if (quantityGap !== 0) {
      return quantityGap
    }
    return String(left.shopName || left.shopShortName || '').localeCompare(String(right.shopName || right.shopShortName || ''), 'zh-CN')
  })
}

async function openDistributionForInventoryChange(item = inventoryChangeAction.value) {
  const goodsId = Number(item?.goodsId || 0)
  if (!goodsId) {
    ElMessage.warning('当前商品信息未准备完成')
    return
  }
  inventoryChangeActionVisible.value = false
  reportDistributionVisible.value = true
  reportDistributionLoading.value = true
  const payload = await apiGet(`/goods/items/${goodsId}/inventory`, {
    token: authStore.token,
    timeoutMs: 12000,
  })
  reportDistributionLoading.value = false
  if (!payload?.success) {
    reportDistributionVisible.value = false
    ElMessage.error(payload?.message || '商品分布加载失败')
    return
  }
  primeReportDistributionState(payload, item)
}

async function openReportDistributionInventoryLog() {
  const goodsId = reportDistributionGoodsId.value
  if (!goodsId) {
    ElMessage.warning('当前商品信息未准备完成')
    return
  }
  reportDistributionActionVisible.value = false
  reportDistributionVisible.value = false
  await router.push({
    name: 'log-center',
    query: buildLogCenterQuery({
      type: 'goods_inventory',
      item_id: String(goodsId),
      subject_name: reportDistributionTitle.value,
      back: route.fullPath,
    }),
  })
}

function openReportDistributionActionMenu(row) {
  if (!row?.shopId) {
    ElMessage.warning('当前点位信息未准备完成')
    return
  }
  if (!reportDistributionGoodsId.value) {
    ElMessage.warning('当前商品信息未准备完成')
    return
  }
  reportDistributionActionRow.value = row
  if (isMobileViewport.value) {
    reportDistributionVisible.value = false
    window.setTimeout(() => {
      reportDistributionActionVisible.value = true
    }, 0)
    return
  }
  reportDistributionActionVisible.value = true
}

async function createTransferFromReportDistribution() {
  const sourceShopId = Number(reportDistributionActionRow.value?.shopId || 0)
  const goodsId = reportDistributionGoodsId.value
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
  reportDistributionActionVisible.value = false
  reportDistributionVisible.value = false
  await router.push({ name: 'work-orders', query: nextQuery })
  if (!defaultTargetShopId) {
    ElMessage.info('已带入商品和调出点位，请在工单中补选调入店铺 / 仓库')
    return
  }
  if (defaultTargetShopId === sourceShopId) {
    ElMessage.warning('已带入商品和调出点位，当前账号默认店铺与调出点位相同，请在工单中改选调入店铺 / 仓库')
  }
}

async function viewReportDistributionInventoryLogs() {
  const sourceShopId = Number(reportDistributionActionRow.value?.shopId || 0)
  const goodsId = reportDistributionGoodsId.value
  if (!sourceShopId || !goodsId) {
    ElMessage.warning('当前商品分布信息未准备完成')
    return
  }
  const sourceLabel = displayShopName(reportDistributionActionRow.value?.shopName || reportDistributionActionRow.value?.shopShortName) || '当前点位'
  reportDistributionActionVisible.value = false
  reportDistributionVisible.value = false
  await router.push({
    name: 'log-center',
    query: buildLogCenterQuery({
      type: 'goods_inventory',
      item_id: String(goodsId),
      shop_id: String(sourceShopId),
      subject_name: `${sourceLabel} · ${reportDistributionTitle.value}`,
      back: route.fullPath,
    }),
  })
}

async function traceInventoryChange() {
  const target = buildInventoryTraceTarget(inventoryChangeAction.value)
  if (!target) {
    ElMessage.warning('当前库存记录缺少可追溯的销售或工单')
    return
  }
  inventoryChangeActionVisible.value = false
  await router.push(target)
}

function reportDistributionTableSummary({ columns, data }) {
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

async function loadReport() {
  loading.value = true
  errorMessage.value = ''
  try {
    const payload = reportId.value
      ? await apiGet(`/reports/${reportId.value}`, { token: authStore.token })
      : await apiGet('/reports/latest', { token: authStore.token })
    if (!payload?.success) {
      errorMessage.value = payload?.message || '报告加载失败'
      report.value = null
      return
    }
    report.value = payload.report || null
  } finally {
    loading.value = false
  }
}

async function loadReportMembers() {
  const payload = await apiGet('/admin/users', { token: authStore.token })
  if (!payload?.success) {
    reportMembers.value = []
    throw new Error(payload?.message || '成员列表加载失败')
  }
  reportMembers.value = payload.users || []
}

async function loadReportSettings() {
  reportSettingsLoading.value = true
  try {
    const payload = await apiGet('/reports/settings', { token: authStore.token })
    if (!payload?.success) {
      throw new Error(payload?.message || '报告设置加载失败')
    }
    reportRoleOptions.value = Array.isArray(payload.roleOptions) && payload.roleOptions.length
      ? payload.roleOptions
      : DEFAULT_REPORT_ROLE_OPTIONS
    reportSettings.value = orderedReportSettings(Array.isArray(payload.settings) ? payload.settings : [])
    if (!reportSettings.value.some((item) => item.periodKey === reportTestForm.periodKey)) {
      reportTestForm.periodKey = reportSettings.value[0]?.periodKey || 'day'
    }
    reportTestForm.userIds = resolveRecommendedReportUserIds(reportTestForm.periodKey)
  } finally {
    reportSettingsLoading.value = false
  }
}

async function openReportSettings() {
  try {
    await Promise.all([loadReportSettings(), loadReportMembers()])
    reportSettingsVisible.value = true
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '报告设置加载失败')
  }
}

function openReportTestDialog() {
  if (!reportSettings.value.length) {
    ElMessage.warning('请先加载报告设置')
    return
  }
  reportTestForm.userIds = []
  reportTestVisible.value = true
}

async function saveReportSettings() {
  reportSettingsSaving.value = true
  const payload = await apiPut('/reports/settings', {
    settings: reportSettings.value.map((item) => ({
      periodKey: item.periodKey,
      enabled: item.enabled,
      recipientRoleKeys: item.recipientRoleKeys || [],
      recipientUserIds: item.recipientUserIds || [],
      pushTime: item.pushTime,
      pushWeekday: item.pushWeekday,
      pushDayOfMonth: item.pushDayOfMonth,
      cleanupTime: item.cleanupTime,
      cleanupWeekday: item.cleanupWeekday,
      cleanupDayOfMonth: item.cleanupDayOfMonth,
      retentionDays: item.retentionDays,
    })),
  }, { token: authStore.token })
  reportSettingsSaving.value = false

  if (!payload?.success) {
    ElMessage.error(payload?.message || '报告设置保存失败')
    return
  }

  reportSettings.value = orderedReportSettings(Array.isArray(payload.settings) ? payload.settings : [])
  ElMessage.success(payload?.message || '报告设置已保存')
  reportSettingsVisible.value = false
}

async function submitReportTest() {
  if (!reportTestForm.userIds.length) {
    ElMessage.warning('请选择至少一位测试成员')
    return
  }
  reportTestSubmitting.value = true
  const payload = await apiPost('/reports/test', {
    periodKey: reportTestForm.periodKey,
    userIds: reportTestForm.userIds,
  }, { token: authStore.token })
  reportTestSubmitting.value = false

  if (!payload?.success) {
    ElMessage.error(payload?.message || '报告测试推送失败')
    return
  }

  ElMessage.success(payload?.message || '报告测试推送成功')
  reportTestVisible.value = false
}

async function openReportHistory() {
  await router.push({
    name: 'log-center',
    query: {
      type: 'report',
      back: route.fullPath,
    },
  })
}

function goBack() {
  if (returnPath.value && returnPath.value !== route.fullPath) {
    router.push(returnPath.value)
    return
  }
  if (window.history.length > 1) {
    router.back()
    return
  }
  router.push({ name: 'dashboard' })
}

watch(
  () => reportTestForm.periodKey,
  () => {
    reportTestForm.userIds = []
  },
)

watch(
  () => route.query.report_id,
  () => {
    expandedKeys.value = []
    inventoryLocationDetailVisible.value = false
    inventoryLocationDetail.value = null
    salespersonDetailVisible.value = false
    salespersonDetail.value = null
    inventoryChangeActionVisible.value = false
    inventoryChangeAction.value = null
    reportDistributionVisible.value = false
    reportDistributionRows.value = []
    reportDistributionItem.value = null
    reportDistributionActionVisible.value = false
    reportDistributionActionRow.value = null
    void loadReport()
  },
  { immediate: true },
)
</script>

<style scoped>
.report-center-page {
  display: grid;
  gap: 16px;
  width: 100%;
}

.report-center-page > * {
  min-width: 0;
}

.report-page-intro,
.report-center-hero,
.report-summary-card,
.report-highlight-card,
.report-module-card,
.report-empty-card {
  box-sizing: border-box;
  overflow: hidden;
  padding: 24px;
}

.report-page-intro-copy,
.report-center-hero-copy {
  display: grid;
  gap: 8px;
}

.report-page-intro-copy h2,
.report-center-hero-copy h3,
.report-card-head h3,
.report-module-head h3 {
  margin: 0;
}

.report-page-intro-copy p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.report-center-hero {
  display: grid;
  gap: 18px;
}

.report-center-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  color: var(--text-secondary);
  font-size: 13px;
}

.report-center-hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;
}

.report-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.report-summary-card,
.report-metric-item {
  display: grid;
  gap: 6px;
}

.report-summary-card {
  min-height: 132px;
  align-content: start;
}

.report-summary-card span,
.report-metric-item span,
.report-summary-card small {
  color: var(--text-light);
  font-size: 12px;
}

.report-summary-card strong,
.report-metric-item strong {
  color: var(--text-primary);
  font-size: 22px;
  line-height: 1.2;
}

.report-highlight-card,
.report-module-card,
.report-empty-card,
.report-settings-shell,
.report-settings-stack,
.report-setting-card,
.report-setting-grid,
.report-setting-field,
.report-settings-overview {
  display: grid;
  gap: 16px;
}

.report-highlight-list,
.report-module-highlight-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.report-highlight-chip,
.report-module-highlight-list span {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0 14px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--field-bg) 92%, transparent);
  color: var(--text-primary);
  font-size: 13px;
  border: 1px solid transparent;
}

.report-module-list {
  display: grid;
  gap: 16px;
}

.report-module-card {
  align-content: start;
}

.report-module-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.report-metric-grid,
.report-detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.report-metric-item {
  padding: 16px 18px;
  border-radius: 20px;
  background: color-mix(in srgb, var(--field-bg) 82%, transparent);
  border: 1px solid color-mix(in srgb, var(--accent-color) 12%, var(--border-color));
}

.report-detail-grid {
  margin-top: 4px;
  padding-top: 2px;
}

.report-detail-section {
  display: grid;
  gap: 12px;
  padding: 16px;
  border-radius: 22px;
  background: color-mix(in srgb, var(--field-bg) 82%, transparent);
  border: 1px solid color-mix(in srgb, var(--accent-color) 12%, var(--border-color));
}

.report-detail-section-full {
  grid-column: span 2;
}

.report-detail-section-scroll {
  grid-template-rows: auto minmax(0, 1fr);
  height: 440px;
}

.report-detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.report-detail-list {
  display: grid;
  gap: 10px;
}

.report-detail-list-scroll {
  min-height: 0;
  overflow-y: auto;
  padding-right: 4px;
  align-content: start;
}

.report-detail-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 18px;
  background: color-mix(in srgb, var(--bg-elevated) 92%, transparent);
  border: 1px solid color-mix(in srgb, var(--border-light) 90%, transparent);
}

.report-detail-row-actionable {
  cursor: pointer;
  transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease;
}

.report-detail-row-actionable:hover,
.report-detail-row-actionable:focus-visible {
  outline: none;
  transform: translateY(-1px);
  border-color: color-mix(in srgb, var(--accent-color) 28%, var(--border-color));
  background: color-mix(in srgb, var(--button-tint-bg) 26%, var(--bg-elevated));
}

.report-detail-row div,
.report-detail-side {
  display: grid;
  gap: 4px;
}

.report-detail-side-inline {
  display: inline-flex;
  align-items: baseline;
  justify-content: flex-end;
  gap: 8px;
}

.report-detail-row span,
.report-setting-caption {
  color: var(--text-light);
  font-size: 12px;
}

.report-detail-row strong {
  color: var(--text-primary);
  font-size: 14px;
}

.report-quantity-change {
  font-weight: 700;
}

.report-quantity-change.positive,
.report-drill-value.positive {
  color: #c68f1f;
}

.report-quantity-change.negative,
.report-drill-value.negative {
  color: #d44b4b;
}

.report-quantity-change.neutral,
.report-drill-value.neutral {
  color: var(--text-light);
}

.report-drill-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.report-drill-summary-card,
.report-drill-card {
  border-radius: 22px;
  border: 1px solid color-mix(in srgb, var(--accent-color) 12%, var(--border-color));
  background: color-mix(in srgb, var(--field-bg) 86%, transparent);
}

.report-drill-summary-card {
  display: grid;
  gap: 6px;
  padding: 16px 18px;
}

.report-drill-summary-card span,
.report-drill-card-head p,
.report-drill-log-row span,
.report-drill-empty {
  color: var(--text-light);
  font-size: 12px;
}

.report-drill-summary-card strong,
.report-drill-card-head strong,
.report-drill-log-row strong {
  color: var(--text-primary);
}

.report-drill-card {
  display: grid;
  gap: 12px;
  padding: 16px;
}

.report-salesperson-summary-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.report-salesperson-mobile-panel {
  display: grid;
  gap: 12px;
}

.report-salesperson-mobile-list {
  max-height: min(56vh, 520px);
  overflow-y: auto;
  padding-right: 2px;
}

.report-salesperson-mobile-side {
  min-width: 112px;
}

.report-drill-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.report-drill-card-head p {
  margin: 4px 0 0;
}

.report-drill-log-list {
  display: grid;
  gap: 10px;
  max-height: 420px;
  overflow-y: auto;
  padding-right: 4px;
}

.report-drill-log-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 18px;
  background: color-mix(in srgb, var(--bg-elevated) 92%, transparent);
  border: 1px solid color-mix(in srgb, var(--border-light) 90%, transparent);
}

.report-drill-empty {
  padding: 16px;
  border-radius: 18px;
  background: color-mix(in srgb, var(--bg-elevated) 92%, transparent);
}

.report-module-footer {
  display: flex;
  justify-content: flex-end;
  padding-top: 4px;
}

.report-module-footer :deep(.el-button) {
  min-width: 104px;
}

.report-empty-card strong {
  font-size: 20px;
}

.report-empty-card p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.report-settings-overview {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.report-settings-overview-card,
.report-setting-card,
.report-test-hint {
  border-radius: 24px;
  border: 1px solid color-mix(in srgb, var(--accent-color) 12%, var(--border-color));
  background: color-mix(in srgb, var(--field-bg) 86%, transparent);
}

.report-settings-overview-card,
.report-setting-card {
  padding: 18px;
}

.report-settings-overview-card span,
.report-setting-copy p,
.report-test-hint {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.report-settings-overview-card strong,
.report-setting-copy h3 {
  color: var(--text-primary);
  margin: 0;
}

.report-settings-overview-card p,
.report-setting-copy p {
  margin: 0;
}

.report-setting-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.report-setting-copy {
  display: grid;
  gap: 6px;
}

.report-setting-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.report-role-group {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
}

.report-settings-footer {
  justify-content: flex-end;
}

.report-test-form {
  display: grid;
  gap: 8px;
}

.report-test-hint {
  padding: 14px 16px;
}

@media (max-width: 980px) {
  .report-summary-grid,
  .report-metric-grid,
  .report-detail-grid,
  .report-setting-grid,
  .report-drill-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .report-salesperson-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .report-settings-overview,
  .report-setting-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .report-setting-head,
  .report-center-hero {
    align-items: stretch;
  }
}

@media (max-width: 680px) {
  .report-page-intro,
  .report-center-hero,
  .report-summary-card,
  .report-highlight-card,
  .report-module-card,
  .report-empty-card {
    padding: 20px;
  }

  .report-summary-grid,
  .report-metric-grid,
  .report-detail-grid,
  .report-drill-summary-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .report-salesperson-summary-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .report-detail-section-full {
    grid-column: span 1;
  }

  .report-detail-section-scroll {
    height: 360px;
  }

  .report-detail-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .report-drill-log-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .report-center-hero-actions {
    justify-content: flex-start;
  }

  .report-summary-card {
    min-height: unset;
  }
}
</style>
