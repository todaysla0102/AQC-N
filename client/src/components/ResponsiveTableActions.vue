<template>
  <div class="table-action-cell">
    <div v-if="!isCompact" class="table-actions">
      <slot />
    </div>

    <el-popover
      v-else
      v-model:visible="menuVisible"
      trigger="click"
      placement="bottom-end"
      :width="menuWidth"
      popper-class="table-action-menu-popper"
      :teleported="true"
    >
      <template #reference>
        <button
          type="button"
          class="table-action-trigger"
          :aria-label="label"
        >
          <el-icon><MoreFilled /></el-icon>
        </button>
      </template>

      <div class="table-action-menu" @click="closeMenu">
        <slot />
      </div>
    </el-popover>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

import { useMobileViewport } from '../composables/useMobileViewport'

const props = defineProps({
  breakpoint: {
    type: Number,
    default: 980,
  },
  forceCompact: {
    type: Boolean,
    default: false,
  },
  label: {
    type: String,
    default: '操作',
  },
  menuWidth: {
    type: Number,
    default: 172,
  },
})

const { isMobileViewport } = useMobileViewport(props.breakpoint)
const isCompact = computed(() => props.forceCompact || isMobileViewport.value)
const menuVisible = ref(false)

function closeMenu() {
  menuVisible.value = false
}

watch(isCompact, (value) => {
  if (!value) {
    closeMenu()
  }
})
</script>
