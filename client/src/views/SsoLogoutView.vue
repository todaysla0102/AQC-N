<template>
  <section class="auth-page">
    <div class="auth-panel card-surface">
      <div class="auth-head">
        <h1>已同步退出</h1>
        <p>AQC-N 本地登录态已清除，请返回账号中心继续操作。</p>
      </div>
    </div>
  </section>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { apiPost } from '../services/api'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

function resolveReturnTo() {
  const raw = String(route.query.return_to || '/login').trim()
  if (!raw) {
    return '/login'
  }
  if (raw.startsWith('/')) {
    return raw
  }
  return '/login'
}

onMounted(async () => {
  const token =
    authStore.token ||
    sessionStorage.getItem('aqc_n_token') ||
    localStorage.getItem('aqc_n_token') ||
    ''
  if (token) {
    try {
      await apiPost('/auth/logout', {}, { token })
    } catch (error) {
      console.error(error)
    }
  }

  authStore.clearAuth('已同步退出')

  if (window.self !== window.top) {
    return
  }

  window.setTimeout(() => {
    void router.replace(resolveReturnTo())
  }, 160)
})
</script>
