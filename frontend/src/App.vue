<template>
  <div>
    <header class="topbar">
      <div class="container topbar-inner">
        <div class="brand">
          <span class="brand-mark" aria-hidden="true">
            <img src="/claimy-mark.svg?v=inkcapsule" alt="" width="30" height="30" />
          </span>
          <div class="brand-text">
            <strong class="brand-name">Claimy</strong>
            <span class="brand-sub">Evidence-driven claim verification</span>
          </div>
        </div>
        <nav class="topnav">
          <RouterLink to="/" class="navlink">Dashboard</RouterLink>
          <button class="navlink theme-toggle" type="button" @click="toggleTheme" :title="themeLabel">
            {{ themeIcon }}
          </button>
        </nav>
      </div>
    </header>
    <RouterView />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

type Theme = "dark" | "light";
const theme = ref<Theme>("dark");

function applyTheme(t: Theme) {
  theme.value = t;
  document.documentElement.dataset.theme = t;
  try {
    localStorage.setItem("claimy_theme", t);
  } catch {
    // ignore
  }
}

function detectInitialTheme(): Theme {
  try {
    const saved = localStorage.getItem("claimy_theme");
    if (saved === "dark" || saved === "light") return saved;
  } catch {
    // ignore
  }
  const prefersLight = window.matchMedia?.("(prefers-color-scheme: light)")?.matches;
  return prefersLight ? "light" : "dark";
}

function toggleTheme() {
  applyTheme(theme.value === "dark" ? "light" : "dark");
}

const themeIcon = computed(() => (theme.value === "dark" ? "☾" : "☀"));
const themeLabel = computed(() => (theme.value === "dark" ? "라이트 모드로 전환" : "다크 모드로 전환"));

onMounted(() => {
  applyTheme(detectInitialTheme());
});
</script>

