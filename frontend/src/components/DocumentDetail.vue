<script setup lang="ts">
import { onUnmounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import { api } from "../services/api";
import { date, text } from "../services/format";
import type { DataRow } from "../types";
import DetailDialog from "./DetailDialog.vue";

const props = defineProps<{
  documentId: number | null;
  ordinal?: number;
  field?: string;
}>();
const emit = defineEmits<{ close: [] }>();
const detail = ref<{
  documento: DataRow;
  registro: DataRow | null;
  original: { texto: string; truncado: boolean };
} | null>(null);
const error = ref("");
const loading = ref(false);
let controller: AbortController | null = null;
watch(
  () => [props.documentId, props.ordinal],
  async () => {
    controller?.abort();
    detail.value = null;
    error.value = "";
    if (!props.documentId) return;
    controller = new AbortController();
    const signal = controller.signal;
    loading.value = true;
    try {
      const result = await api<typeof detail.value>(
        `/documentos/${props.documentId}${props.ordinal ? `?ordinal=${props.ordinal}` : ""}`,
        { signal },
      );
      if (!signal.aborted) detail.value = result;
    } catch (failure) {
      if (!signal.aborted) error.value = (failure as Error).message;
    } finally {
      if (!signal.aborted) loading.value = false;
    }
  },
  { immediate: true },
);
onUnmounted(() => controller?.abort());
</script>

<template>
  <DetailDialog
    :open="!!documentId"
    :title="`Documento #${documentId || ''}`"
    eyebrow="ORIGEN Y CALIDAD"
    @close="emit('close')"
  >
    <p v-if="loading" role="status">Consultando documento…</p>
    <p v-if="error" class="notice notice-error" role="alert">{{ error }}</p>
    <template v-if="detail">
      <dl class="record-fields">
        <div
          v-for="key in [
            'EstadoDocumento',
            'HttpStatus',
            'AnoEje',
            'SecEjec',
            'RegistrosDetalle',
            'Observaciones',
            'Vigente',
            'CreadoUtc',
          ]"
          :key="key"
        >
          <dt>{{ key }}</dt>
          <dd>
            {{
              key.endsWith("Utc")
                ? date(detail.documento[key])
                : text(detail.documento[key])
            }}
          </dd>
        </div>
      </dl>
      <p class="document-url">{{ detail.documento.Url }}</p>
      <p v-if="detail.documento.ErrorValidacion" class="notice notice-error">
        {{ detail.documento.ErrorValidacion }}
      </p>
      <div class="document-links">
        <RouterLink
          class="row-action"
          :to="{ name: 'observaciones', query: { documento_id: documentId } }"
          @click="emit('close')"
          >Ver observaciones ↗</RouterLink
        >
        <RouterLink
          class="row-action"
          :to="{ name: 'datos', query: { documento_id: documentId } }"
          @click="emit('close')"
          >Ver detalle XML ↗</RouterLink
        >
      </div>
      <template v-if="detail.registro">
        <h3>Registro observado · Item {{ ordinal }}</h3>
        <dl class="record-fields">
          <div
            v-for="(value, key) in detail.registro"
            :key="key"
            :class="{ 'field-highlight': key === field }"
          >
            <dt>{{ key }}</dt>
            <dd>{{ value === null ? "NULL" : text(value) }}</dd>
          </div>
        </dl>
      </template>
      <h3>Respuesta original</h3>
      <p class="subtle">
        Vista de texto del contenido recibido{{
          detail.original.truncado ? " · limitada a los primeros 64 KiB" : ""
        }}.
      </p>
      <pre class="original-preview" tabindex="0">{{
        detail.original.texto
      }}</pre>
    </template>
  </DetailDialog>
</template>
