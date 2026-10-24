<script setup lang="ts">
import { computed, ref } from "vue";
import { RouterLink, useRouter } from "vue-router";
import { api } from "../services/api";
import { date, number } from "../services/format";
import { usePolling } from "../composables/usePolling";
import type { BatchResult, DataRow } from "../types";

const router = useRouter();
const input = ref("");
const urls = computed(() =>
  input.value
    .split(/\r?\n/)
    .map((value) => value.trim())
    .filter(Boolean),
);
const batches = ref<DataRow[]>([]);
const submitting = ref(false);
const error = ref("");
const file = ref<File | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);
const activity = usePolling(async (signal) => {
  batches.value = await api<DataRow[]>("/lotes?limite=8", { signal });
});
function example() {
  input.value =
    "http://s3.mef.gob.pe/servicios/WSPCM/SG/gastopipsg-old.asmx/ObtenerDataGastoPIP_old_2?anoEje=2020&nivelGobierno=E&sec_ejec=3";
}
async function submit(excel = false) {
  error.value = "";
  if (excel && !file.value) {
    error.value = "Selecciona un archivo Excel.";
    return;
  }
  if (!excel && (!urls.value.length || urls.value.length > 1000)) {
    error.value = "Introduce de 1 a 1000 enlaces, uno por línea.";
    return;
  }
  submitting.value = true;
  try {
    let body: FormData | string;
    if (excel) {
      body = new FormData();
      body.append("file", file.value!);
    } else body = JSON.stringify({ urls: urls.value });
    const result = await api<BatchResult>("/lotes", { method: "POST", body });
    await router.push({
      name: "seguimiento",
      query: {
        lote: result.lote_id,
        nuevas: result.nuevas,
        ya_cargadas: result.ya_cargadas,
        duplicados: result.duplicados_omitidos,
      },
    });
  } catch (failure) {
    error.value = (failure as Error).message;
  } finally {
    submitting.value = false;
  }
}
</script>
<template>
  <section class="workspace">
    <div class="card upload-card">
      <form id="upload-form" @submit.prevent="submit(false)">
        <div class="section-number">01 <span>NUEVA CARGA</span></div>
        <h2>Todo empieza con un enlace.</h2>
        <p class="card-intro">
          Pega una o varias URLs del MEF para cargar sus datos.
        </p>
        <div class="input-heading">
          <label for="urls">Enlaces XML</label
          ><span id="url-count"
            >{{ number(urls.length) }}
            {{ urls.length === 1 ? "enlace" : "enlaces" }}</span
          >
        </div>
        <textarea
          id="urls"
          v-model="input"
          rows="7"
          spellcheck="false"
          placeholder="http://s3.mef.gob.pe/servicios/…"
          required
        ></textarea>
        <div class="input-helper">
          <span>Un enlace por línea · máximo 1.000</span>
          ><button
            id="example"
            type="button"
            class="text-button"
            @click="example"
          >
            Usar ejemplo ↗
          </button>
        </div>
        <div class="form-footer">
          <span class="subtle"
            >Los repetidos se omiten y las consultas válidas se
            reutilizan.</span
          ><button
            id="submit"
            class="button button-primary"
            :disabled="submitting || !urls.length"
          >
            {{ submitting ? "Registrando…" : "Cargar datos →" }}
          </button>
        </div>
      </form>
      <div class="excel-upload">
        <label for="excel-file">¿Tienes una lista en Excel?</label>
        <p class="subtle">
          URLs en la primera columna, con encabezado opcional y sin conteos
          esperados.
        </p>
        <input
          id="excel-file"
          ref="fileInput"
          type="file"
          accept=".xlsx"
          @change="file = fileInput?.files?.[0] || null"
        /><button
          id="excel-submit"
          class="button button-outline"
          :disabled="submitting"
          @click="submit(true)"
        >
          Importar Excel ↗
        </button>
      </div>
      <p
        v-if="error"
        id="form-message"
        class="notice notice-error"
        role="alert"
      >
        {{ error }}
      </p>
    </div>
    <aside class="card activity-card">
      <div class="section-number">02 <span>TU ACTIVIDAD</span></div>
      <div class="activity-heading">
        <h2>Cargas recientes</h2>
        <span class="small-tag">ÚLTIMAS 8</span>
      </div>
      <p class="card-intro">Retoma una carga para consultar su resultado.</p>
      <p v-if="activity.error.value" class="notice notice-error">
        {{ activity.error.value }}
      </p>
      <div class="history-list">
        <RouterLink
          v-for="batch in batches"
          :key="Number(batch.Id)"
          class="history-item"
          :to="{ name: 'seguimiento', query: { lote: Number(batch.Id) } }"
          ><span class="history-symbol">{{
            batch.Completados === batch.Total ? "✓" : "↥"
          }}</span
          ><span
            ><strong class="history-title">Carga #{{ batch.Id }}</strong
            ><span class="history-date">{{ date(batch.CreadoUtc) }}</span></span
          ><span class="history-count"
            >{{ batch.Completados }}/{{ batch.Total }} listas</span
          ></RouterLink
        >
        <p v-if="!batches.length" class="empty-history">
          {{
            activity.loading.value
              ? "Buscando cargas…"
              : "Tu primera integración aparecerá aquí."
          }}
        </p>
      </div>
      <div class="activity-tip">
        <span class="tip-icon">i</span>
        <p>
          Completado confirma que los datos ya están guardados. Ya cargada
          reutiliza una consulta válida.
        </p>
      </div>
    </aside>
  </section>
</template>
