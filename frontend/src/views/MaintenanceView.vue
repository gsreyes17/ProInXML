<script setup lang="ts">
import { computed, ref } from "vue";
import PagedExplorer from "../components/PagedExplorer.vue";
import DetailDialog from "../components/DetailDialog.vue";
import DocumentDetail from "../components/DocumentDetail.vue";
import { api } from "../services/api";
import { number } from "../services/format";
import type { DataRow } from "../types";

interface Preview {
  alcance: "documento" | "todo";
  documento: DataRow | null;
  conteos: Record<string, number>;
  revision: string;
  confirmacion: string;
  conserva: string[];
  nota: string;
  trabajos_en_curso: number;
}
const explorer = ref<InstanceType<typeof PagedExplorer> | null>(null);
const documentId = ref<number | null>(null);
const preview = ref<Preview | null>(null);
const confirmation = ref("");
const reason = ref("");
const busy = ref(false);
const normalizingId = ref<number | null>(null);
const error = ref("");
const message = ref("");
const filters = [
  { key: "documento_id", label: "Documento", type: "number" },
  { key: "ano", label: "Año", type: "number" },
  { key: "sec_ejec", label: "Ejecutora", type: "number" },
  { key: "http_status", label: "HTTP", type: "number" },
  {
    key: "calidad",
    label: "Calidad",
    options: [
      { value: "validos", label: "Válidos" },
      { value: "rechazados", label: "Rechazados por validación" },
      { value: "con_observaciones", label: "Con observaciones" },
      { value: "errores_http", label: "Errores HTTP" },
    ],
  },
];
const labels: Record<string, string> = {
  documentos: "Documentos",
  registros_xml: "Filas XML",
  registros_modelo: "Filas del modelo",
  observaciones: "Observaciones",
  trabajos: "Trabajos",
  intentos: "Intentos",
  consultas: "Consultas",
  lotes: "Lotes",
};
const canDelete = computed(
  () =>
    preview.value &&
    !busy.value &&
    !preview.value.trabajos_en_curso &&
    confirmation.value === preview.value.confirmacion &&
    reason.value.trim().length >= 5,
);
const deletionHint = computed(() => {
  if (busy.value)
    return "Eliminando los datos. Espera a que finalice la operación.";
  if (preview.value?.trabajos_en_curso)
    return "Espera a que terminen los trabajos y solicita otra vista previa.";
  if (reason.value.trim().length < 5)
    return "Para habilitar el borrado, indica un motivo de al menos 5 caracteres.";
  if (confirmation.value !== preview.value?.confirmacion)
    return "Escribe la frase de confirmación exactamente como aparece arriba.";
  return "Confirmación completa. Puedes eliminar los datos revisados.";
});
async function prepare(id?: number) {
  busy.value = true;
  error.value = "";
  message.value = "";
  confirmation.value = "";
  reason.value = "";
  try {
    preview.value = await api<Preview>("/mantenimiento/vista-previa", {
      method: "POST",
      body: JSON.stringify({
        alcance: id ? "documento" : "todo",
        documento_id: id ?? null,
      }),
    });
  } catch (failure) {
    error.value = (failure as Error).message;
  } finally {
    busy.value = false;
  }
}
async function remove() {
  if (!canDelete.value || !preview.value) return;
  busy.value = true;
  error.value = "";
  const scope = preview.value;
  try {
    const result = await api<{
      mensaje: string;
      conteos?: Record<string, number>;
    }>("/mantenimiento/eliminar", {
      method: "POST",
      body: JSON.stringify({
        alcance: scope.alcance,
        documento_id: scope.documento?.Id ?? null,
        revision: scope.revision,
        confirmacion: confirmation.value,
        motivo: reason.value.trim(),
      }),
    });
    preview.value = null;
    message.value = result.conteos
      ? `${result.mensaje} Se eliminaron ${number(result.conteos.documentos || 0)} documentos, ${number(result.conteos.registros_xml || 0)} filas XML y ${number(result.conteos.registros_modelo || 0)} filas del modelo. Usuarios, configuración, auditoría y métricas se conservan.`
      : `${result.mensaje} La auditoría y las métricas se han conservado.`;
    await explorer.value?.reload();
  } catch (failure) {
    error.value = (failure as Error).message;
    // Hace falta revisar otra vista previa antes de volver a intentar.
    preview.value = null;
  } finally {
    busy.value = false;
  }
}
async function rebuild(id: number) {
  busy.value = true;
  normalizingId.value = id;
  error.value = "";
  message.value = "";
  try {
    const result = await api<{
      filas_crudas: number;
      filas_modelo_antes: number;
      filas_modelo_despues: number;
    }>("/mantenimiento/normalizar", {
      method: "POST",
      body: JSON.stringify({ documento_id: id }),
    });
    message.value = `Documento #${id}: ${number(result.filas_crudas)} filas XML conservadas y ${number(result.filas_modelo_despues)} filas en el modelo (antes: ${number(result.filas_modelo_antes)}). La operación quedó registrada en auditoría.`;
    await explorer.value?.reload();
  } catch (failure) {
    error.value = (failure as Error).message;
  } finally {
    normalizingId.value = null;
    busy.value = false;
  }
}
</script>

