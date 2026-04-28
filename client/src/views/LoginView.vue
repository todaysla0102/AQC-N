<template>
  <section class="auth-page">
    <div class="auth-panel card-surface motion-fade-slide">
      <div class="auth-head">
        <div class="auth-brand">
          <img src="/aqc-logo.svg" alt="AQC Logo" class="theme-sensitive-logo" />
          <p class="auth-tag">{{ localTestLoginEnabled ? '本地测试系统' : '账号中心连接中' }}</p>
        </div>
        <h1>{{ localTestLoginEnabled ? '本地测试登录' : '正在连接统一登录' }}</h1>
        <p>
          {{
            localTestLoginEnabled
              ? '当前前端已连接本地测试 API，可使用测试账号进入系统验收，线上环境不会显示此入口。'
              : '如果页面没有自动跳转，我们会保留这个备用页，方便你继续前往 account.symuse.com 完成登录。'
          }}
        </p>
      </div>

      <div class="auth-block">
        <div class="auth-status-card" :class="{ error: isError }">
          <span>当前状态</span>
          <strong>{{ isError ? '需要重新发起登录' : localTestLoginEnabled ? '等待本地测试登录' : '准备跳转到账号中心' }}</strong>
          <p>
            {{
              message ||
              (localTestLoginEnabled
                ? '本地测试模式不会自动跳转统一登录。'
                : '未检测到回调时会自动跳转到 account.symuse.com 登录。')
            }}
          </p>
        </div>

        <el-form v-if="localTestLoginEnabled" class="auth-form local-test-login-form" @submit.prevent="onLocalLogin">
          <el-input
            v-model="localLoginAccount"
            autocomplete="username"
            clearable
            placeholder="测试账号"
            @keydown.enter.prevent="onLocalLogin"
          />
          <el-input
            v-model="localLoginPassword"
            autocomplete="current-password"
            placeholder="测试密码"
            show-password
            type="password"
            @keydown.enter.prevent="onLocalLogin"
          />
          <div class="auth-actions local-test-login-actions">
            <el-button type="primary" native-type="submit" :loading="localSubmitting">
              登录本地测试系统
            </el-button>
            <el-button :disabled="preparing || submitting" @click="goSymuseAuth">
              改用统一登录
            </el-button>
          </div>
          <p class="local-test-login-hint">默认账号与密码以本地测试环境配置为准，仅随本地测试环境启用。</p>
        </el-form>

        <div v-if="!localTestLoginEnabled" class="auth-actions">
          <el-button type="primary" :loading="preparing || submitting" @click="goSymuseAuth">
            前往 account.symuse.com 登录
          </el-button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'
import {
  clearStoredLoginState,
  consumeStoredPostLoginPath,
  readStoredLoginState,
  resolvePublicAppOrigin,
  resolveSymuseLoginRedirectUri,
  sanitizeReturnPath,
  storeLoginState,
  storePostLoginPath,
} from '../utils/authRedirect'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

const localTestLoginEnabled = import.meta.env.VITE_LOCAL_TEST_LOGIN === 'true'
const submitting = ref(false)
const preparing = ref(false)
const localSubmitting = ref(false)
const isError = ref(false)
const message = ref('')
const callbackCode = ref('')
const callbackState = ref('')
const callbackRememberLogin = ref(null)
const localLoginAccount = ref(import.meta.env.VITE_LOCAL_TEST_ACCOUNT || 'La')
const localLoginPassword = ref('')

function shouldForceLogin() {
  return String(route.query.force_login || '').trim() === '1'
}

function appendForceLogin(url) {
  if (!shouldForceLogin()) {
    return url
  }
  try {
    const parsed = new URL(url)
    parsed.searchParams.set('force_login', '1')
    return parsed.toString()
  } catch (error) {
    const separator = url.includes('?') ? '&' : '?'
    return `${url}${separator}force_login=1`
  }
}

function setMessage(text, isErr = false) {
  message.value = text
  isError.value = isErr
}

function currentReturnPath() {
  return sanitizeReturnPath(route.query.redirect || '/')
}

