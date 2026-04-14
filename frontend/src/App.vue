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
        </nav>
      </div>
    </header>
    <RouterView />
  </div>
</template>

<script setup lang="ts"></script>

