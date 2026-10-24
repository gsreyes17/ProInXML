import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "./stores/auth";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/ui/login",
      name: "login",
      component: () => import("./views/LoginView.vue"),
      meta: { title: "Inicia sesión", public: true },
    },
    {
      path: "/",
      name: "carga",
      component: () => import("./views/UploadView.vue"),
      meta: {
        title: "Carga de XML",
        description: "Integra tus enlaces y sigue el recorrido de tus datos.",
        write: true,
      },
    },
    {
      path: "/ui/seguimiento",
      name: "seguimiento",
      component: () => import("./views/TrackingView.vue"),
      meta: {
        title: "Seguimiento",
        description:
          "Consulta el resultado de cada carga y sus registros guardados.",
      },
    },
    {
      path: "/ui/datos",
      name: "datos",
      component: () => import("./views/XmlView.vue"),
      meta: {
        title: "Registros XML",
        description: "Explora los 39 campos recibidos y su trazabilidad.",
      },
    },
    {
      path: "/ui/modelo",
      name: "modelo",
      component: () => import("./views/ModelView.vue"),
      meta: {
        title: "Modelo 3FN",
        description:
          "Recorre las entidades y sus relaciones a partir de los datos guardados.",
      },
    },
    {
      path: "/ui/auditoria",
      name: "auditoria",
      component: () => import("./views/AuditView.vue"),
      meta: {
        title: "Auditoría",
        description:
          "Consulta cambios, cargas por documento y eventos de acceso.",
        admin: true,
      },
    },
    {
      path: "/ui/ejecucion",
      name: "ejecucion",
      component: () => import("./views/OperationsView.vue"),
      meta: {
        title: "Ejecución del servicio",
        description: "HTTP, tiempos, etapas y resultados de cada intento.",
      },
    },
    {
      path: "/ui/observaciones",
      name: "observaciones",
      component: () => import("./views/OperationsView.vue"),
      meta: {
        title: "Observaciones",
        description: "Valores no informados e incidencias de validación.",
      },
    },
    {
      path: "/ui/metricas",
      name: "metricas",
      component: () => import("./views/MetricsView.vue"),
      meta: {
        title: "Métricas de carga",
        description:
          "Descarga, validación, SQL y rendimiento por intento y lote.",
      },
    },
    {
      path: "/ui/mantenimiento",
      name: "mantenimiento",
      component: () => import("./views/MaintenanceView.vue"),
      meta: {
        title: "Mantenimiento",
        description:
          "Inspecciona documentos y limpia las cargas del laboratorio.",
        admin: true,
      },
    },
    {
      path: "/ui/usuarios",
      name: "usuarios",
      component: () => import("./views/UsersView.vue"),
      meta: {
        title: "Usuarios",
        description: "Gestiona las cuentas y los permisos del proyecto.",
        admin: true,
      },
    },
    { path: "/:pathMatch(.*)*", redirect: "/ui/seguimiento" },
  ],
  scrollBehavior: () => ({ top: 0 }),
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  if (to.meta.public) {
    if (auth.user) return auth.canWrite ? "/" : "/ui/seguimiento";
    return;
  }
  try {
    await auth.ensure();
  } catch {
    return { name: "login", query: { conexion: "1" } };
  }
  if (!auth.user) return { name: "login", query: { redirect: to.fullPath } };
  if ((to.meta.admin && !auth.isAdmin) || (to.meta.write && !auth.canWrite))
    return "/ui/seguimiento";
});
router.afterEach((to) => {
  document.title = `ProInXML · ${String(to.meta.title || "Integración")}`;
});
