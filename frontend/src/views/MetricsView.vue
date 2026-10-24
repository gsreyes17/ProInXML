<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";
import PagedExplorer from "../components/PagedExplorer.vue";
import DataTable from "../components/DataTable.vue";
import DetailDialog from "../components/DetailDialog.vue";
import { usePolling } from "../composables/usePolling";
import { api, query } from "../services/api";
import { date, number, text } from "../services/format";
import type { DataRow } from "../types";

interface Phase {
  Campo: string;
  Nombre: string;
  Color: string;
  Muestras: number;
  PromedioMs: number | null;
  P95Ms: number | null;
  MaximoMs: number | null;
}
interface Metrics {
  resumen: DataRow;
  fases: Phase[];
  total_intento: { PromedioMs: number; P95Ms: number } | null;
  comparacion: DataRow[];
  lentos: DataRow[];
  intentos_sin_medicion: number;
  concurrencia_configurada: number;
  nota: string;
}
const route = useRoute();
const lote = ref(String(route.query.lote_id || ""));
const concurrency = ref("");
const state = ref("");
const batches = ref<{ LoteId: number; Nombre: string }[]>([]);
const result = ref<Metrics | null>(null);
const detail = ref<DataRow | null>(null);
const explorer = ref<InstanceType<typeof PagedExplorer> | null>(null);
const fixed = computed(() => {
  const values: Record<string, string | number> = {};
  if (lote.value) values.lote_id = Number(lote.value);
  if (concurrency.value) values.concurrencia = Number(concurrency.value);
  if (state.value) values.estado = state.value;
  return values;
});
let generation = 0;
const poll = usePolling(async (signal) => {
  const current = generation;
  const [list, data] = await Promise.all([
    api<typeof batches.value>("/metricas/lotes", { signal }),
    api<Metrics>(`/metricas/resumen?${query(fixed.value)}`, { signal }),
  ]);
  if (current !== generation) return;
  batches.value = list;
  result.value = data;
  await explorer.value?.refresh();
});
watch([lote, concurrency, state], () => {
  generation++;
  result.value = null;
  void poll.restart();
});
const highest = computed(() =>
  Math.max(1, ...(result.value?.fases.map((p) => p.PromedioMs ?? 0) || [])),
);
const bottleneck = computed(
  () =>
    [...(result.value?.fases || [])]
      .filter((p) => p.Muestras > 0)
      .sort((a, b) => (b.PromedioMs || 0) - (a.PromedioMs || 0))[0],
);
function duration(value: unknown) {
  if (value === null || value === undefined) return "—";
  const ms = Number(value);
  return ms >= 1000
    ? `${(ms / 1000).toLocaleString("es-PE", { maximumFractionDigits: 2 })} s`
    : `${ms.toLocaleString("es-PE", { maximumFractionDigits: 3 })} ms`;
}
function rate(value: unknown) {
  return value === null || value === undefined
    ? "—"
    : Number(value).toLocaleString("es-PE", { maximumFractionDigits: 2 });
}
const labels = {
  IntentoId: "Intento",
  DocumentoId: "Documento",
  LoteId: "Lote",
  Concurrencia: "Concurrencia",
  TotalMs: "Total",
  DescargaMs: "Descarga",
  EsperaSqlMs: "Espera SQL",
  NormalizacionMs: "Normalización",
  RegistrosInsertados: "Filas nuevas",
  RegistrosLeidos: "Filas leídas",
  HttpStatus: "HTTP",
};
</script>

