-- Migracion conservadora del MVP al contrato de las secciones 12 y 13.
-- Requiere detener API/worker durante su aplicacion. No elimina datos historicos.
USE ProInXML;
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
BEGIN TRANSACTION;
-- Retirar los triggers anteriores: la nueva politica se instala en 004.
DECLARE @sql nvarchar(max)=N'';
SELECT @sql+=N'DROP TRIGGER '+QUOTENAME(OBJECT_SCHEMA_NAME(object_id))+N'.'+QUOTENAME(name)+N';'
FROM sys.triggers WHERE name LIKE N'tr_Audit[_]%';
EXEC sys.sp_executesql @sql;
IF OBJECT_ID(N'integracion.Fuente',N'U') IS NOT NULL
 EXEC sys.sp_rename N'integracion.Fuente',N'Consulta';
IF COL_LENGTH(N'integracion.Trabajo',N'FuenteId') IS NOT NULL
 EXEC sys.sp_rename N'integracion.Trabajo.FuenteId',N'ConsultaId',N'COLUMN';
IF COL_LENGTH(N'integracion.Documento',N'FuenteId') IS NOT NULL
 EXEC sys.sp_rename N'integracion.Documento.FuenteId',N'ConsultaId',N'COLUMN';
GO
IF OBJECT_ID(N'seguridad.Rol',N'U') IS NULL
 CREATE TABLE seguridad.Rol(Id bigint IDENTITY PRIMARY KEY,Nombre nvarchar(40) NOT NULL UNIQUE,
 CreadoUtc datetime2(3) NOT NULL DEFAULT SYSUTCDATETIME());
IF OBJECT_ID(N'seguridad.Usuario',N'U') IS NULL
 CREATE TABLE seguridad.Usuario(Id bigint IDENTITY PRIMARY KEY,NombreUsuario nvarchar(80) NOT NULL UNIQUE,
 NombreCompleto nvarchar(160) NOT NULL,HashContrasena nvarchar(500) NOT NULL,
 RolId bigint NOT NULL CONSTRAINT FK_Usuario_Rol REFERENCES seguridad.Rol(Id),Activo bit NOT NULL DEFAULT 1,
 CreadoUtc datetime2(3) NOT NULL DEFAULT SYSUTCDATETIME());
IF OBJECT_ID(N'seguridad.EventoAcceso',N'U') IS NULL
 CREATE TABLE seguridad.EventoAcceso(Id bigint IDENTITY PRIMARY KEY,
 UsuarioId bigint NULL CONSTRAINT FK_EventoAcceso_Usuario REFERENCES seguridad.Usuario(Id),
 NombreIntentado nvarchar(80) NOT NULL,Evento nvarchar(80) NOT NULL,Exitoso bit NOT NULL,
 Ip nvarchar(64) NULL,FechaUtc datetime2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
 CreadoUtc datetime2(3) NOT NULL DEFAULT SYSUTCDATETIME());
IF OBJECT_ID(N'integracion.Servicio',N'U') IS NULL
 CREATE TABLE integracion.Servicio(Id bigint IDENTITY PRIMARY KEY,Nombre nvarchar(160) NOT NULL,
 UrlBase nvarchar(200) NOT NULL,Ruta nvarchar(400) NOT NULL,VersionContrato varchar(32) NOT NULL,
 Activo bit NOT NULL DEFAULT 1,CreadoUtc datetime2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
 CONSTRAINT UQ_Servicio_Endpoint UNIQUE(UrlBase,Ruta));
INSERT seguridad.Rol(Nombre) SELECT v.Nombre FROM (VALUES(N'Administrador'),(N'Operador'),(N'Consulta'))v(Nombre)
 WHERE NOT EXISTS(SELECT 1 FROM seguridad.Rol r WHERE r.Nombre=v.Nombre);
-- Identidad de procesos; no permite login interactivo y no tiene contrasena utilizable.
IF NOT EXISTS(SELECT 1 FROM seguridad.Usuario WHERE NombreUsuario=N'sistema')
 INSERT seguridad.Usuario(NombreUsuario,NombreCompleto,HashContrasena,RolId,Activo)
 SELECT N'sistema',N'Proceso de integracion',N'!no-login!',Id,0 FROM seguridad.Rol WHERE Nombre=N'Administrador';
