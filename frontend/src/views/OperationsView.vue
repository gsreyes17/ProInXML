<script setup lang="ts">
import { computed, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";
import PagedExplorer from "../components/PagedExplorer.vue";
import DocumentDetail from "../components/DocumentDetail.vue";
import { date, text } from "../services/format";
import type { DataRow } from "../types";
const route = useRoute();
const selected = ref<DataRow | null>(null);
const execution = computed(() => route.name === "ejecucion");
const columns = computed(() =>
  execution.value
    ? [
        "Id",
        "TrabajoId",
        "LoteId",
        "Numero",
        "Estado",
        "Etapa",
        "HTTPStatus",
        "InicioUTC",
        "FinUTC",
        "DuracionMs",
        "DocumentoId",
        "RegistrosLeidos",
        "RegistrosInsertados",
        "RegistrosReutilizados",
        "RegistrosRechazados",
        "Observaciones",
        "Error",
        "URLSolicitada",
      ]
    : [
        "Id",
        "DocumentoId",
        "OrdinalItem",
        "Campo",
        "CodigoObservacion",
        "Severidad",
        "Detalle",
        "FechaUTC",
      ],
);
const filters = computed(() =>
  execution.value
    ? [
        { key: "lote_id", label: "Lote", type: "number" },
        { key: "trabajo_id", label: "Trabajo", type: "number" },
        { key: "http_status", label: "HTTP", type: "number" },
        {
          key: "solo_fallos",
          label: "Incidencias",
          options: [{ value: "true", label: "Solo fallos e interrupciones" }],
        },
        {
          key: "estado",
          label: "Resultado",
          options: ["Completado", "Error", "EnCurso", "Interrumpido"].map(
            (value) => ({ value, label: value }),
          ),
        },
      ]
    : [
        { key: "documento_id", label: "Documento", type: "number" },
        { key: "campo", label: "Campo" },
        { key: "codigo", label: "Código" },
        {
          key: "severidad",
          label: "Severidad",
          options: ["Info", "Advertencia", "Error"].map((value) => ({
            value,
            label: value,
          })),
        },
      ],
);
</script>
<template>
  <PagedExplorer
    :key="String(route.name)"
    :path="execution ? '/reportes/ejecucion' : '/observaciones'"
    :title="execution ? 'Intentos del servicio' : 'Incidencias por documento'"
    :prefix="execution ? 'execution' : 'observations'"
    :columns="columns"
    :filters="filters"
    :labels="{
      HTTPStatus: 'HTTP',
      DuracionMs: 'Duración (ms)',
      RegistrosLeidos: 'Leídos',
      RegistrosInsertados: 'Insertados',
      RegistrosReutilizados: 'Reutilizados',
      RegistrosRechazados: 'Rechazados',
      URLSolicitada: 'URL solicitada',
    }"
    ><template #cell="{ row, column }"
      ><RouterLink
        v-if="column === 'DocumentoId' && row[column]"
        class="row-action"
        :to="{ name: 'datos', query: { documento_id: Number(row[column]) } }"
        >{{ row[column] }} ↗</RouterLink
      ><template v-else-if="column === 'HTTPStatus'">{{
        row[column] === null ? "Sin respuesta" : row[column]
      }}</template
      ><template v-else>{{
        column.endsWith("UTC") ? date(row[column]) : text(row[column])
      }}</template></template
    ><template #actions="{ row }"
      ><button
        v-if="row.DocumentoId"
        class="row-action"
        @click="selected = row"
      >
        {{
          execution ? "Inspeccionar respuesta ↗" : "Ver dato observado ↗"
        }}</button
      ><span v-else class="subtle">Sin respuesta guardada</span></template
    ></PagedExplorer
  >
  <DocumentDetail
    :document-id="selected?.DocumentoId ? Number(selected.DocumentoId) : null"
    :ordinal="selected?.OrdinalItem ? Number(selected.OrdinalItem) : undefined"
    :field="selected?.Campo ? String(selected.Campo) : undefined"
    @close="selected = null"
  />
</template>
