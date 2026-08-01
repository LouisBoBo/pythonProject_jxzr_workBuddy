<template>
  <!-- 内联 SVG：保留文件内动画（勿用 img，否则动画不播） -->
  <span class="ai-avatar" aria-hidden="true" v-html="avatarMarkup" />
</template>

<script setup>
import { computed } from 'vue'
import rawSvg from '../assets/pcb-ai-avatar2.svg?raw'

defineProps({
  spinning: { type: Boolean, default: false },
})

const avatarMarkup = computed(() => {
  let svg = String(rawSvg || '')
  svg = svg
    .replace(/\swidth="[^"]*"/, '')
    .replace(/\sheight="[^"]*"/, '')
    .replace(/<title>[\s\S]*?<\/title>/, '')
    .replace(/<desc>[\s\S]*?<\/desc>/, '')
  return svg
})
</script>

<style scoped>
.ai-avatar {
  display: inline-flex;
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  border-radius: 50%;
  overflow: hidden;
  background: #162E1F;
}

.ai-avatar :deep(svg) {
  width: 100%;
  height: 100%;
  display: block;
}

@media (prefers-reduced-motion: reduce) {
  .ai-avatar :deep(animate),
  .ai-avatar :deep(animateTransform) {
    display: none;
  }
}
</style>
