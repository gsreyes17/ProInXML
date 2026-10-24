import { onMounted, onUnmounted, ref } from "vue";

/** Una solicitud a la vez; cancela al desmontar y descansa si la pestaña está oculta. */
export function usePolling(
  task: (signal: AbortSignal) => Promise<void>,
  interval = 3000,
) {
  const loading = ref(false);
  const error = ref("");
  const updated = ref<Date | null>(null);
  let stopped = false;
  let controller: AbortController | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let generation = 0;

  async function run(replace = false) {
    if (stopped || (loading.value && !replace) || document.hidden) return;
    if (replace) controller?.abort();
    const current = ++generation;
    loading.value = true;
    const active = new AbortController();
    controller = active;
    try {
      await task(active.signal);
      if (!stopped && current === generation) {
        error.value = "";
        updated.value = new Date();
      }
    } catch (failure) {
      if (!active.signal.aborted && !stopped && current === generation)
        error.value =
          failure instanceof Error ? failure.message : "No se pudo actualizar.";
    } finally {
      if (current === generation) loading.value = false;
    }
  }
  const refresh = () => run();
  const restart = () => run(true);
  async function tick() {
    await refresh();
    if (!stopped) timer = setTimeout(tick, interval);
  }
  function visible() {
    if (!document.hidden) void refresh();
  }
  onMounted(() => {
    void tick();
    document.addEventListener("visibilitychange", visible);
  });
  onUnmounted(() => {
    stopped = true;
    clearTimeout(timer);
    controller?.abort();
    document.removeEventListener("visibilitychange", visible);
  });
  return { loading, error, updated, refresh, restart };
}
