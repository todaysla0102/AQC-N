<template>
  <Teleport to="body">
    <div
      v-if="rendered"
      class="mobile-bottom-sheet-portal"
      :class="{ visible: opened }"
      :style="portalStyle"
      @keydown.esc.prevent="requestClose"
    >
      <div class="mobile-bottom-sheet-backdrop" @click="requestClose" />

      <section
        class="mobile-bottom-sheet"
        :class="{ dragging: dragState.active }"
        :style="sheetStyle"
        role="dialog"
        aria-modal="true"
        @click.stop
      >
        <header class="mobile-bottom-sheet-header" @pointerdown="onHeaderPointerDown">
          <span class="mobile-bottom-sheet-grabber" aria-hidden="true" />
          <div class="mobile-bottom-sheet-head-row">
            <div class="mobile-bottom-sheet-head-copy">
              <span v-if="subtitle">{{ subtitle }}</span>
              <strong>{{ title }}</strong>
            </div>
            <button
              type="button"
              class="mobile-bottom-sheet-close"
              aria-label="关闭面板"
              @pointerdown.stop
              @click.stop="requestClose"
            >
              关闭
            </button>
          </div>
          <slot name="header" />
        </header>

        <div
          ref="bodyRef"
          class="mobile-bottom-sheet-body"
          :class="{ scrollable: bodyScrollable }"
          @scroll.passive="syncBodyScroll"
          @pointerdown="onBodyPointerDown"
        >
          <slot />
        </div>

        <footer v-if="slots.footer" class="mobile-bottom-sheet-footer">
          <slot name="footer" />
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref, useSlots, watch } from 'vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  title: {
    type: String,
    default: '',
  },
  subtitle: {
    type: String,
    default: '',
  },
  initialSnap: {
    type: Number,
    default: 0.56,
  },
  expandedSnap: {
    type: Number,
    default: 0.9,
  },
  closeThreshold: {
    type: Number,
    default: 0.38,
  },
  baseZIndex: {
    type: Number,
    default: 2600,
  },
})

const emit = defineEmits(['update:modelValue', 'opened', 'closed'])

const slots = useSlots()
const bodyRef = ref(null)
const rendered = ref(false)
const opened = ref(false)
const viewportHeight = ref(0)
const currentSnap = ref(props.initialSnap)
const bodyScrollTop = ref(0)
const stackZIndex = ref(2600)
const dragState = reactive({
  pointerId: null,
  source: '',
  mode: '',
  active: false,
  startY: 0,
  startSnap: 0,
  startScrollTop: 0,
  lastY: 0,
  lastTime: 0,
  velocityY: 0,
})

let closeTimer = 0
let savedBodyOverflow = ''
let savedHtmlOverscroll = ''
const SNAP_DRAG_MULTIPLIER = 1.08
const SNAP_SWITCH_PROGRESS = 0.15
const SNAP_CLOSE_PROGRESS = 0.16
const SNAP_COLLAPSE_DRAG_MULTIPLIER = 1.34
const SNAP_COLLAPSE_DISTANCE = 54
const SNAP_COLLAPSE_PROGRESS = 0.1

function getViewportHeight() {
  if (typeof window === 'undefined') {
    return 0
  }
  return Math.max(window.visualViewport?.height || 0, window.innerHeight || 0, 320)
}

function nextSheetZIndex(baseZIndex = 2600) {
  if (typeof window === 'undefined') {
    return Number(baseZIndex || 2600)
  }
  const fallback = Math.max(2600, Number(baseZIndex || 2600))
  const current = Number(window.__aqcMobileSheetZIndexSeed || fallback)
  const next = Math.max(current, fallback) + 1
  window.__aqcMobileSheetZIndexSeed = next
  return next
}

function resolveMinSnap() {
  return Math.min(props.initialSnap, props.expandedSnap)
}

function resolveMaxSnap() {
  return Math.max(props.initialSnap, props.expandedSnap)
}

function clampSnap(value) {
  const minSnap = resolveMinSnap()
  const maxSnap = resolveMaxSnap()
  if (value < minSnap) {
    return Math.max(0.14, minSnap - (minSnap - value) * 0.48)
  }
  if (value > maxSnap) {
    return maxSnap + (value - maxSnap) * 0.36
  }
  return value
}

function updateViewportHeight() {
  if (
    rendered.value
    && props.modelValue
    && Math.abs(resolveMaxSnap() - resolveMinSnap()) < 0.01
  ) {
    return
  }
  viewportHeight.value = getViewportHeight()
}

