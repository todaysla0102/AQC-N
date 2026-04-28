<template>
  <section class="shop-schedule-page account-page">
    <article class="card-surface account-overview-hero motion-fade-slide shop-schedule-hero">
      <div class="account-overview-copy">
        <p class="panel-tag">排班</p>
        <h2>{{ scheduleShop.name || '店铺排班' }}</h2>
        <div class="account-overview-meta">
          <span>{{ monthLabel }}</span>
          <span>{{ scheduleShop.managerName ? `店长 ${scheduleShop.managerName}` : '未设置店长' }}</span>
          <span>排班成员 {{ assignedStaffCount }} 人</span>
        </div>
      </div>

      <div class="toolbar-actions account-overview-actions shop-schedule-hero-actions">
        <el-button @click="goBack">返回店铺/仓库管理</el-button>
        <el-button @click="openLogCenter">排班日志</el-button>
        <el-button v-if="canEdit" @click="toggleEditMode()">{{ editMode ? '退出编辑' : '编辑排班' }}</el-button>
        <el-button v-if="canEdit && editMode" type="primary" :loading="saving" @click="onSave()">保存排班</el-button>
      </div>
    </article>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" show-icon />

    <section class="shop-schedule-layout">
      <article class="card-surface sales-calendar-card motion-fade-slide shop-schedule-calendar-card" style="--motion-delay: 0.08s">
        <header class="sales-filter-head sales-calendar-head shop-schedule-calendar-head">
          <div class="sales-filter-head-copy sales-calendar-summary-head">
            <h2>排班日历</h2>
            <span v-if="editMode">{{ calendarEditHint }}</span>
          </div>

          <div class="sales-calendar-nav shop-schedule-nav">
            <el-button @click="shiftMonth(-1)">上一月</el-button>
            <el-date-picker
              :model-value="activeMonth"
              type="month"
              value-format="YYYY-MM"
              class="shop-schedule-month-picker"
              @update:model-value="handleMonthChange"
            />
            <el-button @click="shiftMonth(1)">下一月</el-button>
          </div>
        </header>

        <div v-loading="loading" class="sales-calendar-board shop-schedule-board">
          <div class="shop-schedule-calendar-scroll">
            <div class="sales-calendar-weekdays shop-schedule-weekdays">
              <span v-for="item in weekdayLabels" :key="item">{{ item }}</span>
            </div>

            <div ref="calendarGridRef" class="sales-calendar-grid shop-schedule-grid">
              <article
                v-for="day in calendarDays"
                :key="day.date"
                class="sales-calendar-day shop-schedule-day"
                :data-date="day.date"
                :class="{
                  'is-outside': !day.isCurrentMonth,
                  'is-today': day.isToday,
                  'is-incomplete': day.isCurrentMonth && isDayIncomplete(day),
                  'is-editing': editMode && day.isCurrentMonth,
                }"
              >
                <div class="shop-schedule-day-head">
                  <span class="sales-calendar-day-number">{{ day.day }}</span>
                  <small v-if="day.isCurrentMonth && isDayIncomplete(day)">早/晚待补</small>
                  <small v-else-if="day.isCurrentMonth">当日排班</small>
                  <small v-else>非本月</small>
                </div>

                <div v-if="day.isCurrentMonth" class="shop-schedule-shift-list">
                  <section
                    v-for="slot in day.shiftSlots"
                    :key="`${day.date}-${slot.key}`"
                    class="shop-schedule-shift-slot"
                    :class="{ droppable: editMode }"
                    @dragover.prevent="handleSlotDragOver(day, slot)"
                    @drop.prevent="handleSlotDrop(day, slot)"
                    @click="openSlotEditor(day, slot)"
                  >
                    <div v-if="slot.assignments.length" class="shop-schedule-card-list">
                      <div
                        v-for="assignment in slot.assignments"
                        :key="`${day.date}-${slot.key}-${assignment.userId}`"
                        class="shop-schedule-assignment-card"
                        :class="{
                          'current-user': isCurrentUser(assignment.userId),
                          inactive: !assignment.isActive,
                        }"
                        :draggable="editMode && !isMobileViewport"
                        @dragstart="handleAssignmentDragStart(day, slot, assignment)"
                        @dragend="handleAssignmentDragEnd($event, day, slot, assignment)"
                        @click.stop="openSlotEditor(day, slot)"
                      >
                        <span class="shop-schedule-assignment-name">{{ assignment.displayName }}</span>
                        <button
                          v-if="editMode"
                          type="button"
                          class="shop-schedule-assignment-remove"
                          @click.stop="removeAssignmentChip(day, slot, assignment)"
                        >
                          ×
                        </button>
                      </div>
                    </div>
                    <span v-if="!slot.assignments.length" class="shop-schedule-slot-placeholder">
                      {{ slotPlaceholderText(slot) }}
                    </span>
                  </section>
                </div>
              </article>
            </div>
          </div>
        </div>
      </article>

      <article class="card-surface motion-fade-slide shop-schedule-side-card" style="--motion-delay: 0.14s">
        <header class="section-head shop-schedule-side-head">
          <div>
            <h2>排班统计</h2>
          </div>
        </header>

        <div class="shop-schedule-stat-list">
          <article
            v-for="item in staffStats"
            :key="item.userId"
            class="shop-schedule-stat-card"
            :class="{ inactive: !item.isActive, 'current-user': isCurrentUser(item.userId) }"
          >
            <div class="shop-schedule-stat-head">
              <strong>{{ item.displayName }}</strong>
              <span>{{ item.roleName || (item.isManager ? '店长' : '销售员') }}</span>
            </div>

            <div class="shop-schedule-stat-metrics">
              <div class="shop-schedule-stat-metric">
                <span>排班数</span>
                <strong>{{ item.shiftCount }}</strong>
              </div>
              <div class="shop-schedule-stat-metric">
                <span>连班数</span>
                <strong>{{ item.doubleShiftDays }}</strong>
              </div>
              <div class="shop-schedule-stat-metric">
                <span>上班天数</span>
                <strong>{{ item.workDays }}</strong>
              </div>
              <div class="shop-schedule-stat-metric">
                <span>休息天数</span>
                <strong>{{ item.restDays }}</strong>
              </div>
            </div>
          </article>
        </div>
      </article>
    </section>

    <Teleport to="body">
      <transition name="settings-float">
        <div
          v-if="editMode && canEdit && !isMobileViewport"
          ref="staffPaletteRef"
          class="shop-schedule-staff-palette card-surface"
          :style="staffPaletteStyle"
        >
          <div class="shop-schedule-staff-palette-head" @pointerdown="handlePalettePointerDown">
            <div>
              <strong>店铺人员卡片</strong>
              <span>{{ isMobileViewport ? '点击班次后选择人员' : '可拖动窗口，也可直接拖动卡片到日历中' }}</span>
            </div>
          </div>

          <div class="shop-schedule-staff-palette-body">
            <div class="toolbar-actions goods-search-actions shop-schedule-search-actions">
              <el-input
                v-model.trim="paletteSearchKeyword"
                clearable
                placeholder="搜索销售员或店长"
              />
            </div>

            <div v-if="paletteStaffGroups.length" class="shop-schedule-group-list">
              <section
                v-for="group in paletteStaffGroups"
                :key="`palette-group-${group.shopId}`"
                class="shop-schedule-group-card"
              >
                <button
                  type="button"
                  class="shop-schedule-group-head"
                  :class="{ expanded: isStaffGroupExpanded(group, 'palette') }"
                  @click="toggleStaffGroup(group.shopId, 'palette')"
                >
                  <div>
                    <strong>{{ group.shopName }}</strong>
                    <span>{{ group.staff.length }} 人</span>
                  </div>
                  <small>{{ isStaffGroupExpanded(group, 'palette') ? '收起' : '展开' }}</small>
                </button>

                <div v-if="isStaffGroupExpanded(group, 'palette')" class="shop-schedule-group-body">
                  <button
                    v-for="item in group.staff"
                    :key="`${group.shopId}-${item.id}`"
                    type="button"
                    class="shop-schedule-staff-chip"
                    :class="{ 'current-user': isCurrentUser(item.id), inactive: !item.isActive }"
                    :draggable="!isMobileViewport"
                    @dragstart="handlePoolDragStart(item)"
                    @dragend="handlePoolDragEnd"
                  >
                    {{ item.displayName }}
                  </button>
                </div>
              </section>
            </div>

            <div v-else class="shop-schedule-group-empty">没有匹配的排班人员</div>
          </div>

          <div class="shop-schedule-staff-palette-stats">
            <article
              v-for="item in staffStats"
              :key="`palette-${item.userId}`"
              class="shop-schedule-palette-stat-card"
              :class="{ inactive: !item.isActive, 'current-user': isCurrentUser(item.userId) }"
            >
              <strong>{{ item.displayName }}</strong>
              <span>{{ item.shiftCount }} 班 · 连班 {{ item.doubleShiftDays }} 天 · 休 {{ item.restDays }} 天</span>
            </article>
          </div>

          <div class="shop-schedule-staff-palette-actions">
            <el-button @click="toggleEditMode()">退出编辑</el-button>
            <el-button type="primary" :loading="saving" @click="onSave()">保存排班</el-button>
          </div>
        </div>
      </transition>
    </Teleport>

    <el-dialog
      v-model="slotEditorVisible"
      :title="slotEditorTitle"
      width="min(760px, 94vw)"
      append-to-body
      destroy-on-close
      align-center
      class="aqc-app-dialog shop-schedule-selector-dialog"
    >
      <div class="shop-schedule-selector-shell">
        <div class="shop-schedule-selector-head">
          <strong>{{ slotEditorSubtitle }}</strong>
          <span>可同时选择多位销售员；同一人可在同一天早晚连班。</span>
        </div>

        <div class="toolbar-actions goods-search-actions shop-schedule-search-actions">
          <el-input
            v-model.trim="slotEditorSearchKeyword"
            clearable
            placeholder="搜索销售员或店长"
          />
        </div>

        <div v-if="slotEditorStaffGroups.length" class="shop-schedule-group-list shop-schedule-selector-group-list">
          <section
            v-for="group in slotEditorStaffGroups"
            :key="`selector-group-${group.shopId}`"
            class="shop-schedule-group-card"
          >
            <button
              type="button"
              class="shop-schedule-group-head"
              :class="{ expanded: isStaffGroupExpanded(group, 'selector') }"
              @click="toggleStaffGroup(group.shopId, 'selector')"
            >
              <div>
                <strong>{{ group.shopName }}</strong>
                <span>{{ group.staff.length }} 人</span>
              </div>
              <small>{{ isStaffGroupExpanded(group, 'selector') ? '收起' : '展开' }}</small>
            </button>

            <div v-if="isStaffGroupExpanded(group, 'selector')" class="shop-schedule-selector-list">
              <button
                v-for="item in group.staff"
                :key="`${group.shopId}-${item.id}`"
                type="button"
                class="shop-schedule-selector-chip compact"
                :class="{
                  active: slotEditorSelection.has(item.id),
                  'current-user': isCurrentUser(item.id),
                  inactive: !item.isActive,
                }"
                @click="toggleSlotEditorUser(item.id)"
              >
                <span>{{ item.displayName }}</span>
                <small>{{ item.roleName || (item.isManager ? '店长' : '销售员') }}</small>
              </button>
            </div>
          </section>
        </div>
        <div v-else class="shop-schedule-group-empty">没有匹配的排班人员</div>
      </div>

      <template #footer>
        <div class="form-actions">
          <el-button @click="slotEditorVisible = false">取消</el-button>
          <el-button type="primary" @click="applySlotEditorSelection">应用</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="logDialogVisible"
      title="排班日志"
      width="min(820px, 95vw)"
      append-to-body
      destroy-on-close
      align-center
      class="aqc-app-dialog shop-schedule-log-dialog"
    >
      <div v-if="scheduleLogs.length" class="shop-schedule-log-list">
        <article v-for="item in scheduleLogs" :key="item.id" class="shop-schedule-log-item">
          <div class="shop-schedule-log-head">
            <strong>{{ item.summary }}</strong>
            <span>{{ item.operatorName || '系统' }} · {{ formatLogTime(item.createdAt) }}</span>
          </div>
          <ul v-if="item.highlights?.length" class="shop-schedule-log-highlights">
            <li v-for="line in item.highlights" :key="line">{{ line }}</li>
          </ul>
        </article>
      </div>
      <div v-else class="shop-schedule-log-empty">暂无排班日志</div>

      <template #footer>
        <div class="form-actions">
          <el-button @click="logDialogVisible = false">关闭</el-button>
        </div>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'

