<template>
  <div class="bar-mini">
    <div v-for="(b, i) in bars" :key="i" class="bar-row">
      <div class="bar-label">{{ b.label }}</div>
      <div class="bar-track">
        <div class="bar-fill" :style="{ width: clampPct(b.value) + '%'}" :class="badgeClass(b.level)" />
      </div>
      <div class="bar-val">{{ Math.round(b.value) }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
type Level = "HIGH" | "MED" | "LOW" | string;
type ScoreBar = { label: string; value: number; level?: Level };
defineProps<{ bars: ScoreBar[] }>();

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
</script>

