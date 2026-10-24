<script setup lang="ts">
import { nextTick, ref, watch } from "vue";
const props = defineProps<{
  open: boolean;
  title: string;
  eyebrow?: string;
  busy?: boolean;
}>();
const emit = defineEmits<{ close: [] }>();
const dialog = ref<HTMLDialogElement | null>(null);
watch(
  () => props.open,
  async (open) => {
    await nextTick();
    if (open && !dialog.value?.open) dialog.value?.showModal();
    else if (!open && dialog.value?.open) dialog.value?.close();
  },
  { immediate: true },
);
</script>
<template>
  <dialog
    ref="dialog"
    @close="emit('close')"
    @cancel="busy && $event.preventDefault()"
  >
    <div class="dialog-heading">
      <div>
        <div class="eyebrow">{{ eyebrow || "DETALLE" }}</div>
        <h2>{{ title }}</h2>
      </div>
      <button
        class="close-button"
        aria-label="Cerrar detalle"
        :disabled="busy"
        @click="dialog?.close()"
      >
        ×
      </button>
    </div>
    <div class="dialog-content"><slot /></div>
  </dialog>
</template>
