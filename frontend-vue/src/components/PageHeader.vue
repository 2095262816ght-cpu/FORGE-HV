<template>
  <div class="page-head">
    <div>
      <div class="page-sub">{{ sub }}</div>
      <h1 class="page-title">
        <template v-if="em">{{ before }}<em>{{ em }}</em></template>
        <template v-else>{{ title }}</template>
      </h1>
    </div>
    <div v-if="desc" class="page-desc">{{ desc }}</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  sub: { type: String, default: '' },
  title: { type: String, default: '' },
  /** Emphasized trailing phrase for gradient title, e.g. title="数据" em="可视化" */
  em: { type: String, default: '' },
  desc: { type: String, default: '' },
})

const before = computed(() => (props.em ? `${props.title} ` : props.title))
</script>