import { useMobileViewport } from '../composables/useMobileViewport'
import { apiGet, apiPut } from '../services/api'
import { useAuthStore } from '../stores/auth'
import { confirmAction } from '../utils/confirm'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()
const { isMobileViewport } = useMobileViewport()

const loading = ref(false)
const saving = ref(false)
const canEdit = ref(false)
const editMode = ref(false)
const errorMessage = ref('')
const activeMonth = ref(resolveInitialMonth())
const scheduleShop = ref({ id: 0, name: '', managerName: '', staffCount: 0 })
const scheduleStaff = ref([])
const scheduleStaffGroups = ref([])
const scheduleStaffStats = ref([])
const scheduleStatEntries = ref([])
const calendarDays = ref([])
const scheduleLogs = ref([])
const serverCalendarDays = ref([])
const dragPayload = ref(null)
const dragDropHandled = ref(false)
const logDialogVisible = ref(false)
const paletteSearchKeyword = ref('')
const slotEditorSearchKeyword = ref('')
const paletteExpandedGroups = ref({})
const selectorExpandedGroups = ref({})
const slotEditorVisible = ref(false)
const slotEditorState = ref({
  date: '',
  shiftKey: '',
  shiftLabel: '',
  selectedIds: [],
})
const calendarGridRef = ref(null)
const staffPaletteRef = ref(null)
const palettePosition = ref({ x: 0, y: 0 })
const paletteReady = ref(false)
const savedScheduleSnapshot = ref('')