<template>
  <section class="maintenance-page">
    <div class="card maintenance-intro">
      <div>
        <h2>Mantenimiento de datos</h2>
        <p>
          Reconstruye el modelo de un documento a partir de sus filas XML
          guardadas, sin volver a descargarlo ni cambiar el original. También
          puedes eliminar un documento o vaciar las cargas para repetir pruebas.
        </p>
        <p class="subtle">
          La eliminación es definitiva. El sistema no permite limpiar mientras
          existan trabajos en curso.
        </p>
      </div>
      <button
        id="reset-lab"
        class="button button-danger"
        :disabled="busy"
        @click="prepare()"
      >
        Vaciar todas las cargas
      </button>
    </div>
    <p v-if="message" id="maintenance-message" class="notice" role="status">
      {{ message }}
    </p>
    <p
      v-if="error"
      id="maintenance-error"
      class="notice notice-error"
      role="alert"
    >
      {{ error }}
    </p>
    <PagedExplorer
      ref="explorer"
      path="/documentos"
      title="Documentos recibidos"
      prefix="maintenance"
      :filters="filters"
      :columns="[
        'Id',
        'AnoEje',
        'SecEjec',
        'EstadoDocumento',
        'HTTPStatus',
        'RegistrosDetalle',
        'Observaciones',
        'Vigente',
        'ErrorValidacion',
      ]"
      :labels="{
        Id: 'Documento',
        AnoEje: 'Año',
        SecEjec: 'Ejecutora',
        EstadoDocumento: 'Estado',
        HTTPStatus: 'HTTP',
        RegistrosDetalle: 'Filas XML',
        Observaciones: 'Incidencias',
        Vigente: 'Actual',
        ErrorValidacion: 'Error',
      }"
    >
      <template #cell="{ row, column }">{{
        column === "Vigente"
          ? row[column]
            ? "Sí"
            : "No"
          : (row[column] ?? "—")
      }}</template>
      <template #actions="{ row }"
        ><button class="row-action" @click="documentId = Number(row.Id)">
          Inspeccionar ↗</button
        ><button
          class="row-action"
          :disabled="busy"
          @click="rebuild(Number(row.Id))"
        >
          {{
            normalizingId === Number(row.Id)
              ? "Reconstruyendo…"
              : "Reconstruir modelo"
          }}</button
        ><button
          class="row-action danger-text"
          :disabled="busy"
          @click="prepare(Number(row.Id))"
        >
          Eliminar documento
        </button></template
      >
    </PagedExplorer>
    <DocumentDetail :document-id="documentId" @close="documentId = null" />
    <DetailDialog
      :open="!!preview"
      :busy="busy"
      :title="
        preview?.alcance === 'todo'
          ? 'Vaciar todas las cargas'
          : `Eliminar documento #${preview?.documento?.Id}`
      "
      eyebrow="CONFIRMAR ELIMINACIÓN"
      @close="preview = null"
    >
      <template v-if="preview">
        <p class="notice notice-error">{{ preview.nota }}</p>
        <p v-if="preview.documento" class="document-url">
          {{ preview.documento.URL }}
        </p>
        <dl class="record-fields">
          <template v-for="(value, key) in preview.conteos" :key="key"
            ><div v-if="labels[key]">
              <dt>{{ labels[key] }}</dt>
              <dd>{{ number(value) }}</dd>
            </div></template
          >
        </dl>
        <p v-if="preview.alcance === 'documento'" class="subtle">
          Trabajos e intentos indican vínculos que se conservarán como
          historial. Solo se eliminan entidades del modelo que queden sin
          referencias.
        </p>
        <p>Se conserva: {{ preview.conserva.join(", ") }}.</p>
        <p
          v-if="preview.trabajos_en_curso"
          class="notice notice-error"
          role="alert"
        >
          Hay {{ preview.trabajos_en_curso }} trabajos en curso. Cierra esta
          ventana y vuelve a revisar cuando terminen.
        </p>
        <form class="maintenance-form" @submit.prevent="remove">
          <label for="delete-reason"
            >Motivo de la limpieza
            <span class="subtle"
              >Mínimo 5 caracteres; quedará registrado en auditoría.</span
            ><textarea
              id="delete-reason"
              v-model="reason"
              minlength="5"
              maxlength="500"
              required
              :disabled="busy"
              placeholder="Por ejemplo: repetir la prueba del laboratorio"
            />
          </label>
          <label for="delete-confirmation"
            >Escribe <strong>{{ preview.confirmacion }}</strong
            ><input
              id="delete-confirmation"
              v-model="confirmation"
              autocomplete="off"
              required
              :disabled="busy"
          /></label>
          <p id="delete-requirements" class="deletion-hint" role="status">
            {{ deletionHint }}
          </p>
          <div class="dialog-footer">
            <button
              class="button button-outline"
              type="button"
              :disabled="busy"
              @click="preview = null"
            >
              Cancelar</button
            ><button
              id="confirm-delete"
              aria-describedby="delete-requirements"
              class="button button-danger"
              type="submit"
              :disabled="!canDelete"
            >
              {{ busy ? "Eliminando…" : "Eliminar definitivamente" }}
            </button>
          </div>
        </form>
      </template>
    </DetailDialog>
  </section>
</template>
