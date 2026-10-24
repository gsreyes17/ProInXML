<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from "vue";
import { RouterLink, RouterView, useRoute, useRouter } from "vue-router";
import { useAuthStore } from "./stores/auth";
import { usePolling } from "./composables/usePolling";
import { api } from "./services/api";

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();
const sessionError = ref("");
const connected = ref(false);
const navigation = computed(() => [
  ...(auth.canWrite ? [{ path: "/", title: "Carga de datos", icon: "↥" }] : []),
  { path: "/ui/seguimiento", title: "Seguimiento", icon: "☷" },
  { path: "/ui/ejecucion", title: "Ejecución del servicio", icon: "◴" },
  { path: "/ui/metricas", title: "Métricas de carga", icon: "▥" },
  { path: "/ui/observaciones", title: "Observaciones", icon: "!" },
  ...(auth.isAdmin
    ? [{ path: "/ui/auditoria", title: "Auditoría", icon: "◷" }]
    : []),
  { path: "/ui/datos", title: "Registros XML", icon: "▤" },
  { path: "/ui/modelo", title: "Modelo 3FN", icon: "◇" },
  ...(auth.isAdmin
    ? [
        { path: "/ui/usuarios", title: "Usuarios", icon: "♙" },
        { path: "/ui/mantenimiento", title: "Mantenimiento", icon: "⚙" },
      ]
    : []),
]);
const health = usePolling(async (signal) => {
  if (!auth.user) return;
  try {
    await api("/salud", { signal });
    connected.value = true;
  } catch (error) {
    connected.value = false;
    throw error;
  }
}, 30000);
watch(
  () => auth.user,
  (user) => {
    if (user) void health.refresh();
  },
);
async function logout() {
  try {
    await auth.logout();
    await router.replace("/ui/login");
  } catch (error) {
    sessionError.value = (error as Error).message;
  }
}
function expired() {
  auth.clear();
  void router.replace({ name: "login", query: { redirect: route.fullPath } });
}
window.addEventListener("session-expired", expired);
onUnmounted(() => window.removeEventListener("session-expired", expired));
</script>

<template>
  <div :class="['app-shell', { 'login-screen': route.name === 'login' }]">
    <a class="skip-link" href="#contenido">Saltar al contenido</a>
    <aside
      v-if="route.name !== 'login'"
      class="sidebar"
      aria-label="Navegación principal"
    >
      <RouterLink class="brand" :to="auth.canWrite ? '/' : '/ui/seguimiento'"
        ><span class="brand-icon">&lt;/&gt;</span
        ><span
          >ProIn<span class="brand-light">XML</span
          ><small>INTEGRACIÓN DE DATOS</small></span
        ></RouterLink
      >
      <div class="nav-label">ESPACIO DE TRABAJO</div>
      <nav class="primary-nav" aria-label="Pantallas">
        <RouterLink
          v-for="item in navigation"
          :key="item.path"
          class="nav-item"
          active-class="selected"
          :to="item.path"
          ><span aria-hidden="true">{{ item.icon }}</span
          >{{ item.title }}</RouterLink
        >
      </nav>     
      <div class="sidebar-footer">
        <span class="environment-dot"></span
        ><span>Entorno local</span
        ><a
          href="/docs"
          target="_blank"
          rel="noopener"
          aria-label="Documentación de la API"
          >↗</a
        >
      </div>
    </aside>
    <main id="contenido">
      <template v-if="route.name !== 'login'">
        <div class="session-bar">
          <span id="session-name"
            >{{ auth.user?.NombreUsuario }} · {{ auth.user?.Rol }}</span
          ><button id="logout" class="text-button" @click="logout">
            Cerrar sesión ↗
          </button>
        </div>
        <p v-if="sessionError" class="notice notice-error" role="alert">
          {{ sessionError }}
        </p>
        <header class="page-header">
          <div>
            <div class="eyebrow">INTEGRACIÓN / MEF</div>
            <h1>{{ route.meta.title }}<span>.</span></h1>
            <p>{{ route.meta.description }}</p>
          </div>
          <div
            :class="['connection', connected ? 'connected' : 'disconnected']"
            role="status"
          >
            <span class="connection-dot"></span
            ><span id="connection-text">{{
              connected
                ? "Base de datos conectada"
                : health.loading.value
                  ? "Comprobando conexión"
                  : "Sin conexión a la base"
            }}</span>
          </div>
        </header>
      </template>
      <RouterView v-slot="{ Component, route: current }"
        ><component :is="Component" :key="String(current.name)"
      /></RouterView>
    </main>
  </div>
</template>
