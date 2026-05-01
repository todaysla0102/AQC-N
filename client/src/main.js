import { createApp, watch } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import NativeSystemSelect from './components/NativeSystemSelect.vue'
import router from './router'
import './styles.css'
import { useAppVersionStore } from './stores/appVersion'
import { useThemeStore } from './stores/theme'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(ElementPlus, {
  locale: zhCn,
  zIndex: 8200,
})
app.component('ElSelect', NativeSystemSelect)

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

const themeStore = useThemeStore(pinia)
const appVersionStore = useAppVersionStore(pinia)
themeStore.initTheme()

function syncThemeBrandAssets(isDark) {
  if (typeof window === 'undefined') {
    return
  }
  if (typeof window.__AQC_APPLY_THEME_ASSETS__ === 'function') {
    window.__AQC_APPLY_THEME_ASSETS__(isDark)
    return
  }

  const suffix = isDark ? 'dark' : 'light'
  const themeColor = isDark ? '#0f0f0f' : '#f8f8f8'
  const mappings = [
    ['app-favicon-svg', `/aqc-logo-home-${isDark ? 'd' : 'l'}.svg`],
    ['app-favicon-png', `/aqc-logo-home-${isDark ? 'd' : 'l'}.png`],
    ['app-favicon-png-192', `/icon-192-${suffix}.png`],
    ['app-apple-touch-icon', `/apple-touch-icon-${suffix}.png`],
    ['app-manifest', `/site-${suffix}.webmanifest`],
  ]
  mappings.forEach(([id, href]) => {
    const element = document.getElementById(id)
    if (element) {
      element.setAttribute('href', href)
    }
  })
  const themeColorMeta = document.getElementById('app-theme-color')
  if (themeColorMeta) {
    themeColorMeta.setAttribute('content', themeColor)
  }
}

watch(
  () => themeStore.isDark,
  (isDark) => {
    syncThemeBrandAssets(isDark)
  },
  { immediate: true },
)

app.mount('#app')

router.isReady().then(() => {
  appVersionStore.startWatcher(router)
})
