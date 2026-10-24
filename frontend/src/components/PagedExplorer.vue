<script setup lang="ts">
import { computed, onUnmounted, reactive, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { api, query } from "../services/api";
import { number } from "../services/format";
import type { DataRow, PageData } from "../types";
import DataTable from "./DataTable.vue";

export interface Filter {
  key: string;
  label: string;
  type?: string;
  options?: { value: string; label: string }[];
}
const props = withDefaults(
  defineProps<{
    path: string;
    title: string;
    columns?: string[];
    labels?: Record<string, string>;
    filters?: Filter[];
    descending?: boolean;
    fixed?: Record<string, string | number | boolean>;
    prefix?: string;
  }>(),
  { descending: true, filters: () => [], prefix: "explorer" },
);
const emit = defineEmits<{ loaded: [result: PageData] }>();
const route = useRoute();
const fields = reactive<Record<string, string>>({});
const rows = ref<DataRow[]>([]);
const total = ref(0);
const columns = ref<string[]>([]);
const cursors = ref<(number | null)[]>([null]);
const next = ref<number | null>(null);
const loading = ref(false);
const error = ref("");
let controller: AbortController | null = null;
let generation = 0;
const pagination = computed(() =>
  rows.value.length
    ? `${number((cursors.value.length - 1) * 25 + 1)}–${number((cursors.value.length - 1) * 25 + rows.value.length)} de ${number(total.value)}`
    : "0 resultados",
);

function initialize() {
  Object.keys(fields).forEach((key) => delete fields[key]);
  props.filters.forEach((filter) => {
    fields[filter.key] = String(route.query[filter.key] || "");
  });
}
async function load(reset = false) {
  if (reset) cursors.value = [null];
  controller?.abort();
  controller = new AbortController();
  const signal = controller.signal;
  const current = ++generation;
  loading.value = true;
  try {
    const values: Record<string, string | number | boolean | null | undefined> =
      { ...fields, ...props.fixed, limite: 25 };
    props.filters.forEach((filter) => {
      if (filter.type === "date" && fields[filter.key]) {
        const value = new Date(`${fields[filter.key]}T00:00:00`);
        if (filter.key === "hasta") value.setDate(value.getDate() + 1);
        values[filter.key] = value.toISOString();
      }
    });
    values[props.descending ? "antes_de" : "despues_de"] = cursors.value.at(-1);
    const result = await api<PageData>(`${props.path}?${query(values)}`, {
      signal,
    });
    if (current !== generation) return;
    rows.value = result.registros;
    total.value = result.total;
    columns.value =
      props.columns ||
      result.columnas ||
      Object.keys(result.registros[0] || {});
    next.value = result.siguiente_cursor;
    error.value = "";
    emit("loaded", result);
  } catch (failure) {
    if (!signal.aborted && current === generation)
      error.value = (failure as Error).message;
  } finally {
    if (current === generation) loading.value = false;
  }
}
function clear() {
  props.filters.forEach((filter) => {
    fields[filter.key] = "";
  });
  void load(true);
}
function previous() {
  if (cursors.value.length > 1) {
    cursors.value.pop();
    void load();
  }
}
function following() {
  if (next.value !== null) {
    cursors.value.push(next.value);
    void load();
  }
}
watch(
  () => props.path,
  () => {
    initialize();
    void load(true);
  },
  { immediate: true },
);
watch(
  () => JSON.stringify(route.query),
  () => {
    initialize();
    void load(true);
  },
);
watch(
  () => JSON.stringify(props.fixed),
  () => {
    void load(true);
  },
);
onUnmounted(() => {
  generation++;
  controller?.abort();
});
defineExpose({ reload: () => load(true), refresh: () => load() });
</script>

<template>
  <section class="paged-explorer">
    <form
      v-if="filters.length || $slots.filters"
      class="card filter-card"
      :id="`${prefix}-filters`"
      @submit.prevent="load(true)"
    >
      <div class="filter-grid">
        <label v-for="filter in filters" :key="filter.key"
          >{{ filter.label
          }}<select
            v-if="filter.options"
            v-model="fields[filter.key]"
            :id="`${prefix}-${filter.key}`"
          >
            <option value="">Todos</option>
            <option
              v-for="option in filter.options"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option></select
          ><input
            v-else
            v-model="fields[filter.key]"
            :id="`${prefix}-${filter.key}`"
            :type="filter.type || 'text'"
            :min="filter.type === 'number' ? 1 : undefined" /></label
        ><slot name="filters" />
      </div>
      <div class="filter-actions">
        <span>Resultados paginados · consulta de solo lectura</span
        ><button class="button button-outline" type="button" @click="clear">
          Limpiar</button
        ><button
          class="button button-primary"
          :disabled="loading"
          type="submit"
        >
          Consultar →
        </button>
      </div>
    </form>
    <p v-if="error" class="notice notice-error" role="alert">{{ error }}</p>
    <div class="card explorer-card">
      <div class="table-heading">
        <div>
          <h2>{{ title }}</h2>
          <p :id="`${prefix}-description`">{{ number(total) }} resultados</p>
        </div>
        <slot name="heading" />
      </div>
      <DataTable
        :columns="columns"
        :rows="rows"
        :labels="labels"
        :busy="loading"
        ><template v-if="$slots.cell" #cell="data"
          ><slot name="cell" v-bind="data" /></template
        ><template v-if="$slots.actions" #actions="data"
          ><slot name="actions" v-bind="data" /></template
      ></DataTable>
      <div class="table-footer">
        <span :id="`${prefix}-pagination`">{{ pagination }}</span>
        <div>
          <button
            :id="`${prefix}-previous`"
            class="pagination-button"
            :disabled="loading || cursors.length === 1"
            @click="previous"
          >
            ← Anterior</button
          ><button
            :id="`${prefix}-next`"
            class="pagination-button"
            :disabled="loading || next === null"
            @click="following"
          >
            Siguiente →
          </button>
        </div>
      </div>
    </div>
  </section>
</template>
