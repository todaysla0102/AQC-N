<template>
  <Transition
    @before-enter="onBeforeEnter"
    @enter="onEnter"
    @after-enter="onAfterEnter"
    @before-leave="onBeforeLeave"
    @leave="onLeave"
    @after-leave="onAfterLeave"
  >
    <slot />
  </Transition>
</template>

<script setup>
const TRANSITION_VALUE = [
  'height 0.34s cubic-bezier(0.19, 1, 0.22, 1)',
  'padding-top 0.34s cubic-bezier(0.19, 1, 0.22, 1)',
  'padding-bottom 0.34s cubic-bezier(0.19, 1, 0.22, 1)',
  'margin-top 0.34s cubic-bezier(0.19, 1, 0.22, 1)',
  'margin-bottom 0.34s cubic-bezier(0.19, 1, 0.22, 1)',
  'opacity 0.24s ease',
].join(', ')

const elementMetricsStore = new WeakMap()
const settleFrameStore = new WeakMap()

function toPixelNumber(value) {
  const parsed = Number.parseFloat(value || '0')
  return Number.isFinite(parsed) ? parsed : 0
}

function captureExpandedMetrics(element) {
  const computed = window.getComputedStyle(element)
  const paddingTop = toPixelNumber(computed.paddingTop)
  const paddingBottom = toPixelNumber(computed.paddingBottom)
  const marginTop = toPixelNumber(computed.marginTop)
  const marginBottom = toPixelNumber(computed.marginBottom)
  const boxHeight = Math.max(
    Math.ceil(element.scrollHeight || element.getBoundingClientRect().height || 0),
    0,
  )
  const metrics = {
    boxHeight,
    paddingTop,
    paddingBottom,
    marginTop,
    marginBottom,
  }
  elementMetricsStore.set(element, metrics)
  return metrics
}

function setBaseStyles(element) {
  element.style.overflow = 'hidden'
  element.style.willChange = 'height, padding-top, padding-bottom, margin-top, margin-bottom, opacity'
}

function clearStyles(element) {
  element.style.transition = ''
  element.style.height = ''
  element.style.opacity = ''
  element.style.paddingTop = ''
  element.style.paddingBottom = ''
  element.style.marginTop = ''
  element.style.marginBottom = ''
  element.style.overflow = 'hidden'
  element.style.willChange = ''
}

function applyMetrics(element, metrics) {
  element.style.height = `${metrics.boxHeight}px`
  element.style.paddingTop = `${metrics.paddingTop}px`
  element.style.paddingBottom = `${metrics.paddingBottom}px`
  element.style.marginTop = `${metrics.marginTop}px`
  element.style.marginBottom = `${metrics.marginBottom}px`
}

function cancelSettleFrames(element) {
  const frameId = settleFrameStore.get(element)
  if (frameId) {
    cancelAnimationFrame(frameId)
    settleFrameStore.delete(element)
  }
}

function runTransition(element, applyFinalState, done) {
  let finished = false
  const finish = (event) => {
    if (finished) {
      return
    }
    if (event && event.target !== element) {
      return
    }
    if (event && event.propertyName !== 'height') {
      return
    }
    finished = true
    element.removeEventListener('transitionend', finish)
    done()
  }
  element.addEventListener('transitionend', finish)
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      applyFinalState()
    })
  })
}

function onBeforeEnter(element) {
  setBaseStyles(element)
  element.style.opacity = '0'
  element.style.transition = 'none'
}

function onEnter(element, done) {
  const metrics = captureExpandedMetrics(element)
  element.style.height = '0px'
  element.style.paddingTop = '0px'
  element.style.paddingBottom = '0px'
  element.style.marginTop = '0px'
  element.style.marginBottom = '0px'
  void element.offsetHeight

  let previousContentHeight = Math.ceil(element.scrollHeight || 0)
  let stableFrames = 0
  let frameCount = 0

  const startEnter = () => {
    cancelSettleFrames(element)
    metrics.boxHeight = previousContentHeight + metrics.paddingTop + metrics.paddingBottom
    element.style.transition = TRANSITION_VALUE
    runTransition(
      element,
      () => {
        applyMetrics(element, metrics)
        element.style.opacity = '1'
      },
      done,
    )
  }

  const settleBeforeEnter = () => {
    frameCount += 1
    const nextContentHeight = Math.ceil(element.scrollHeight || 0)
    if (Math.abs(nextContentHeight - previousContentHeight) <= 1) {
      stableFrames += 1
    } else {
      stableFrames = 0
      previousContentHeight = nextContentHeight
    }

    if (stableFrames >= 2 || frameCount >= 12) {
      startEnter()
      return
    }

    const frameId = requestAnimationFrame(settleBeforeEnter)
    settleFrameStore.set(element, frameId)
  }

  const frameId = requestAnimationFrame(settleBeforeEnter)
  settleFrameStore.set(element, frameId)
}

function onAfterEnter(element) {
  cancelSettleFrames(element)
  clearStyles(element)
}

function onBeforeLeave(element) {
  cancelSettleFrames(element)
  const metrics = captureExpandedMetrics(element)
  setBaseStyles(element)
  applyMetrics(element, metrics)
  element.style.opacity = '1'
}

function onLeave(element, done) {
  element.style.transition = TRANSITION_VALUE
  runTransition(
    element,
    () => {
      element.style.height = '0px'
      element.style.opacity = '0'
      element.style.paddingTop = '0px'
      element.style.paddingBottom = '0px'
      element.style.marginTop = '0px'
      element.style.marginBottom = '0px'
    },
    done,
  )
}

function onAfterLeave(element) {
  cancelSettleFrames(element)
  clearStyles(element)
}
</script>
