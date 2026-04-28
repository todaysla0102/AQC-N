<template>
  <section class="update-log-history-page account-page">
    <article class="card-surface account-overview-hero motion-fade-slide">
      <div class="account-overview-copy">
        <p class="panel-tag">更新日志</p>
        <h2>历史版本日志</h2>
        <div class="account-overview-meta">
          <span>{{ filteredEntries.length }} 条记录</span>
          <span>{{ latestVersionLabel }}</span>
          <span>{{ updatedAtLabel }}</span>
        </div>
      </div>

      <div class="toolbar-actions account-overview-actions">
        <el-button @click="goBack">返回</el-button>
      </div>
    </article>

    <article class="card-surface motion-fade-slide update-log-history-filter-card" style="--motion-delay: 0.06s">
      <header class="sales-filter-head">
        <div class="sales-filter-head-copy">
          <h2>搜索与筛选</h2>
          <span>支持按关键词、范围和版本快速查看完整更新记录。</span>
        </div>
      </header>

      <div class="sales-filter-grid update-log-history-filter-grid">
        <div class="sales-filter-field sales-filter-field-wide">
          <label class="sales-filter-label">关键词</label>
          <el-input v-model.trim="keyword" placeholder="搜索标题、摘要或更新点" clearable />
        </div>

        <div class="sales-filter-field">
          <label class="sales-filter-label">范围</label>
          <el-select v-model="scopeFilter" class="full-width">
            <el-option label="全部范围" value="all" />
            <el-option
              v-for="scope in scopeOptions"
              :key="scope"
              :label="scope"
              :value="scope"
            />
          </el-select>
        </div>

        <div class="sales-filter-field">
          <label class="sales-filter-label">版本</label>
          <el-select v-model="versionFilter" class="full-width">
            <el-option label="全部版本" value="all" />
            <el-option
              v-for="version in versionOptions"
              :key="version"
              :label="version"
              :value="version"
            />
          </el-select>
        </div>
      </div>
    </article>

    <el-alert v-if="errorMessage && !entries.length" :title="errorMessage" type="error" :closable="false" show-icon />

    <section class="update-log-history-list" v-loading="loading">
      <article
        v-for="entry in pagedEntries"
        :key="`${entry.date}-${entry.version || ''}-${entry.title}`"
        class="card-surface motion-fade-slide update-log-entry"
      >
        <div class="update-log-entry-copy">
          <div class="update-log-entry-meta">
            <span>{{ entry.date }}</span>
            <span v-if="entry.version" class="update-log-entry-tag">{{ entry.version }}</span>
            <span
              v-for="scopeTag in entry.scopeTags"
              :key="`${entry.date}-${entry.version || ''}-${entry.title}-${scopeTag}`"
              class="update-log-entry-tag"
            >
              {{ scopeTag }}
            </span>
          </div>
          <strong>{{ entry.title }}</strong>
          <p v-if="entry.summary">{{ entry.summary }}</p>
        </div>
        <ul v-if="entry.highlights.length" class="update-log-entry-list">
          <li v-for="item in entry.highlights" :key="item">{{ item }}</li>
        </ul>
      </article>

      <div v-if="!loading && !filteredEntries.length" class="update-log-empty">
        <strong>没有匹配的更新日志</strong>
        <p>{{ errorMessage || '可以换一个关键词，或清空筛选条件后再试。' }}</p>
      </div>
    </section>

    <div v-if="filteredEntries.length > historyPageSize" class="pager-wrap update-log-history-pager">
      <el-pagination
        background
        :layout="pagerLayout"
        :total="filteredEntries.length"
        :current-page="historyPage"
        :page-size="historyPageSize"
        @current-change="onHistoryPageChange"
      />
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { useMobileViewport } from '../composables/useMobileViewport'
import { compareUpdateLogVersionsDesc, fetchUpdateLogEntries } from '../utils/updateLog'

const router = useRouter()
const { isMobileViewport } = useMobileViewport()

const loading = ref(false)
const keyword = ref('')
const scopeFilter = ref('all')
const versionFilter = ref('all')
const updatedAt = ref('')
const errorMessage = ref('')
const entries = ref([])
const historyPage = ref(1)
const historyPageSize = 10
const pagerLayout = computed(() => (isMobileViewport.value ? 'prev, pager, next' : 'total, prev, pager, next'))

const scopeOptions = computed(() => (
  [...new Set(entries.value.flatMap((item) => item.scopeTags || []))]
    .sort((left, right) => left.localeCompare(right, 'zh-Hans-CN'))
))
const versionOptions = computed(() => (
  [...new Set(entries.value.map((item) => item.majorVersion).filter(Boolean))]
    .sort(compareUpdateLogVersionsDesc)
))

const filteredEntries = computed(() => {
  const keywordText = String(keyword.value || '').trim().toLowerCase()
  return entries.value.filter((entry) => {
    if (scopeFilter.value !== 'all' && !(entry.scopeTags || []).includes(scopeFilter.value)) {
      return false
    }
    if (versionFilter.value !== 'all' && entry.majorVersion !== versionFilter.value) {
      return false
    }
    if (!keywordText) {
      return true
    }
    const haystack = [
      entry.date,
      entry.version,
      entry.majorVersion,
      entry.title,
      entry.scope,
      ...(entry.scopeTags || []),
      entry.summary,
      ...(entry.highlights || []),
    ]
      .join('\n')
      .toLowerCase()
    return haystack.includes(keywordText)
  })
})

const pagedEntries = computed(() => {
  const startIndex = Math.max(historyPage.value - 1, 0) * historyPageSize
  return filteredEntries.value.slice(startIndex, startIndex + historyPageSize)
})

const latestVersionLabel = computed(() => {
  const version = String(entries.value[0]?.version || '').trim()
  return version ? `最新版本 ${version}` : '全部版本'
})

const updatedAtLabel = computed(() => {
  const text = String(updatedAt.value || '').trim()
  if (!text) {
    return '更新时间待同步'
  }
  return `更新于 ${text.replace('T', ' ').slice(0, 16)}`
})

function goBack() {
  if (window.history.length > 1) {
    router.back()
    return
  }
  router.push({ name: 'dashboard' })
}

function onHistoryPageChange(nextPage) {
  historyPage.value = nextPage
}

async function loadUpdateLogHistory() {
  loading.value = true
  errorMessage.value = ''
  try {
    const payload = await fetchUpdateLogEntries()
    entries.value = payload.entries
    updatedAt.value = payload.updatedAt
  } catch (error) {
    console.error('Update log history load failed', error)
    errorMessage.value = error instanceof Error && error.message ? error.message : '更新日志读取失败'
    entries.value = []
    updatedAt.value = ''
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadUpdateLogHistory()
})

watch([keyword, scopeFilter, versionFilter], () => {
  historyPage.value = 1
})

watch(filteredEntries, (list) => {
  const maxPage = Math.max(Math.ceil(list.length / historyPageSize), 1)
  if (historyPage.value > maxPage) {
    historyPage.value = maxPage
  }
})
</script>
