-- Cola, vistas operativas, auditoria inmutable y permisos de aplicacion.
USE ProInXML;
GO
SET NOCOUNT ON;
GO
-- Consultas de datos vigentes y trazabilidad de intentos.
CREATE OR ALTER VIEW datos.GastoActual AS
SELECT g.* FROM datos.Gasto g JOIN integracion.Consulta c ON c.DocumentoActualId=g.DocumentoId;
GO
CREATE OR ALTER VIEW modelo.GastoActual AS
SELECT m.* FROM modelo.Gasto m JOIN datos.GastoActual g ON g.Id=m.Id;
GO
CREATE OR ALTER VIEW datos.vw_GastoXML AS
SELECT AnoEje,MesEje,IdNivelGobierno,Sub_tipo_gobierno,IdSector,IdPliego,IdEjecutora,SecEjec,
 Funcion,Programa,Programa_ppto,Categ_gasto,Tipo_transaccion,Generica,Subgenerica,Subgenerica_det,
 Especifica,Especifica_det,SecFunc,IdFuente,IdRubro,IdTipoRecurso,IdComponente,IdProyecto,TipoActProy,
 IdMeta,IdFinalidad,IdProyectoSNIP,Departamento,Provincia,Distrito,Unidad_Medida,
 PIA,PIM,Certificado,CompAnual,AtencionCompMensual,Devengado,Girado FROM datos.GastoActual;
GO
CREATE OR ALTER VIEW reportes.EjecucionServicio AS
SELECT a.Id,a.TrabajoId,t.LoteId,t.ConsultaId,a.Numero,a.Estado,a.Etapa,a.HttpStatus,
 a.InicioUtc,a.FinUtc,DATEDIFF_BIG(millisecond,a.InicioUtc,COALESCE(a.FinUtc,SYSUTCDATETIME())) AS DuracionMs,
 a.UrlSolicitada,a.DocumentoId,a.Error,a.RegistrosLeidos,a.RegistrosInsertados,a.RegistrosReutilizados,
 a.RegistrosRechazados,a.Observaciones,a.CreadoUtc FROM integracion.Intento a
 JOIN integracion.Trabajo t ON t.Id=a.TrabajoId;
GO
-- Toma atomica de trabajos y recuperacion de leases vencidos.
CREATE OR ALTER PROCEDURE integracion.TomarTrabajo @LoteId bigint=NULL AS
BEGIN
 SET NOCOUNT ON;
 SET XACT_ABORT ON;
 BEGIN TRANSACTION;
 DECLARE @Ahora datetime2(3)=SYSUTCDATETIME();
 DECLARE @tomado TABLE(Id bigint,ConsultaId bigint,Intentos int,Token uniqueidentifier);
 -- Un corte no consume el presupuesto de errores: el intento queda registrado como interrumpido.
 DECLARE @vencidos TABLE(Id bigint);
 UPDATE t WITH(ROWLOCK,READPAST) SET Estado='Pendiente',Intentos=CASE WHEN Intentos>0 THEN Intentos-1 ELSE 0 END,
 Token=NULL,LeaseHastaUtc=NULL,ProximoIntentoUtc=@Ahora,UltimoError=N'Lease vencido; trabajo recuperado'
 OUTPUT inserted.Id INTO @vencidos FROM integracion.Trabajo t
 WHERE Estado='EnCurso' AND LeaseHastaUtc<@Ahora;
 UPDATE a SET Estado='Interrumpido',FinUtc=@Ahora,Error=N'Worker interrumpido: lease vencido'
 FROM integracion.Intento a JOIN @vencidos v ON v.Id=a.TrabajoId WHERE a.Estado='EnCurso';
 ;WITH siguiente AS(
 SELECT TOP(1) * FROM integracion.Trabajo WITH(UPDLOCK,READPAST,ROWLOCK)
 WHERE Estado='Pendiente' AND Intentos<MaxIntentos AND ProximoIntentoUtc<=@Ahora
 AND (@LoteId IS NULL OR LoteId=@LoteId)
 ORDER BY ProximoIntentoUtc,Id)
 UPDATE siguiente SET Estado='EnCurso',Intentos=Intentos+1,Token=NEWID(),
 LeaseHastaUtc=DATEADD(minute,10,@Ahora),FinalizadoUtc=NULL
 OUTPUT inserted.Id,inserted.ConsultaId,inserted.Intentos,inserted.Token INTO @tomado;
 INSERT integracion.Intento(TrabajoId,Numero,UrlSolicitada,Etapa)
 SELECT t.Id,COALESCE((SELECT MAX(a.Numero) FROM integracion.Intento a WHERE a.TrabajoId=t.Id),0)+1,c.Url,N'Descarga'
 FROM @tomado t JOIN integracion.Consulta c ON c.Id=t.ConsultaId;
 SELECT t.*,w.LoteId,a.Id AS IntentoId,c.Url,c.AnoEje,c.NivelGobierno,c.SecEjec FROM @tomado t
 JOIN integracion.Trabajo w ON w.Id=t.Id
 JOIN integracion.Consulta c ON c.Id=t.ConsultaId JOIN integracion.Intento a ON a.TrabajoId=t.Id AND a.Estado='EnCurso';
 COMMIT;
