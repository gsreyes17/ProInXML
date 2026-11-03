<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
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
const sidebarCollapsed = ref(false);
const viewportWidth = ref(window.innerWidth);
const isCollapsed = computed(
  () => sidebarCollapsed.value && viewportWidth.value > 900,
);
const expandedGroup = ref("Procesamiento");
const now = ref(Date.now());
let clock: ReturnType<typeof setInterval> | undefined;
const navigation = computed(() => [
  {
    key: "procesamiento",
    title: "Procesamiento",
    icon: "processing",
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
    key: "consultas",
    title: "Consultas",
    icon: "queries",
    items: [
      { path: "/ui/datos", title: "Registros XML", icon: "xml" },
      { path: "/ui/modelo", title: "Modelo 3FN", icon: "model" },
      { path: "/ui/observaciones", title: "Observaciones", icon: "quality" },
    ],
  },
  ...(auth.isAdmin
    ? [
        {
          key: "administracion",
          title: "Administración",
          icon: "admin",
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
watch(section, (value) => (expandedGroup.value = value), { immediate: true });
const secondsLeft = computed(() =>
  auth.expiresAt === null
    ? null
    : Math.max(0, Math.ceil((auth.expiresAt - now.value) / 1000)),
);
const sessionTime = computed(() => {
  if (secondsLeft.value === null) return "--:--:--";
  const left = secondsLeft.value;
  return `${String(Math.floor(left / 3600)).padStart(2, "0")}:${String(Math.floor((left % 3600) / 60)).padStart(2, "0")}:${String(left % 60).padStart(2, "0")}`;
});
function toggleGroup(title: string) {
  if (isCollapsed.value) {
    sidebarCollapsed.value = false;
    expandedGroup.value = title;
    return;
  }
  expandedGroup.value = expandedGroup.value === title ? "" : title;
}
function tick() {
  now.value = Date.now();
  if (auth.user && auth.expiresAt !== null && now.value >= auth.expiresAt) {
    void api("/auth/logout", { method: "POST" }).catch(() => {});
    expired();
  }
}
onMounted(() => {
  clock = setInterval(tick, 1000);
  document.addEventListener("visibilitychange", tick);
  window.addEventListener("resize", updateViewport);
});
onUnmounted(() => {
  if (clock) clearInterval(clock);
  document.removeEventListener("visibilitychange", tick);
  window.removeEventListener("resize", updateViewport);
});
function updateViewport() {
  viewportWidth.value = window.innerWidth;
}
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
  if (!auth.user) return;
  auth.clear();
  void router.replace({ name: "login", query: { expirada: "1" } });
}
window.addEventListener("session-expired", expired);
onUnmounted(() => window.removeEventListener("session-expired", expired));
</script>

<template>
  <div
    :class="[
      'app-shell',
      {
        'login-screen': route.name === 'login',
        'sidebar-collapsed': isCollapsed,
      },
    ]"
  >
    <a class="skip-link" href="#contenido">Saltar al contenido</a>
    <aside
      v-if="route.name !== 'login'"
      class="sidebar"
      aria-label="Navegación principal"
    >
      <div class="sidebar-brand">
        <RouterLink
          class="brand"
          :to="auth.canWrite ? '/' : '/ui/seguimiento'"
          :aria-label="isCollapsed ? 'ProInXML, ir al inicio' : undefined"
        >
          <span class="brand-icon" aria-hidden="true">&lt;&gt;</span>
          <span v-if="!isCollapsed"
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
          <button
            class="nav-heading"
            type="button"
            :aria-expanded="!isCollapsed && expandedGroup === group.title"
            :aria-controls="`nav-${group.key}`"
            :aria-label="isCollapsed ? group.title : undefined"
            :title="isCollapsed ? group.title : undefined"
            @click="toggleGroup(group.title)"
          >
            <NavIcon :name="group.icon" />
            <span v-if="!isCollapsed" class="nav-heading-label">{{
              group.title
            }}</span>
            <span
              v-if="!isCollapsed"
              class="nav-chevron"
              aria-hidden="true"
            ></span>
          </button>
          <div
            v-show="!isCollapsed && expandedGroup === group.title"
            :id="`nav-${group.key}`"
            class="nav-items"
          >
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
          </div>
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
          <button
            class="sidebar-collapse"
            type="button"
            :aria-label="
              isCollapsed ? 'Expandir barra lateral' : 'Contraer barra lateral'
            "
            :title="isCollapsed ? 'Expandir menú' : 'Contraer menú'"
            :aria-expanded="!isCollapsed"
            aria-controls="workspace-navigation"
            @click="sidebarCollapsed = !sidebarCollapsed"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              aria-hidden="true"
            >
              <path
                :d="isCollapsed ? 'M4 7h16M4 12h16M4 17h16' : 'm15 5-7 7 7 7'"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
          </button>
          <span class="session-timer" aria-label="Tiempo restante de sesión">
            <strong>{{ sessionTime }}</strong>
          </span>
          <span id="session-name">{{ auth.user?.NombreUsuario }}</span>
          <button id="logout" class="text-button" @click="logout">
            <NavIcon name="power" />Salir
          </button>
        </div>
        <p v-if="sessionError" class="notice notice-error" role="alert">
          {{ sessionError }}
        </p>
        <header class="page-header">
          <div>
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