function lockBodyScroll() {
  if (typeof document === 'undefined') {
    return
  }
  savedBodyOverflow = document.body.style.overflow
  savedHtmlOverscroll = document.documentElement.style.overscrollBehaviorY
  document.body.style.overflow = 'hidden'
  document.documentElement.style.overscrollBehaviorY = 'none'
}

function unlockBodyScroll() {
  if (typeof document === 'undefined') {
    return
  }
  document.body.style.overflow = savedBodyOverflow
  document.documentElement.style.overscrollBehaviorY = savedHtmlOverscroll
}

function clearCloseTimer() {
  if (closeTimer) {
    window.clearTimeout(closeTimer)
    closeTimer = 0
  }
}

function cleanupDrag() {
  dragState.pointerId = null
  dragState.source = ''
  dragState.mode = ''
  dragState.active = false
  dragState.startY = 0
  dragState.startSnap = currentSnap.value
  dragState.startScrollTop = Math.max(0, bodyRef.value?.scrollTop || 0)
  dragState.lastY = 0
  dragState.lastTime = 0
  dragState.velocityY = 0
  if (typeof window !== 'undefined') {
    window.removeEventListener('pointermove', onPointerMove)
    window.removeEventListener('pointerup', onPointerUp)
    window.removeEventListener('pointercancel', onPointerUp)
  }
}

function syncBodyScroll() {
  bodyScrollTop.value = Math.max(0, bodyRef.value?.scrollTop || 0)
}

function openSheet() {
  clearCloseTimer()
  cleanupDrag()
  updateViewportHeight()
  currentSnap.value = resolveMinSnap()
  stackZIndex.value = nextSheetZIndex(props.baseZIndex)
  rendered.value = true
  nextTick(() => {
    bodyScrollTop.value = 0
    if (bodyRef.value) {
      bodyRef.value.scrollTop = 0
    }
    lockBodyScroll()
    window.requestAnimationFrame(() => {
      opened.value = true
      emit('opened')
    })
  })
}

function finalizeClose() {
  rendered.value = false
  unlockBodyScroll()
  emit('closed')
}

function closeSheet() {
  clearCloseTimer()
  cleanupDrag()
  opened.value = false
  closeTimer = window.setTimeout(() => {
    finalizeClose()
  }, 420)
}

function requestClose() {
  emit('update:modelValue', false)
}

function startPointerSession(event, source) {
  if (!props.modelValue) {
    return
  }
  if (typeof event.button === 'number' && event.button !== 0) {
    return
  }
  cleanupDrag()
  updateViewportHeight()
  syncBodyScroll()
  dragState.pointerId = event.pointerId
  dragState.source = source
  dragState.mode = source === 'header' ? 'resize' : 'pending'
  dragState.active = source === 'header'
  dragState.startY = event.clientY
  dragState.startSnap = currentSnap.value
  dragState.startScrollTop = Math.max(0, bodyRef.value?.scrollTop || 0)
  dragState.lastY = event.clientY
  dragState.lastTime = performance.now()
  dragState.velocityY = 0
  if (bodyRef.value && currentSnap.value < resolveMaxSnap() - 0.01) {
    bodyRef.value.scrollTop = 0
    syncBodyScroll()
  }
  window.addEventListener('pointermove', onPointerMove)
  window.addEventListener('pointerup', onPointerUp)
  window.addEventListener('pointercancel', onPointerUp)
}

function onHeaderPointerDown(event) {
  if (Math.abs(resolveMaxSnap() - resolveMinSnap()) < 0.01) {
    return
  }
  startPointerSession(event, 'header')
}

function onBodyPointerDown(event) {
  if (Math.abs(resolveMaxSnap() - resolveMinSnap()) < 0.01) {
    return
  }
  if (currentSnap.value >= resolveMaxSnap() - 0.01 && Math.max(0, bodyRef.value?.scrollTop || 0) > 1) {
    syncBodyScroll()
    return
  }
  startPointerSession(event, 'body')
}

