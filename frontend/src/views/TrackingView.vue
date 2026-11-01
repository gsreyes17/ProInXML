<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import { api, query } from "../services/api";
import { date, decimal, number } from "../services/format";
import { usePolling } from "../composables/usePolling";
import { useAuthStore } from "../stores/auth";
import type { DataRow } from "../types";
import DataTable from "../components/DataTable.vue";
import DetailDialog from "../components/DetailDialog.vue";
import DocumentDetail from "../components/DocumentDetail.vue";

interface Summary {
  lote: DataRow;
  resumen: { Estado: string; Cantidad: number }[];
  registros: number;
  eta_segundos: number | null;
}
const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const selected = computed(() => Number(route.query.lote) || null);
const batches = ref<DataRow[]>([]);
const activeBatch = ref<DataRow | null>(null);
const summary = ref<Summary | null>(null);
const jobs = ref<DataRow[]>([]);
const filter = ref("");
const cursors = ref([0]);
const hasNext = ref(false);
const error = ref("");
const acting = ref<number | null>(null);
const inspectedDocument = ref<number | null>(null);
const complete = ["Completado", "CompletadoSinDatos", "YaCargada"];
const labels: Record<string, string> = {
  Pendiente: "Pendiente",
  EnCurso: "En curso",
  Completado: "Completado",
  CompletadoSinDatos: "Sin datos",
  YaCargada: "Ya cargada",
  Fallido: "Con error",
  Cancelado: "Cancelado",
};
let generation = 0;
let previousCompleted = new Map<number, number>();
let activeSeenAt = 0;
const poll = usePolling(async (signal) => {
  const current = generation;
  const batchId = selected.value;
  const pending = [api<DataRow[]>("/lotes?limite=8", { signal })];
  const history = await pending[0]!;
  if (current !== generation) return;
  const advanced = history.find(
    (batch) =>
      Number(batch.Completados) >
      (previousCompleted.get(Number(batch.Id)) ?? Number(batch.Completados)),
  );
  previousCompleted = new Map(
    history.map((batch) => [Number(batch.Id), Number(batch.Completados)]),
  );
  if (advanced) {
    activeBatch.value = advanced;
    activeSeenAt = Date.now();
  } else if (Date.now() - activeSeenAt > 30000) {
    activeBatch.value = null;
  }
  batches.value = history;
  if (!batchId) {
    if (history.length)
      await router.replace({
        name: "seguimiento",
        query: { lote: Number(history[0]!.Id) },
      });
    return;
  }
  const [status, list] = await Promise.all([
    api<Summary>(`/lotes/${batchId}`, { signal }),
    api<DataRow[]>(
      `/lotes/${batchId}/trabajos?${query({ limite: 51, despues_de: cursors.value.at(-1), estado: filter.value })}`,
      { signal },
    ),
  ]);
  if (current !== generation) return;
  summary.value = status;
  jobs.value = list.slice(0, 50);
  hasNext.value = list.length > 50;
});
watch([selected, filter], () => {
  generation++;
  cursors.value = [0];
  jobs.value = [];
  summary.value = null;
  void poll.restart();
});
const counts = computed(() =>
  Object.fromEntries(
    (summary.value?.resumen || []).map((item) => [item.Estado, item.Cantidad]),
  ),
);
const total = computed(() =>
  (summary.value?.resumen || []).reduce((sum, item) => sum + item.Cantidad, 0),
);
const completed = computed(() =>
  complete.reduce((sum, key) => sum + (counts.value[key] || 0), 0),
);
const failed = computed(() => counts.value.Fallido || 0);
const remaining = computed(
  () =>
    total.value -
    completed.value -
    failed.value -
    (counts.value.Cancelado || 0),
);
const percentage = computed(() =>
  total.value
    ? Math.round(((total.value - remaining.value) / total.value) * 100)
    : 0,
);
function navigatePage(next: boolean) {
  generation++;
  if (next && jobs.value.length)
    cursors.value.push(Number(jobs.value.at(-1)!.Id));
  else if (!next && cursors.value.length > 1) cursors.value.pop();
  void poll.restart();
}
async function action(job: DataRow, force = false) {
  acting.value = Number(job.Id);
  try {
    await api(
      `/trabajos/${job.Id}/${force ? "forzar-revision" : "reintentar"}`,
      { method: "POST" },
    );
    error.value = "";
    await poll.restart();
  } catch (failure) {
    error.value = (failure as Error).message;
  } finally {
    acting.value = null;
  }
}
const recordJob = ref<DataRow | null>(null);
const records = ref<DataRow[]>([]);
const recordCursors = ref([0]);
const recordNext = ref(false);
const recordsError = ref("");
const recordsLoading = ref(false);
let recordGeneration = 0;
async function loadRecords() {
  const job = recordJob.value;
  if (!job) return;
  const current = ++recordGeneration;
  recordsLoading.value = true;
  try {
    const list = await api<DataRow[]>(
      `/trabajos/${job.Id}/gastos?${query({ limite: 51, despues_de: recordCursors.value.at(-1) })}`,
    );
    if (current !== recordGeneration) return;
    records.value = list.slice(0, 50);
    recordNext.value = list.length > 50;
    recordsError.value = "";
  } catch (failure) {
    if (current === recordGeneration)
      recordsError.value = (failure as Error).message;
  } finally {
    if (current === recordGeneration) recordsLoading.value = false;
  }
}
function openRecords(job: DataRow) {
  recordJob.value = job;
  records.value = [];
  recordCursors.value = [0];
  void loadRecords();
}
function recordPage(next: boolean) {
  if (next && records.value.length)
    recordCursors.value.push(Number(records.value.at(-1)!.Id));
  else if (!next && recordCursors.value.length > 1) recordCursors.value.pop();
  void loadRecords();
}
function closeRecords() {
  recordGeneration++;
  recordJob.value = null;
}
</script>
<template>
  <section class="results-section">
    <DocumentDetail
      :document-id="inspectedDocument"
      @close="inspectedDocument = null"
    />
    <p v-if="route.query.nuevas !== undefined" class="notice" role="status">
      Carga registrada: {{ route.query.nuevas }} por procesar,
      {{ route.query.ya_cargadas }} ya cargadas y
      {{ route.query.duplicados }} repetidas omitidas.
    </p>
    <div class="card batch-selector">
      <label for="batch-select"
        >Seleccionar carga<select
          id="batch-select"
          :value="selected || ''"
          @change="
            router.push({
              name: 'seguimiento',
              query: { lote: ($event.target as HTMLSelectElement).value },
            })
          "
        >
          <option value="" disabled>Selecciona un lote</option>
          <option
            v-for="batch in batches"
            :key="Number(batch.Id)"
            :value="Number(batch.Id)"
          >
            #{{ batch.Id }} · {{ batch.Nombre }} · {{ batch.Completados }}/{{
              batch.Total
            }}
          </option>
        </select></label
      >
      <div class="batch-actions">
        <button
          id="refresh"
          class="button button-outline"
          :disabled="poll.loading.value"
          @click="poll.refresh"
        >
          ↻ Actualizar
        </button>
        <span class="sync-status" role="status">{{
          poll.updated.value
            ? `Actualizado ${poll.updated.value.toLocaleTimeString("es-PE")}`
            : "Actualizando…"
        }}</span>
      </div>
    </div>
    <div
      v-if="summary && remaining && !(counts.EnCurso || 0)"
      class="notice queue-notice"
      role="status"
    >
      <span v-if="activeBatch && Number(activeBatch.Id) !== selected">
        Este lote espera su turno o un reintento. La cola está procesando el lote
        #{{ activeBatch.Id }}.
        <RouterLink
          class="text-button"
          :to="{ name: 'seguimiento', query: { lote: Number(activeBatch.Id) } }"
        >Ver lote activo</RouterLink>
      </span>
      <span v-else>
        Este lote conserva trabajos pendientes. Si no avanzan, comprueba que el
        worker siga activo con iniciar.cmd.
      </span>
    </div>
    <p
      v-if="poll.error.value || error"
      class="notice notice-error"
      role="alert"
    >
      {{ error || poll.error.value }}
    </p>
    <div v-if="summary" class="stats">
      <div class="stat">
        <span class="stat-label">Enlaces en la carga</span
        ><strong id="stat-total" class="stat-number">{{ number(total) }}</strong
        ><span class="stat-caption"
          >#{{ selected }} · {{ date(summary.lote.CreadoUTC) }}</span
        >
      </div>
      <div class="stat">
        <span class="stat-label">Completados</span
        ><strong id="stat-completed" class="stat-number">{{
          number(completed)
        }}</strong
        ><span class="stat-caption">{{
          remaining ? `${remaining} por finalizar` : "Procesamiento finalizado"
        }}</span>
      </div>
      <div class="stat">
        <span class="stat-label">Registros disponibles</span
        ><strong id="stat-records" class="stat-number">{{
          number(summary.registros)
        }}</strong
        ><span class="stat-caption">Asociados a esta carga</span>
      </div>
      <div class="stat">
        <span class="stat-label">Con error</span
        ><strong id="stat-errors" class="stat-number">{{
          number(failed)
        }}</strong
        ><span class="stat-caption">{{
          failed ? "Revisa el detalle de enlaces" : "Sin errores definitivos"
        }}</span>
      </div>
    </div>
    <label class="job-state-filter" for="job-state"
      >Estado de enlaces<select id="job-state" v-model="filter">
        <option value="">Todos los estados</option>
        <option v-for="(label, key) in labels" :key="key" :value="key">
          {{ label }}
        </option>
      </select></label
    >
    <div class="card results-card">
      <div class="table-heading">
        <div>
          <h2>
            Detalle de enlaces
            <span v-if="selected" class="batch-tag">#{{ selected }}</span>
          </h2>
          <p>
            {{ completed }} completados · {{ failed }} con error ·
            {{ counts.YaCargada || 0 }} ya cargados<span
              v-if="summary?.eta_segundos"
            >
              · Estimación:
              {{ Math.max(1, Math.ceil(summary.eta_segundos / 60)) }} min</span
            >
          </p>
        </div>
        <span v-if="remaining" class="live-badge"
          ><span></span>Actualización cada 3 s</span
        >
      </div>
      <div
        v-if="summary"
        class="progress-track"
        role="progressbar"
        :aria-valuenow="percentage"
        aria-valuemin="0"
        aria-valuemax="100"
        aria-label="Enlaces finalizados"
      >
        <div :style="{ width: percentage + '%' }"></div>
      </div>
      <div class="table-scroll">
        <table class="jobs-table">
          <thead>
            <tr>
              <th>Fuente XML</th>
              <th>Estado</th>
              <th>Intentos / HTTP</th>
              <th class="align-right">Registros</th>
              <th>Acciones</th>
            </tr>
          </thead>
          <tbody id="jobs-body">
            <tr v-for="job in jobs" :key="Number(job.Id)">
              <td>
                <div class="source-title">
                  <strong>{{ job.AnoEje }}</strong
                  ><span
                    >Ejecutora {{ job.SecEjec }} · {{ job.NivelGobierno }}</span
                  >
                </div>
                <span class="source-url" :title="String(job.URL)">{{
                  job.URL
                }}</span>
                <details v-if="job.UltimoError" class="error-details">
                  <summary>Ver último error</summary>
                  <p>{{ job.UltimoError }}</p>
                  <p v-if="job.Estado === 'Pendiente'">
                    Próximo intento: {{ date(job.ProximoIntentoUTC) }}
                  </p>
                </details>
              </td>
              <td>
                <span
                  :class="[
                    'status-badge',
                    complete.includes(String(job.Estado))
                      ? 'status-COMPLETADO'
                      : job.Estado === 'Fallido'
                        ? 'status-FALLIDO'
                        : job.Estado === 'EnCurso'
                          ? 'status-PROCESANDO'
                          : 'status-PENDIENTE',
                  ]"
                  >{{ labels[String(job.Estado)] || job.Estado }}</span
                >
              </td>
              <td>
                {{ job.Intentos }} / {{ job.MaxIntentos
                }}<small class="cell-caption">{{
                  job.HTTPStatus
                    ? `HTTP ${job.HTTPStatus}`
                    : "Sin respuesta HTTP"
                }}</small>
              </td>
              <td class="align-right">
                {{
                  job.CantidadRegistros === null
                    ? "—"
                    : number(Number(job.CantidadRegistros))
                }}
              </td>
              <td>
                <button
                  v-if="complete.includes(String(job.Estado))"
                  class="row-action"
                  @click="openRecords(job)"
                >
                  Ver datos ↗</button
                ><button
                  v-if="job.Estado === 'Fallido' && auth.canWrite"
                  class="row-action"
                  :disabled="acting === job.Id"
                  @click="action(job)"
                >
                  Reintentar ↻</button
                ><button
                  v-if="complete.includes(String(job.Estado)) && auth.isAdmin"
                  class="row-action"
                  :disabled="acting === job.Id"
                  @click="action(job, true)"
                >
                  Forzar revisión ↻</button
                ><RouterLink
                  class="row-action"
                  :to="{
                    name: 'ejecucion',
                    query: { trabajo_id: Number(job.Id) },
                  }"
                  >Ver intentos ↗</RouterLink
                ><button
                  v-if="job.DocumentoId"
                  class="row-action"
                  @click="inspectedDocument = Number(job.DocumentoId)"
                >
                  Inspeccionar respuesta ↗
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!jobs.length" id="empty-state" class="explorer-empty">
        {{
          !selected
            ? "Selecciona o crea una carga para ver su avance."
            : poll.loading.value
              ? "Consultando enlaces…"
              : "No hay enlaces con este estado."
        }}
      </div>
      <div class="table-footer">
        <span
          >Enlaces {{ jobs.length ? (cursors.length - 1) * 50 + 1 : 0 }}–{{
            (cursors.length - 1) * 50 + jobs.length
          }}</span
        >
        <div>
          <button
            class="pagination-button"
            :disabled="poll.loading.value || cursors.length === 1"
            @click="navigatePage(false)"
          >
            ← Anterior</button
          ><button
            class="pagination-button"
            :disabled="poll.loading.value || !hasNext"
            @click="navigatePage(true)"
          >
            Siguiente →
          </button>
        </div>
      </div>
    </div>
    <DetailDialog
      :open="!!recordJob"
      :title="`Registros del enlace · ${recordJob?.SecEjec || ''}`"
      @close="closeRecords"
      ><p v-if="recordsError" class="notice notice-error">{{ recordsError }}</p>
      <DataTable
        :rows="records"
        :columns="[
          'AnoEje',
          'MesEje',
          'SecEjec',
          'IdProyecto',
          'IdMeta',
          'PIM',
          'Devengado',
        ]"
        :busy="recordsLoading"
        empty="El documento completo no contiene registros."
        ><template #cell="{ row, column }">{{
          ["PIM", "Devengado"].includes(column)
            ? decimal(row[column])
            : row[column]
        }}</template></DataTable
      >
      <div class="dialog-footer">
        <span>Página {{ recordCursors.length }}</span>
        <div>
          <button
            class="pagination-button"
            :disabled="recordsLoading || recordCursors.length === 1"
            @click="recordPage(false)"
          >
            ← Anterior</button
          ><button
            class="pagination-button"
            :disabled="recordsLoading || !recordNext"
            @click="recordPage(true)"
          >
            Siguiente →
          </button>
        </div>
      </div></DetailDialog
    >
  </section>
</template>
