import { defineStore } from "pinia";
import { api, ApiError, setCsrf } from "../services/api";
import type { User } from "../types";

let loading: Promise<void> | null = null;
const FALLBACK_SESSION_MS = 60 * 60 * 1000;
function remainingSessionMs(value: number | undefined) {
  return typeof value === "number" && Number.isFinite(value)
    ? value
    : FALLBACK_SESSION_MS;
}
export const useAuthStore = defineStore("auth", {
  state: () => ({
    user: null as User | null,
    initialized: false,
    expiresAt: null as number | null,
  }),
  getters: {
    canWrite: (state) => !!state.user && state.user.Rol !== "Consulta",
    isAdmin: (state) => state.user?.Rol === "Administrador",
  },
  actions: {
    async ensure() {
      if (this.initialized) return;
      loading ??= (async () => {
        try {
          const data = await api<{
            usuario: User;
            csrf: string;
            expires_in_ms: number;
          }>("/auth/me");
          this.user = data.usuario;
          this.expiresAt = Date.now() + remainingSessionMs(data.expires_in_ms);
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
      const data = await api<{
        usuario: User;
        csrf: string;
        expires_in_ms: number;
      }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ usuario, contrasena }),
      });
      this.user = data.usuario;
      this.expiresAt = Date.now() + remainingSessionMs(data.expires_in_ms);
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
      this.expiresAt = null;
      this.initialized = true;
      setCsrf("");
    },
  },
});
