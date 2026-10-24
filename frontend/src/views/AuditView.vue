<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { RouterLink } from "vue-router";
import PagedExplorer from "../components/PagedExplorer.vue";
import DetailDialog from "../components/DetailDialog.vue";
import { api } from "../services/api";
import { date, text } from "../services/format";
import type { DataRow } from "../types";

const tab = ref("cambios");
const tables = ref<string[]>([]);
const setupError = ref("");
const path = computed(() =>
  tab.value === "cambios"
    ? "/auditoria"
    : tab.value === "cargas"
      ? "/auditoria/cargas"
      : "/auditoria/accesos",
);
const title = computed(() =>
  tab.value === "cambios"
    ? "Historial de cambios"
    : tab.value === "cargas"
      ? "Cargas por documento"
      : "Eventos de acceso",
);
const columns = computed(() =>
  tab.value === "cambios"
    ? [
        "Id",
        "FechaUtc",
        "Tabla",
        "RegistroId",
        "Operacion",
        "Actor",
        "Rol",
        "LoginSql",
      ]
    : tab.value === "cargas"
      ? [
          "Id",
          "DocumentoId",
          "LoteId",
          "UsuarioId",
          "Rol",
          "FilasInsertadas",
          "FilasReutilizadas",
          "FechaUtc",
        ]
      : [
          "Id",
          "UsuarioId",
          "NombreIntentado",
          "Evento",
          "Exitoso",
          "Ip",
          "FechaUtc",
        ],
);
const filters = computed(() =>
  tab.value === "cambios"
    ? [
        {
          key: "tabla",
          label: "Tabla",
          options: tables.value.map((value) => ({ value, label: value })),
        },
        {
          key: "operacion",
          label: "Operación",
          options: [
            { value: "I", label: "Alta" },
            { value: "U", label: "Modificación" },
            { value: "D", label: "Eliminación" },
          ],
        },
        { key: "actor", label: "Actor" },
        {
          key: "rol",
          label: "Rol",
          options: [
            "Administrador",
            "Operador",
            "Consulta",
            "Sin identificar",
          ].map((value) => ({ value, label: value })),
        },
        { key: "registro_id", label: "Registro", type: "number" },
        { key: "desde", label: "Desde", type: "date" },
        { key: "hasta", label: "Hasta", type: "date" },
      ]
    : tab.value === "cargas"
      ? [{ key: "documento_id", label: "Documento", type: "number" }]
      : [],
);
interface Change {
  Id: number;
  Tabla: string;
  RegistroId: number;
  Actor: string;
  Rol: string;
  LoginSql: string;
  FechaUtc: string;
  Correlacion: string | null;
  Antes: DataRow | null;
  Despues: DataRow | null;
}
const detail = ref<Change | null>(null);
const opened = ref(false);
const error = ref("");
let controller: AbortController | null = null;
const fields = computed(() => [
  ...new Set([
    ...Object.keys(detail.value?.Antes || {}),
    ...Object.keys(detail.value?.Despues || {}),
  ]),
]);
onMounted(async () => {
  try {
    tables.value = await api<string[]>("/auditoria/tablas");
  } catch (failure) {
    setupError.value = (failure as Error).message;
  }
});
async function open(row: DataRow) {
  controller?.abort();
  controller = new AbortController();
  const signal = controller.signal;
  opened.value = true;
  detail.value = null;
  error.value = "";
  try {
    const result = await api<Change>(`/auditoria/${row.Id}`, { signal });
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
  <div class="tabs" aria-label="Tipo de auditoría">
    <button
      v-for="(label, key) in {
        cambios: 'Cambios de registros',
        cargas: 'Cargas por documento',
        accesos: 'Eventos de acceso',
      }"
      :key="key"
      :class="['tab', { active: tab === key }]"
      :aria-pressed="tab === key"
      @click="tab = key"
    >
      {{ label }}
    </button>
  </div>
  <p v-if="setupError" class="notice notice-error">{{ setupError }}</p>
  <PagedExplorer
    :path="path"
    :title="title"
    prefix="audit"
    :columns="columns"
    :filters="filters"
    ><template #cell="{ row, column }"
      ><RouterLink
        v-if="column === 'DocumentoId'"
        class="row-action"
        :to="{ name: 'datos', query: { documento_id: Number(row[column]) } }"
        >{{ row[column] }} ↗</RouterLink
      ><template v-else>{{
        column.endsWith("Utc") ? date(row[column]) : text(row[column])
      }}</template></template
    ><template v-if="tab === 'cambios'" #actions="{ row }"
      ><button class="row-action" @click="open(row)">
        Ver cambios ↗
      </button></template
    ></PagedExplorer
  >
  <DetailDialog
    :open="opened"
    :title="detail ? `Evento #${detail.Id}` : 'Consultando evento…'"
    eyebrow="AUDITORÍA · ANTES Y DESPUÉS"
    @close="close"
    ><p v-if="error" class="notice notice-error">{{ error }}</p>
    <template v-if="detail"
      ><p class="detail-meta">
        {{ detail.Tabla }} · Registro #{{ detail.RegistroId }} ·
        {{ detail.Actor }} · {{ detail.Rol }} · {{ date(detail.FechaUtc) }}
      </p>
      <p class="detail-meta">
        Usuario SQL: {{ detail.LoginSql }} · Correlación:
        {{ detail.Correlacion }}
      </p>
      <div class="table-scroll">
        <table class="audit-comparison">
          <thead>
            <tr>
              <th>Campo</th>
              <th>Antes</th>
              <th>Después</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="field in fields"
              :key="field"
              :class="{
                'field-changed':
                  detail.Antes?.[field] !== detail.Despues?.[field],
              }"
            >
              <td>{{ field }}</td>
              <td>
                <pre>{{
                  detail.Antes && Object.hasOwn(detail.Antes, field)
                    ? text(detail.Antes[field])
                    : "—"
                }}</pre>
              </td>
              <td>
                <pre>{{
                  detail.Despues && Object.hasOwn(detail.Despues, field)
                    ? text(detail.Despues[field])
                    : "—"
                }}</pre>
              </td>
            </tr>
          </tbody>
        </table>
      </div></template
    ></DetailDialog
  >
</template>
