import { defineStore } from "pinia";
import { api, ApiError, setCsrf } from "../services/api";
import type { User } from "../types";

let loading: Promise<void> | null = null;
export const useAuthStore = defineStore("auth", {
  state: () => ({ user: null as User | null, initialized: false }),
  getters: {
    canWrite: (state) => !!state.user && state.user.Rol !== "Consulta",
    isAdmin: (state) => state.user?.Rol === "Administrador",
  },
  actions: {
    async ensure() {
      if (this.initialized) return;
      loading ??= (async () => {
        try {
          const data = await api<{ usuario: User; csrf: string }>("/auth/me");
          this.user = data.usuario;
          setCsrf(data.csrf);
          this.initialized = true;
        } catch (error) {
          if (!(error instanceof ApiError) || error.status !== 401) throw error;
          this.clear();
        } finally {
          loading = null;
        }
      })();
      await loading;
    },
    async login(usuario: string, contrasena: string) {
      const data = await api<{ usuario: User; csrf: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ usuario, contrasena }),
      });
      this.user = data.usuario;
      this.initialized = true;
      setCsrf(data.csrf);
    },
    async logout() {
      try {
        await api("/auth/logout", { method: "POST" });
      } catch (error) {
        if (!(error instanceof ApiError) || error.status !== 401) throw error;
      }
      this.clear();
    },
    clear() {
      this.user = null;
      this.initialized = true;
      setCsrf("");
    },
  },
});