IF NOT EXISTS(SELECT 1 FROM integracion.Servicio)
 INSERT integracion.Servicio(Nombre,UrlBase,Ruta,VersionContrato)
 VALUES(N'MEF Gasto PIP',N'http://s3.mef.gob.pe',N'/servicios/WSPCM/SG/gastopipsg-old.asmx/ObtenerDataGastoPIP_old_2','1');
IF NOT EXISTS(SELECT 1 FROM catalogo.TipoActProy WHERE Id=2) INSERT catalogo.TipoActProy(Id,Nombre) VALUES(2,N'Proyecto');
IF NOT EXISTS(SELECT 1 FROM catalogo.TipoActProy WHERE Id=3) INSERT catalogo.TipoActProy(Id,Nombre) VALUES(3,N'Actividad');
IF COL_LENGTH(N'integracion.Lote',N'CreadoPorUsuarioId') IS NULL
 ALTER TABLE integracion.Lote ADD CreadoPorUsuarioId bigint NULL;
IF COL_LENGTH(N'integracion.Consulta',N'ServicioId') IS NULL
 ALTER TABLE integracion.Consulta ADD ServicioId bigint NULL;
IF COL_LENGTH(N'integracion.Intento',N'Etapa') IS NULL
 ALTER TABLE integracion.Intento ADD Etapa nvarchar(40) NOT NULL DEFAULT N'Descarga',
 UrlSolicitada nvarchar(1000) NULL,DocumentoId bigint NULL,RegistrosLeidos int NULL,
 RegistrosInsertados int NULL,RegistrosReutilizados int NULL,RegistrosRechazados int NULL,
 Observaciones int NULL;
IF COL_LENGTH(N'auditoria.Cambio',N'UsuarioId') IS NULL
 ALTER TABLE auditoria.Cambio ADD UsuarioId bigint NULL,Rol nvarchar(40) NOT NULL DEFAULT N'Sin identificar';
GO
UPDATE integracion.Lote SET CreadoPorUsuarioId=(SELECT Id FROM seguridad.Usuario WHERE NombreUsuario=N'sistema')
 WHERE CreadoPorUsuarioId IS NULL;
