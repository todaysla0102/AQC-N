<template>
  <section class="account-admin-grid">
    <section class="catalog-controls card-surface motion-fade-slide" style="--motion-delay: 0.08s">
      <div class="goods-search-shell account-admin-search-shell">
        <el-input
          v-model.trim="keyword"
          clearable
          class="goods-search-input"
          placeholder="搜索账号 / 姓名 / 门店 / 手机号"
          @keyup.enter="onSearch"
        />

        <div class="toolbar-actions goods-search-actions account-admin-search-actions">
          <el-button :loading="loading" @click="onSearch">查询</el-button>
          <el-button @click="onResetFilters">重置</el-button>
          <el-button v-if="notificationSupported" @click="sendTestNotification">测试通知</el-button>
          <el-button type="primary" @click="openCreateDialog">新增账户</el-button>
        </div>
      </div>

      <section class="sales-filter-shell goods-filter-shell">
        <div class="sales-filter-trigger-row">
          <button type="button" class="sales-filter-trigger" :class="{ active: filterPanelOpen }" @click="filterPanelOpen = !filterPanelOpen">
            <div class="sales-filter-trigger-copy">
              <span>筛选</span>
              <strong>{{ filterPanelOpen ? '收起账户筛选' : '展开账户筛选' }}</strong>
            </div>
            <div class="sales-filter-trigger-meta">
              <div class="sales-filter-trigger-stats">
                <span>已筛选 {{ activeFilterCount }} 项</span>
                <strong>{{ filteredUsers.length }} 条结果</strong>
              </div>
            </div>
          </button>
        </div>

        <CollapsePanelTransition>
          <div v-if="filterPanelOpen" class="sales-filter-collapse-shell">
            <section class="sales-filter-panel goods-filter-panel account-admin-filter-panel">
              <header class="sales-filter-head">
              <div class="sales-filter-head-copy">
                <h2>筛选</h2>
                <span>{{ filteredUsers.length }} 条结果</span>
              </div>
              <div class="toolbar-actions sales-filter-head-actions">
                <el-button type="primary" :loading="loading" @click="onSearch">查询</el-button>
                <el-button class="sales-filter-reset-btn" :disabled="!activeFilterCount" @click="onResetFilters">清空筛选</el-button>
              </div>
            </header>

              <div class="sales-filter-grid goods-filter-grid">
              <div class="sales-filter-field">
                <label class="sales-filter-label">门店</label>
                <el-select
                  v-model="shopFilter"
                  clearable
                  filterable
                  placeholder="全部门店"
                  class="full-width"
                  @change="onSearch"
                >
                  <el-option v-for="item in shopOptions" :key="item.id" :label="item.name" :value="item.name" />
                </el-select>
              </div>

              <div class="sales-filter-field">
                <label class="sales-filter-label">身份</label>
                <el-select
                  v-model="roleFilter"
                  clearable
                  placeholder="全部身份"
                  class="full-width"
                  @change="onSearch"
                >
                  <el-option v-for="item in roleOptions" :key="item.value" :label="item.label" :value="item.value" />
                </el-select>
              </div>
              </div>
            </section>
          </div>
        </CollapsePanelTransition>
      </section>
    </section>

    <article class="card-surface account-users-panel motion-fade-slide" style="--motion-delay: 0.16s">

      <div class="table-shell open-table-shell">
        <el-table :data="pagedUsers" border stripe v-loading="loading">
          <el-table-column label="账号" min-width="138">
            <template #default="{ row }">{{ displayAccount(row) }}</template>
          </el-table-column>
          <el-table-column prop="displayName" label="姓名" min-width="120" />
          <el-table-column label="门店" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">{{ formatShopNames(row) }}</template>
          </el-table-column>
          <el-table-column prop="employmentDate" label="入职时间" min-width="128" />
          <el-table-column label="身份" min-width="120">
            <template #default="{ row }">
              <span class="role-badge">{{ row.aqcRoleName }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.isActive ? 'success' : 'info'">{{ row.isActive ? '启用' : '停用' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="权限" min-width="210" show-overflow-tooltip>
            <template #default="{ row }">{{ formatPermissionSummary(row) }}</template>
          </el-table-column>
          <el-table-column prop="lastLoginAt" label="最近登录" min-width="160" />
          <el-table-column label="操作" :width="actionColumnWidth" fixed="right">
            <template #default="{ row }">
              <ResponsiveTableActions>
                <el-button text type="primary" @click="editRow(row)">编辑</el-button>
                <el-button text type="danger" @click="removeRow(row.id)">删除</el-button>
              </ResponsiveTableActions>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="pager-wrap">
        <el-pagination
          background
          :layout="pagerLayout"
          :total="filteredUsers.length"
          :current-page="page"
          :page-size="pageSize"
          :page-sizes="[20, 50, 100]"
          @current-change="onPageChange"
          @size-change="onPageSizeChange"
        />
      </div>
    </article>

    <el-alert v-if="message" :title="message" :type="isError ? 'error' : 'success'" :closable="false" show-icon />

    <ResponsiveDialog v-model="editorVisible" :title="dialogTitle" width="680px" class="aqc-app-dialog account-admin-editor-dialog" mobile-subtitle="管理员设置">
      <el-alert v-if="editorMessage" :title="editorMessage" :type="editorMessageIsError ? 'error' : 'success'" :closable="false" show-icon />

      <el-form label-position="top" class="dialog-form" @submit.prevent="submitDialogForm">
        <div class="dialog-grid">
          <el-form-item label="账号（手机号）">
            <el-input v-model.trim="dialogForm.accountPhone" maxlength="20" placeholder="请输入 11 位手机号" />
          </el-form-item>
          <el-form-item label="姓名">
            <el-input v-model.trim="dialogForm.displayName" placeholder="请输入姓名" />
          </el-form-item>
          <el-form-item label="身份">
            <el-select v-model="dialogForm.aqcRoleKey" class="full-width">
              <el-option v-for="item in roleOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="所属门店 / 维修点（可多选）">
            <el-select
              v-model="dialogForm.shopIds"
              multiple
              clearable
              filterable
              collapse-tags
              collapse-tags-tooltip
              class="full-width"
              placeholder="不选择则不绑定门店"
            >
              <el-option v-for="item in shopOptions" :key="item.id" :label="item.name" :value="item.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="入职时间">
            <el-date-picker
              v-model="dialogForm.employmentDate"
              type="date"
              value-format="YYYY-MM-DD"
              class="full-width"
              placeholder="请选择入职时间"
            />
          </el-form-item>
          <el-form-item :label="editingId ? '新密码' : '初始密码（至少 8 位）'">
            <el-input
              v-model.trim="dialogForm.password"
              type="password"
              show-password
              :placeholder="editingId ? '留空则不修改' : '请输入至少 8 位密码'"
            />
          </el-form-item>
        </div>

        <el-form-item>
          <el-checkbox v-model="dialogForm.isActive">启用该账户</el-checkbox>
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="form-actions">
          <el-button @click="closeEditor">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="submitDialogForm">{{ editingId ? '保存修改' : '创建账户' }}</el-button>
        </div>
      </template>
    </ResponsiveDialog>

    <ResponsiveDialog
      v-model="reportSettingsVisible"
      title="报告设置"
      width="900px"
      class="aqc-app-dialog report-settings-dialog"
      mobile-subtitle="管理员设置"
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
                  placeholder="可按成员追加测试或旁路接收人"
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
  </section>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import CollapsePanelTransition from '../components/CollapsePanelTransition.vue'
import ResponsiveDialog from '../components/ResponsiveDialog.vue'
import ResponsiveTableActions from '../components/ResponsiveTableActions.vue'
import { useMobileViewport } from '../composables/useMobileViewport'
import { apiDelete, apiGet, apiPost, apiPut } from '../services/api'
import { useAuthStore } from '../stores/auth'
import { formatPermissionSummaryFromUser } from '../utils/permissions'
import { confirmDestructiveAction } from '../utils/confirm'
import { resolveTableActionWidth } from '../utils/tableActions'

const authStore = useAuthStore()
const { isMobileViewport } = useMobileViewport()

const roleOptions = [
  { value: 'aqc_admin', label: '管理员' },
  { value: 'aqc_manager', label: '店长' },
  { value: 'aqc_sales', label: '销售员' },
  { value: 'aqc_engineer', label: '工程师' },
  { value: 'aqc_departed', label: '离职人员' },
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
const submitting = ref(false)
const keyword = ref('')
const shopFilter = ref('')
const roleFilter = ref('')
const appliedKeyword = ref('')
const appliedShopFilter = ref('')
const appliedRoleFilter = ref('')
const filterPanelOpen = ref(false)
const editingId = ref(null)
const editorVisible = ref(false)
const message = ref('')
const isError = ref(false)
const editorMessage = ref('')
const editorMessageIsError = ref(false)
const users = ref([])
const shopOptions = ref([])
const page = ref(1)
const pageSize = ref(20)
const reportSettingsVisible = ref(false)
const reportTestVisible = ref(false)
const reportSettingsLoading = ref(false)
const reportSettingsSaving = ref(false)
const reportTestSubmitting = ref(false)
const reportSettings = ref([])
const reportRoleOptions = ref([])
const actionColumnWidth = computed(() => resolveTableActionWidth([['编辑', '删除']], {
  compact: isMobileViewport.value,
  minWidth: 112,
  maxWidth: 180,
}))
const pagerLayout = computed(() => (isMobileViewport.value ? 'prev, pager, next' : 'total, prev, pager, next, sizes'))
const activeFilterCount = computed(() => [appliedKeyword.value, appliedShopFilter.value, appliedRoleFilter.value].filter(Boolean).length)
const notificationSupported = typeof window !== 'undefined' && typeof Notification !== 'undefined'

const dialogForm = reactive({
  accountPhone: '',
  displayName: '',
  aqcRoleKey: 'aqc_sales',
  shopIds: [],
  employmentDate: '',
  password: '',
  isActive: true,
})
const reportTestForm = reactive({
  periodKey: 'day',
  userIds: [],
})

const dialogTitle = computed(() => (editingId.value ? '编辑账户' : '新增账户'))
const defaultReportRoleOptions = computed(() => roleOptions
  .filter((item) => ['aqc_admin', 'aqc_manager', 'aqc_sales'].includes(item.value))
  .map((item) => ({ value: item.value, label: item.label })))
const reportWeekdayOptions = REPORT_WEEKDAY_OPTIONS
const reportMonthDayOptions = REPORT_MONTH_DAY_OPTIONS
const reportRecipientOptions = computed(() => users.value
  .filter((item) => item?.isActive && item?.aqcRoleKey !== 'aqc_departed')
  .map((item) => ({
    value: Number(item.id || 0),
    label: [
      item.displayName || item.phone || item.username || `成员 ${item.id || ''}`,
      roleOptions.find((role) => role.value === item.aqcRoleKey)?.label || item.aqcRoleKey || '未设置身份',
      formatShopNames(item) !== '-' ? formatShopNames(item) : '',
    ].filter(Boolean).join(' · '),
  }))
  .filter((item) => item.value > 0))

function setMessage(text, error = false) {
  message.value = text
  isError.value = error
}

function setEditorMessage(text, error = false) {
  editorMessage.value = text
  editorMessageIsError.value = error
  if (!String(text || '').trim()) {
    return
  }
  if (error) {
    ElMessage.error(text)
    return
  }
  ElMessage.success(text)
}

function displayAccount(row) {
  return row.phone || row.username || '-'
}

function formatPermissionSummary(row) {
  return formatPermissionSummaryFromUser(row)
}

function formatShopNames(row) {
  const names = Array.isArray(row?.shopNames) ? row.shopNames.filter(Boolean) : []
  if (names.length) {
    return names.join('、')
  }
  return row?.shopName || '-'
}

function resetDialogForm() {
  editingId.value = null
  dialogForm.accountPhone = ''
  dialogForm.displayName = ''
  dialogForm.aqcRoleKey = 'aqc_sales'
  dialogForm.shopIds = []
  dialogForm.employmentDate = ''
  dialogForm.password = ''
  dialogForm.isActive = true
  editorMessage.value = ''
  editorMessageIsError.value = false
}

function closeEditor() {
  editorVisible.value = false
  resetDialogForm()
}

function openCreateDialog() {
  resetDialogForm()
  editorVisible.value = true
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
    updatedAt: String(item.updatedAt || '').trim(),
  }
}

function orderedReportSettings(items = []) {
  const itemMap = new Map(items.map((item) => [item.periodKey, normalizeReportSetting(item)]))
  return ['day', 'week', 'month'].map((periodKey) => itemMap.get(periodKey) || normalizeReportSetting({
    periodKey,
    periodLabel: periodKey === 'day' ? '日报' : periodKey === 'week' ? '周报' : '月报',
    enabled: true,
    recipientRoleKeys: defaultReportRoleOptions.value.map((item) => item.value),
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
  users.value.forEach((item) => {
    if (!item?.isActive || item?.aqcRoleKey === 'aqc_departed') {
      return
    }
    if (selectedRoleKeys.has(item.aqcRoleKey)) {
      selectedUserIds.add(Number(item.id || 0))
    }
  })
  return [...selectedUserIds].filter((value) => value > 0)
}

async function loadReportSettings() {
  reportSettingsLoading.value = true
  const payload = await apiGet('/reports/settings', { token: authStore.token })
  reportSettingsLoading.value = false
  if (!payload?.success) {
    ElMessage.error(payload?.message || '报告设置加载失败')
    return false
  }
  reportRoleOptions.value = Array.isArray(payload.roleOptions) && payload.roleOptions.length
    ? payload.roleOptions
    : defaultReportRoleOptions.value
  reportSettings.value = orderedReportSettings(Array.isArray(payload.settings) ? payload.settings : [])
  if (!reportSettings.value.some((item) => item.periodKey === reportTestForm.periodKey)) {
    reportTestForm.periodKey = reportSettings.value[0]?.periodKey || 'day'
  }
  reportTestForm.userIds = resolveRecommendedReportUserIds(reportTestForm.periodKey)
  return true
}

async function openReportSettings() {
  const loaded = await loadReportSettings()
  if (!loaded) {
    return
  }
  reportSettingsVisible.value = true
}

function openReportTestDialog() {
  if (!reportSettings.value.length) {
    ElMessage.warning('请先加载报告设置')
    return
  }
  reportTestForm.userIds = resolveRecommendedReportUserIds(reportTestForm.periodKey)
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

const filteredUsers = computed(() => {
  const key = appliedKeyword.value.toLowerCase()
  return users.value.filter((item) => {
    const shopText = [item.shopName, ...(item.shopNames || [])].filter(Boolean).join(' ')
    const matchesKeyword = !key
      || [item.username, item.displayName, item.phone, item.email, shopText].some((value) => String(value || '').toLowerCase().includes(key))
    const matchesShop = !appliedShopFilter.value || (item.shopNames || []).includes(appliedShopFilter.value) || String(item.shopName || '') === appliedShopFilter.value
    const matchesRole = !appliedRoleFilter.value || item.aqcRoleKey === appliedRoleFilter.value
    return matchesKeyword && matchesShop && matchesRole
  }).sort((left, right) => {
    if (left.isActive !== right.isActive) {
      return left.isActive ? -1 : 1
    }
    return String(left.displayName || left.username || '').localeCompare(String(right.displayName || right.username || ''), 'zh-CN')
  })
})

const pagedUsers = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredUsers.value.slice(start, start + pageSize.value)
})

function onSearch() {
  appliedKeyword.value = String(keyword.value || '').trim()
  appliedShopFilter.value = String(shopFilter.value || '').trim()
  appliedRoleFilter.value = String(roleFilter.value || '').trim()
  page.value = 1
}

function onResetFilters() {
  keyword.value = ''
  shopFilter.value = ''
  roleFilter.value = ''
  appliedKeyword.value = ''
  appliedShopFilter.value = ''
  appliedRoleFilter.value = ''
  filterPanelOpen.value = false
  page.value = 1
}

function onPageChange(nextPage) {
  page.value = Number(nextPage || 1)
}

function onPageSizeChange(nextSize) {
  pageSize.value = Number(nextSize || 20)
  page.value = 1
}

async function sendTestNotification() {
  if (!notificationSupported) {
    ElMessage.warning('当前浏览器不支持系统通知')
    return
  }

  let permission = Notification.permission
  if (permission !== 'granted') {
    permission = await Notification.requestPermission()
  }

  if (permission !== 'granted') {
    ElMessage.warning(permission === 'denied' ? '浏览器通知已被拒绝' : '未开启浏览器通知')
    return
  }

  const notification = new Notification('AQC-N 通知测试', {
    body: '浏览器通知链路已经接通，后续可以承接系统提醒。',
    tag: 'aqc-admin-notification-test',
  })
  notification.onclick = () => {
    window.focus()
    notification.close()
  }
  ElMessage.success('测试通知已发出')
}

async function loadUsers() {
  loading.value = true
  const payload = await apiGet('/admin/users', { token: authStore.token })
  loading.value = false
  if (!payload?.success) {
    users.value = []
    setMessage(payload?.message || '加载账户失败', true)
    return
  }
  users.value = payload.users || []
}

watch(filteredUsers, (rows) => {
  const totalPages = Math.max(1, Math.ceil((rows?.length || 0) / pageSize.value))
  if (page.value > totalPages) {
    page.value = totalPages
  }
})

async function loadShops() {
  const payload = await apiGet('/shops/options', {
    token: authStore.token,
    query: { limit: '200' },
  })
  if (payload?.success) {
    shopOptions.value = payload.options || []
  }
}

function editRow(row) {
  editingId.value = row.id
  dialogForm.accountPhone = row.phone || row.username || ''
  dialogForm.displayName = row.displayName || ''
  dialogForm.aqcRoleKey = row.aqcRoleKey || 'aqc_sales'
  dialogForm.shopIds = Array.isArray(row.shopIds) ? [...row.shopIds] : (row.shopId ? [row.shopId] : [])
  dialogForm.employmentDate = row.employmentDate || ''
  dialogForm.password = ''
  dialogForm.isActive = !!row.isActive
  editorVisible.value = true
}

function buildAccountPayload(formState) {
  const accountPhone = String(formState.accountPhone || '').trim()
  return {
    username: accountPhone,
    phone: accountPhone,
    displayName: formState.displayName,
    aqcRoleKey: formState.aqcRoleKey,
    shopId: formState.shopIds?.[0] ?? null,
    shopIds: formState.shopIds || [],
    employmentDate: formState.employmentDate || null,
    isActive: formState.isActive,
    ...(formState.password ? { password: formState.password } : {}),
  }
}

async function submitDialogForm() {
  if (!String(dialogForm.accountPhone || '').trim()) {
    setEditorMessage('请填写账号手机号', true)
    return
  }
  if (!String(dialogForm.displayName || '').trim()) {
    setEditorMessage('请填写姓名', true)
    return
  }
  if (!editingId.value && !String(dialogForm.password || '').trim()) {
    setEditorMessage('请填写初始密码', true)
    return
  }
  if (String(dialogForm.password || '').trim() && String(dialogForm.password || '').trim().length < 8) {
    setEditorMessage('密码需大于等于 8 位', true)
    return
  }

  submitting.value = true
  const payload = editingId.value
    ? await apiPut(`/admin/users/${editingId.value}`, buildAccountPayload(dialogForm), { token: authStore.token })
    : await apiPost('/admin/users', buildAccountPayload(dialogForm), { token: authStore.token })
  submitting.value = false

  if (!payload?.success) {
    setMessage(payload?.message || '保存失败', true)
    setEditorMessage(payload?.message || '保存失败', true)
    return
  }

  setMessage(payload?.message || '保存成功')
  setEditorMessage(payload?.message || '保存成功')
  closeEditor()
  await loadUsers()
}

async function removeRow(userId) {
  try {
    await confirmDestructiveAction('确认删除该账户吗？删除后账户会停用。')
  } catch (error) {
    return
  }

  const payload = await apiDelete(`/admin/users/${userId}`, { token: authStore.token })
  if (!payload?.success) {
    setMessage(payload?.message || '删除失败', true)
    return
  }
  setMessage(payload?.message || '删除成功')
  await loadUsers()
}

watch(
  () => reportTestForm.periodKey,
  (periodKey) => {
    reportTestForm.userIds = resolveRecommendedReportUserIds(periodKey)
  },
)

void Promise.all([loadUsers(), loadShops()])
</script>

<style scoped>
.report-settings-shell,
.report-settings-stack,
.report-setting-card,
.report-setting-grid,
.report-setting-field,
.report-settings-overview {
  display: grid;
  gap: 16px;
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

@media (max-width: 760px) {
  .report-settings-overview,
  .report-setting-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .report-setting-head {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
