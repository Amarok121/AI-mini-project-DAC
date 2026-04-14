<template>
  <div class="timeline">
    <div v-if="!steps?.length" class="hint">roadmap_steps가 있으면 타임라인이 표시됩니다.</div>
    <ol v-else class="timeline-list">
      <li v-for="(s, i) in steps" :key="i" class="timeline-item">
        <div class="timeline-dot" :class="badgeClass(s.status)" />
        <div class="timeline-body">
          <div class="timeline-title">
            <span style="font-weight: 800">{{ s.title }}</span>
            <span class="badge" :class="badgeClass(s.status)">{{ s.status }}</span>
          </div>
          <div class="hint" v-if="s.description">{{ s.description }}</div>
        </div>
      </li>
    </ol>
  </div>
</template>

<script setup lang="ts">
type Level = "HIGH" | "MED" | "LOW" | "DONE" | "NEXT" | "RISK" | string;
export type RoadmapStep = { title: string; description?: string; status?: Level };
defineProps<{ steps?: RoadmapStep[] }>();

function badgeClass(level?: string) {
  const v = (level ?? "").toUpperCase();
  if (v === "HIGH" || v === "DONE") return "high";
  if (v === "MED" || v === "NEXT") return "med";
  if (v === "LOW" || v === "RISK") return "low";
  return "neutral";
}
</script>

