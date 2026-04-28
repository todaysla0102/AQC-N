<template>
  <div class="app-root">
    <div v-if="showRouter" class="app-shell-stage">
      <RouterView />
    </div>

    <div v-if="bootVisible" class="boot-screen" :class="`stage-${bootStage}`">
      <div class="boot-screen-inner">
        <div class="boot-logo-wrap">
          <img src="/aqc-logo.svg" alt="AQC Logo" class="boot-logo" />
        </div>
        <div class="boot-dots" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterView, useRouter } from 'vue-router'

import { useAuthStore } from './stores/auth'

const authStore = useAuthStore()
const router = useRouter()

const bootStage = ref('loading')
const bootVisible = ref(true)
const showRouter = ref(false)
const routerReady = ref(false)
const bootStarted = ref(false)
const bootTimers = []

function queueBootStep(callback, delay) {
  const timer = window.setTimeout(callback, delay)
  bootTimers.push(timer)
}

function clearBootTimers() {
  while (bootTimers.length) {
    const timer = bootTimers.pop()
    clearTimeout(timer)
  }
}

function startBootSequence() {
  if (bootStarted.value) {
    return
  }
  bootStarted.value = true
  bootStage.value = 'loading'

  queueBootStep(() => {
    bootStage.value = 'logo-fade'
  }, 1000)

  queueBootStep(() => {
    showRouter.value = true
    bootStage.value = 'shell-enter'
  }, 1500)

  queueBootStep(() => {
    bootVisible.value = false
    bootStage.value = 'done'
  }, 1700)
}

watch(
  [() => authStore.loading, routerReady],
  ([loading, ready]) => {
    if (!loading && ready) {
      startBootSequence()
    }
  },
  { immediate: true },
)

onMounted(async () => {
  await router.isReady()
  routerReady.value = true
})

onBeforeUnmount(() => {
  clearBootTimers()
})
</script>
