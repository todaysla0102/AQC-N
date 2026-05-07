import fs from 'node:fs'
import path from 'node:path'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const packageJson = JSON.parse(
  fs.readFileSync(new URL('./package.json', import.meta.url), 'utf-8'),
)

function buildVersionPlugin(buildVersion) {
  return {
    name: 'aqc-build-version',
    apply: 'build',
    generateBundle() {
      this.emitFile({
        type: 'asset',
        fileName: 'version.json',
        source: JSON.stringify({
          version: buildVersion,
          packageVersion: packageJson.version,
          builtAt: new Date().toISOString(),
        }, null, 2),
      })
    },
    closeBundle() {
      const versionFile = path.resolve(process.cwd(), 'dist/version.json')
      if (!fs.existsSync(versionFile)) {
        return
      }
      const payload = JSON.parse(fs.readFileSync(versionFile, 'utf-8'))
      payload.builtAt = new Date().toISOString()
      fs.writeFileSync(versionFile, `${JSON.stringify(payload, null, 2)}\n`, 'utf-8')
    },
  }
}

export default defineConfig(() => {
  const buildVersion = process.env.BUILD_VERSION || packageJson.version

  return {
    plugins: [vue(), buildVersionPlugin(buildVersion)],
    define: {
      __APP_BUILD_VERSION__: JSON.stringify(buildVersion),
    },
    server: {
      host: '0.0.0.0',
      port: 5173,
    },
    build: {
      chunkSizeWarningLimit: 1000,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (!id.includes('node_modules')) {
              return undefined
            }
            if (id.includes('element-plus') || id.includes('@element-plus')) {
              return 'vendor-element-plus'
            }
            if (id.includes('echarts')) {
              return 'vendor-echarts'
            }
            if (id.includes('@zxing')) {
              return 'vendor-zxing'
            }
            if (id.includes('vue') || id.includes('pinia')) {
              return 'vendor-vue'
            }
            return 'vendor'
          },
        },
      },
    },
  }
})
