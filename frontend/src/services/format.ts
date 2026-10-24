import type { Cell } from "../types";

export function text(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}
export const number = (value: number) =>
  new Intl.NumberFormat("es-PE").format(value);
export function date(value: Cell | undefined) {
  if (!value) return "";
  const raw = String(value);
  const parsed = new Date(/Z$|[+-]\d\d:\d\d$/.test(raw) ? raw : `${raw}Z`);
  return Number.isNaN(parsed.getTime())
    ? raw
    : new Intl.DateTimeFormat("es-PE", {
        day: "2-digit",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      }).format(parsed);
}
export function decimal(value: Cell | undefined) {
  if (value === null || value === undefined) return "—";
  const [whole, fraction = ""] = String(value).split(".");
  return (
    whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",") +
    "." +
    fraction.replace(/0+$/, "").padEnd(2, "0")
  );
}
