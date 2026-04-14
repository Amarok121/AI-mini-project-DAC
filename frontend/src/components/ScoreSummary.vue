<template>
  <div class="score-grid">
    <div class="score-card">
      <div class="score-label">Scientific Readiness</div>
      <div class="score-row">
        <div class="score-value">{{ scoreSummary?.trl ?? "—" }}</div>
        <span class="badge" :class="badgeClass(scoreSummary?.trl_level)">{{ scoreSummary?.trl_level ?? "—" }}</span>
      </div>
    </div>

    <div class="score-card">
      <div class="score-label">Industrial Readiness</div>
      <div class="score-row">
        <div class="score-value">{{ scoreSummary?.mrl ?? "—" }}</div>
        <span class="badge" :class="badgeClass(scoreSummary?.mrl_level)">{{ scoreSummary?.mrl_level ?? "—" }}</span>
      </div>
    </div>

    <div class="score-card score-card-wide">
      <div class="score-label">Confidence Index</div>
      <div class="score-row">
        <div class="score-value">{{ scoreSummary?.cri ?? "—" }}</div>
        <span class="badge" :class="badgeClass(scoreSummary?.cri_level)">{{ scoreSummary?.cri_level ?? "—" }}</span>
      </div>
      <BarMini v-if="scoreSummary?.bars?.length" :bars="scoreSummary.bars" />
      <div v-else class="hint">score_summary.bars가 있으면 막대그래프가 렌더링됩니다.</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import BarMini from "./mini/BarMini.vue";

type Level = "HIGH" | "MED" | "LOW" | string;

export type ScoreBar = { label: string; value: number; level?: Level };
export type ScoreSummary = {
  trl?: string;
  mrl?: string;
  cri?: string;
  trl_level?: Level;
  mrl_level?: Level;
  cri_level?: Level;
  bars?: ScoreBar[];
};

defineProps<{ scoreSummary?: ScoreSummary }>();

function badgeClass(level?: string) {
  const v = (level ?? "").toUpperCase();
  if (v === "HIGH") return "high";
  if (v === "MED") return "med";
  if (v === "LOW") return "low";
  return "neutral";
}
</script>

