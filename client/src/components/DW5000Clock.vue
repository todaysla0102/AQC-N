<template>
  <div class="dw5000-widget" role="img" :aria-label="`北京时间 ${mainTimeText}`">
    <div class="dw5000-visual">
      <img src="/aqc-dw5000.png" alt="" class="dw5000-illustration" aria-hidden="true" />

      <div class="dw5000-display">
        <div class="dw5000-display-time">
          <div class="seven-seg-group hero">
            <template v-for="(char, index) in mainTimeChars" :key="`main-${index}-${char}`">
              <span v-if="char === ':'" class="seven-seg-colon hero">
                <i />
                <i />
              </span>
              <span v-else class="seven-seg-digit hero">
                <i
                  v-for="segment in SEGMENT_NAMES"
                  :key="segment"
                  class="seven-seg-segment"
                  :class="[`seg-${segment}`, { active: hasSegment(char, segment) }]"
                />
              </span>
            </template>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const SEGMENT_NAMES = ['a', 'b', 'c', 'd', 'e', 'f', 'g']

const SEGMENT_MAP = {
  '0': ['a', 'b', 'c', 'd', 'e', 'f'],
  '1': ['b', 'c'],
  '2': ['a', 'b', 'd', 'e', 'g'],
  '3': ['a', 'b', 'c', 'd', 'g'],
  '4': ['b', 'c', 'f', 'g'],
  '5': ['a', 'c', 'd', 'f', 'g'],
  '6': ['a', 'c', 'd', 'e', 'f', 'g'],
  '7': ['a', 'b', 'c'],
  '8': ['a', 'b', 'c', 'd', 'e', 'f', 'g'],
  '9': ['a', 'b', 'c', 'd', 'f', 'g'],
  '-': ['g'],
}

const ZH_TZ = 'Asia/Shanghai'

const TIME_PARTS_FORMATTER = new Intl.DateTimeFormat('en-US', {
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
  timeZone: ZH_TZ,
})

const tick = ref(Date.now())
let timer = null

const clockNow = computed(() => new Date(tick.value))

const timeParts = computed(() => {
  const parts = TIME_PARTS_FORMATTER.formatToParts(clockNow.value)
  const valueMap = Object.fromEntries(parts.map((item) => [item.type, item.value]))
  const hour = String(valueMap.hour || '00').padStart(2, '0')
  const minute = String(valueMap.minute || '00').padStart(2, '0')
  return { hour, minute }
})

const mainTimeText = computed(() => `${timeParts.value.hour}:${timeParts.value.minute}`)
const mainTimeChars = computed(() => mainTimeText.value.split(''))

function hasSegment(char, segment) {
  return (SEGMENT_MAP[char] || []).includes(segment)
}

onMounted(() => {
  timer = window.setInterval(() => {
    tick.value = Date.now()
  }, 1000)
})

onBeforeUnmount(() => {
  if (timer) {
    window.clearInterval(timer)
    timer = null
  }
})
</script>