const weekdayLabels = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
const paletteDragState = {
  active: false,
  pointerId: null,
  offsetX: 0,
  offsetY: 0,
}

const monthLabel = computed(() => {
  const [year, month] = String(activeMonth.value || '').split('-')
  if (!year || !month) {
    return '当前月份'
  }
  return `${year} 年 ${Number(month)} 月`
})

const currentUserId = computed(() => Number(authStore.user?.id || 0))
const assignedStaffCount = computed(() => Number(scheduleShop.value?.staffCount || 0))

const calendarEditHint = computed(() => (
  isMobileViewport.value
    ? '点击班次直接选择销售员。'
    : '支持拖动人员卡片排班，也可以点击班次直接选择销售员。'
))

const currentMonthDays = computed(() => calendarDays.value.filter((item) => item.isCurrentMonth))

const trackedStatUserIds = computed(() => {
  const ids = new Set(
    scheduleStaff.value
      .filter((item) => item.isAssigned)
      .map((item) => Number(item.id))
      .filter((item) => item > 0),
  )
  for (const day of currentMonthDays.value) {
    for (const slot of day.shiftSlots || []) {
      for (const assignment of slot.assignments || []) {
        const userId = Number(assignment.userId || 0)
        if (userId > 0) {
          ids.add(userId)
        }
      }
    }
  }
  return ids
})

const mergedStaffStatEntries = computed(() => {
  const currentShopId = Number(scheduleShop.value?.id || 0)
  const retainedEntries = (scheduleStatEntries.value || []).filter((item) => Number(item.shopId || 0) !== currentShopId)
  const currentShopName = String(scheduleShop.value?.name || '')
  const nextEntries = []
  for (const day of currentMonthDays.value) {
    for (const slot of day.shiftSlots || []) {
      for (const assignment of slot.assignments || []) {
        const userId = Number(assignment.userId || 0)
        if (userId <= 0) {
          continue
        }
        nextEntries.push({
          shopId: currentShopId,
          shopName: currentShopName,
          userId,
          date: String(day.date || ''),
          shiftKey: String(slot.key || ''),
        })
      }
    }
  }
  return [...retainedEntries, ...nextEntries]
})

const hasUnsavedChanges = computed(() => (
  editMode.value
  && savedScheduleSnapshot.value
  && savedScheduleSnapshot.value !== buildScheduleSnapshot()
))