function onPointerMove(event) {
  if (event.pointerId !== dragState.pointerId) {
    return
  }
  const now = performance.now()
  const deltaTime = Math.max(now - dragState.lastTime, 1)
  dragState.velocityY = (event.clientY - dragState.lastY) / deltaTime
  dragState.lastY = event.clientY
  dragState.lastTime = now
  const deltaY = event.clientY - dragState.startY
  const viewport = Math.max(viewportHeight.value || getViewportHeight(), 1)
  const maxSnap = resolveMaxSnap()
  const snapDelta = (deltaY * SNAP_DRAG_MULTIPLIER) / viewport
  const collapseSnapDelta = (deltaY * SNAP_COLLAPSE_DRAG_MULTIPLIER) / viewport
  const startedFromMax = dragState.startSnap >= maxSnap - 0.01
  const startedAtTop = dragState.startScrollTop <= 1

  if (dragState.source === 'body') {
    if (!dragState.active && Math.abs(deltaY) < 6) {
      return
    }
    dragState.active = true
    if (dragState.mode !== 'resize') {
      dragState.mode = 'resize'
    }

    if (currentSnap.value < maxSnap - 0.01) {
      if (bodyRef.value) {
        bodyRef.value.scrollTop = 0
      }
      bodyScrollTop.value = 0
      currentSnap.value = clampSnap(dragState.startSnap - snapDelta)
      event.preventDefault()
      return
    }

    if (bodyRef.value && dragState.startScrollTop <= 1) {
      bodyRef.value.scrollTop = 0
    }
    bodyScrollTop.value = Math.max(0, bodyRef.value?.scrollTop || 0)

    if (startedFromMax && startedAtTop) {
      if (deltaY > 0) {
        currentSnap.value = clampSnap(maxSnap - collapseSnapDelta)
      } else {
        currentSnap.value = maxSnap
      }
      event.preventDefault()
      return
    }

    currentSnap.value = clampSnap(dragState.startSnap - snapDelta)
    event.preventDefault()
    return
  }

  if (!dragState.active) {
    dragState.active = true
  }
  currentSnap.value = clampSnap(dragState.startSnap - snapDelta)
  event.preventDefault()
}

function onPointerUp(event) {
  if (event.pointerId !== dragState.pointerId) {
    return
  }

  const nextVelocity = dragState.velocityY
  const snapAtRelease = currentSnap.value
  const dragDistance = event.clientY - dragState.startY
  const dragDistanceInSnap = dragState.startSnap - snapAtRelease
  const minSnap = resolveMinSnap()
  const maxSnap = resolveMaxSnap()
  const snapRange = Math.max(maxSnap - minSnap, 0.01)
  const switchDistance = snapRange * SNAP_SWITCH_PROGRESS
  const closeDistance = snapRange * SNAP_CLOSE_PROGRESS
  const collapseDistance = snapRange * SNAP_COLLAPSE_PROGRESS
  const releaseFromMin = dragState.startSnap <= minSnap + 0.02
  const releaseFromMax = dragState.startSnap >= maxSnap - 0.02
  const contentAtTop = bodyScrollTop.value <= 1
  const shouldExpand =
    dragDistanceInSnap >= switchDistance
    || dragDistance <= -72
    || nextVelocity < -0.42
    || snapAtRelease >= minSnap + snapRange * 0.48
  const shouldCollapse =
    dragDistanceInSnap <= -switchDistance
    || (releaseFromMax && dragDistanceInSnap <= -collapseDistance)
    || (releaseFromMax && dragDistance >= SNAP_COLLAPSE_DISTANCE)
    || dragDistance >= 72
    || nextVelocity > 0.42
  const shouldClose =
    (releaseFromMin && (minSnap - snapAtRelease >= closeDistance || dragDistance >= 88))
    || (releaseFromMin && nextVelocity > 0.72 && snapAtRelease <= minSnap + snapRange * 0.08)
  cleanupDrag()

  if (shouldClose || snapAtRelease <= props.closeThreshold) {
    requestClose()
    return
  }

  if (releaseFromMax) {
    if (contentAtTop && shouldCollapse) {
      currentSnap.value = minSnap
      return
    }
    currentSnap.value = maxSnap
    return
  }

  currentSnap.value = shouldExpand ? maxSnap : minSnap
}

const bodyScrollable = computed(() => {
  if (Math.abs(resolveMaxSnap() - resolveMinSnap()) < 0.01) {
    return false
  }
  return currentSnap.value >= resolveMaxSnap() - 0.02
})

const portalStyle = computed(() => ({
  zIndex: String(stackZIndex.value),
}))

const sheetStyle = computed(() => {
  const minHeight = 320
  const resolvedViewport = Math.max(viewportHeight.value || getViewportHeight(), minHeight)
  const height = Math.round(Math.max(minHeight, resolvedViewport * currentSnap.value))
  return {
    '--mobile-sheet-height': `${height}px`,
    '--mobile-sheet-vh': `${resolvedViewport}px`,
    transform: `translate3d(0, ${opened.value ? 0 : resolvedViewport + 40}px, 0)`,
  }
})

