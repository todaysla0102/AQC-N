<template>
  <section class="placeholder-page card-surface">
    <header class="section-head">
      <h2>{{ moduleInfo.title }}</h2>
      <p>{{ moduleInfo.description }}</p>
    </header>

    <div class="placeholder-list">
      <div v-for="(text, idx) in moduleInfo.bullets" :key="`${idx}-${text}`" class="placeholder-item">
        <el-icon><CircleCheckFilled /></el-icon>
        <span>{{ text }}</span>
      </div>
    </div>
  </section>
</template>

<script setup>
import { CircleCheckFilled } from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import { moduleMap } from '../data/modules'

const route = useRoute()

const moduleInfo = computed(() => {
  const key = String(route.params.moduleKey || '')
  return (
    moduleMap[key] || {
      title: '迁移中模块',
      description: '该模块正在从 AQC-O 迁移到 AQC-N，后续会逐步补充。',
      bullets: ['当前模块已占位', '可继续按需求细化接口与页面'],
    }
  )
})
</script>