const staffStats = computed(() => {
  const trackedIds = trackedStatUserIds.value
  const shiftCountMap = new Map()
  const doubleShiftMap = new Map()
  const workDayMap = new Map()
  for (const item of scheduleStaff.value) {
    const userId = Number(item.id || 0)
    if (!trackedIds.has(userId)) {
      continue
    }
    shiftCountMap.set(userId, 0)
    doubleShiftMap.set(userId, 0)
    workDayMap.set(userId, new Set())
  }

  const dateShiftMap = new Map()
  for (const entry of mergedStaffStatEntries.value) {
    const userId = Number(entry.userId || 0)
    const shiftKey = String(entry.shiftKey || '')
    const dateKey = String(entry.date || '')
    if (!trackedIds.has(userId) || !dateKey || !['morning', 'extra', 'night'].includes(shiftKey)) {
      continue
    }
    shiftCountMap.set(userId, Number(shiftCountMap.get(userId) || 0) + 1)
    if (!workDayMap.has(userId)) {
      workDayMap.set(userId, new Set())
    }
    workDayMap.get(userId).add(dateKey)
    if (!dateShiftMap.has(dateKey)) {
      dateShiftMap.set(dateKey, { morning: new Set(), extra: new Set(), night: new Set() })
    }
    dateShiftMap.get(dateKey)[shiftKey].add(userId)
  }

  for (const [, dayMap] of dateShiftMap.entries()) {
    for (const userId of dayMap.morning) {
      if (dayMap.night.has(userId)) {
        doubleShiftMap.set(userId, Number(doubleShiftMap.get(userId) || 0) + 1)
      }
    }
  }

  const totalDays = currentMonthDays.value.length
  return scheduleStaff.value
    .filter((item) => trackedIds.has(Number(item.id || 0)))
    .map((item) => {
      const workDays = workDayMap.get(item.id)?.size || 0
      return {
        userId: item.id,
        displayName: item.displayName,
        username: item.username,
        roleName: item.roleName,
        isManager: item.isManager,
        isActive: item.isActive,
        isAssigned: item.isAssigned,
        shiftCount: Number(shiftCountMap.get(item.id) || 0),
        doubleShiftDays: Number(doubleShiftMap.get(item.id) || 0),
        workDays,
        restDays: Math.max(totalDays - workDays, 0),
      }
    })
    .sort((left, right) => {
      if (Boolean(left.isAssigned) !== Boolean(right.isAssigned)) {
        return left.isAssigned ? -1 : 1
      }
      if (Boolean(left.isManager) !== Boolean(right.isManager)) {
        return left.isManager ? -1 : 1
      }
      return String(left.displayName || '').localeCompare(String(right.displayName || ''), 'zh-CN')
    })
})

const paletteStaffGroups = computed(() => filterStaffGroups(paletteSearchKeyword.value))
const slotEditorStaffGroups = computed(() => filterStaffGroups(slotEditorSearchKeyword.value))

const slotEditorSelection = computed(() => new Set(slotEditorState.value.selectedIds.map((item) => Number(item))))

const slotEditorTitle = computed(() => {
  const dateText = String(slotEditorState.value.date || '').trim()
  const shiftLabel = String(slotEditorState.value.shiftLabel || '班次').trim()
  if (!dateText) {
    return '选择排班人员'
  }
  return `${dateText} · ${shiftLabel}`
})

const slotEditorSubtitle = computed(() => {
  const day = findDay(slotEditorState.value.date)
  if (!day) {
    return '编辑当前班次'
  }
  const weekday = weekdayLabels[Number(day.weekday || 0)] || ''
  return `${monthLabel.value} · ${weekday}`
})

const staffPaletteStyle = computed(() => {
  if (isMobileViewport.value) {
    return {}
  }
  if (!paletteReady.value) {
    return { visibility: 'hidden' }
  }
  return {
    left: `${Math.round(palettePosition.value.x)}px`,
    top: `${Math.round(palettePosition.value.y)}px`,
  }
})

function buildDefaultGroupState(groups) {
  return Object.fromEntries(
    (groups || []).map((group) => [Number(group.shopId || 0), Boolean(group.isCurrentShop)]),
  )
}

function normalizeGroupSearchKeyword(value) {
  return String(value || '').trim().toLowerCase()
}

function matchesStaffSearch(item, keyword) {
  if (!keyword) {
    return true
  }
  const haystack = [
    item?.displayName,
    item?.username,
    item?.roleName,
    item?.isManager ? '店长' : '销售员',
  ]
    .map((part) => String(part || '').toLowerCase())
    .join(' ')
  return haystack.includes(keyword)
}

function filterStaffGroups(keyword) {
  const normalizedKeyword = normalizeGroupSearchKeyword(keyword)
  return (scheduleStaffGroups.value || [])
    .map((group) => ({
      ...group,
      staff: (group.staff || []).filter((item) => matchesStaffSearch(item, normalizedKeyword)),
    }))
    .filter((group) => group.staff.length > 0 || (!normalizedKeyword && group.isCurrentShop))
}

function isStaffGroupExpanded(group, mode) {
  const keyword = mode === 'selector' ? slotEditorSearchKeyword.value : paletteSearchKeyword.value
  if (normalizeGroupSearchKeyword(keyword)) {
    return true
  }
  const targetMap = mode === 'selector' ? selectorExpandedGroups.value : paletteExpandedGroups.value
  const shopId = Number(group?.shopId || 0)
  if (Object.prototype.hasOwnProperty.call(targetMap, shopId)) {
    return Boolean(targetMap[shopId])
  }
  return Boolean(group?.isCurrentShop)
}

function toggleStaffGroup(shopId, mode) {
  const targetRef = mode === 'selector' ? selectorExpandedGroups : paletteExpandedGroups
  const nextMap = { ...targetRef.value }
  const key = Number(shopId || 0)
  nextMap[key] = !Boolean(nextMap[key])
  targetRef.value = nextMap
}

