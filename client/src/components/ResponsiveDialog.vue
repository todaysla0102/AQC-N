<template>
  <MobileBottomSheet
    v-if="isMobileViewport"
    v-bind="attrs"
    :model-value="modelValue"
    :title="mobileTitle || title"
    :subtitle="mobileSubtitle"
    :initial-snap="initialSnap"
    :expanded-snap="expandedSnap"
    :close-threshold="closeThreshold"
    :base-z-index="mobileBaseZIndex"
    @update:modelValue="onMobileModelUpdate"
  >
    <template v-if="$slots.header" #header>
      <slot name="header" />
    </template>

    <slot />

    <template v-if="$slots.footer" #footer>
      <slot name="footer" />
    </template>
  </MobileBottomSheet>

  <el-dialog
    v-else
    v-bind="attrs"
    :model-value="modelValue"
    :title="title"
    :width="width"
    :append-to-body="appendToBody"
    :destroy-on-close="destroyOnClose"
    :align-center="alignCenter"
    :before-close="onDesktopBeforeClose"
    @update:modelValue="emit('update:modelValue', $event)"
  >
    <template v-if="$slots.header" #header>
      <slot name="header" />
    </template>

    <slot />

    <template v-if="$slots.footer" #footer>
      <slot name="footer" />
    </template>
  </el-dialog>
</template>

<script setup>
import { useAttrs } from 'vue'

import { useMobileViewport } from '../composables/useMobileViewport'
import MobileBottomSheet from './MobileBottomSheet.vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  title: {
    type: String,
    default: '',
  },
  mobileTitle: {
    type: String,
    default: '',
  },
  mobileSubtitle: {
    type: String,
    default: '',
  },
  width: {
    type: String,
    default: 'min(860px, 96vw)',
  },
  appendToBody: {
    type: Boolean,
    default: true,
  },
  destroyOnClose: {
    type: Boolean,
    default: true,
  },
  alignCenter: {
    type: Boolean,
    default: true,
  },
  beforeClose: {
    type: Function,
    default: null,
  },
  initialSnap: {
    type: Number,
    default: 0.56,
  },
  expandedSnap: {
    type: Number,
    default: 0.92,
  },
  closeThreshold: {
    type: Number,
    default: 0.38,
  },
  mobileBaseZIndex: {
    type: Number,
    default: 2600,
  },
})

const emit = defineEmits(['update:modelValue'])

const attrs = useAttrs()
const { isMobileViewport } = useMobileViewport()

function runBeforeClose(done) {
  if (typeof props.beforeClose === 'function') {
    props.beforeClose(done)
    return
  }
  done()
}

function onDesktopBeforeClose(done) {
  runBeforeClose(done)
}

function onMobileModelUpdate(value) {
  if (value) {
    emit('update:modelValue', true)
    return
  }
  runBeforeClose(() => emit('update:modelValue', false))
}
</script>
