<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import PagedExplorer from "../components/PagedExplorer.vue";
import DetailDialog from "../components/DetailDialog.vue";
import { api } from "../services/api";
import { text } from "../services/format";
import type { DataRow, ModelDefinition } from "../types";
const route = useRoute(),
  router = useRouter();
const definitions = ref<ModelDefinition[]>([]);
const error = ref("");
const selected = computed(
  () =>
    definitions.value.find((item) => item.tabla === route.query.tabla) ||
    definitions.value.find((item) => item.tabla === "Gasto"),
);
const groups = computed(() => [
  ...new Set(definitions.value.map((item) => item.grupo)),
]);
const relations = computed(() =>
  Object.fromEntries(
    (selected.value?.relaciones || []).map((item) => [
      item.columna,
      item.tabla,
    ]),
  ),
);
const detail = ref<DataRow | null>(null);
onMounted(async () => {
  try {
    definitions.value = (
      await api<{ tablas: ModelDefinition[] }>("/modelo/tablas")
    ).tablas;
  } catch (failure) {
    error.value = (failure as Error).message;
  }
});
function select(table: string, id?: number) {
  void router.push({
    name: "modelo",
    query: { tabla: table, ...(id ? { registro_id: id } : {}) },
  });
}
</script>
<template>
  <div class="model-intro card">
    <span class="model-symbol">◇</span>
    <div>
      <h2>Los mismos datos, organizados por entidad.</h2>
      <p>
        Recorre claves y relaciones sin perder el registro de origen. Los
        códigos conservan su contexto; los maestros oficiales pueden
        incorporarse después.
      </p>
    </div>
    <span class="small-tag">30 TABLAS RELACIONADAS</span>
  </div>
  <p v-if="error" class="notice notice-error" role="alert">{{ error }}</p>
  <div v-if="selected" class="model-layout">
    <aside class="card model-directory">
      <label for="model-select">Explorar tabla</label
      ><select
        id="model-select"
        :value="selected.tabla"
        @change="select(($event.target as HTMLSelectElement).value)"
      >
        <optgroup v-for="group in groups" :key="group" :label="group">
          <option
            v-for="item in definitions.filter((item) => item.grupo === group)"
            :key="item.tabla"
            :value="item.tabla"
          >
            {{ item.nombre }}
          </option>
        </optgroup>
      </select>
      <div class="model-directory-list">
        <details
          v-for="group in groups"
          :key="group"
          class="entity-group"
          :open="selected.grupo === group"
        >
          <summary>{{ group }}</summary>
          <button
            v-for="item in definitions.filter((item) => item.grupo === group)"
            :key="item.tabla"
            :class="[
              'entity-button',
              { active: selected.tabla === item.tabla },
            ]"
            :aria-pressed="selected.tabla === item.tabla"
            @click="select(item.tabla)"
          >
            {{ item.nombre }}
          </button>
        </details>
      </div>
    </aside>
    <div class="model-content">
      <div class="relation-list">
        <span
          v-for="relation in selected.relaciones"
          :key="relation.columna"
          class="relation-chip"
          >{{ relation.columna }} → {{ relation.tabla }}.Id</span
        ><button
          v-if="route.query.registro_id"
          class="text-button"
          @click="select(selected.tabla)"
        >
          Quitar filtro de relación
        </button>
      </div>
      <PagedExplorer
        :key="selected.tabla + String(route.query.registro_id || '')"
        :path="`/modelo/tablas/${selected.tabla}`"
        :title="selected.nombre"
        :columns="selected.columnas"
        :filters="[
          { key: 'registro_id', label: 'Registro', type: 'number' },
          { key: 'buscar', label: 'Buscar código o valor' },
        ]"
        :descending="false"
        prefix="model"
        ><template #cell="{ row, column }"
          ><RouterLink
            v-if="relations[column] === 'XML'"
            class="fk-link"
            :to="{ name: 'datos', query: { registro_id: Number(row[column]) } }"
            >{{ row[column] }} ↗</RouterLink
          ><button
            v-else-if="relations[column] && row[column] !== null"
            class="fk-link"
            :aria-label="`${relations[column]} #${row[column]}`"
            @click="select(relations[column]!, Number(row[column]))"
          >
            {{ row[column] }} ↗</button
          ><button
            v-else-if="column === 'Id'"
            class="row-action"
            @click="detail = row"
          >
            #{{ row.Id }}</button
          ><template v-else>{{ text(row[column]) }}</template></template
        ></PagedExplorer
      >
    </div>
  </div>
  <DetailDialog
    :open="!!detail"
    :title="`${selected?.nombre || 'Registro'} #${detail?.Id || ''}`"
    @close="detail = null"
    ><dl v-if="detail" class="record-fields">
      <div v-for="(value, field) in detail" :key="field">
        <dt>{{ field }}</dt>
        <dd>{{ text(value) }}</dd>
      </div>
    </dl></DetailDialog
  >
</template>