function resolveInitialMonth() {
  const queryMonth = String(route.query.month || '').trim()
  if (/^\d{4}-\d{2}$/.test(queryMonth)) {
    return queryMonth
  }
  const now = new Date()
  return `${now.getFullYear()}-${`${now.getMonth() + 1}`.padStart(2, '0')}`
}

function normalizeAssignment(assignment) {
  return {
    userId: Number(assignment?.userId || 0),
    displayName: String(assignment?.displayName || ''),
    username: String(assignment?.username || ''),
    roleName: String(assignment?.roleName || ''),
    isManager: Boolean(assignment?.isManager),
    isActive: Boolean(assignment?.isActive ?? true),
    isAssigned: Boolean(assignment?.isAssigned ?? true),
  }
}

function normalizeStaff(item) {
  return {
    id: Number(item?.id || 0),
    username: String(item?.username || ''),
    displayName: String(item?.displayName || ''),
    roleName: String(item?.roleName || ''),
    isManager: Boolean(item?.isManager),
    isActive: Boolean(item?.isActive ?? true),
    isAssigned: Boolean(item?.isAssigned ?? true),
  }
}

function normalizeStaffGroup(group) {
  return {
    shopId: Number(group?.shopId || 0),
    shopName: String(group?.shopName || ''),
    isCurrentShop: Boolean(group?.isCurrentShop),
    staff: Array.isArray(group?.staff) ? group.staff.map(normalizeStaff) : [],
  }
}

function normalizeStatEntry(item) {
  return {
    shopId: Number(item?.shopId || 0),
    shopName: String(item?.shopName || ''),
    userId: Number(item?.userId || 0),
    date: String(item?.date || ''),
    shiftKey: String(item?.shiftKey || ''),
  }
}

function normalizeDay(day) {
  return {
    date: String(day?.date || ''),
    day: Number(day?.day || 0),
    weekday: Number(day?.weekday || 0),
    isCurrentMonth: Boolean(day?.isCurrentMonth),
    isToday: Boolean(day?.isToday),
    shiftSlots: Array.isArray(day?.shiftSlots)
      ? day.shiftSlots.map((slot) => ({
          key: String(slot?.key || ''),
          label: String(slot?.label || ''),
          assignments: Array.isArray(slot?.assignments) ? slot.assignments.map(normalizeAssignment) : [],
        }))
      : [],
  }
}

function cloneCalendarDays(days) {
  return Array.isArray(days) ? days.map((item) => normalizeDay(item)) : []
}

function resetInteractionState() {
  dragPayload.value = null
  dragDropHandled.value = false
}

function goBack() {
  router.push({ name: 'shops-manage' })
}

function isDayIncomplete(day) {
  if (!day?.isCurrentMonth) {
    return false
  }
  const morningSlot = day.shiftSlots.find((item) => item.key === 'morning')
  const nightSlot = day.shiftSlots.find((item) => item.key === 'night')
  return !morningSlot?.assignments?.length || !nightSlot?.assignments?.length
}

function slotPlaceholderText(slot) {
  if ((slot?.assignments || []).length) {
    return ''
  }
  if (slot?.key === 'morning') {
    return '早'
  }
  if (slot?.key === 'extra') {
    return '插'
  }
  return '晚'
}

function isCurrentUser(userId) {
  return Number(userId || 0) > 0 && Number(userId || 0) === currentUserId.value
}

function findDay(date) {
  return calendarDays.value.find((item) => item.date === date) || null
}

function findSlot(date, shiftKey) {
  return findDay(date)?.shiftSlots?.find((item) => item.key === shiftKey) || null
}

function getStaff(userId) {
  return scheduleStaff.value.find((item) => item.id === Number(userId)) || null
}

function assignmentFromStaff(staff) {
  return {
    userId: Number(staff.id),
    displayName: staff.displayName,
    username: staff.username,
    roleName: staff.roleName,
    isManager: staff.isManager,
    isActive: staff.isActive,
    isAssigned: staff.isAssigned,
  }
}

function buildScheduleSnapshot() {
  return JSON.stringify(
    currentMonthDays.value.map((day) => ({
      date: day.date,
      morning: [...(day.shiftSlots.find((item) => item.key === 'morning')?.assignments || [])]
        .map((item) => Number(item.userId))
        .filter((item) => item > 0)
        .sort((left, right) => left - right),
      extra: [...(day.shiftSlots.find((item) => item.key === 'extra')?.assignments || [])]
        .map((item) => Number(item.userId))
        .filter((item) => item > 0)
        .sort((left, right) => left - right),
      night: [...(day.shiftSlots.find((item) => item.key === 'night')?.assignments || [])]
        .map((item) => Number(item.userId))
        .filter((item) => item > 0)
        .sort((left, right) => left - right),
    })),
  )
}

function addAssignment(date, shiftKey, userId) {
  const slot = findSlot(date, shiftKey)
  const staff = getStaff(userId)
  if (!slot || !staff) {
    return false
  }
  if ((slot.assignments || []).some((item) => Number(item.userId) === Number(userId))) {
    return false
  }
  slot.assignments.push(assignmentFromStaff(staff))
  return true
}

function removeAssignment(date, shiftKey, userId) {
  const slot = findSlot(date, shiftKey)
  if (!slot) {
    return false
  }
  const nextAssignments = (slot.assignments || []).filter((item) => Number(item.userId) !== Number(userId))
  if (nextAssignments.length === slot.assignments.length) {
    return false
  }
  slot.assignments = nextAssignments
  return true
}

function moveAssignment(fromDate, fromShiftKey, toDate, toShiftKey, userId) {
  if (fromDate === toDate && fromShiftKey === toShiftKey) {
    return false
  }
  const removed = removeAssignment(fromDate, fromShiftKey, userId)
  const added = addAssignment(toDate, toShiftKey, userId)
  if (!added && removed) {
    addAssignment(fromDate, fromShiftKey, userId)
  }
  return removed && added
}

