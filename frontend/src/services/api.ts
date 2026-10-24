let csrf = "";
export function setCsrf(value: string) {
  csrf = value;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (csrf && options.method && !["GET", "HEAD"].includes(options.method))
    headers.set("X-CSRF-Token", csrf);
  if (typeof options.body === "string")
    headers.set("Content-Type", "application/json");
  const timeout = AbortSignal.timeout(
    options.method === "POST" &&
      (path.startsWith("/lotes") || path.startsWith("/mantenimiento"))
      ? 180000
      : 20000,
  );
  const signal = options.signal
    ? AbortSignal.any([options.signal, timeout])
    : timeout;
  let response: Response;
  try {
    response = await fetch(path, {
      ...options,
      headers,
      signal,
      credentials: "same-origin",
    });
  } catch (error) {
    if (options.signal?.aborted) throw error;
    throw new ApiError(
      "No se pudo conectar. Comprueba que la aplicación siga abierta e inténtalo de nuevo.",
      0,
    );
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    if (
      response.status === 401 &&
      path !== "/auth/login" &&
      path !== "/auth/me"
    ) {
      window.dispatchEvent(new Event("session-expired"));
    }
    const detail = data?.detail;
    let message = typeof detail === "string" ? detail : detail?.mensaje;
    if (Array.isArray(detail))
      message = detail.map((item) => item.msg).join(". ");
    if (detail?.errores)
      message +=
        "\n" +
        detail.errores
          .map(
            (item: { linea: number; detalle: string }) =>
              `Enlace ${item.linea}: ${item.detalle}`,
          )
          .join("\n");
    throw new ApiError(
      message || "No se pudo completar la solicitud.",
      response.status,
    );
  }
  return data as T;
}

export function query(
  values: Record<string, string | number | boolean | null | undefined>,
) {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== "" && value !== null && value !== undefined)
      params.set(key, String(value));
  });
  return params.toString();
}