watch(
  () => props.modelValue,
  (value) => {
    if (value) {
      openSheet()
      return
    }
    if (rendered.value) {
      closeSheet()
    }
  },
  { immediate: true },
)

if (typeof window !== 'undefined') {
  updateViewportHeight()
  window.addEventListener('resize', updateViewportHeight, { passive: true })
  window.visualViewport?.addEventListener?.('resize', updateViewportHeight, { passive: true })
}

onBeforeUnmount(() => {
  clearCloseTimer()
  cleanupDrag()
  unlockBodyScroll()
  if (typeof window === 'undefined') {
    return
  }
  window.removeEventListener('resize', updateViewportHeight)
  window.visualViewport?.removeEventListener?.('resize', updateViewportHeight)
})
</script>

<style scoped>
.mobile-bottom-sheet-portal {
  position: fixed;
  inset: 0;
  z-index: 2600;
  pointer-events: none;
}

.mobile-bottom-sheet-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(10, 12, 11, 0.2);
  opacity: 0;
  transition: opacity 0.4s ease;
}

.mobile-bottom-sheet-portal.visible {
  pointer-events: auto;
}

.mobile-bottom-sheet-portal.visible .mobile-bottom-sheet-backdrop {
  opacity: 1;
}

.mobile-bottom-sheet {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: min(var(--mobile-sheet-height), calc(var(--mobile-sheet-vh) - 10px));
  max-height: calc(var(--mobile-sheet-vh) - 10px);
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  border-radius: 30px 30px 0 0;
  border: 1px solid color-mix(in srgb, var(--accent-color) 20%, var(--border-color));
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--bg-elevated) 98%, transparent) 0%, var(--bg-elevated) 100%);
  box-shadow: 0 -24px 60px rgba(0, 0, 0, 0.14);
  overflow: hidden;
  transition:
    transform 0.42s cubic-bezier(0.22, 1, 0.36, 1),
    height 0.42s cubic-bezier(0.22, 1, 0.36, 1);
}

.mobile-bottom-sheet.dragging {
  transition: none;
}

.mobile-bottom-sheet-header {
  position: relative;
  padding: 10px 18px 12px;
  display: grid;
  gap: 10px;
  background: color-mix(in srgb, var(--bg-elevated) 94%, transparent);
  border-bottom: 1px solid var(--border-soft);
  touch-action: none;
}

.mobile-bottom-sheet-grabber {
  width: 44px;
  height: 5px;
  border-radius: 999px;
  justify-self: center;
  background: color-mix(in srgb, var(--text-light) 42%, white 24%);
}

.mobile-bottom-sheet-head-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.mobile-bottom-sheet-head-copy {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.mobile-bottom-sheet-head-copy span {
  color: var(--text-light);
  font-size: 12px;
  font-weight: 600;
}

.mobile-bottom-sheet-head-copy strong {
  color: var(--text-primary);
  font-family: 'Manrope', 'Noto Sans SC', sans-serif;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.03em;
}

.mobile-bottom-sheet-close {
  appearance: none;
  border: none;
  background: transparent;
  color: var(--accent-color);
  font: inherit;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  padding: 2px 0 0;
}

.mobile-bottom-sheet-body {
  min-height: 0;
  overflow: hidden;
  overscroll-behavior: contain;
  padding: 12px 16px calc(18px + env(safe-area-inset-bottom, 0px));
  touch-action: none;
  -webkit-overflow-scrolling: touch;
}

.mobile-bottom-sheet-body.scrollable {
  overflow: auto;
  touch-action: pan-y;
}

.mobile-bottom-sheet-footer {
  padding: 0 16px calc(16px + env(safe-area-inset-bottom, 0px));
  border-top: 1px solid var(--border-soft);
  background: color-mix(in srgb, var(--bg-elevated) 94%, transparent);
}

.mobile-bottom-sheet-footer :deep(.form-actions) {
  justify-content: stretch;
}

.mobile-bottom-sheet-footer :deep(.form-actions .el-button) {
  flex: 1 1 0;
  min-height: 42px;
}

.dark .mobile-bottom-sheet-backdrop {
  background: rgba(2, 4, 3, 0.42);
}

.dark .mobile-bottom-sheet {
  box-shadow: 0 -24px 60px rgba(0, 0, 0, 0.4);
}

.dark .mobile-bottom-sheet-grabber {
  background: color-mix(in srgb, var(--text-light) 76%, white 20%);
}
</style>
