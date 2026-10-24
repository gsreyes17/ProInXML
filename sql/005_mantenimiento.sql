USE ProInXML;
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
BEGIN TRANSACTION;
-- La bitacora conserva identificadores historicos aunque se eliminen las cargas.
-- No modificar sus filas ni reiniciar identidades: los IDs nunca se reutilizan.
-- La FK al usuario permanece y los triggers de inmutabilidad siguen activos.
IF OBJECT_ID(N'auditoria.FK_Carga_Documento',N'F') IS NOT NULL
 ALTER TABLE auditoria.CargaDocumento DROP CONSTRAINT FK_Carga_Documento;
IF OBJECT_ID(N'auditoria.FK_Carga_Lote',N'F') IS NOT NULL
 ALTER TABLE auditoria.CargaDocumento DROP CONSTRAINT FK_Carga_Lote;
COMMIT;
GO