function replaceSlotAssignments(date, shiftKey, userIds) {
  const slot = findSlot(date, shiftKey)
  if (!slot) {
    return
  }
  const nextAssignments = scheduleStaff.value
    .filter((item) => userIds.includes(Number(item.id)))
    .map((item) => assignmentFromStaff(item))
  slot.assignments = nextAssignments
}

function openSlotEditor(day, slot) {
  if (!editMode.value || !day?.isCurrentMonth) {
    return
  }
  slotEditorSearchKeyword.value = ''
  selectorExpandedGroups.value = buildDefaultGroupState(scheduleStaffGroups.value)
  slotEditorState.value = {
    date: String(day.date || ''),
    shiftKey: String(slot?.key || ''),
    shiftLabel: String(slot?.label || ''),
    selectedIds: Array.isArray(slot?.assignments) ? slot.assignments.map((item) => Number(item.userId)).filter((item) => item > 0) : [],
  }
  slotEditorVisible.value = true
}

function toggleSlotEditorUser(userId) {
  const nextId = Number(userId || 0)
  if (nextId <= 0) {
    return
  }
  const currentIds = new Set(slotEditorState.value.selectedIds.map((item) => Number(item)))
  if (currentIds.has(nextId)) {
    currentIds.delete(nextId)
  } else {
    currentIds.add(nextId)
  }
  slotEditorState.value = {
    ...slotEditorState.value,
    selectedIds: [...currentIds],
  }
}

function applySlotEditorSelection() {
  replaceSlotAssignments(
    slotEditorState.value.date,
    slotEditorState.value.shiftKey,
    slotEditorState.value.selectedIds.map((item) => Number(item)).filter((item) => item > 0),
  )
  slotEditorVisible.value = false
}

function handlePoolDragStart(item) {
  if (!editMode.value || isMobileViewport.value) {
    return
  }
  dragDropHandled.value = false
  dragPayload.value = {
    type: 'pool',
    userId: Number(item?.id || item?.userId || 0),
  }
}

function handlePoolDragEnd() {
  window.setTimeout(() => {
    resetInteractionState()
  }, 0)
}

function handleAssignmentDragStart(day, slot, assignment) {
  if (!editMode.value || isMobileViewport.value) {
    return
  }
  dragDropHandled.value = false
  dragPayload.value = {
    type: 'assignment',
    userId: Number(assignment.userId),
    fromDate: day.date,
    fromShiftKey: slot.key,
  }
}

function handleAssignmentDragEnd(event, day, slot, assignment) {
  const payload = dragPayload.value
  if (
    editMode.value
    && payload?.type === 'assignment'
    && !dragDropHandled.value
    && Number(payload.userId) === Number(assignment.userId)
    && payload.fromDate === day.date
    && payload.fromShiftKey === slot.key
    && droppedOutsideDayCard(event, day.date)
  ) {
    removeAssignment(day.date, slot.key, assignment.userId)
  }
  window.setTimeout(() => {
    resetInteractionState()
  }, 0)
}

function droppedOutsideDayCard(event, originDate) {
  if (isMobileViewport.value) {
    return false
  }
  const target = document.elementFromPoint(Number(event?.clientX || 0), Number(event?.clientY || 0))
  const dayCard = target?.closest?.('.shop-schedule-day')
  if (!dayCard) {
    return true
  }
  return String(dayCard.getAttribute('data-date') || '') !== String(originDate || '')
}

function handleSlotDragOver(day) {
  if (!editMode.value || !day.isCurrentMonth) {
    return
  }
}

function handleSlotDrop(day, slot) {
  if (!editMode.value || !day.isCurrentMonth || !dragPayload.value) {
    return
  }
  dragDropHandled.value = true
  const payload = dragPayload.value
  if (payload.type === 'pool') {
    addAssignment(day.date, slot.key, payload.userId)
  } else if (payload.type === 'assignment') {
    moveAssignment(payload.fromDate, payload.fromShiftKey, day.date, slot.key, payload.userId)
  }
  window.setTimeout(() => {
    resetInteractionState()
  }, 0)
}

function buildSavePayload() {
  return {
    month: activeMonth.value,
    confirmIncomplete: false,
    confirmConflicts: false,
    days: currentMonthDays.value.map((day) => ({
      date: day.date,
      morning: day.shiftSlots.find((item) => item.key === 'morning')?.assignments?.map((item) => Number(item.userId)) || [],
      extra: day.shiftSlots.find((item) => item.key === 'extra')?.assignments?.map((item) => Number(item.userId)) || [],
      night: day.shiftSlots.find((item) => item.key === 'night')?.assignments?.map((item) => Number(item.userId)) || [],
    })),
  }
}

async function confirmDiscardChanges(message, title = '离开确认', confirmText = '确认离开') {
  if (!editMode.value || !hasUnsavedChanges.value) {
    return true
  }
  try {
    await confirmAction(message, title, confirmText)
    return true
  } catch {
    return false
  }
}

