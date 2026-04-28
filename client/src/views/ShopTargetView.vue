<template>
  <section class="shop-target-page account-page">
    <article class="card-surface account-overview-hero motion-fade-slide shop-target-hero">
      <div class="account-overview-copy">
        <p class="panel-tag">目标</p>
        <h2>{{ targetShop.name || '店铺目标' }}</h2>
        <div class="account-overview-meta">
          <span>{{ yearLabel }}</span>
          <span>{{ targetShop.managerName ? `店长 ${targetShop.managerName}` : '未设置店长' }}</span>
          <span>{{ canEdit ? '可按月份编辑' : '当前仅查看' }}</span>
        </div>
      </div>

      <div class="toolbar-actions account-overview-actions shop-target-hero-actions">
        <el-button @click="goBack">返回店铺/仓库管理</el-button>
        <el-button @click="openLogCenter">目标日志</el-button>
      </div>
    </article>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" show-icon />

    <article
      v-if="currentMonthCard"
      class="card-surface sales-calendar-card motion-fade-slide shop-target-current-card-panel"
      style="--motion-delay: 0.06s"
    >
      <header class="sales-filter-head sales-calendar-head shop-target-calendar-head">
        <div class="sales-filter-head-copy sales-calendar-summary-head">
          <h2>本月目标</h2>
          <span>本月卡片会单独置顶，月历中仍保留当月显示。</span>
        </div>
      </header>

      <button
        type="button"
        class="shop-target-month-card shop-target-month-card-current"
        @click="openDetail(currentMonthCard)"
      >
        <div class="shop-target-month-head">
          <div class="shop-target-month-head-copy">
            <strong>{{ currentMonthCard.monthLabel }}</strong>
            <span class="shop-target-month-badge">本月</span>
          </div>
          <span class="shop-target-ratio-chip">{{ formatPercent(currentMonthCard.completionRatio) }}</span>
        </div>

        <div class="shop-target-month-metrics shop-target-month-metrics-compact">
          <article class="shop-target-month-metric">
            <span>目标</span>
            <strong>¥ {{ formatMoney(resolveDisplayedTargetAmount(currentMonthCard)) }}</strong>
          </article>
          <article class="shop-target-month-metric">
            <span>实际</span>
            <strong>¥ {{ formatMoney(currentMonthCard.actualAmount) }}</strong>
          </article>
        </div>

        <div class="shop-target-current-extra">
          <article class="shop-target-current-extra-item">
            <span>当前阶段</span>
            <strong>{{ currentMonthCard.currentStageLabel || '未设阶段' }}</strong>
          </article>
          <article class="shop-target-current-extra-item">
            <span>阶段奖励</span>
            <strong>¥ {{ formatMoney(currentMonthCard.totalStageReward) }}</strong>
          </article>
          <article class="shop-target-current-extra-item">
            <span>型号奖励</span>
            <strong>¥ {{ formatMoney(currentMonthCard.totalModelReward) }}</strong>
          </article>
          <article class="shop-target-current-extra-item">
            <span>目标型号</span>
            <strong>{{ currentMonthCard.modelGoals.length }} 个</strong>
          </article>
        </div>

        <div class="shop-target-month-foot">
          <strong>{{ currentMonthCard.currentStageLabel || '未设阶段' }}</strong>
          <span>阶段奖励 ¥ {{ formatMoney(currentMonthCard.totalStageReward) }} · 型号奖励 ¥ {{ formatMoney(currentMonthCard.totalModelReward) }}</span>
        </div>

        <div class="shop-target-progress-shell">
          <div class="shop-target-progress-track"></div>
          <div class="shop-target-progress-fill" :style="{ width: `${monthProgressPercent(currentMonthCard)}%` }"></div>
          <div
            v-for="stage in currentMonthCard.stages"
            :key="`${currentMonthCard.month}-stage-${stage.level}`"
            class="shop-target-progress-node"
            :class="{ achieved: stage.achieved }"
            :style="{ left: `${monthStagePercent(currentMonthCard, stage)}%` }"
          >
            <span class="shop-target-progress-dot"></span>
            <small>阶段 {{ stage.level }}</small>
            <span class="shop-target-progress-value">¥{{ formatCompactMoney(stage.targetAmount) }}</span>
          </div>
        </div>
      </button>
    </article>

    <article class="card-surface sales-calendar-card motion-fade-slide shop-target-calendar-card" style="--motion-delay: 0.08s">
      <header class="sales-filter-head sales-calendar-head shop-target-calendar-head">
        <div class="sales-filter-head-copy sales-calendar-summary-head">
          <h2>目标月历</h2>
          <span>{{ canEdit ? '点击月份查看详情，编辑入口在详情弹窗中。' : '点击月份查看当月目标详情。' }}</span>
        </div>

        <div class="sales-calendar-nav shop-target-nav">
          <el-button @click="shiftYear(-1)">上一年</el-button>
          <el-date-picker
            :model-value="String(activeYear)"
            type="year"
            value-format="YYYY"
            class="shop-target-year-picker"
            @update:model-value="handleYearChange"
          />
          <el-button @click="shiftYear(1)">下一年</el-button>
        </div>
      </header>

      <div v-loading="loading" class="shop-target-grid">
        <button
          v-for="month in displayMonths"
          :key="month.month"
          type="button"
          class="shop-target-month-card"
          :class="{ empty: !hasMonthConfig(month) && !month.actualAmount, current: isCurrentMonth(month) }"
          @click="openDetail(month)"
        >
          <div class="shop-target-month-head">
            <div class="shop-target-month-head-copy">
              <strong>{{ month.monthLabel }}</strong>
              <span v-if="isCurrentMonth(month)" class="shop-target-month-badge">本月</span>
            </div>
            <span class="shop-target-ratio-chip">{{ formatPercent(month.completionRatio) }}</span>
          </div>

          <div class="shop-target-month-metrics shop-target-month-metrics-compact">
            <article class="shop-target-month-metric">
              <span>目标</span>
              <strong>¥ {{ formatMoney(resolveDisplayedTargetAmount(month)) }}</strong>
            </article>
            <article class="shop-target-month-metric">
              <span>实际</span>
              <strong>¥ {{ formatMoney(month.actualAmount) }}</strong>
            </article>
          </div>

          <div class="shop-target-month-foot">
            <strong>{{ month.currentStageLabel || '未设阶段' }}</strong>
            <span>阶段奖励 ¥ {{ formatMoney(month.totalStageReward) }} · 型号奖励 ¥ {{ formatMoney(month.totalModelReward) }}</span>
          </div>

          <div class="shop-target-progress-shell">
            <div class="shop-target-progress-track"></div>
            <div class="shop-target-progress-fill" :style="{ width: `${monthProgressPercent(month)}%` }"></div>
            <div
              v-for="stage in month.stages"
              :key="`${month.month}-stage-${stage.level}`"
              class="shop-target-progress-node"
              :class="{ achieved: stage.achieved }"
              :style="{ left: `${monthStagePercent(month, stage)}%` }"
            >
              <span class="shop-target-progress-dot"></span>
              <small>阶段 {{ stage.level }}</small>
              <span class="shop-target-progress-value">¥{{ formatCompactMoney(stage.targetAmount) }}</span>
            </div>
          </div>
        </button>
      </div>
    </article>

    <ResponsiveDialog
      v-model="detailVisible"
      :title="detailMonth?.monthLabel || '目标详情'"
      mobile-title="目标详情"
      mobile-subtitle="店铺目标"
      width="min(960px, 96vw)"
      class="aqc-app-dialog shop-target-detail-dialog"
      :initial-snap="0.72"
      :expanded-snap="0.95"
      @closed="detailMonth = null"
    >
      <div v-if="detailMonth" class="shop-target-detail-shell">
        <section class="inventory-hero-card inventory-hero-card-strong shop-target-detail-hero">
          <span>目标完成比值</span>
          <strong>{{ formatPercent(detailMonth.completionRatio) }}</strong>
          <h3>{{ detailMonth.currentStageLabel || '未设阶段' }}</h3>
          <p>目标额 ¥ {{ formatMoney(resolveDisplayedTargetAmount(detailMonth)) }} · 实际销售额 ¥ {{ formatMoney(detailMonth.actualAmount) }}</p>
        </section>

        <section class="shop-target-detail-section">
          <header class="shop-target-detail-section-head">
            <strong>阶段目标</strong>
            <span>当前阶段奖励 ¥ {{ formatMoney(detailMonth.currentStageRewardAmount) }}</span>
          </header>
          <div class="shop-target-progress-shell detail">
            <div class="shop-target-progress-track"></div>
            <div class="shop-target-progress-fill" :style="{ width: `${monthProgressPercent(detailMonth)}%` }"></div>
            <div
              v-for="stage in detailMonth.stages"
              :key="`${detailMonth.month}-detail-stage-${stage.level}`"
              class="shop-target-progress-node"
              :class="{ achieved: stage.achieved }"
              :style="{ left: `${monthStagePercent(detailMonth, stage)}%` }"
            >
              <span class="shop-target-progress-dot"></span>
              <small>阶段 {{ stage.level }}</small>
              <span class="shop-target-progress-value">¥{{ formatCompactMoney(stage.targetAmount) }}</span>
            </div>
          </div>

          <div class="shop-target-detail-stats">
            <article class="shop-target-detail-stat">
              <span>阶段达成</span>
              <strong>{{ detailMonth.currentStageLevel }} 阶</strong>
            </article>
            <article class="shop-target-detail-stat">
              <span>阶段奖励</span>
              <strong>¥ {{ formatMoney(detailMonth.totalStageReward) }}</strong>
            </article>
            <article class="shop-target-detail-stat">
              <span>型号奖励</span>
              <strong>¥ {{ formatMoney(detailMonth.totalModelReward) }}</strong>
            </article>
          </div>
        </section>

        <section class="shop-target-detail-section">
          <header class="shop-target-detail-section-head">
            <strong>店员贡献占比</strong>
            <span>{{ detailMonth.contributions.length }} 人</span>
          </header>
          <div v-if="detailMonth.contributions.length" class="shop-target-detail-list">
            <article v-for="item in detailMonth.contributions" :key="`${detailMonth.month}-${item.label}`" class="shop-target-detail-list-item">
              <div>
                <strong>{{ item.label }}</strong>
                <span>{{ formatPercent(item.ratio) }}</span>
              </div>
              <strong>¥ {{ formatMoney(item.amount) }}</strong>
            </article>
          </div>
          <div v-else class="shop-target-empty">当月暂无人员贡献数据。</div>
        </section>

        <section class="shop-target-detail-section">
          <header class="shop-target-detail-section-head">
            <strong>目标型号完成情况</strong>
            <span>{{ detailMonth.modelGoals.length }} 个</span>
          </header>
          <div v-if="detailMonth.modelGoals.length" class="shop-target-detail-list">
            <article v-for="item in detailMonth.modelGoals" :key="`${detailMonth.month}-${buildGoalSignature(item)}`" class="shop-target-detail-list-item">
              <div>
                <strong>{{ item.modelDisplay || item.name }}</strong>
                <span>{{ formatModelGoalMeta(item) }}</span>
              </div>
              <strong>{{ formatModelGoalProgress(item) }} · {{ formatModelGoalRewardSummary(item) }}</strong>
            </article>
          </div>
          <div v-else class="shop-target-empty">当月还没有配置型号目标。</div>
        </section>
      </div>

      <template #footer>
        <div class="form-actions">
          <el-button @click="detailVisible = false">关闭</el-button>
          <el-button v-if="canEdit && detailMonth" type="primary" @click="openEditor(detailMonth)">编辑本月目标</el-button>
        </div>
      </template>
    </ResponsiveDialog>

    <ResponsiveDialog
      v-model="editorVisible"
      :title="editorDraft.monthLabel || '编辑目标'"
      width="min(980px, 96vw)"
      class="aqc-app-dialog shop-target-editor-dialog"
      mobile-subtitle="店铺目标"
    >
      <div class="shop-target-editor-shell">
        <section class="shop-target-editor-main">
          <section class="shop-target-editor-block">
            <header class="shop-target-editor-block-head">
              <strong>阶段目标</strong>
              <el-button type="primary" text @click="addStage">新增阶段</el-button>
            </header>
            <div v-if="editorDraft.stages.length" class="shop-target-editor-list">
              <article v-for="(item, index) in editorDraft.stages" :key="item.localId" class="shop-target-editor-row">
                <strong class="shop-target-editor-row-index">阶段 {{ index + 1 }}</strong>
                <el-input-number v-model="item.targetAmount" :min="0" :step="1000" :precision="2" class="full-width" />
                <el-input-number v-model="item.rewardAmount" :min="0" :step="100" :precision="2" class="full-width" />
                <button type="button" class="shop-schedule-assignment-remove shop-target-inline-remove" @click="removeStage(index)">×</button>
              </article>
            </div>
            <div v-else class="shop-target-empty">还没有设置阶段目标。</div>
          </section>

          <section class="shop-target-editor-block">
            <header class="shop-target-editor-block-head">
              <div>
                <strong>目标型号</strong>
                <span>点击新增型号后可批量选择商品，每销售一只就按该型号奖励金额计奖一次。</span>
              </div>
              <el-button type="primary" text @click="goodsPickerVisible = true">新增型号</el-button>
            </header>

            <div v-if="editorDraft.modelGoals.length" class="shop-target-editor-list target-goal-list">
              <article v-for="(item, index) in editorDraft.modelGoals" :key="item.localId" class="shop-target-editor-card">
                <div class="shop-target-editor-card-head">
                  <div class="shop-target-model-copy">
                    <strong>{{ item.modelDisplay || item.name }}</strong>
                    <span>{{ formatModelGoalMeta(item) }}</span>
                  </div>
                  <button type="button" class="shop-schedule-assignment-remove shop-target-inline-remove" @click="removeModelGoal(index)">×</button>
                </div>

                <div class="shop-target-model-row">
                  <div class="shop-target-model-row-main">
                    <span>当前按该型号的实际销售件数统计完成情况，每销售一只就累计一次奖励金额。</span>
                  </div>
                  <div class="shop-target-editor-field">
                    <label class="shop-editor-label">单只奖励金额</label>
                    <el-input-number v-model="item.rewardAmount" :min="0" :step="100" :precision="2" class="full-width" />
                  </div>
                </div>
              </article>
            </div>
            <div v-else class="shop-target-empty">还没有设置目标型号。</div>
          </section>
        </section>
      </div>

      <template #footer>
        <div class="form-actions">
          <el-button @click="editorVisible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="saveCurrentMonth">保存本月目标</el-button>
        </div>
      </template>
    </ResponsiveDialog>

    <WorkOrderGoodsPickerDialog
      v-model="goodsPickerVisible"
      title="新增目标型号"
      multiple
      :distribution-shop-id="targetShop.id || null"
      quantity-label="店铺库存"
      :selected-items="selectedModelPickerItems"
      @confirm="handleModelPickerConfirm"
    />
  </section>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import ResponsiveDialog from '../components/ResponsiveDialog.vue'