function persistReturnPath() {
  const target = currentReturnPath()
  if (target && target !== '/login') {
    storePostLoginPath(target)
  }
}

function resolveNextRoute() {
  const redirectTo = sanitizeReturnPath(authStore.lastRedirectTo || '')
  if (redirectTo && redirectTo !== '/') {
    return redirectTo
  }
  const stored = consumeStoredPostLoginPath()
  if (stored && stored !== '/') {
    return stored
  }
  return '/'
}

function validateFrontendState() {
  const expected = readStoredLoginState()
  if (!expected || !callbackState.value) {
    return true
  }
  if (expected === callbackState.value) {
    return true
  }
  setMessage('登录回调校验失败，请重新发起登录', true)
  clearStoredLoginState()
  return false
}

async function goSymuseAuth() {
  if (preparing.value) {
    return
  }

  persistReturnPath()
  preparing.value = true
  const payload = await authStore.prepareSymuseState(resolveSymuseLoginRedirectUri(), currentReturnPath())
  preparing.value = false

  if (!payload?.success || !payload.authUrl || !payload.state) {
    setMessage(payload?.message || '生成登录参数失败', true)
    return
  }

  storeLoginState(payload.state)
  window.location.replace(appendForceLogin(payload.authUrl))
}

async function onExchangeCode() {
  if (!callbackCode.value || !callbackState.value) {
    setMessage('回调参数缺失，请重新发起统一登录', true)
    return
  }
  if (!validateFrontendState()) {
    return
  }

  submitting.value = true
  const ok = await authStore.exchangeSymuseCode(
    callbackCode.value,
    callbackState.value,
    callbackRememberLogin.value,
  )
  submitting.value = false

  if (!ok) {
    setMessage(authStore.lastMessage || '换票失败', true)
    return
  }

  clearStoredLoginState()
  setMessage('登录成功')
  window.history.replaceState({}, '', `${resolvePublicAppOrigin()}/login`)

  const nextRoute = resolveNextRoute()
  if (nextRoute === '/') {
    router.replace({ name: 'dashboard' })
    return
  }
  router.replace(nextRoute)
}

async function onLocalLogin() {
  if (!localTestLoginEnabled || localSubmitting.value) {
    return
  }

  const account = localLoginAccount.value.trim()
  const password = localLoginPassword.value
  if (!account || !password) {
    setMessage('请输入本地测试账号和密码', true)
    return
  }

  persistReturnPath()
  localSubmitting.value = true
  const ok = await authStore.localLogin(account, password)
  localSubmitting.value = false

  if (!ok) {
    setMessage(authStore.lastMessage || '本地测试登录失败', true)
    return
  }

  setMessage('本地测试登录成功')
  const nextRoute = resolveNextRoute()
  if (nextRoute === '/') {
    router.replace({ name: 'dashboard' })
    return
  }
  router.replace(nextRoute)
}

function loadCodeFromUrl() {
  const query = new URLSearchParams(window.location.search)
  const code = (query.get('code') || '').trim()
  const state = (query.get('state') || '').trim()
  const rememberLogin = (query.get('remember_login') || '').trim()
  if (!code) {
    return
  }

  callbackCode.value = code
  callbackState.value = state
  callbackRememberLogin.value = rememberLogin === '1' ? true : rememberLogin === '0' ? false : null
}

async function bootAuthFlow() {
  if (shouldForceLogin()) {
    authStore.clearAuth('请重新登录')
    clearStoredLoginState()
  }

  loadCodeFromUrl()
  if (callbackCode.value) {
    if (!callbackState.value) {
      setMessage('检测到回调 code，但缺少 state，请重新发起登录', true)
      return
    }
    setMessage('检测到回调参数，正在换票登录...')
    await onExchangeCode()
    return
  }
  if (localTestLoginEnabled) {
    setMessage('本地测试登录已开启，请使用测试账号进入系统。')
    return
  }
  setMessage('正在跳转到 account.symuse.com 登录...')
  await goSymuseAuth()
}

onMounted(() => {
  void bootAuthFlow()
})
</script>
