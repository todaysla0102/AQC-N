<template>
  <section class="account-page account-settings-page">
    <article class="card-surface account-overview-hero motion-fade-slide">
      <div class="account-overview-copy">
        <p class="panel-tag">账户设置</p>
        <h2>{{ authStore.user?.displayName || 'AQC 成员' }}</h2>
        <div class="account-overview-meta">
          <span>{{ authStore.user?.aqcRoleName || '销售员' }}</span>
          <span>{{ shopSummary }}</span>
          <span>{{ authStore.user?.phone || authStore.user?.username || '-' }}</span>
        </div>
      </div>

      <div class="toolbar-actions account-overview-actions">
        <el-button type="primary" @click="router.push({ name: 'user-center' })">返回统计与账户</el-button>
      </div>
    </article>

    <article class="card-surface profile-card motion-fade-slide">
      <header class="section-head">
        <h2>账户设置</h2>
        <p>可以修改用户名、手机号、显示名称和登录密码。</p>
      </header>

      <el-form class="entry-form" label-position="top" @submit.prevent="saveProfile">
        <div class="entry-grid">
          <el-form-item label="用户名（手机号）">
            <el-input v-model.trim="profileForm.username" placeholder="请输入用户名" />
          </el-form-item>
          <el-form-item label="手机号">
            <el-input v-model.trim="profileForm.phone" placeholder="请输入手机号" />
          </el-form-item>
          <el-form-item label="显示名称">
            <el-input v-model.trim="profileForm.displayName" placeholder="请输入显示名称" />
          </el-form-item>
        </div>

        <div class="form-actions">
          <el-button type="primary" :loading="savingProfile" native-type="submit">保存账户信息</el-button>
        </div>
      </el-form>

      <el-form class="entry-form" label-position="top" @submit.prevent="savePassword">
        <div class="entry-grid">
          <el-form-item label="新密码">
            <el-input v-model.trim="passwordForm.password" type="password" show-password placeholder="请输入新密码" />
          </el-form-item>
        </div>

        <div class="form-actions">
          <el-button type="primary" :loading="savingPassword" native-type="submit">修改密码</el-button>
        </div>
      </el-form>
    </article>

    <article class="card-surface profile-card motion-fade-slide" style="--motion-delay: 0.08s">
      <header class="section-head">
        <h2>当前账户</h2>
        <p>下面展示当前登录身份与可见的数据范围。</p>
      </header>

      <div class="profile-grid">
        <div class="profile-item"><span>用户名称</span><strong>{{ authStore.user?.displayName || '-' }}</strong></div>
        <div class="profile-item"><span>用户名</span><strong>{{ authStore.user?.username || '-' }}</strong></div>
        <div class="profile-item"><span>手机号</span><strong>{{ authStore.user?.phone || '-' }}</strong></div>
        <div class="profile-item"><span>所处门店</span><strong>{{ shopSummary }}</strong></div>
        <div class="profile-item"><span>身份</span><strong>{{ authStore.user?.aqcRoleName || '-' }}</strong></div>
        <div class="profile-item"><span>权限</span><strong>{{ permissionSummary }}</strong></div>
      </div>
    </article>

    <article class="card-surface sessions-card motion-fade-slide" style="--motion-delay: 0.16s">
      <header class="sessions-head">
        <div>
          <h3>登录会话</h3>
          <p>保留当前设备和最近活跃设备，支持刷新登录态或下线其他设备。</p>
        </div>
        <div class="sessions-actions">
          <el-button @click="onRefreshToken">刷新登录态</el-button>
          <el-button type="warning" plain @click="onRevokeOthers">下线其他会话</el-button>
        </div>
      </header>

      <div class="sessions-list">
        <article v-for="row in sessionCards" :key="row.id" class="session-item">
          <div class="session-item-main">
            <div class="session-item-head">
              <div class="session-item-copy">
                <strong>{{ summarizeUserAgent(row.userAgent) }}</strong>
                <span>{{ sessionTypeLabel(row) }}</span>
              </div>
              <el-tag :type="row.isCurrent ? 'success' : 'info'">{{ row.isCurrent ? '当前' : '其他设备' }}</el-tag>
            </div>

            <div class="session-item-meta">
              <span>IP {{ row.ipAddress || '-' }}</span>
              <span>最近活跃 {{ formatSessionTime(row.lastUsedAt) }}</span>
              <span>登录于 {{ formatSessionTime(row.createdAt) }}</span>
            </div>
          </div>

          <el-button type="danger" text :disabled="row.isCurrent" @click="onRevokeSession(row.id)">下线</el-button>
        </article>
      </div>
    </article>

    <el-alert v-if="message" :title="message" :type="messageError ? 'error' : 'success'" :closable="false" show-icon />
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { apiPost, apiPut } from '../services/api'
import { useAuthStore } from '../stores/auth'
import { formatPermissionSummaryFromUser } from '../utils/permissions'