async function loadSchedule() {
  loading.value = true
  errorMessage.value = ''
  slotEditorVisible.value = false
  resetInteractionState()
  const payload = await apiGet(`/shop-schedules/${route.params.shopId}`, {
    token: authStore.token,
    query: { month: activeMonth.value },
  })
  loading.value = false
  if (!payload?.success) {
    calendarDays.value = []
    serverCalendarDays.value = []
    scheduleStaff.value = []
    scheduleStaffGroups.value = []
    scheduleStaffStats.value = []
    scheduleStatEntries.value = []
    scheduleLogs.value = []
    paletteExpandedGroups.value = {}
    selectorExpandedGroups.value = {}
    paletteSearchKeyword.value = ''
    slotEditorSearchKeyword.value = ''
    scheduleShop.value = { id: Number(route.params.shopId || 0), name: '', managerName: '', staffCount: 0 }
    savedScheduleSnapshot.value = ''
    errorMessage.value = payload?.message || '排班数据加载失败'
    return
  }
  canEdit.value = Boolean(payload.canEdit)
  if (!canEdit.value) {
    editMode.value = false
  }
  activeMonth.value = String(payload.month || activeMonth.value || '')
  scheduleShop.value = {
    id: Number(payload.shop?.id || 0),
    name: String(payload.shop?.name || ''),
    managerName: String(payload.shop?.managerName || ''),
    staffCount: Number(payload.shop?.staffCount || 0),
  }
  scheduleStaff.value = Array.isArray(payload.staff) ? payload.staff.map(normalizeStaff) : []
  scheduleStaffGroups.value = Array.isArray(payload.staffGroups) ? payload.staffGroups.map(normalizeStaffGroup) : []
  scheduleStaffStats.value = Array.isArray(payload.staffStats)
    ? payload.staffStats.map((item) => ({
        userId: Number(item?.userId || 0),
        displayName: String(item?.displayName || ''),
        username: String(item?.username || ''),
        roleName: String(item?.roleName || ''),
        isManager: Boolean(item?.isManager),
        isActive: Boolean(item?.isActive ?? true),
        isAssigned: Boolean(item?.isAssigned ?? true),
        shiftCount: Number(item?.shiftCount || 0),
        doubleShiftDays: Number(item?.doubleShiftDays || 0),
        workDays: Number(item?.workDays || 0),
        restDays: Number(item?.restDays || 0),
      }))
    : []
  scheduleStatEntries.value = Array.isArray(payload.staffStatEntries) ? payload.staffStatEntries.map(normalizeStatEntry) : []
  serverCalendarDays.value = cloneCalendarDays(payload.days)
  calendarDays.value = cloneCalendarDays(serverCalendarDays.value)
  scheduleLogs.value = Array.isArray(payload.logs)
    ? payload.logs.map((item) => ({
        id: Number(item?.id || 0),
        operatorName: String(item?.operatorName || ''),
        createdAt: String(item?.createdAt || ''),
        summary: String(item?.summary || ''),
        highlights: Array.isArray(item?.highlights) ? item.highlights.map((line) => String(line || '')).filter(Boolean) : [],
      }))
    : []
  paletteExpandedGroups.value = buildDefaultGroupState(scheduleStaffGroups.value)
  selectorExpandedGroups.value = buildDefaultGroupState(scheduleStaffGroups.value)
  paletteSearchKeyword.value = ''
  slotEditorSearchKeyword.value = ''
  savedScheduleSnapshot.value = buildScheduleSnapshot()
}

function buildConflictConfirmMessage(conflictWarnings) {
  const lines = (conflictWarnings || [])
    .slice(0, 8)
    .map((item) => `${String(item.date || '').slice(5)} ${item.shiftLabel} · ${item.displayName} 已在 ${item.shopName} 排班`)
  const extraCount = Math.max((conflictWarnings || []).length - lines.length, 0)
  if (extraCount > 0) {
    lines.push(`还有 ${extraCount} 条冲突未展开`)
  }
  return [
    '检测到以下跨店同班冲突，确认仍然保存吗？',
    '',
    ...lines,
  ].join('\n')
}

async function onSave(confirmConflicts = false) {
  if (!canEdit.value) {
    return
  }
  saving.value = true
  const payload = await apiPut(`/shop-schedules/${route.params.shopId}`, {
    ...buildSavePayload(),
    confirmConflicts: Boolean(confirmConflicts),
  }, {
    token: authStore.token,
  })
  saving.value = false
  if (payload?.needsConfirm && Array.isArray(payload?.conflictWarnings) && payload.conflictWarnings.length && !confirmConflicts) {
    try {
      await confirmAction(
        buildConflictConfirmMessage(payload.conflictWarnings),
        '排班冲突确认',
        '确认保存',
      )
    } catch {
      return
    }
    await onSave(true)
    return
  }
  if (!payload?.success) {
    ElMessage.error(payload?.message || '排班保存失败')
    return
  }
  ElMessage.success(payload.message || '排班已保存')
  editMode.value = false
  slotEditorVisible.value = false
  await loadSchedule()
}

function removeAssignmentChip(day, slot, assignment) {
  removeAssignment(day.date, slot.key, assignment.userId)
}

async function toggleEditMode() {
  if (!editMode.value) {
    calendarDays.value = cloneCalendarDays(serverCalendarDays.value)
    savedScheduleSnapshot.value = buildScheduleSnapshot()
    editMode.value = true
    paletteSearchKeyword.value = ''
    paletteExpandedGroups.value = buildDefaultGroupState(scheduleStaffGroups.value)
    slotEditorVisible.value = false
    resetInteractionState()
    return
  }
  const confirmed = await confirmDiscardChanges(
    '当前排班有未保存的修改，退出编辑不会保存这些调整，确认仍然退出吗？',
    '退出编辑',
    '确认退出',
  )
  if (!confirmed) {
    return
  }
  calendarDays.value = cloneCalendarDays(serverCalendarDays.value)
  savedScheduleSnapshot.value = buildScheduleSnapshot()
  editMode.value = false
  slotEditorVisible.value = false
  resetInteractionState()
}

