import { defineStore } from 'pinia'


const THEME_KEY = 'aqc_n_theme_mode'
let themeMediaQuery = null
let themeMediaHandler = null


function resolveStoredTheme() {
  const raw = (localStorage.getItem(THEME_KEY) || '').trim()
  if (raw === 'light' || raw === 'dark' || raw === 'system') {
    return raw
  }
  return 'system'
}


function computeDark(mode) {
  if (mode === 'dark') {
    return true
  }
  if (mode === 'light') {
    return false
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}


export const useThemeStore = defineStore('theme', {
  state: () => ({
    mode: resolveStoredTheme(),
    isDark: false,
  }),

  actions: {
    applyTheme() {
      this.isDark = computeDark(this.mode)
      document.documentElement.classList.toggle('dark', this.isDark)
      document.documentElement.dataset.themeMode = this.mode
      document.documentElement.dataset.themeResolved = this.isDark ? 'dark' : 'light'
      document.documentElement.style.colorScheme = this.isDark ? 'dark' : 'light'
      localStorage.setItem(THEME_KEY, this.mode)
    },

    initTheme() {
      this.applyTheme()
      if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
        return
      }

      if (themeMediaQuery && themeMediaHandler) {
        if (typeof themeMediaQuery.removeEventListener === 'function') {
          themeMediaQuery.removeEventListener('change', themeMediaHandler)
        } else if (typeof themeMediaQuery.removeListener === 'function') {
          themeMediaQuery.removeListener(themeMediaHandler)
        }
      }

      themeMediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
      themeMediaHandler = () => {
        if (this.mode === 'system') {
          this.applyTheme()
        }
      }

      if (typeof themeMediaQuery.addEventListener === 'function') {
        themeMediaQuery.addEventListener('change', themeMediaHandler)
      } else if (typeof themeMediaQuery.addListener === 'function') {
        themeMediaQuery.addListener(themeMediaHandler)
      }
    },

    setMode(mode) {
      this.mode = mode
      this.applyTheme()
    },

    cycleMode() {
      if (this.mode === 'light') {
        this.setMode('dark')
        return
      }
      if (this.mode === 'dark') {
        this.setMode('system')
        return
      }
      this.setMode('light')
    },
  },
})
