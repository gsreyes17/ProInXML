<script setup lang="ts">
import { computed, onUnmounted, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";
import PagedExplorer from "../components/PagedExplorer.vue";
import DetailDialog from "../components/DetailDialog.vue";
import { api } from "../services/api";
import { text } from "../services/format";
import type { DataRow, PageData } from "../types";

const route = useRoute();
const mode = ref("true");
const versions = ref(
  route.query.documento_id || route.query.registro_id ? "false" : "true",
);
const fixed = computed(() => ({
  solo_xml: mode.value === "true",
  vigentes: versions.value === "true",
}));
const filters = [
  { key: "ano", label: "Año", type: "number" },
  { key: "sec_ejec", label: "Ejecutora", type: "number" },
  { key: "proyecto", label: "Proyecto" },
  { key: "documento_id", label: "Documento", type: "number" },
  { key: "registro_id", label: "Registro", type: "number" },
];
const identifiers = ref<number[]>([]);
function loaded(result: PageData) {
  identifiers.value = result.identificadores || [];
}
const opened = ref(false);
const detailId = ref<number | null>(null);
const detail = ref<{ registro: DataRow; trazabilidad: DataRow } | null>(null);
const error = ref("");
let controller: AbortController | null = null;
async function open(row: DataRow, index: number) {
  controller?.abort();
  controller = new AbortController();
  const signal = controller.signal;
  detailId.value = Number(row.Id || identifiers.value[index]);
  detail.value = null;
  opened.value = true;
  error.value = "";
  try {
    const result = await api<{ registro: DataRow; trazabilidad: DataRow }>(
      `/datos/xml/${detailId.value}`,
      { signal },
    );
    if (!signal.aborted) detail.value = result;
  } catch (failure) {
    if (!signal.aborted) error.value = (failure as Error).message;
  }
}
function close() {
  opened.value = false;
  controller?.abort();
}
onUnmounted(() => controller?.abort());
</script>
<template>
  <PagedExplorer
    path="/datos/xml"
    title="Registros originales"
    prefix="data"
    :filters="filters"
    :fixed="fixed"
    :descending="false"
    @loaded="loaded"
  >
    <template #filters
      ><label
        >Versiones<select id="data-versions" v-model="versions">
          <option value="true">Última versión por consulta</option>
          <option value="false">Todas las versiones</option>
        </select></label
      ><label
        >Vista<select id="data-mode" v-model="mode">
          <option value="true">Solo XML · 39 campos</option>
          <option value="false">XML con identificadores</option>
        </select></label
      ></template
    >
    <template #heading
      ><span id="data-mode-tag" class="small-tag">{{
        mode === "true" ? "SOLO XML · 39 CAMPOS" : "XML + TRAZABILIDAD"
      }}</span></template
    >
    <template #cell="{ row, column, index }"
      ><button
        v-if="column === (mode === 'true' ? 'AnoEje' : 'Id')"
        class="row-action"
        :aria-label="`Abrir registro XML ${row.Id || identifiers[index]}`"
        @click="open(row, index)"
      >
        {{ row[column] }} ↗</button
      ><template v-else>{{ text(row[column]) }}</template></template
    >
  </PagedExplorer>
  <DetailDialog
    :open="opened"
    :title="`Registro #${detailId}`"
    eyebrow="XML Y TRAZABILIDAD"
    @close="close"
    ><p v-if="error" class="notice notice-error">{{ error }}</p>
    <p v-else-if="!detail">Consultando registro…</p>
    <template v-if="detail"
      ><div class="detail-actions">
        <RouterLink
          class="button button-outline button-small"
          :to="{
            name: 'modelo',
            query: { tabla: 'Gasto', registro_id: detailId },
          }"
          >Ver en modelo ↗</RouterLink
        ><RouterLink
          class="button button-outline button-small"
          :to="{
            name: 'observaciones',
            query: { documento_id: Number(detail.trazabilidad.DocumentoId) },
          }"
          >Observaciones del documento ↗</RouterLink
        >
      </div>
      <template
        v-for="(values, section) in {
          Trazabilidad: detail.trazabilidad,
          'Los 39 campos del XML': detail.registro,
        }"
        :key="section"
        ><h3 class="detail-section-title">{{ section }}</h3>
        <dl class="record-fields">
          <div v-for="(value, field) in values" :key="field">
            <dt>{{ field }}</dt>
            <dd>{{ text(value) }}</dd>
          </div>
        </dl></template
      ></template
    ></DetailDialog
  >
</template>
