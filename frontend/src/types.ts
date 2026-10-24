export type Role = "Administrador" | "Operador" | "Consulta";
export interface User {
  Id: number;
  NombreUsuario: string;
  NombreCompleto: string;
  Rol: Role;
  Activo: boolean;
}
export type Cell = string | number | boolean | null;
export type DataRow = Record<string, Cell>;
export interface PageData {
  registros: DataRow[];
  total: number;
  siguiente_cursor: number | null;
  columnas?: string[];
  identificadores?: number[];
}
export interface ModelDefinition {
  tabla: string;
  nombre: string;
  grupo: string;
  columnas: string[];
  relaciones: { columna: string; tabla: string }[];
}
export interface BatchResult {
  lote_id: number;
  trabajos: number;
  nuevas: number;
  ya_cargadas: number;
  duplicados_omitidos: number;
}
