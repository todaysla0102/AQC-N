<template>
  <ElSelect
    v-if="useElementSelect"
    v-bind="attrs"
    :model-value="modelValue"
    :placeholder="placeholder"
    :clearable="clearable"
    :disabled="disabled"
    :multiple="multiple"
    :remote="remote"
    :remote-method="remoteMethod"
    :loading="loading"
    @update:model-value="emit('update:modelValue', $event)"
    @change="emit('change', $event)"
  >
    <slot />
  </ElSelect>

  <div
    v-else
    :class="rootClass"
    :style="attrs.style"
    @click="focusNativeSelect"
  >
    <div
      class="el-select__wrapper native-system-select-wrapper"
      :class="{
        'is-focused': focused,
        'is-disabled': disabled,
      }"
    >
      <span
        class="el-select__selected-item native-system-select-value"
        :class="{ 'el-select__placeholder': isPlaceholderVisible }"
      >
        {{ displayText }}
      </span>
      <span v-if="loading" class="native-system-select-loading">加载中</span>
      <button
        v-else-if="canClear"
        type="button"
        class="native-system-select-clear"
        aria-label="清空选择"
        @click.stop="clearSelection"
      >
        ×
      </button>
      <span v-else class="native-system-select-arrow" aria-hidden="true">⌄</span>
      <select
        ref="nativeSelectRef"
        class="native-system-select-control"
        :value="selectedToken"
        :disabled="disabled"
        @focus="handleFocus"
        @blur="handleBlur"
        @change="handleChange"
      >
        <option v-if="showEmptyOption" value="">{{ placeholder || '请选择' }}</option>
        <option
          v-for="option in normalizedOptions"
          :key="option.token"
          :value="option.token"
          :disabled="option.disabled"
        >
          {{ option.label }}
        </option>
      </select>
    </div>
  </div>
</template>

<script setup>
import { ElSelect } from 'element-plus'
import { Comment, Fragment, Text, computed, ref, useAttrs, useSlots } from 'vue'
import { useRoute } from 'vue-router'

defineOptions({
  inheritAttrs: false,
})

const props = defineProps({
  modelValue: {
    type: [String, Number, Boolean, Array, Object],
    default: '',
  },
  placeholder: {
    type: String,
    default: '',
  },
  clearable: {
    type: Boolean,
    default: false,
  },
  disabled: {
    type: Boolean,
    default: false,
  },
  multiple: {
    type: Boolean,
    default: false,
  },
  remote: {
    type: Boolean,
    default: false,
  },
  remoteMethod: {
    type: Function,
    default: null,
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:modelValue', 'change', 'clear', 'visible-change'])
const attrs = useAttrs()
const slots = useSlots()
const route = useRoute()
const nativeSelectRef = ref(null)
const focused = ref(false)
const remoteLoaded = ref(false)

const useElementSelect = computed(() => String(route.name || '') === 'work-orders')

const rootClass = computed(() => [
  'el-select',
  'native-system-select',
  attrs.class,
  {
    'is-disabled': props.disabled,
  },
])

const rawOptions = computed(() => {
  const nodes = slots.default?.() || []
  return flattenOptionNodes(nodes)
})

const normalizedOptions = computed(() => rawOptions.value.map((option, index) => ({
  ...option,
  token: `native-option-${index}`,
})))

const selectedOption = computed(() => (
  normalizedOptions.value.find((option) => isSameValue(option.value, props.modelValue)) || null
))

const selectedToken = computed(() => selectedOption.value?.token || '')
const isPlaceholderVisible = computed(() => !selectedOption.value)
const displayText = computed(() => {
  if (selectedOption.value) {
    return selectedOption.value.label
  }
  return props.placeholder || '请选择'
})
const hasValue = computed(() => {
  if (Array.isArray(props.modelValue)) {
    return props.modelValue.length > 0
  }
  return props.modelValue !== '' && props.modelValue !== null && props.modelValue !== undefined
})
const canClear = computed(() => props.clearable && !props.disabled && hasValue.value)
const showEmptyOption = computed(() => props.clearable || Boolean(props.placeholder))

function flattenOptionNodes(nodes, result = []) {
  for (const node of Array.isArray(nodes) ? nodes : [nodes]) {
    if (!node || node.type === Comment) {
      continue
    }
    if (node.type === Fragment || Array.isArray(node.children)) {
      flattenOptionNodes(node.children || [], result)
      continue
    }
    if (node.type === Text) {
      continue
    }
    const props = node.props || {}
    if ('value' in props || 'label' in props) {
      result.push({
        label: resolveOptionLabel(props, node),
        value: props.value,
        disabled: Boolean(props.disabled),
      })
      continue
    }
    if (node.children) {
      flattenOptionNodes(node.children, result)
    }
  }
  return result
}

function resolveOptionLabel(optionProps, node) {
  if (optionProps.label !== undefined && optionProps.label !== null) {
    return String(optionProps.label)
  }
  if (typeof node.children === 'string') {
    return node.children
  }
  return String(optionProps.value ?? '')
}

function isSameValue(left, right) {
  if (Object.is(left, right)) {
    return true
  }
  if (left === null || left === undefined || right === null || right === undefined) {
    return false
  }
  return String(left) === String(right)
}

function focusNativeSelect() {
  if (props.disabled) {
    return
  }
  nativeSelectRef.value?.focus?.()
}

function handleFocus() {
  focused.value = true
  emit('visible-change', true)
  if (props.remote && typeof props.remoteMethod === 'function' && !remoteLoaded.value) {
    remoteLoaded.value = true
    props.remoteMethod('')
  }
}

function handleBlur() {
  focused.value = false
  emit('visible-change', false)
}

function handleChange(event) {
  const token = String(event?.target?.value || '')
  const option = normalizedOptions.value.find((item) => item.token === token)
  const nextValue = option ? option.value : ''
  emit('update:modelValue', nextValue)
  emit('change', nextValue)
}

function clearSelection() {
  emit('update:modelValue', '')
  emit('change', '')
  emit('clear')
}
</script>