function shiftMonth(offset) {
  const [yearText, monthText] = String(activeMonth.value || '').split('-')
  const year = Number(yearText || 0)
  const month = Number(monthText || 1)
  const next = new Date(year, month - 1 + Number(offset || 0), 1)
  const nextMonth = `${next.getFullYear()}-${`${next.getMonth() + 1}`.padStart(2, '0')}`
  void handleMonthChange(nextMonth)
}

async function handleMonthChange(value) {
  const nextMonth = String(value || '').trim()
  if (!/^\d{4}-\d{2}$/.test(nextMonth) || nextMonth === activeMonth.value) {
    return
  }
  await router.replace({
    name: 'shop-schedule',
    params: { shopId: route.params.shopId },
    query: {
      ...route.query,
      month: nextMonth,
    },
  })
}

function formatLogTime(value) {
  const text = String(value || '').trim()
  return text ? text.replace('T', ' ').slice(5, 16) : '-'
}

async function openLogCenter() {
  await router.push({
    name: 'log-center',
    query: {
      type: 'shop_schedule',
      shop_id: String(scheduleShop.value?.id || route.params.shopId || ''),
      subject_name: scheduleShop.value?.name || '当前店铺排班',
      month: activeMonth.value,
      back: router.resolve({
        name: 'shop-schedule',
        params: { shopId: route.params.shopId },
        query: {
          ...route.query,
          month: activeMonth.value,
        },
      }).fullPath,
    },
  })
}

function defaultPalettePosition() {
  const width = typeof window !== 'undefined' ? window.innerWidth : 1440
  return {
    x: Math.max(12, width - 360),
    y: 132,
  }
}

function clampPalettePosition() {
  if (typeof window === 'undefined' || isMobileViewport.value) {
    return
  }
  const paletteWidth = staffPaletteRef.value?.offsetWidth || 320
  const paletteHeight = staffPaletteRef.value?.offsetHeight || 220
  const maxX = Math.max(12, window.innerWidth - paletteWidth - 12)
  const maxY = Math.max(12, window.innerHeight - paletteHeight - 12)
  palettePosition.value = {
    x: Math.min(Math.max(12, palettePosition.value.x), maxX),
    y: Math.min(Math.max(12, palettePosition.value.y), maxY),
  }
}

function syncPalettePosition(reset = false) {
  if (typeof window === 'undefined') {
    return
  }
  nextTick(() => {
    if (isMobileViewport.value) {
      paletteReady.value = false
      return
    }
    if (reset || !paletteReady.value) {
      palettePosition.value = defaultPalettePosition()
    }
    clampPalettePosition()
    paletteReady.value = true
  })
}

function stopPaletteDragging() {
  if (!paletteDragState.active) {
    return
  }
  paletteDragState.active = false
  paletteDragState.pointerId = null
  window.removeEventListener('pointermove', handlePalettePointerMove)
  window.removeEventListener('pointerup', stopPaletteDragging)
  window.removeEventListener('pointercancel', stopPaletteDragging)
}

function handlePalettePointerMove(event) {
  if (!paletteDragState.active || isMobileViewport.value) {
    return
  }
  palettePosition.value = {
    x: Number(event.clientX || 0) - paletteDragState.offsetX,
    y: Number(event.clientY || 0) - paletteDragState.offsetY,
  }
  clampPalettePosition()
}

function handlePalettePointerDown(event) {
  if (isMobileViewport.value) {
    return
  }
  const paletteRect = staffPaletteRef.value?.getBoundingClientRect?.()
  if (!paletteRect) {
    return
  }
  paletteDragState.active = true
  paletteDragState.pointerId = event.pointerId
  paletteDragState.offsetX = Number(event.clientX || 0) - paletteRect.left
  paletteDragState.offsetY = Number(event.clientY || 0) - paletteRect.top
  window.addEventListener('pointermove', handlePalettePointerMove)
  window.addEventListener('pointerup', stopPaletteDragging)
  window.addEventListener('pointercancel', stopPaletteDragging)
}

function handleWindowResize() {
  syncPalettePosition(false)
}

function handleWindowBeforeUnload(event) {
  if (!editMode.value || !hasUnsavedChanges.value) {
    return
  }
  event.preventDefault()
  event.returnValue = ''
}

watch(
  () => [route.params.shopId, route.query.month],
  () => {
    activeMonth.value = resolveInitialMonth()
    void loadSchedule()
  },
)

watch(editMode, (nextValue) => {
  if (!nextValue) {
    stopPaletteDragging()
    return
  }
  syncPalettePosition(true)
})

watch(isMobileViewport, () => {
  syncPalettePosition(false)
})

onMounted(() => {
  window.addEventListener('beforeunload', handleWindowBeforeUnload)
  window.addEventListener('resize', handleWindowResize)
  void loadSchedule()
})

onBeforeRouteLeave(async () => {
  if (!editMode.value || !hasUnsavedChanges.value) {
    return true
  }
  return confirmDiscardChanges('当前排班有未保存的修改，确认离开当前页面吗？', '离开确认', '确认离开')
})

onBeforeRouteUpdate(async (to, from) => {
  if (!editMode.value || !hasUnsavedChanges.value) {
    return true
  }
  if (to.fullPath === from.fullPath) {
    return true
  }
  const stayingOnSchedulePage = to.name === 'shop-schedule' && from.name === 'shop-schedule'
  if (stayingOnSchedulePage) {
    return confirmDiscardChanges('当前排班有未保存的修改，切换当前排班视图不会保存这些调整，确认继续吗？', '切换确认', '确认切换')
  }
  return confirmDiscardChanges('当前排班有未保存的修改，确认离开当前页面吗？', '离开确认', '确认离开')
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', handleWindowBeforeUnload)
  window.removeEventListener('resize', handleWindowResize)
  stopPaletteDragging()
})
</script>
