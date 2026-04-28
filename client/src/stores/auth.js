import { defineStore } from 'pinia'

import { apiDelete, apiGet, apiPost } from '../services/api'


const TOKEN_KEY = 'aqc_n_token'

function canUseStorage() {
  return typeof window !== 'undefined'
}

function readToken() {
  if (!canUseStorage()) {
    return ''
  }
  try {
    return sessionStorage.getItem(TOKEN_KEY) || localStorage.getItem(TOKEN_KEY) || ''
  } catch (error) {
    console.error(error)
    return ''
  }
}

function writeToken(token, rememberLogin = true) {
  if (!canUseStorage()) {
    return
  }
  try {
    localStorage.removeItem(TOKEN_KEY)
    sessionStorage.removeItem(TOKEN_KEY)
    if (token) {
      const targetStorage = rememberLogin ? localStorage : sessionStorage
      targetStorage.setItem(TOKEN_KEY, token)
    }
  } catch (error) {
    console.error(error)
  }
}


export const useAuthStore = defineStore('auth', {
  state: () => ({
    loading: true,
    token: readToken(),
    isAuthenticated: false,
    user: null,
    session: null,
    sessions: [],
    lastMessage: '',
    lastRedirectTo: '',
  }),

  getters: {
    displayName(state) {
      return state.user?.displayName || state.user?.username || '未登录用户'
    },

    roleSlugs(state) {
      return state.user?.roles || []
    },

    permissionCodes(state) {
      return state.user?.permissions || []
    },

    aqcRoleKey(state) {
      return state.user?.aqcRoleKey || 'aqc_sales'
    },

    shopId(state) {
      return state.user?.shopId || null
    },

    isAdmin(state) {
      const role = state.user?.role || ''
      const roles = state.user?.roles || []
      const permissions = state.user?.permissions || []
      return role === 'admin' || roles.includes('administrator') || permissions.includes('*') || state.user?.aqcRoleKey === 'aqc_admin'
    },
  },

  actions: {
    can(permissionCode) {
      if (!permissionCode) {
        return true
      }
      if (this.isAdmin) {
        return true
      }
      return this.permissionCodes.includes(permissionCode)
    },

    async bootstrap() {
      if (!this.token) {
        this.loading = false
        this.isAuthenticated = false
        return
      }

      await this.checkAuth()
      this.loading = false
    },

    applyLoginResponse(payload, rememberLogin = true) {
      if (!payload?.success || !payload.token || !payload.user) {
        return false
      }

      this.token = payload.token
      this.user = payload.user
      this.session = payload.session || null
      this.isAuthenticated = true
      this.lastMessage = payload.message || ''
      this.lastRedirectTo = payload.redirectTo || ''
      writeToken(payload.token, rememberLogin)
      return true
    },

    clearAuth(message = '') {
      this.token = ''
      this.user = null
      this.session = null
      this.sessions = []
      this.isAuthenticated = false
      this.lastMessage = message
      this.lastRedirectTo = ''
      writeToken('')
    },

    async checkAuth() {
      if (!this.token) {
        this.clearAuth('未登录')
        return false
      }

      const payload = await apiGet('/auth/check', {
        token: this.token,
      })

      if (payload?.success && payload.isAuthenticated && payload.user) {
        this.user = payload.user
        this.session = payload.session || null
        this.isAuthenticated = true
        return true
      }

      this.clearAuth(payload?.message || '登录状态已失效')
      return false
    },

    async localLogin(account, password) {
      const payload = await apiPost('/auth/local-login', { account, password })
      const ok = this.applyLoginResponse(payload, payload?.rememberLogin !== false)
      if (!ok) {
        this.lastMessage = payload?.message || '登录失败'
      }
      return ok
    },

    async prepareSymuseState(redirectUri = '', returnPath = '') {
      return apiPost('/auth/symuse/state', { redirectUri, returnPath })
    },

    async exchangeSymuseCode(code, state, rememberLogin = null) {
      const payload = await apiPost('/auth/symuse/exchange', { code, state })
      const shouldRemember = typeof rememberLogin === 'boolean'
        ? rememberLogin
        : payload?.rememberLogin !== false
      const ok = this.applyLoginResponse(payload, shouldRemember)
      if (!ok) {
        this.lastMessage = payload?.message || '换取登录失败'
      }
      return ok
    },

    async listSessions() {
      if (!this.token) {
        return []
      }

      const payload = await apiGet('/auth/sessions', {
        token: this.token,
      })
      if (payload?.success) {
        this.sessions = payload.sessions || []
      }
      return this.sessions
    },

    async revokeSession(sessionId) {
      if (!this.token) {
        return { success: false, message: '未登录' }
      }
      const payload = await apiDelete(`/auth/sessions/${sessionId}`, {
        token: this.token,
      })
      await this.listSessions()
      return payload
    },

    async revokeOthers() {
      if (!this.token) {
        return { success: false, message: '未登录' }
      }
      const payload = await apiPost('/auth/sessions/revoke-others', {}, {
        token: this.token,
      })
      await this.listSessions()
      return payload
    },

    async refreshSession() {
      if (!this.token) {
        return { success: false, message: '未登录' }
      }
      const payload = await apiPost('/auth/refresh', {}, {
        token: this.token,
      })
      this.applyLoginResponse(payload)
      await this.listSessions()
      return payload
    },

    async logout() {
      if (this.token) {
        try {
          await apiPost('/auth/logout', {}, {
            token: this.token,
          })
        } catch (error) {
          console.error(error)
        }
      }
      this.clearAuth('已退出登录')
    },
  },
})
