<script setup lang="ts">
import { reactive, ref } from "vue";
import PagedExplorer from "../components/PagedExplorer.vue";
import { api } from "../services/api";
import type { DataRow, Role } from "../types";
const explorer = ref<InstanceType<typeof PagedExplorer> | null>(null);
const form = reactive({
  id: null as number | null,
  usuario: "",
  nombre: "",
  contrasena: "",
  rol: "Consulta" as Role,
  activo: true,
});
const error = ref(""),
  message = ref(""),
  saving = ref(false);
function reset() {
  Object.assign(form, {
    id: null,
    usuario: "",
    nombre: "",
    contrasena: "",
    rol: "Consulta",
    activo: true,
  });
  message.value = "";
  error.value = "";
}
function edit(row: DataRow) {
  if (row.NombreUsuario === "sistema") {
    error.value = "La identidad sistema está reservada al worker.";
    return;
  }
  Object.assign(form, {
    id: Number(row.Id),
    usuario: String(row.NombreUsuario),
    nombre: String(row.NombreCompleto),
    contrasena: "",
    rol: row.Rol,
    activo: Boolean(row.Activo),
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}
async function save() {
  saving.value = true;
  error.value = "";
  message.value = "";
  try {
    await api("/usuarios", {
      method: "POST",
      body: JSON.stringify({
        ...form,
        contrasena: form.contrasena || undefined,
      }),
    });
    form.contrasena = "";
    message.value =
      "Usuario guardado. Los cambios de cuenta cierran sus sesiones activas.";
    await explorer.value?.reload();
  } catch (failure) {
    error.value = (failure as Error).message;
  } finally {
    saving.value = false;
  }
}
</script>
<template>
  <form
    id="user-form"
    class="card filter-card user-form"
    @submit.prevent="save"
  >
    <h2>{{ form.id ? `Editar cuenta #${form.id}` : "Crear una cuenta" }}</h2>
    <div class="filter-grid">
      <label
        >Usuario<input
          id="user-usuario"
          v-model="form.usuario"
          required
          minlength="3"
          maxlength="80"
          pattern="[A-Za-z0-9_.-]+"
          autocomplete="off" /></label
      ><label
        >Nombre completo<input
          id="user-nombre"
          v-model="form.nombre"
          required
          maxlength="160" /></label
      ><label
        >Contraseña
        {{ form.id ? "(vacía para conservar)" : "(mínimo 10 caracteres)"
        }}<input
          id="user-contrasena"
          v-model="form.contrasena"
          type="password"
          autocomplete="new-password"
          :required="!form.id"
          minlength="10"
          maxlength="256" /></label
      ><label
        >Rol<select id="user-role" v-model="form.rol">
          <option>Consulta</option>
          <option>Operador</option>
          <option>Administrador</option>
        </select></label
      ><label class="checkbox-label"
        ><input id="user-active" v-model="form.activo" type="checkbox" /><span
          >Cuenta activa</span
        ></label
      >
    </div>
    <div class="filter-actions">
      <button class="button button-outline" type="button" @click="reset">
        Nueva cuenta</button
      ><button class="button button-primary" :disabled="saving">
        {{ saving ? "Guardando…" : "Guardar usuario →" }}
      </button>
    </div>
    <p v-if="error" class="notice notice-error" role="alert">{{ error }}</p>
    <p v-if="message" class="notice" role="status">{{ message }}</p>
  </form>
  <PagedExplorer
    ref="explorer"
    path="/usuarios"
    title="Cuentas del proyecto"
    prefix="users"
    :columns="[
      'Id',
      'NombreUsuario',
      'NombreCompleto',
      'Rol',
      'Activo',
      'CreadoUTC',
    ]"
    :descending="false"
    ><template #actions="{ row }"
      ><button
        v-if="row.NombreUsuario !== 'sistema'"
        class="row-action"
        @click="edit(row)"
      >
        Editar</button
      ><span v-else class="subtle">Proceso</span></template
    ></PagedExplorer
  >
</template>