import WorkOrderGoodsPickerDialog from '../components/WorkOrderGoodsPickerDialog.vue'
import { apiGet, apiPut } from '../services/api'
import { useAuthStore } from '../stores/auth'
import { buildLogCenterQuery } from '../utils/logCenter'
import { getShanghaiParts } from '../utils/shanghaiTime'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

const loading = ref(false)
const saving = ref(false)
const canEdit = ref(false)
const errorMessage = ref('')
const activeYear = ref(resolveInitialYear())
const targetShop = ref({ id: Number(route.params.shopId || 0), name: '', managerName: '' })
const baseMonths = ref([])
const detailVisible = ref(false)
const detailMonth = ref(null)
const editorVisible = ref(false)
const goodsPickerVisible = ref(false)
const editorDraft = reactive(createEmptyEditorDraft())
let stageDraftSeed = 0
let modelGoalDraftSeed = 0

function resolveInitialYear() {
  const raw = Number(route.query.year || new Date().getFullYear())
  return Number.isInteger(raw) && raw >= 2000 && raw <= 2100 ? raw : new Date().getFullYear()
}

function createEmptyEditorDraft() {
  return {
    month: '',
    monthLabel: '',
    stages: [],
    modelGoals: [],
  }
}

function cloneData(value) {
  return JSON.parse(JSON.stringify(value || null))
}

