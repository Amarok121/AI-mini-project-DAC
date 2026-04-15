<template>
  <div class="gauge">
    <div class="gauge-top">
      <span class="badge" :class="badgeClass(level)">{{ levelLabel }}</span>
      <span class="hint">{{ Math.round(pct) }}%</span>
    </div>
    <div class="gauge-track">
      <div class="gauge-fill" :class="badgeClass(level)" :style="{ width: clampPct(pct) + '%' }" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";

type Level = "HIGH" | "MED" | "LOW" | string;
const props = defineProps<{ pct: number; level?: Level }>();

function clampPct(v: number) {
  if (!Number.isFinite(v)) return 0;
  return Math.max(0, Math.min(100, v));
}

function badgeClass(level?: string) {
  const v = (level ?? "").toUpperCase();
  if (v === "HIGH") return "high";
  if (v === "MED") return "med";
  if (v === "LOW") return "low";
  return "neutral";
}

const levelLabel = computed(() => (props.level ?? "—"));
</script>