ALTER TABLE integracion.Lote ALTER COLUMN CreadoPorUsuarioId bigint NOT NULL;
IF NOT EXISTS(SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_Lote_Usuario')
 ALTER TABLE integracion.Lote ADD CONSTRAINT FK_Lote_Usuario FOREIGN KEY(CreadoPorUsuarioId) REFERENCES seguridad.Usuario(Id);
UPDATE integracion.Consulta SET ServicioId=(SELECT MIN(Id) FROM integracion.Servicio) WHERE ServicioId IS NULL;
ALTER TABLE integracion.Consulta ALTER COLUMN ServicioId bigint NOT NULL;
IF NOT EXISTS(SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_Consulta_Servicio')
 ALTER TABLE integracion.Consulta ADD CONSTRAINT FK_Consulta_Servicio FOREIGN KEY(ServicioId) REFERENCES integracion.Servicio(Id);
IF EXISTS(SELECT 1 FROM sys.key_constraints WHERE name=N'UQ_Fuente_Parametros')
 ALTER TABLE integracion.Consulta DROP CONSTRAINT UQ_Fuente_Parametros;
-- La clave natural antigua y su check dependen del tipo anterior de NivelGobierno.
IF NOT EXISTS(SELECT 1 FROM sys.key_constraints WHERE name=N'UQ_Consulta_Parametros')
BEGIN
 DECLARE @checks nvarchar(max)=N'';
 SELECT @checks+=N'ALTER TABLE integracion.Consulta DROP CONSTRAINT '+QUOTENAME(name)+N';'
 FROM sys.check_constraints WHERE parent_object_id=OBJECT_ID(N'integracion.Consulta') AND definition LIKE '%NivelGobierno%';
 EXEC sys.sp_executesql @checks;
 ALTER TABLE integracion.Consulta ALTER COLUMN NivelGobierno varchar(8) NOT NULL;
 ALTER TABLE integracion.Consulta ADD CONSTRAINT UQ_Consulta_Parametros UNIQUE(ServicioId,AnoEje,NivelGobierno,SecEjec);
END;
UPDATE a SET UrlSolicitada=c.Url FROM integracion.Intento a JOIN integracion.Trabajo t ON t.Id=a.TrabajoId
 JOIN integracion.Consulta c ON c.Id=t.ConsultaId WHERE a.UrlSolicitada IS NULL;
ALTER TABLE integracion.Intento ALTER COLUMN UrlSolicitada nvarchar(1000) NOT NULL;
IF NOT EXISTS(SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_Intento_Documento')
 ALTER TABLE integracion.Intento ADD CONSTRAINT FK_Intento_Documento FOREIGN KEY(DocumentoId) REFERENCES integracion.Documento(Id);
IF NOT EXISTS(SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_Cambio_Usuario')
 ALTER TABLE auditoria.Cambio ADD CONSTRAINT FK_Cambio_Usuario FOREIGN KEY(UsuarioId) REFERENCES seguridad.Usuario(Id);
GO
-- Los estados se migran una vez; no se cambia la fecha del evento historico.
DECLARE @sql nvarchar(max)=N'';
SELECT @sql+=N'ALTER TABLE '+QUOTENAME(OBJECT_SCHEMA_NAME(parent_object_id))+N'.'+QUOTENAME(OBJECT_NAME(parent_object_id))+
 N' DROP CONSTRAINT '+QUOTENAME(name)+N';' FROM sys.check_constraints
 WHERE parent_object_id IN (OBJECT_ID(N'integracion.Trabajo'),OBJECT_ID(N'integracion.Intento')) AND definition LIKE '%Estado%';
EXEC sys.sp_executesql @sql;
ALTER TABLE integracion.Trabajo ALTER COLUMN Estado varchar(24) NOT NULL;
ALTER TABLE integracion.Intento ALTER COLUMN Estado varchar(24) NOT NULL;
UPDATE integracion.Trabajo SET Estado=CASE Estado COLLATE Latin1_General_100_BIN2
 WHEN 'PENDIENTE' THEN 'Pendiente' WHEN 'REINTENTO' THEN 'Pendiente' WHEN 'PROCESANDO' THEN 'EnCurso'
 WHEN 'COMPLETADO' THEN 'Completado' WHEN 'FALLIDO' THEN 'Fallido' ELSE Estado END
 WHERE Estado COLLATE Latin1_General_100_BIN2 IN ('PENDIENTE','REINTENTO','PROCESANDO','COMPLETADO','FALLIDO');
UPDATE integracion.Intento SET Estado=CASE Estado COLLATE Latin1_General_100_BIN2
 WHEN 'PROCESANDO' THEN 'EnCurso' WHEN 'COMPLETADO' THEN 'Completado' WHEN 'ERROR' THEN 'Error'
 WHEN 'ABANDONADO' THEN 'Interrumpido' ELSE Estado END
 WHERE Estado COLLATE Latin1_General_100_BIN2 IN ('PROCESANDO','COMPLETADO','ERROR','ABANDONADO');
ALTER TABLE integracion.Trabajo ADD CONSTRAINT CK_Trabajo_Estado
 CHECK(Estado IN ('Pendiente','EnCurso','Completado','CompletadoSinDatos','Fallido','YaCargada','Cancelado'));
ALTER TABLE integracion.Intento ADD CONSTRAINT CK_Intento_Estado CHECK(Estado IN ('EnCurso','Completado','Error','Interrumpido'));
DECLARE @defaults nvarchar(max)=N'';
SELECT @defaults+=N'ALTER TABLE '+QUOTENAME(OBJECT_SCHEMA_NAME(d.parent_object_id))+N'.'+QUOTENAME(OBJECT_NAME(d.parent_object_id))+
 N' DROP CONSTRAINT '+QUOTENAME(d.name)+N';' FROM sys.default_constraints d
 JOIN sys.columns c ON c.object_id=d.parent_object_id AND c.column_id=d.parent_column_id
 WHERE c.name='Estado' AND d.parent_object_id IN(OBJECT_ID(N'integracion.Trabajo'),OBJECT_ID(N'integracion.Intento'));
EXEC sys.sp_executesql @defaults;
ALTER TABLE integracion.Trabajo ADD CONSTRAINT DF_Trabajo_Estado DEFAULT 'Pendiente' FOR Estado;
ALTER TABLE integracion.Intento ADD CONSTRAINT DF_Intento_Estado DEFAULT 'EnCurso' FOR Estado;
GO
-- Retirar solamente la FK del catalogo en el detalle; se conserva la de Documento.
DECLARE @sql nvarchar(max)=N'';
SELECT @sql+=N'ALTER TABLE datos.Gasto DROP CONSTRAINT '+QUOTENAME(name)+N';' FROM sys.foreign_keys
 WHERE parent_object_id=OBJECT_ID(N'datos.Gasto') AND referenced_object_id=OBJECT_ID(N'catalogo.TipoActProy');
EXEC sys.sp_executesql @sql;
ALTER TABLE datos.Gasto ALTER COLUMN Unidad_Medida varchar(32) NULL;
IF OBJECT_ID(N'modelo.Meta',N'U') IS NOT NULL
 ALTER TABLE modelo.Meta ALTER COLUMN UnidadMedidaId bigint NULL;
IF EXISTS(SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID(N'integracion.Documento') AND name='Sha256' AND TYPE_NAME(user_type_id)='binary')
BEGIN
 SELECT Id,CONVERT(char(64),Sha256,2) AS HashTexto INTO #hash FROM integracion.Documento;
 ALTER TABLE integracion.Documento DROP CONSTRAINT UQ_Documento_Hash;
 ALTER TABLE integracion.Documento ALTER COLUMN Sha256 char(64) NOT NULL;
 UPDATE d SET Sha256=LOWER(h.HashTexto) FROM integracion.Documento d JOIN #hash h ON h.Id=d.Id;
 ALTER TABLE integracion.Documento ADD CONSTRAINT UQ_Documento_Hash UNIQUE(ConsultaId,Sha256);
END;
UPDATE integracion.Documento SET Respuesta=COMPRESS(Respuesta) WHERE SUBSTRING(Respuesta,1,2)<>0x1F8B;
IF OBJECT_ID(N'integracion.ObservacionDato',N'U') IS NULL
 CREATE TABLE integracion.ObservacionDato(Id bigint IDENTITY PRIMARY KEY,
 DocumentoId bigint NOT NULL CONSTRAINT FK_Observacion_Documento REFERENCES integracion.Documento(Id),
 OrdinalItem int NOT NULL,Campo varchar(64) NOT NULL,CodigoObservacion varchar(64) NOT NULL,
 Severidad varchar(16) NOT NULL CONSTRAINT CK_Observacion_Severidad CHECK(Severidad IN ('Info','Advertencia','Error')),
 Detalle nvarchar(1000) NOT NULL,FechaUtc datetime2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
 CreadoUtc datetime2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
 CONSTRAINT UQ_Observacion_Origen UNIQUE(DocumentoId,OrdinalItem,Campo,CodigoObservacion));
IF OBJECT_ID(N'auditoria.CargaDocumento',N'U') IS NULL
 CREATE TABLE auditoria.CargaDocumento(Id bigint IDENTITY PRIMARY KEY,
 DocumentoId bigint NOT NULL CONSTRAINT FK_Carga_Documento REFERENCES integracion.Documento(Id),
 LoteId bigint NOT NULL CONSTRAINT FK_Carga_Lote REFERENCES integracion.Lote(Id),
 UsuarioId bigint NULL CONSTRAINT FK_Carga_Usuario REFERENCES seguridad.Usuario(Id),Rol nvarchar(40) NOT NULL,
 FilasInsertadas int NOT NULL,FilasReutilizadas int NOT NULL,FechaUtc datetime2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
 CreadoUtc datetime2(3) NOT NULL DEFAULT SYSUTCDATETIME(),CONSTRAINT UQ_Carga_Documento UNIQUE(DocumentoId));
GO
-- Agregar CreadoUtc a las tablas heredadas que no lo tenian.
DECLARE @sql nvarchar(max)=N'';
SELECT @sql+=N'ALTER TABLE '+QUOTENAME(s.name)+N'.'+QUOTENAME(t.name)+
 N' ADD CreadoUtc datetime2(3) NOT NULL DEFAULT SYSUTCDATETIME();'
FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id
WHERE s.name IN ('integracion','datos','modelo','catalogo','seguridad','auditoria')
 AND NOT EXISTS(SELECT 1 FROM sys.columns c WHERE c.object_id=t.object_id AND c.name='CreadoUtc');
EXEC sys.sp_executesql @sql;
IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'auditoria.Cambio') AND name=N'IX_Cambio_Fecha')
 CREATE INDEX IX_Cambio_Fecha ON auditoria.Cambio(FechaUtc,Id);
IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'integracion.Intento') AND name=N'IX_Intento_Trabajo')
 CREATE INDEX IX_Intento_Trabajo ON integracion.Intento(TrabajoId,Numero DESC) INCLUDE(HttpStatus,Estado,FinUtc);
IF DATABASE_PRINCIPAL_ID(N'proinxml_app') IS NULL CREATE ROLE proinxml_app AUTHORIZATION dbo;
COMMIT;
GO