function cleanText(value) {
  return String(value || '').trim()
}

function formatMoney(value) {
  return Number(value || 0).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function formatCompactMoney(value) {
  const amount = Number(value || 0)
  if (Math.abs(amount) >= 10000) {
    return `${(amount / 10000).toFixed(1)}w`
  }
  return Number.isInteger(amount) ? String(amount) : amount.toFixed(2)
}

function formatPercent(value) {
  return `${(Number(value || 0) * 100).toFixed(1)}%`
}

function resolveDisplayedTargetAmount(month) {
  const currentStageTargetAmount = Number(month?.currentStageTargetAmount || 0)
  if (currentStageTargetAmount > 0) {
    return currentStageTargetAmount
  }
  return Number(month?.targetAmount || 0)
}

function nextStageDraftId() {
  stageDraftSeed += 1
  return `stage-draft-${stageDraftSeed}`
}

function nextModelGoalDraftId() {
  modelGoalDraftSeed += 1
  return `model-goal-draft-${modelGoalDraftSeed}`
}

function createStageDraft(stage = {}) {
  return {
    localId: nextStageDraftId(),
    targetAmount: Number(stage?.targetAmount || 0),
    rewardAmount: Number(stage?.rewardAmount || 0),
  }
}

function createModelGoalDraft(goal = {}) {
  return {
    ...goal,
    localId: cleanText(goal?.localId) || nextModelGoalDraftId(),
  }
}

function buildGoalSignature(goal) {
  const goodsId = Number(goal?.goodsId || 0)
  if (goodsId) {
    return `goods-${goodsId}`
  }
  const models = Array.isArray(goal?.models) ? goal.models.map((item) => cleanText(item).toUpperCase()).filter(Boolean) : []
  return models.join('|') || cleanText(goal?.name).toUpperCase()
}

function formatModelGoalMeta(goal) {
  const parts = [cleanText(goal?.brand), cleanText(goal?.series), cleanText(goal?.barcode)].filter(Boolean)
  if (parts.length) {
    return parts.join(' / ')
  }
  const models = Array.isArray(goal?.models) ? goal.models.map((item) => cleanText(item)).filter(Boolean) : []
  return models.join(' / ') || '未设型号'
}

function formatModelGoalProgress(goal) {
  const completedQuantity = Number(goal?.completedQuantity || 0)
  return completedQuantity > 0 ? `已售 ${completedQuantity} 件` : '暂未售出'
}

function formatModelGoalRewardSummary(goal) {
  const rewardAmount = Number(goal?.rewardAmount || 0)
  const completedQuantity = Math.max(0, Number(goal?.completedQuantity || 0))
  const earnedAmount = rewardAmount * completedQuantity
  if (completedQuantity > 0) {
    return `每只 ¥ ${formatMoney(rewardAmount)} · 已奖 ¥ ${formatMoney(earnedAmount)}`
  }
  return `每只 ¥ ${formatMoney(rewardAmount)}`
}

function sanitizeStageDrafts(stages) {
  return (stages || [])
    .map((item, index) => ({
      level: index + 1,
      targetAmount: Number(item?.targetAmount || 0),
      rewardAmount: Number(item?.rewardAmount || 0),
    }))
    .filter((item) => item.targetAmount > 0)
}

function sanitizeModelGoalDrafts(goals) {
  return (goals || [])
    .map((item) => ({
      goodsId: Number(item?.goodsId || 0),
      name: cleanText(item?.name) || cleanText(item?.modelDisplay) || '未命名目标',
      modelDisplay: cleanText(item?.modelDisplay),
      brand: cleanText(item?.brand),
      series: cleanText(item?.series),
      barcode: cleanText(item?.barcode),
      models: Array.isArray(item?.models) ? item.models.map((model) => cleanText(model)).filter(Boolean) : [],
      targetQuantity: 0,
      rewardAmount: Number(item?.rewardAmount || 0),
      completedQuantity: Number(item?.completedQuantity || 0),
      achieved: Boolean(item?.achieved),
    }))
    .filter((item) => item.goodsId > 0 || item.models.length || item.name)
}

function normalizeStage(stage, index = 0) {
  return {
    level: Number(stage?.level || index + 1),
    targetAmount: Number(stage?.targetAmount || 0),
    rewardAmount: Number(stage?.rewardAmount || 0),
    achieved: Boolean(stage?.achieved),
  }
}

function normalizeGoal(goal) {
  const models = Array.isArray(goal?.models) ? goal.models.map((item) => cleanText(item)).filter(Boolean) : []
  const modelDisplay = cleanText(goal?.modelDisplay) || (models.length === 1 ? models[0] : '')
  return {
    goodsId: Number(goal?.goodsId || 0),
    name: cleanText(goal?.name) || modelDisplay || '未命名目标',
    modelDisplay,
    brand: cleanText(goal?.brand),
    series: cleanText(goal?.series),
    barcode: cleanText(goal?.barcode),
    models,
    targetQuantity: 0,
    completedQuantity: Number(goal?.completedQuantity || 0),
    rewardAmount: Number(goal?.rewardAmount || 0),
    achieved: Boolean(goal?.achieved),
  }
}

function normalizeModelGoalsWithCounts(modelGoals, modelSales) {
  return (modelGoals || []).map((item) => {
    const goal = normalizeGoal(item)
    const completedQuantity = (modelSales || []).reduce((sum, row) => {
      const label = cleanText(row.label).toUpperCase()
      const matched = goal.models.some((model) => {
        const token = cleanText(model).toUpperCase()
        return token && (label === token || label.startsWith(token))
      })
      return matched ? sum + Number(row.quantity || 0) : sum
    }, 0)
    return {
      ...goal,
      completedQuantity,
      achieved: completedQuantity > 0,
    }
  })
}

function recalculateMonth(month) {
  const normalized = cloneData(month) || {}
  normalized.targetAmount = Number(normalized.targetAmount || 0)
  normalized.actualAmount = Number(normalized.actualAmount || 0)
  normalized.stages = Array.isArray(normalized.stages)
    ? normalized.stages
        .map((item, index) => ({
          level: index + 1,
          targetAmount: Number(item?.targetAmount || 0),
          rewardAmount: Number(item?.rewardAmount || 0),
          achieved: false,
        }))
        .filter((item) => item.targetAmount > 0)
        .sort((left, right) => left.targetAmount - right.targetAmount)
        .map((item, index) => ({ ...item, level: index + 1 }))
    : []
  if (!normalized.stages.length && normalized.targetAmount > 0) {
    normalized.stages = [{ level: 1, targetAmount: normalized.targetAmount, rewardAmount: 0, achieved: false }]
  }
  normalized.modelGoals = normalizeModelGoalsWithCounts(
    Array.isArray(normalized.modelGoals) ? normalized.modelGoals.map(normalizeGoal) : [],
    normalized.modelSales || [],
  )
  normalized.targetAmount = Math.max(
    Number(normalized.targetAmount || 0),
    ...normalized.stages.map((item) => Number(item.targetAmount || 0)),
    0,
  )
  normalized.completionRatio = normalized.targetAmount > 0 ? normalized.actualAmount / normalized.targetAmount : 0
  normalized.currentStageLevel = 0
  normalized.totalStageReward = 0
  normalized.currentStageTargetAmount = normalized.targetAmount
  normalized.currentStageRewardAmount = 0
  for (const stage of normalized.stages) {
    stage.achieved = normalized.actualAmount >= Number(stage.targetAmount || 0)
    if (stage.achieved) {
      normalized.currentStageLevel = Math.max(normalized.currentStageLevel, Number(stage.level || 0))
      normalized.totalStageReward = Number(stage.rewardAmount || 0)
    }
  }
  const nextStage = normalized.stages.find((item) => !item.achieved) || normalized.stages.at(-1)
  if (nextStage) {
    normalized.currentStageTargetAmount = Number(nextStage.targetAmount || normalized.targetAmount || 0)
    normalized.currentStageRewardAmount = Number(nextStage.rewardAmount || 0)
  }
  normalized.totalModelReward = normalized.modelGoals.reduce((sum, item) => (
    sum + Math.max(0, Number(item.completedQuantity || 0)) * Number(item.rewardAmount || 0)
  ), 0)
  if (!normalized.stages.length && normalized.targetAmount <= 0) {
    normalized.currentStageLabel = '未设目标'
  } else if (normalized.currentStageLevel >= normalized.stages.length && normalized.stages.length) {
    normalized.currentStageLabel = `已完成阶段 ${normalized.currentStageLevel}`
  } else {
    normalized.currentStageLabel = `进行中 · 阶段 ${Math.max(1, normalized.currentStageLevel + 1)}`
  }
  return normalized
}

function normalizeMonth(month) {
  return recalculateMonth({
    month: cleanText(month?.month),
    monthLabel: cleanText(month?.monthLabel),
    targetAmount: Number(month?.targetAmount || 0),
    actualAmount: Number(month?.actualAmount || 0),
    completionRatio: Number(month?.completionRatio || 0),
    currentStageLevel: Number(month?.currentStageLevel || 0),
    currentStageLabel: cleanText(month?.currentStageLabel),
    currentStageTargetAmount: Number(month?.currentStageTargetAmount || 0),
    currentStageRewardAmount: Number(month?.currentStageRewardAmount || 0),
    totalStageReward: Number(month?.totalStageReward || 0),
    totalModelReward: Number(month?.totalModelReward || 0),
    stages: Array.isArray(month?.stages) ? month.stages.map((item, index) => normalizeStage(item, index)) : [],
    modelGoals: Array.isArray(month?.modelGoals) ? month.modelGoals.map(normalizeGoal) : [],
    contributions: Array.isArray(month?.contributions)
      ? month.contributions.map((item) => ({
          label: cleanText(item?.label) || '未登记人员',
          amount: Number(item?.amount || 0),
          ratio: Number(item?.ratio || 0),
        }))
      : [],
    modelSales: Array.isArray(month?.modelSales)
      ? month.modelSales.map((item) => ({
          label: cleanText(item?.label),
          quantity: Number(item?.quantity || 0),
        })).filter((item) => item.label)
      : [],
  })
}

function hasMonthConfig(month) {
  return Number(month?.targetAmount || 0) > 0 || (month?.stages?.length || 0) > 0 || (month?.modelGoals?.length || 0) > 0
}

function monthProgressMax(month) {
  const stageMax = Math.max(0, ...((month?.stages || []).map((item) => Number(item.targetAmount || 0))))
  return Math.max(stageMax, Number(month?.targetAmount || 0), Number(month?.actualAmount || 0), 1)
}

function monthProgressPercent(month) {
  return Math.min(100, Math.max(0, Number(month?.actualAmount || 0) / monthProgressMax(month) * 100))
}

function monthStagePercent(month, stage) {
  return Math.min(100, Math.max(0, Number(stage?.targetAmount || 0) / monthProgressMax(month) * 100))
}

const yearLabel = computed(() => `${activeYear.value} 年`)
const displayMonths = computed(() => baseMonths.value.map(recalculateMonth))
const currentMonthToken = computed(() => {
  const parts = getShanghaiParts()
  if (Number(parts.year || 0) !== Number(activeYear.value || 0)) {
    return ''
  }
  return `${parts.year}-${parts.month}`
})
const currentMonthCard = computed(() => (
  displayMonths.value.find((item) => item.month === currentMonthToken.value) || null
))
const selectedModelPickerItems = computed(() => (
  editorDraft.modelGoals.map((item) => ({
    id: Number(item.goodsId || 0),
    model: item.modelDisplay || item.models[0] || item.name,
    barcode: item.barcode || '',
    brand: item.brand || '',
    series: item.series || '',
    name: item.name || '',
  })).filter((item) => item.id)
))

async function loadTargetPage() {
  loading.value = true
  errorMessage.value = ''
  const payload = await apiGet(`/shop-targets/${route.params.shopId}`, {
    token: authStore.token,
    query: { year: String(activeYear.value) },
  })
  loading.value = false
  if (!payload?.success) {
    targetShop.value = { id: Number(route.params.shopId || 0), name: '', managerName: '' }
    baseMonths.value = []
    canEdit.value = false
    errorMessage.value = payload?.message || '目标数据加载失败'
    detailVisible.value = false
    editorVisible.value = false
    return
  }
  targetShop.value = {
    id: Number(payload.shop?.id || route.params.shopId || 0),
    name: cleanText(payload.shop?.name),
    managerName: cleanText(payload.shop?.managerName),
  }
  canEdit.value = Boolean(payload.canEdit)
  activeYear.value = Number(payload.year || activeYear.value)
  baseMonths.value = Array.isArray(payload.months) ? payload.months.map(normalizeMonth) : []
}

function goBack() {
  router.push({ name: 'shops-manage' })
}

function shiftYear(offset) {
  void handleYearChange(String(activeYear.value + Number(offset || 0)))
}

async function handleYearChange(value) {
  const nextYear = Number(value || 0)
  if (!Number.isInteger(nextYear) || nextYear < 2000 || nextYear > 2100 || nextYear === activeYear.value) {
    return
  }
  await router.replace({
    name: 'shop-target',
    params: { shopId: route.params.shopId },
    query: {
      ...route.query,
      year: String(nextYear),
    },
  })
}

function openDetail(month) {
  detailMonth.value = cloneData(recalculateMonth(month))
  detailVisible.value = true
}

function isCurrentMonth(month) {
  return cleanText(month?.month) === currentMonthToken.value
}

function fillEditorDraft(month) {
  editorDraft.month = cleanText(month?.month)
  editorDraft.monthLabel = cleanText(month?.monthLabel)
  editorDraft.stages = (month?.stages || []).map((item) => createStageDraft(item))
  editorDraft.modelGoals = (month?.modelGoals || []).map((item) => createModelGoalDraft(normalizeGoal(item)))
}

function openEditor(month = detailMonth.value) {
  if (!canEdit.value || !month) {
    return
  }
  fillEditorDraft(month)
  editorVisible.value = true
}

function addStage() {
  editorDraft.stages.push(createStageDraft())
}

function removeStage(index) {
  editorDraft.stages.splice(index, 1)
}

function createModelGoalFromGoods(goods, existingGoal = null) {
  const goodsId = Number(goods?.id || existingGoal?.goodsId || 0)
  const modelDisplay = cleanText(goods?.model || existingGoal?.modelDisplay || existingGoal?.models?.[0] || goods?.name || goods?.barcode)
  const brand = cleanText(goods?.brand || existingGoal?.brand)
  const series = cleanText(goods?.series || existingGoal?.series)
  const barcode = cleanText(goods?.barcode || existingGoal?.barcode)
  return createModelGoalDraft({
    goodsId,
    name: [brand, series, modelDisplay].filter(Boolean).join(' ') || modelDisplay || cleanText(existingGoal?.name) || `商品 ${goodsId || ''}`,
    modelDisplay,
    brand,
    series,
    barcode,
    models: modelDisplay ? [modelDisplay] : (Array.isArray(existingGoal?.models) ? existingGoal.models.map((item) => cleanText(item)).filter(Boolean) : []),
    targetQuantity: 0,
    completedQuantity: Number(existingGoal?.completedQuantity || 0),
    rewardAmount: Number(existingGoal?.rewardAmount || 0),
    achieved: Boolean(existingGoal?.achieved),
  })
}

function handleModelPickerConfirm(rows) {
  const nextGoals = [...editorDraft.modelGoals]
  const signatures = new Set(nextGoals.map((item) => buildGoalSignature(item)))
  for (const row of rows || []) {
    const nextGoal = createModelGoalFromGoods(row)
    const signature = buildGoalSignature(nextGoal)
    if (!signature || signatures.has(signature)) {
      continue
    }
    signatures.add(signature)
    nextGoals.push(nextGoal)
  }
  editorDraft.modelGoals = nextGoals
}

function removeModelGoal(index) {
  editorDraft.modelGoals.splice(index, 1)
}

function buildEditedMonth() {
  const baseMonth = baseMonths.value.find((item) => item.month === editorDraft.month)
  if (!baseMonth) {
    return null
  }
  const stages = sanitizeStageDrafts(editorDraft.stages)
  const targetAmount = Math.max(0, ...stages.map((item) => Number(item.targetAmount || 0)))
  return recalculateMonth({
    ...baseMonth,
    targetAmount,
    stages,
    modelGoals: sanitizeModelGoalDrafts(editorDraft.modelGoals).map((item) => ({
      ...item,
      completedQuantity: 0,
      achieved: false,
    })),
  })
}

function buildDraftSaveMonth() {
  const stages = sanitizeStageDrafts(editorDraft.stages)
  const modelGoals = sanitizeModelGoalDrafts(editorDraft.modelGoals)
  return {
    month: editorDraft.month,
    targetAmount: Math.max(0, ...stages.map((item) => Number(item.targetAmount || 0))),
    stages: stages.map((item) => ({
      targetAmount: Number(item.targetAmount || 0),
      rewardAmount: Number(item.rewardAmount || 0),
    })),
    modelGoals: modelGoals.map((item) => ({
      goodsId: Number(item.goodsId || 0) || null,
      name: cleanText(item.name),
      modelDisplay: cleanText(item.modelDisplay),
      brand: cleanText(item.brand),
      series: cleanText(item.series),
      barcode: cleanText(item.barcode),
      models: Array.isArray(item.models) ? item.models.map((model) => cleanText(model)).filter(Boolean) : [],
      targetQuantity: 0,
      rewardAmount: Number(item.rewardAmount || 0),
    })),
  }
}

function syncDetailMonth(monthKey = detailMonth.value?.month) {
  const cleanMonth = cleanText(monthKey)
  if (!cleanMonth) {
    detailMonth.value = null
    return
  }
  const matched = displayMonths.value.find((item) => item.month === cleanMonth)
  if (!matched) {
    detailVisible.value = false
    detailMonth.value = null
    return
  }
  detailMonth.value = cloneData(matched)
}

async function saveCurrentMonth() {
  if (!canEdit.value) {
    return
  }
  const nextMonth = buildEditedMonth()
  if (!nextMonth) {
    ElMessage.error('当前月份数据不存在，无法保存')
    return
  }
  saving.value = true
  const payload = await apiPut(`/shop-targets/${route.params.shopId}`, {
    year: Number(activeYear.value),
    months: [buildDraftSaveMonth()],
  }, {
    token: authStore.token,
  })
  saving.value = false
  if (!payload?.success) {
    ElMessage.error(payload?.message || '目标保存失败')
    return
  }
  ElMessage.success(payload.message || '目标已保存')
  await loadTargetPage()
  syncDetailMonth(nextMonth.month)
  editorVisible.value = false
}

function openLogCenter() {
  void router.push({
    name: 'log-center',
    query: buildLogCenterQuery({
      type: 'shop_target',
      shop_id: String(targetShop.value?.id || route.params.shopId || ''),
      subject_name: targetShop.value?.name || '当前店铺目标',
      back: router.resolve({
        name: 'shop-target',
        params: { shopId: route.params.shopId },
        query: {
          ...route.query,
          year: String(activeYear.value),
        },
      }).fullPath,
    }),
  })
}

watch(
  () => [route.params.shopId, route.query.year],
  () => {
    activeYear.value = resolveInitialYear()
    detailVisible.value = false
    editorVisible.value = false
    goodsPickerVisible.value = false
    detailMonth.value = null
    void loadTargetPage()
  },
  { immediate: true },
)
</script>
