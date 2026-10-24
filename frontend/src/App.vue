<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from "vue";
import { RouterLink, RouterView, useRoute, useRouter } from "vue-router";
import { useAuthStore } from "./stores/auth";
import { usePolling } from "./composables/usePolling";
import { api } from "./services/api";
import NavIcon from "./components/NavIcon.vue";

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();
const sessionError = ref("");
const connected = ref(false);
const menuOpen = ref(false);
const navigation = computed(() => [
  {
    title: "Procesamiento",
    description: "Cargas, estados y rendimiento",
    items: [
      ...(auth.canWrite
        ? [{ path: "/", title: "Carga de datos", icon: "upload" }]
        : []),
      { path: "/ui/seguimiento", title: "Seguimiento", icon: "tracking" },
      {
        path: "/ui/ejecucion",
        title: "Ejecución del servicio",
        icon: "attempts",
      },
      { path: "/ui/metricas", title: "Métricas de carga", icon: "metrics" },
    ],
  },
  {
    title: "Consultas",
    description: "Información y calidad de datos",
    items: [
      { path: "/ui/datos", title: "Registros XML", icon: "xml" },
      { path: "/ui/modelo", title: "Modelo 3FN", icon: "model" },
      { path: "/ui/observaciones", title: "Observaciones", icon: "quality" },
    ],
  },
  ...(auth.isAdmin
    ? [
        {
          title: "Administración",
          description: "Auditoría y configuración",
          items: [
            { path: "/ui/auditoria", title: "Auditoría", icon: "audit" },
            { path: "/ui/usuarios", title: "Usuarios", icon: "users" },
            {
              path: "/ui/mantenimiento",
              title: "Mantenimiento",
              icon: "maintenance",
            },
          ],
        },
      ]
    : []),
]);
const section = computed(
  () =>
    navigation.value.find((group) =>
      group.items.some((item) => item.path === route.path),
    )?.title || "Procesamiento",
);
watch(
  () => route.fullPath,
  () => {
    menuOpen.value = false;
  },
);
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
      <div class="sidebar-brand">
        <RouterLink class="brand" :to="auth.canWrite ? '/' : '/ui/seguimiento'">
          <span class="brand-icon" aria-hidden="true">&lt;/&gt;</span>
          <span
            >ProIn<span class="brand-light">XML</span
            ><small>INTEGRACIÓN DE DATOS</small></span
          >
        </RouterLink>
        <button
          class="menu-toggle"
          aria-controls="workspace-navigation"
          :aria-expanded="menuOpen"
          @click="menuOpen = !menuOpen"
        >
          {{ menuOpen ? "Cerrar menú" : "Menú" }}
          <span aria-hidden="true">{{ menuOpen ? "×" : "☰" }}</span>
        </button>
      </div>
      <nav
        id="workspace-navigation"
        :class="['primary-nav', { 'menu-open': menuOpen }]"
        aria-label="Pantallas"
        @keydown.esc="menuOpen = false"
      >
        <section
          v-for="group in navigation"
          :key="group.title"
          class="nav-group"
          :aria-label="group.title"
        >
          <div class="nav-label">{{ group.title }}</div>
          <RouterLink
            v-for="item in group.items"
            :key="item.path"
            class="nav-item"
            active-class="selected"
            :to="item.path"
            @click="menuOpen = false"
          >
            <NavIcon :name="item.icon" /><span>{{ item.title }}</span>
          </RouterLink>
        </section>
      </nav>
      <div class="sidebar-footer">
        <span class="version-tag">v1.0</span>
        <a
          href="/docs"
          target="_blank"
          rel="noopener"
          aria-label="Documentación de la API"
          >Documentación API</a
        >
      </div>
    </aside>
    <main id="contenido">
      <template v-if="route.name !== 'login'">
        <div class="session-bar">
          <span id="session-name"
            >{{ auth.user?.NombreUsuario }} · {{ auth.user?.Rol }}</span
          ><button id="logout" class="text-button" @click="logout">
            Cerrar sesión
          </button>
        </div>
        <p v-if="sessionError" class="notice notice-error" role="alert">
          {{ sessionError }}
        </p>
        <header class="page-header">
          <div>
            <div class="eyebrow">
              <span>ESPACIO DE TRABAJO</span><span aria-hidden="true">/</span
              >{{ section }}
            </div>
            <h1>{{ route.meta.title }}</h1>
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