const authStore = useAuthStore()
const router = useRouter()
const message = ref('')
const messageError = ref(false)
const savingProfile = ref(false)
const savingPassword = ref(false)

const profileForm = reactive({
  username: '',
  phone: '',
  displayName: '',
})

const passwordForm = reactive({
  password: '',
})

const sessionCards = computed(() => {
  return [...(authStore.sessions || [])].sort((left, right) => {
    if (left.isCurrent && !right.isCurrent) {
      return -1
    }
    if (!left.isCurrent && right.isCurrent) {
      return 1
    }
    return String(right.lastUsedAt || '').localeCompare(String(left.lastUsedAt || ''))
  })
})

const shopSummary = computed(() => {
  const names = Array.isArray(authStore.user?.shopNames) ? authStore.user.shopNames.filter(Boolean) : []
  if (names.length) {
    return names.join('、')
  }
  return authStore.user?.shopName || '-'
})

const permissionSummary = computed(() => {
  return formatPermissionSummaryFromUser(authStore.user) || '无数据权限'
})

function summarizeUserAgent(userAgent) {
  const text = String(userAgent || '').trim()
  if (!text) {
    return '未知设备'
  }
  if (/iPhone|iPad|iOS/i.test(text)) {
    return /MicroMessenger/i.test(text) ? 'iPhone · 微信' : 'iPhone'
  }
  if (/Android/i.test(text)) {
    return /MicroMessenger/i.test(text) ? 'Android · 微信' : 'Android'
  }
  if (/Macintosh|Mac OS X/i.test(text)) {
    return 'Mac'
  }
  if (/Windows/i.test(text)) {
    return 'Windows'
  }
  return text.split(' ').slice(0, 2).join(' ')
}

function sessionTypeLabel(session) {
  if (session?.isCurrent) {
    return session?.sessionCount > 1 ? `当前设备，合并了 ${session.sessionCount} 次登录` : '当前正在使用的登录会话'
  }
  return session?.sessionCount > 1 ? `同设备同 IP 已合并 ${session.sessionCount} 次登录` : '可单独下线的其他设备会话'
}

function formatSessionTime(value) {
  const text = String(value || '').trim()
  if (!text) {
    return '-'
  }
  const normalized = text.replace('T', ' ')
  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}(:\d{2})?$/.test(normalized)) {
    return normalized.slice(5, 16)
  }
  return text
}

function setMessage(text, isError = false) {
  message.value = text
  messageError.value = isError
}

function syncProfileForm() {
  profileForm.username = authStore.user?.username || ''
  profileForm.phone = authStore.user?.phone || ''
  profileForm.displayName = authStore.user?.displayName || ''
}

async function loadSessions() {
  await authStore.listSessions()
}

async function saveProfile() {
  savingProfile.value = true
  const payload = await apiPut(
    '/users/me/account-profile',
    {
      username: profileForm.username,
      phone: profileForm.phone,
      displayName: profileForm.displayName,
    },
    { token: authStore.token },
  )
  savingProfile.value = false
  setMessage(payload?.message || '账户信息已保存', payload?.success === false)
  if (payload?.success) {
    await authStore.checkAuth()
    syncProfileForm()
  }
}

async function savePassword() {
  savingPassword.value = true
  const payload = await apiPost(
    '/users/me/account-password',
    { password: passwordForm.password },
    { token: authStore.token },
  )
  savingPassword.value = false
  setMessage(payload?.message || '密码已更新', payload?.success === false)
  if (payload?.success) {
    passwordForm.password = ''
  }
}

async function onRevokeSession(sessionId) {
  const payload = await authStore.revokeSession(sessionId)
  setMessage(payload?.message || '操作完成', payload?.success === false)
}

async function onRevokeOthers() {
  const payload = await authStore.revokeOthers()
  setMessage(payload?.message || '操作完成', payload?.success === false)
}

async function onRefreshToken() {
  const payload = await authStore.refreshSession()
  setMessage(payload?.message || '登录态已刷新', payload?.success === false)
}

watch(
  () => authStore.user,
  () => {
    syncProfileForm()
  },
  { immediate: true },
)

onMounted(async () => {
  await loadSessions()
})
</script>
