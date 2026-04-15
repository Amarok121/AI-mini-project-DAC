<template>
  <article class="card" style="border-radius: 10px">
    <div class="card-body">
      <div style="font-weight: 800; margin-bottom: 4px">{{ title }}</div>
      <div class="hint">{{ body }}</div>
    </div>
  </article>
</template>

<script setup lang="ts">
defineProps<{
  title: string;
  body: string;
}>();
</script>
