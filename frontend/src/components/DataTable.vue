<script setup lang="ts">
import type { DataRow } from "../types";
import { date, text } from "../services/format";
defineProps<{
  columns: string[];
  rows: DataRow[];
  labels?: Record<string, string>;
  busy?: boolean;
  empty?: string;
}>();
</script>

<template>
  <div
    class="table-scroll"
    tabindex="0"
    aria-label="Tabla de resultados, con desplazamiento horizontal"
  >
    <table :aria-busy="busy">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column" scope="col">
            {{ labels?.[column] || column }}
          </th>
          <th v-if="$slots.actions" scope="col">Acciones</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, index) in rows" :key="String(row.Id ?? index)">
          <td
            v-for="column in columns"
            :key="column"
            :class="{
              'wrap-value': [
                'Error',
                'Detalle',
                'URLSolicitada',
                'URL',
                'ErrorValidacion',
              ].includes(column),
            }"
          >
            <slot name="cell" :row="row" :column="column" :index="index">{{
              column.endsWith("UTC") ? date(row[column]) : text(row[column])
            }}</slot>
          </td>
          <td v-if="$slots.actions">
            <div class="table-actions">
              <slot name="actions" :row="row" :index="index" />
            </div>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-if="!rows.length" class="explorer-empty">
      {{
        busy ? "Consultando…" : empty || "No hay resultados para estos filtros."
      }}
    </p>
  </div>
</template>
