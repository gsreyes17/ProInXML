<script setup lang="ts">
defineProps<{ name: string }>();
const paths: Record<string, string> = {
  upload: "M12 16V3m-5 5 5-5 5 5M4 15v5a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-5",
  tracking: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01",
  attempts: "M12 8v4l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z",
  metrics: "M4 20h17M7 16v-5m5 5V4m5 12V8",
  xml: "M4 6c0-4 16-4 16 0s-16 4-16 0Zm0 0v6c0 4 16 4 16 0V6M4 12v6c0 4 16 4 16 0v-6",
  model: "m12 3 10 5-10 5L2 8l10-5Zm-9 9 9 5 9-5M3 16l9 5 9-5",
  quality: "m12 3 9 17H3L12 3Zm0 6v5m0 3h.01",
  audit: "m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Zm-4 9 3 3 5-6",
  users:
    "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2m20 0v-2a4 4 0 0 0-3-3.87M13 3a4 4 0 0 1 0 8M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z",
  maintenance: "m14 5 5 5M3 21l5-1 13-13-5-5L3 15v6Z",
  power: "M12 2v10m6.36-6.36a9 9 0 1 1-12.72 0",
  processing: "M4 4h16v6H4V4Zm0 10h16v6H4v-6Zm4-7h.01M8 17h.01",
  queries: "M11 3a8 8 0 1 0 0 16a8 8 0 0 0 0-16Zm6 14 4 4",
  admin: "M12 2 20 6v6c0 5-8 10-8 10S4 17 4 12V6l8-4Zm-3 10 2 2 4-4",
};
</script>
<template>
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.7"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path :d="paths[name] || paths.tracking" />
  </svg>
</template>
