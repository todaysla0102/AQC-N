import { ElNotification } from 'element-plus'
import { defineStore } from 'pinia'

const APP_BUILD_VERSION = typeof __APP_BUILD_VERSION__ === 'string' ? __APP_BUILD_VERSION__ : 'dev'
const VERSION_CHECK_INTERVAL = 60 * 1000
const UPGRADE_VERSION_QUERY_KEY = '_aqcv'
const UPGRADE_TIMESTAMP_QUERY_KEY = '_aqcts'

let versionCheckTimer = null
let versionPromptVisible = false
let reloadTriggered = false
let browserVersionNoticeVisible = false
let watcherStarted = false

async function fetchServerBuildVersion() {
  const response = await fetch(`/version.json?ts=${Date.now()}`, {
    cache: 'no-store',
    headers: {
      'Cache-Control': 'no-cache',
      Pragma: 'no-cache',
    },
  })
  if (!response.ok) {
    return null
  }
  const payload = await response.json()
  return String(payload?.version || '').trim()
}

function buildUpgradeUrl(nextVersion = '') {
  const url = new URL(window.location.href)
  if (nextVersion) {
    url.searchParams.set(UPGRADE_VERSION_QUERY_KEY, nextVersion)
  }
  url.searchParams.set(UPGRADE_TIMESTAMP_QUERY_KEY, String(Date.now()))
  return url.toString()
}

function sendBrowserNotification(title, body, options = {}) {
  if (typeof window === 'undefined' || typeof Notification === 'undefined') {
    return null
  }
  if (Notification.permission !== 'granted') {
    return null
  }
  if (browserVersionNoticeVisible && options.tag === 'aqc-version-update') {
    return null
  }
  const notification = new Notification(title, {
    body,
    tag: options.tag,
    silent: options.silent ?? false,
  })
  if (options.tag === 'aqc-version-update') {
    browserVersionNoticeVisible = true
    notification.onclose = () => {
      browserVersionNoticeVisible = false
    }
  }
  notification.onclick = () => {
    window.focus()
    if (typeof options.onClick === 'function') {
      options.onClick()
    }
    notification.close()
  }
  return notification
}

export const useAppVersionStore = defineStore('appVersion', {
  state: () => ({
    currentVersion: APP_BUILD_VERSION,
    latestVersion: '',
    hasUpdate: false,
    checking: false,
    lastCheckedAt: 0,
    updateDetectedAt: 0,
  }),

  getters: {
    currentVersionLabel: (state) => String(state.currentVersion || '').trim() || 'dev',
    latestVersionLabel: (state) => String(state.latestVersion || '').trim() || '',
    upgradeSummary(state) {
      if (!state.hasUpdate || !state.latestVersion) {
        return ''
      }
      return `当前为 ${this.currentVersionLabel}，最新为 ${this.latestVersionLabel}`
    },
  },

  actions: {
    markFreshVersion(version = '') {
      this.latestVersion = version || this.currentVersion
      this.hasUpdate = false
      this.updateDetectedAt = 0
    },

    async checkForNewVersion({ silent = false } = {}) {
      if (import.meta.env.DEV || reloadTriggered || this.checking) {
        return false
      }
      this.checking = true
      try {
        const serverVersion = await fetchServerBuildVersion()
        this.lastCheckedAt = Date.now()
        if (!serverVersion) {
          return false
        }
        this.latestVersion = serverVersion
        if (serverVersion === this.currentVersion) {
          this.markFreshVersion(serverVersion)
          return false
        }
        this.hasUpdate = true
        if (!this.updateDetectedAt) {
          this.updateDetectedAt = Date.now()
        }
        if (versionPromptVisible) {
          return true
        }
        versionPromptVisible = true
        ElNotification({
          title: '发现新版本',
          message: `系统已更新到 ${serverVersion}，点击此通知立即进入新版本。`,
          duration: silent ? 6000 : 0,
          customClass: 'app-version-notification',
          onClick: () => this.upgradeToLatestVersion(),
          onClose: () => {
            versionPromptVisible = false
          },
        })
        sendBrowserNotification('AQC-N 已更新', `系统已更新到 ${serverVersion}，点击立即进入新版本。`, {
          tag: 'aqc-version-update',
          onClick: () => this.upgradeToLatestVersion(),
        })
        return true
      } catch (error) {
        console.error('Version check failed', error)
        return false
      } finally {
        this.checking = false
      }
    },

    upgradeToLatestVersion() {
      if (typeof window === 'undefined' || reloadTriggered) {
        return
      }
      reloadTriggered = true
      const targetVersion = this.latestVersion || this.currentVersion
      window.location.replace(buildUpgradeUrl(targetVersion))
    },

    clearUpgradeQuery(router) {
      const currentQuery = router.currentRoute.value?.query || {}
      const nextQuery = { ...currentQuery }
      let changed = false

      if (UPGRADE_VERSION_QUERY_KEY in nextQuery) {
        delete nextQuery[UPGRADE_VERSION_QUERY_KEY]
        changed = true
      }
      if (UPGRADE_TIMESTAMP_QUERY_KEY in nextQuery) {
        delete nextQuery[UPGRADE_TIMESTAMP_QUERY_KEY]
        changed = true
      }

      if (!changed) {
        return
      }

      router.replace({
        path: router.currentRoute.value.path,
        query: nextQuery,
        hash: router.currentRoute.value.hash,
      }).catch(() => {})
    },

    startWatcher(router) {
      if (import.meta.env.DEV || watcherStarted || typeof window === 'undefined') {
        return
      }
      watcherStarted = true
      this.clearUpgradeQuery(router)

      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') {
          void this.checkForNewVersion({ silent: true })
        }
      })
      window.addEventListener('focus', () => {
        void this.checkForNewVersion({ silent: true })
      })
      window.addEventListener('online', () => {
        void this.checkForNewVersion({ silent: true })
      })

      versionCheckTimer = window.setInterval(() => {
        void this.checkForNewVersion({ silent: true })
      }, VERSION_CHECK_INTERVAL)

      void this.checkForNewVersion({ silent: true })
      window.setTimeout(() => {
        void this.checkForNewVersion({ silent: true })
      }, 4000)
    },
  },
})
