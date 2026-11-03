<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";
const auth = useAuthStore();
const router = useRouter();
const route = useRoute();
const username = ref("");
const password = ref("");
const submitting = ref(false);
const error = ref(
  route.query.conexion
    ? "No se pudo comprobar la sesión. Revisa la conexión a SQL Server e inténtalo de nuevo."
    : route.query.expirada
      ? "La sesión terminó después de una hora. Inicia sesión de nuevo."
      : "",
);
async function login() {
  submitting.value = true;
  try {
    await auth.login(username.value, password.value);
    password.value = "";
    const redirect = String(route.query.redirect || "");
    await router.replace(
      redirect.startsWith("/") &&
        !redirect.startsWith("//") &&
        redirect !== "/ui/login"
        ? redirect
        : auth.canWrite
          ? "/"
          : "/ui/seguimiento",
    );
  } catch (failure) {
    error.value = (failure as Error).message;
  } finally {
    submitting.value = false;
  }
}
</script>
<template>
  <section class="login-page">
    <div class="card login-card">
      <div class="login-brand">
        <span class="brand-icon" aria-hidden="true">&lt;&gt;</span> ProInXML
        <span class="login-version">1.0</span>
      </div>
      <div class="eyebrow">TU ESPACIO DE INTEGRACIÓN</div>
      <h1>Inicia sesión</h1>
      <p class="card-intro">Accede a tus cargas, datos y trazabilidad.</p>
      <p v-if="error" class="notice notice-error" role="alert" id="login-error">
        {{ error }}
      </p>
      <form id="login-form" @submit.prevent="login">
        <label for="login-user">Usuario</label
        ><input
          id="login-user"
          v-model="username"
          autocomplete="username"
          required
          maxlength="80"
        /><label for="login-password">Contraseña</label
        ><input
          id="login-password"
          v-model="password"
          type="password"
          autocomplete="current-password"
          required
          maxlength="256"
        /><button
          id="login-submit"
          class="button button-primary"
          :disabled="submitting"
        >
          {{ submitting ? "Entrando…" : "Entrar →" }}
        </button>
      </form>
      <p class="subtle">Usa la cuenta creada para este proyecto.</p>
    </div>
  </section>
</template>