<template>
  <section class="metrics-page">
    <form class="card filter-card" @submit.prevent="poll.refresh()">
      <div class="filter-grid">
        <label
          >Lote<select id="metrics-batch" v-model="lote">
            <option value="">Todos los lotes medidos</option>
            <option
              v-for="batch in batches"
              :key="batch.LoteId"
              :value="String(batch.LoteId)"
            >
              #{{ batch.LoteId }} · {{ batch.Nombre }}
            </option>
          </select></label
        >
        <label
          >Concurrencia registrada<select
            id="metrics-concurrency"
            v-model="concurrency"
          >
            <option value="">Todas</option>
            <option v-for="n in 20" :key="n" :value="String(n)">
              {{ n }} descargas
            </option>
          </select></label
        >
        <label
          >Resultado<select id="metrics-state" v-model="state">
            <option value="">Todos</option>
            <option
              v-for="s in ['EnCurso', 'Completado', 'Error', 'Interrumpido']"
              :key="s"
              :value="s"
            >
              {{ s }}
            </option>
          </select></label
        >
      </div>
      <div class="filter-actions">
        <span>Actualización cada 3 segundos · tiempos por intento</span
        ><button class="button button-primary" :disabled="poll.loading.value">
          Actualizar ↻
        </button>
      </div>
    </form>
    <p v-if="poll.error.value" class="notice notice-error" role="alert">
      {{ poll.error.value }}
    </p>
    <p v-if="result?.intentos_sin_medicion" class="notice" id="metrics-legacy">
      Hay {{ number(result.intentos_sin_medicion) }} intentos anteriores sin
      desglose. Sus tiempos por etapa no se reconstruyen; se medirán las nuevas
      descargas.
    </p>
    <template v-if="result">
      <div class="stats metrics-stats">
        <div class="stat">
          <span class="stat-label">Intentos con métricas</span
          ><strong id="metrics-count" class="stat-number">{{
            number(Number(result.resumen.Intentos))
          }}</strong
          ><span class="stat-caption"
            >{{ result.resumen.EnCurso }} en curso ·
            {{ result.resumen.Errores }} errores ·
            {{ result.resumen.Interrumpidos }} interrumpidos</span
          >
        </div>
        <div class="stat">
          <span class="stat-label">XML completados / minuto</span
          ><strong class="stat-number">{{
            rate(result.resumen.XmlPorMinuto)
          }}</strong
          ><span class="stat-caption"
            >{{ number(Number(result.resumen.Completados)) }} intentos
            completados</span
          >
        </div>
        <div class="stat">
          <span class="stat-label">Filas nuevas / segundo</span
          ><strong class="stat-number">{{
            rate(result.resumen.FilasPorSegundo)
          }}</strong
          ><span class="stat-caption"
            >{{ number(Number(result.resumen.FilasInsertadas)) }} insertadas ·
            {{
              number(Number(result.resumen.FilasReutilizadas))
            }}
            reutilizadas</span
          >
        </div>
        <div class="stat">
          <span class="stat-label">Tiempo total · P95</span
          ><strong class="stat-number metric-time">{{
            duration(result.total_intento?.P95Ms)
          }}</strong
          ><span class="stat-caption"
            >Promedio {{ duration(result.total_intento?.PromedioMs) }}</span
          >
        </div>
      </div>
      <div class="card metrics-phases">
        <div class="table-heading">
          <div>
            <h2>En qué se consume el tiempo</h2>
            <p>
              Promedio por intento que alcanzó cada etapa · P95: el 95 % termina
              en ese tiempo o menos
            </p>
          </div>
        </div>
        <p
          v-if="!Number(result.resumen.Intentos)"
          id="metrics-empty"
          class="explorer-empty"
        >
          Todavía no hay mediciones con estos filtros. Registra nuevas URLs; las
          consultas YaCargada no generan descargas ni tiempos nuevos.
        </p>
        <div v-else class="phase-list">
          <div
            v-for="phase in result.fases"
            :key="phase.Campo"
            class="phase-row"
          >
            <div class="phase-label">
              <strong>{{ phase.Nombre }}</strong
              ><span>{{ number(phase.Muestras) }} muestras</span>
            </div>
            <div class="phase-track" aria-hidden="true">
              <div
                :style="{
                  width: `${phase.PromedioMs === null ? 0 : Math.max(0.5, (phase.PromedioMs / highest) * 100)}%`,
                  background: phase.Color,
                }"
              />
            </div>
            <div class="phase-value">
              <strong>{{ duration(phase.PromedioMs) }}</strong
              ><span>P95 {{ duration(phase.P95Ms) }}</span>
            </div>
          </div>
        </div>
        <p v-if="bottleneck" id="metrics-bottleneck" class="metrics-insight">
          Mayor promedio observado: <strong>{{ bottleneck.Nombre }}</strong
          >.
          {{
            bottleneck.Campo === "EsperaSqlMs"
              ? "Los workers esperan los bloqueos de persistencia; aumentar descargas puede aumentar esta espera."
              : "Compara documentos de tamaños similares antes de atribuir la diferencia a la concurrencia."
          }}
        </p>
      </div>
      <div class="card explorer-card">
        <div class="table-heading">
          <div>
            <h2>Comparación de concurrencia</h2>
            <p>
              El valor se captura desde el worker en cada intento. Compara
              muestras equivalentes y ten en cuenta los reintentos.
            </p>
          </div>
        </div>
        <DataTable
          :rows="result.comparacion"
          :columns="[
            'Concurrencia',
            'Intentos',
            'Completados',
            'Fallos',
            'FilasInsertadas',
            'XmlPorMinuto',
            'FilasPorSegundo',
            'PromedioMs',
          ]"
          :labels="{
            FilasInsertadas: 'Filas nuevas',
            XmlPorMinuto: 'XML/min',
            FilasPorSegundo: 'Filas/s',
            PromedioMs: 'Total promedio',
          }"
          ><template #cell="{ row, column }">{{
            column.endsWith("Ms")
              ? duration(row[column])
              : column.includes("Por")
                ? rate(row[column])
                : text(row[column])
          }}</template></DataTable
        >
      </div>
      <div v-if="result.lentos.length" class="card explorer-card">
        <div class="table-heading">
          <div>
            <h2>Los cinco intentos más lentos</h2>
            <p>Incluye intentos fallidos según el filtro seleccionado.</p>
          </div>
        </div>
        <DataTable
          :rows="result.lentos"
          :columns="[
            'IntentoId',
            'LoteId',
            'Estado',
            'Concurrencia',
            'RegistrosLeidos',
            'TotalMs',
          ]"
          :labels="labels"
          ><template #cell="{ row, column }">{{
            column.endsWith("Ms") ? duration(row[column]) : text(row[column])
          }}</template></DataTable
        >
      </div>
      <p class="subtle metrics-note">
        Configuración actual de la API:
        {{ result.concurrencia_configurada }} descargas. Las métricas reflejan
        la configuración del worker que ejecutó cada intento. El rendimiento usa
        la ventana de tiempo completa, incluidas esperas entre intentos. Las
        fases sin ejecutar aparecen como —. Se conservan las métricas al limpiar
        las cargas.
      </p>
    </template>
    <PagedExplorer
      ref="explorer"
      path="/metricas/intentos"
      title="Mediciones por intento"
      prefix="metrics-attempts"
      :fixed="fixed"
      :columns="[
        'IntentoId',
        'LoteId',
        'Estado',
        'Concurrencia',
        'HttpStatus',
        'RegistrosInsertados',
        'DescargaMs',
        'EsperaSqlMs',
        'NormalizacionMs',
        'TotalMs',
      ]"
      :labels="labels"
      ><template #cell="{ row, column }">{{
        column.endsWith("Ms") ? duration(row[column]) : text(row[column])
      }}</template
      ><template #actions="{ row }"
        ><button class="row-action" @click="detail = row">
          Ver medición ↗
        </button></template
      ></PagedExplorer
    >
    <DetailDialog
      :open="!!detail"
      :title="`Medición del intento #${detail?.IntentoId || ''}`"
      @close="detail = null"
      ><p v-if="detail?.Error" class="notice notice-error">
        {{ detail.Error }}
      </p>
      <dl v-if="detail" class="record-fields">
        <div v-for="(value, key) in detail" :key="key">
          <dt>{{ key }}</dt>
          <dd>
            {{
              String(key).endsWith("Ms")
                ? duration(value)
                : String(key).endsWith("Utc")
                  ? date(value)
                  : text(value)
            }}
          </dd>
        </div>
      </dl></DetailDialog
    >
  </section>
</template>