END;
GO
-- Auditoria fila a fila solamente donde aporta valor; el volumen va a CargaDocumento.
DECLARE @schema sysname,@table sysname,@sql nvarchar(max),@projection nvarchar(max);
DECLARE tablas CURSOR LOCAL FAST_FORWARD FOR
SELECT s.name,t.name FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id
WHERE (s.name='integracion' AND t.name IN ('Servicio','Lote','Consulta','Trabajo'))
 OR s.name='catalogo' OR (s.name='seguridad' AND t.name='Usuario');
OPEN tablas;FETCH NEXT FROM tablas INTO @schema,@table;
WHILE @@FETCH_STATUS=0
BEGIN
 SET @projection=CASE WHEN @schema='seguridad' THEN N'x.Id,x.NombreUsuario,x.NombreCompleto,x.RolId,x.Activo,x.CreadoUtc' ELSE N'x.*' END;
 SET @sql=N'CREATE OR ALTER TRIGGER '+QUOTENAME(@schema)+N'.'+QUOTENAME(N'tr_Audit_'+@table)+N'
 ON '+QUOTENAME(@schema)+N'.'+QUOTENAME(@table)+N' AFTER INSERT,UPDATE,DELETE AS BEGIN SET NOCOUNT ON;
 INSERT auditoria.Cambio(Tabla,RegistroId,Operacion,UsuarioId,Actor,Rol,LoginSql,Correlacion,Antes,Despues)
 SELECT N'''+@schema+N'.'+@table+N''',COALESCE(i.Id,d.Id),
 CASE WHEN d.Id IS NULL THEN ''I'' WHEN i.Id IS NULL THEN ''D'' ELSE ''U'' END,
 TRY_CONVERT(bigint,SESSION_CONTEXT(N''usuario_id'')),
 COALESCE(CONVERT(nvarchar(128),SESSION_CONTEXT(N''actor'')),ORIGINAL_LOGIN()),
 COALESCE(CONVERT(nvarchar(40),SESSION_CONTEXT(N''rol'')),N''Sin identificar''),ORIGINAL_LOGIN(),
 TRY_CONVERT(uniqueidentifier,SESSION_CONTEXT(N''correlation'')),
 CASE WHEN d.Id IS NOT NULL THEN (SELECT '+@projection+N' FROM deleted x WHERE x.Id=d.Id FOR JSON PATH,INCLUDE_NULL_VALUES,WITHOUT_ARRAY_WRAPPER) END,
 CASE WHEN i.Id IS NOT NULL THEN (SELECT '+@projection+N' FROM inserted x WHERE x.Id=i.Id FOR JSON PATH,INCLUDE_NULL_VALUES,WITHOUT_ARRAY_WRAPPER) END
 FROM inserted i FULL OUTER JOIN deleted d ON i.Id=d.Id; END';
 EXEC sys.sp_executesql @sql;
 FETCH NEXT FROM tablas INTO @schema,@table;
END;
CLOSE tablas;DEALLOCATE tablas;
GO
CREATE OR ALTER TRIGGER auditoria.tr_Cambio_Inmutable ON auditoria.Cambio INSTEAD OF UPDATE,DELETE AS
BEGIN THROW 50002,'La bitacora no admite cambios ni eliminaciones.',1; END;
GO
CREATE OR ALTER TRIGGER auditoria.tr_Carga_Inmutable ON auditoria.CargaDocumento INSTEAD OF UPDATE,DELETE AS
BEGIN THROW 50002,'La auditoria de cargas no admite cambios ni eliminaciones.',1; END;
GO
CREATE OR ALTER TRIGGER seguridad.tr_Acceso_Inmutable ON seguridad.EventoAcceso INSTEAD OF UPDATE,DELETE AS
BEGIN THROW 50002,'Los eventos de acceso no admiten cambios ni eliminaciones.',1; END;
GO
-- Permisos de la cuenta de aplicacion; las bitacoras son inmutables.
GRANT SELECT,INSERT,UPDATE,DELETE ON SCHEMA::integracion TO proinxml_app;
GRANT SELECT,INSERT,UPDATE,DELETE ON SCHEMA::datos TO proinxml_app;
GRANT SELECT,INSERT,UPDATE,DELETE ON SCHEMA::modelo TO proinxml_app;
GRANT SELECT,INSERT,UPDATE ON seguridad.Usuario TO proinxml_app;
GRANT SELECT ON seguridad.Rol TO proinxml_app;
GRANT SELECT,INSERT ON seguridad.EventoAcceso TO proinxml_app;
GRANT SELECT ON SCHEMA::catalogo TO proinxml_app;
GRANT SELECT,INSERT ON SCHEMA::auditoria TO proinxml_app;
GRANT SELECT ON SCHEMA::reportes TO proinxml_app;
DENY UPDATE,DELETE ON SCHEMA::auditoria TO proinxml_app;
DENY UPDATE,DELETE ON seguridad.EventoAcceso TO proinxml_app;
DENY ALTER ON SCHEMA::integracion TO proinxml_app;
DENY ALTER ON SCHEMA::datos TO proinxml_app;
DENY ALTER ON SCHEMA::modelo TO proinxml_app;
DENY ALTER ON SCHEMA::seguridad TO proinxml_app;
DENY ALTER ON SCHEMA::auditoria TO proinxml_app;
GRANT EXECUTE ON integracion.TomarTrabajo TO proinxml_app;
GO
