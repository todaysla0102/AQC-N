<template>
  <el-dialog
    :model-value="modelValue"
    :title="title"
    width="min(920px, 96vw)"
    append-to-body
    align-center
    destroy-on-close
    class="aqc-app-dialog export-columns-dialog"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <section class="goods-compare-panel export-columns-panel">
      <div class="goods-compare-toggle-row export-columns-toolbar">
        <div class="export-columns-copy">
          <strong>选择导出列</strong>
          <span>按点击顺序决定导出列顺序</span>
        </div>
        <div class="toolbar-actions">
          <el-button @click="toggleSelectAll">{{ allSelected ? '取消全选' : '全选' }}</el-button>
          <el-button :disabled="!selectedKeys.length" @click="clearSelection">清空选择</el-button>
        </div>
      </div>

      <div v-if="allowPresets" class="goods-compare-preset-row export-columns-preset-row">
        <el-input
          v-model.trim="presetName"
          class="goods-compare-preset-input"
          maxlength="30"
          placeholder="输入预设名称"
          @keyup.enter="savePreset"
        />
        <div class="toolbar-actions">
          <el-button @click="savePreset">保存预设</el-button>
        </div>
      </div>

      <div v-if="allowPresets && presets.length" class="goods-compare-presets export-columns-presets">
        <button
          v-for="preset in presets"
          :key="preset.id"
          type="button"
          class="goods-compare-preset-chip"
          :class="{ active: isPresetActive(preset) }"
          @click="applyPreset(preset)"
        >
          <span>{{ preset.name }}</span>
          <small>{{ preset.keys.length }} 列</small>
        </button>
      </div>

      <div class="goods-compare-selection-summary export-columns-selection-summary">
        <span>已选 {{ selectedKeys.length }} 列</span>
        <strong>{{ selectedLabels }}</strong>
      </div>

      <div class="inventory-button-grid export-columns-grid">
        <button
          v-for="option in options"
          :key="option.key"
          type="button"
          class="inventory-button-main goods-compare-location-button export-columns-option"
          :class="{ active: selectedKeySet.has(option.key) }"
          @click="toggleOption(option.key)"
        >
          <span>{{ option.label }}</span>
          <small v-if="option.description">{{ option.description }}</small>
          <span v-if="selectionOrderMap[option.key]" class="goods-compare-location-order">
            {{ selectionOrderMap[option.key] }}
          </span>
        </button>
      </div>
    </section>

    <template #footer>
      <div class="toolbar-actions export-columns-footer">
        <el-button @click="emit('update:modelValue', false)">取消</el-button>
        <el-button type="primary" :disabled="!selectedKeys.length" @click="confirmSelection">
          {{ confirmText }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  title: {
    type: String,
    default: '导出设置',
  },
  options: {
    type: Array,
    default: () => [],
  },
  selectedKeys: {
    type: Array,
    default: () => [],
  },
  presets: {
    type: Array,
    default: () => [],
  },
  allowPresets: {
    type: Boolean,
    default: false,
  },
  confirmText: {
    type: String,
    default: '确认导出',
  },
})

const emit = defineEmits([
  'update:modelValue',
  'update:selectedKeys',
  'confirm',
  'save-preset',
])

const presetName = ref('')

const selectedKeySet = computed(() => new Set((props.selectedKeys || []).map((item) => String(item || ''))))
const allSelected = computed(() => props.options.length > 0 && props.selectedKeys.length === props.options.length)
const selectionOrderMap = computed(() => Object.fromEntries(
  (props.selectedKeys || []).map((key, index) => [String(key || ''), index + 1]),
))
const selectedLabels = computed(() => {
  const labelMap = new Map(props.options.map((item) => [item.key, item.label]))
  const labels = props.selectedKeys.map((key) => labelMap.get(key)).filter(Boolean)
  return labels.join(' / ') || '未选择'
})

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) {
      presetName.value = ''
    }
  },
)

function updateSelection(nextKeys) {
  emit('update:selectedKeys', nextKeys)
}

function toggleOption(key) {
  const normalizedKey = String(key || '')
  if (!normalizedKey) {
    return
  }
  const exists = selectedKeySet.value.has(normalizedKey)
  updateSelection(
    exists
      ? props.selectedKeys.filter((item) => item !== normalizedKey)
      : [...props.selectedKeys, normalizedKey],
  )
}

function toggleSelectAll() {
  if (allSelected.value) {
    updateSelection([])
    return
  }
  updateSelection(props.options.map((item) => item.key))
}

function clearSelection() {
  updateSelection([])
}

function applyPreset(preset) {
  updateSelection(Array.isArray(preset?.keys) ? preset.keys.map((item) => String(item || '')).filter(Boolean) : [])
}

function isPresetActive(preset) {
  const nextKeys = Array.isArray(preset?.keys) ? preset.keys.map((item) => String(item || '')).filter(Boolean) : []
  return JSON.stringify(nextKeys) === JSON.stringify(props.selectedKeys)
}

function savePreset() {
  const name = String(presetName.value || '').trim()
  if (!name || !props.selectedKeys.length) {
    return
  }
  emit('save-preset', {
    id: Date.now().toString(36),
    name,
    keys: [...props.selectedKeys],
  })
  presetName.value = ''
}

function confirmSelection() {
  emit('confirm', [...props.selectedKeys])
}
</script>
