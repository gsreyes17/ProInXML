-- ProInXML 1.0: tablas base, relaciones, indices y catalogos iniciales.
USE master;
GO
IF DB_ID(N'ProInXML') IS NULL EXEC(N'CREATE DATABASE ProInXML');
GO
USE ProInXML;
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
IF OBJECT_ID(N'integracion.Fuente',N'U') IS NOT NULL THROW 50210,'El esquema MVP requiere migracion previa a integracion.Consulta.',1;
GO
IF SCHEMA_ID(N'seguridad') IS NULL EXEC(N'CREATE SCHEMA seguridad AUTHORIZATION dbo');
IF SCHEMA_ID(N'catalogo') IS NULL EXEC(N'CREATE SCHEMA catalogo AUTHORIZATION dbo');
IF SCHEMA_ID(N'auditoria') IS NULL EXEC(N'CREATE SCHEMA auditoria AUTHORIZATION dbo');
IF SCHEMA_ID(N'integracion') IS NULL EXEC(N'CREATE SCHEMA integracion AUTHORIZATION dbo');
IF SCHEMA_ID(N'datos') IS NULL EXEC(N'CREATE SCHEMA datos AUTHORIZATION dbo');
IF SCHEMA_ID(N'modelo') IS NULL EXEC(N'CREATE SCHEMA modelo AUTHORIZATION dbo');
IF SCHEMA_ID(N'reportes') IS NULL EXEC(N'CREATE SCHEMA reportes AUTHORIZATION dbo');
IF SCHEMA_ID(N'analisis') IS NULL EXEC(N'CREATE SCHEMA analisis AUTHORIZATION dbo');
IF DATABASE_PRINCIPAL_ID(N'proinxml_app') IS NULL CREATE ROLE proinxml_app AUTHORIZATION dbo;
GO

IF OBJECT_ID(N'seguridad.Rol',N'U') IS NULL
BEGIN
    CREATE TABLE seguridad.Rol(
        [Id] bigint IDENTITY(1,1) NOT NULL,
        [Nombre] nvarchar(40) NOT NULL,
        [CreadoUtc] datetime2(3) NOT NULL CONSTRAINT [DF_seguridad_Rol_CreadoUtc] DEFAULT (sysutcdatetime()),
        CONSTRAINT [PK_seguridad_Rol] PRIMARY KEY CLUSTERED ([Id]),
        CONSTRAINT [UQ_Rol_Nombre] UNIQUE ([Nombre])
    );
END;
GO

IF OBJECT_ID(N'seguridad.Usuario',N'U') IS NULL
BEGIN
    CREATE TABLE seguridad.Usuario(
        [Id] bigint IDENTITY(1,1) NOT NULL,
        [NombreUsuario] nvarchar(80) NOT NULL,
        [NombreCompleto] nvarchar(160) NOT NULL,
        [HashContrasena] nvarchar(500) NOT NULL,
        [RolId] bigint NOT NULL,
        [Activo] bit NOT NULL CONSTRAINT [DF_seguridad_Usuario_Activo] DEFAULT ((1)),
        [CreadoUtc] datetime2(3) NOT NULL CONSTRAINT [DF_seguridad_Usuario_CreadoUtc] DEFAULT (sysutcdatetime()),
        CONSTRAINT [PK_seguridad_Usuario] PRIMARY KEY CLUSTERED ([Id]),
        CONSTRAINT [UQ_Usuario_NombreUsuario] UNIQUE ([NombreUsuario])
    );
END;
GO

IF OBJECT_ID(N'seguridad.EventoAcceso',N'U') IS NULL
BEGIN
    CREATE TABLE seguridad.EventoAcceso(
        [Id] bigint IDENTITY(1,1) NOT NULL,
        [UsuarioId] bigint NULL,
        [NombreIntentado] nvarchar(80) NOT NULL,
        [Evento] nvarchar(80) NOT NULL,
        [Exitoso] bit NOT NULL,
        [Ip] nvarchar(64) NULL,
        [FechaUtc] datetime2(3) NOT NULL CONSTRAINT [DF_seguridad_EventoAcceso_FechaUtc] DEFAULT (sysutcdatetime()),
        [CreadoUtc] datetime2(3) NOT NULL CONSTRAINT [DF_seguridad_EventoAcceso_CreadoUtc] DEFAULT (sysutcdatetime()),
        CONSTRAINT [PK_seguridad_EventoAcceso] PRIMARY KEY CLUSTERED ([Id])
    );
END;
GO

IF OBJECT_ID(N'catalogo.TipoActProy',N'U') IS NULL
BEGIN
    CREATE TABLE catalogo.TipoActProy(
        [Id] bigint NOT NULL,
        [Nombre] nvarchar(40) NOT NULL,
        [CreadoUtc] datetime2(3) NOT NULL CONSTRAINT [DF_catalogo_TipoActProy_CreadoUtc] DEFAULT (sysutcdatetime()),
        CONSTRAINT [PK_catalogo_TipoActProy] PRIMARY KEY CLUSTERED ([Id]),
        CONSTRAINT [CK_catalogo_TipoActProy_01] CHECK ([Id]=(3) OR [Id]=(2))
    );
END;
GO

IF OBJECT_ID(N'auditoria.Cambio',N'U') IS NULL
BEGIN
    CREATE TABLE auditoria.Cambio(
        [Id] bigint IDENTITY(1,1) NOT NULL,
        [Tabla] nvarchar(128) NOT NULL,
        [RegistroId] bigint NOT NULL,
        [Operacion] char(1) NOT NULL,
        [FechaUtc] datetime2(3) NOT NULL CONSTRAINT [DF_auditoria_Cambio_FechaUtc] DEFAULT (sysutcdatetime()),
        [Actor] nvarchar(128) NOT NULL,
        [LoginSql] nvarchar(128) NOT NULL,
        [Correlacion] uniqueidentifier NULL,
        [Antes] nvarchar(max) NULL,
        [Despues] nvarchar(max) NULL,
        [UsuarioId] bigint NULL,
        [Rol] nvarchar(40) NOT NULL CONSTRAINT [DF_auditoria_Cambio_Rol] DEFAULT (N'Sin identificar'),
        [CreadoUtc] datetime2(3) NOT NULL CONSTRAINT [DF_auditoria_Cambio_CreadoUtc] DEFAULT (sysutcdatetime()),
        CONSTRAINT [PK_auditoria_Cambio] PRIMARY KEY CLUSTERED ([Id]),
        CONSTRAINT [CK_auditoria_Cambio_01] CHECK ([Antes] IS NULL OR isjson([Antes])=(1)),
        CONSTRAINT [CK_auditoria_Cambio_02] CHECK ([Despues] IS NULL OR isjson([Despues])=(1)),
        CONSTRAINT [CK_auditoria_Cambio_03] CHECK ([Operacion]='D' OR [Operacion]='U' OR [Operacion]='I')
    );
END;
IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'auditoria.Cambio') AND name=N'IX_Cambio_Registro')
    CREATE INDEX [IX_Cambio_Registro] ON auditoria.Cambio([Tabla],[RegistroId],[Id]);
IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'auditoria.Cambio') AND name=N'IX_Cambio_Correlacion')
    CREATE INDEX [IX_Cambio_Correlacion] ON auditoria.Cambio([Correlacion],[Id]);
IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'auditoria.Cambio') AND name=N'IX_Cambio_Fecha')
    CREATE INDEX [IX_Cambio_Fecha] ON auditoria.Cambio([FechaUtc],[Id]);
GO

IF OBJECT_ID(N'integracion.Servicio',N'U') IS NULL
BEGIN
    CREATE TABLE integracion.Servicio(
        [Id] bigint IDENTITY(1,1) NOT NULL,
        [Nombre] nvarchar(160) NOT NULL,
        [UrlBase] nvarchar(200) NOT NULL,
        [Ruta] nvarchar(400) NOT NULL,
        [VersionContrato] varchar(32) NOT NULL,
        [Activo] bit NOT NULL CONSTRAINT [DF_integracion_Servicio_Activo] DEFAULT ((1)),
        [CreadoUtc] datetime2(3) NOT NULL CONSTRAINT [DF_integracion_Servicio_CreadoUtc] DEFAULT (sysutcdatetime()),
        CONSTRAINT [PK_integracion_Servicio] PRIMARY KEY CLUSTERED ([Id]),
        CONSTRAINT [UQ_Servicio_Endpoint] UNIQUE ([UrlBase],[Ruta])
    );
END;
GO

IF OBJECT_ID(N'integracion.Lote',N'U') IS NULL
BEGIN
    CREATE TABLE integracion.Lote(
        [Id] bigint IDENTITY(1,1) NOT NULL,
        [Nombre] nvarchar(260) NOT NULL,
        [CreadoUtc] datetime2(3) NOT NULL CONSTRAINT [DF_integracion_Lote_CreadoUtc] DEFAULT (sysutcdatetime()),
        [CreadoPorUsuarioId] bigint NOT NULL,
        CONSTRAINT [PK_integracion_Lote] PRIMARY KEY CLUSTERED ([Id])
    );
END;
GO

IF OBJECT_ID(N'integracion.Consulta',N'U') IS NULL
BEGIN
    CREATE TABLE integracion.Consulta(
        [Id] bigint IDENTITY(1,1) NOT NULL,
        [Url] nvarchar(1000) NOT NULL,
        [AnoEje] smallint NOT NULL,
        [NivelGobierno] varchar(8) NOT NULL,
        [SecEjec] int NOT NULL,
        [DocumentoActualId] bigint NULL,
        [CreadoUtc] datetime2(3) NOT NULL CONSTRAINT [DF_integracion_Consulta_CreadoUtc] DEFAULT (sysutcdatetime()),
        [ServicioId] bigint NOT NULL,
        CONSTRAINT [PK_integracion_Consulta] PRIMARY KEY CLUSTERED ([Id]),
        CONSTRAINT [UQ_Consulta_Parametros] UNIQUE ([ServicioId],[AnoEje],[NivelGobierno],[SecEjec]),
        CONSTRAINT [CK_integracion_Consulta_01] CHECK ([AnoEje]>=(1900) AND [AnoEje]<=(2100)),
        CONSTRAINT [CK_integracion_Consulta_02] CHECK ([SecEjec]>(0))
    );
END;
GO

IF OBJECT_ID(N'integracion.Trabajo',N'U') IS NULL
BEGIN
    CREATE TABLE integracion.Trabajo(
        [Id] bigint IDENTITY(1,1) NOT NULL,
        [LoteId] bigint NOT NULL,
        [ConsultaId] bigint NOT NULL,
        [Estado] varchar(24) NOT NULL CONSTRAINT [DF_integracion_Trabajo_Estado] DEFAULT ('Pendiente'),
        [Intentos] int NOT NULL CONSTRAINT [DF_integracion_Trabajo_Intentos] DEFAULT ((0)),
        [MaxIntentos] int NOT NULL CONSTRAINT [DF_integracion_Trabajo_MaxIntentos] DEFAULT ((4)),
        [ProximoIntentoUtc] datetime2(3) NOT NULL CONSTRAINT [DF_integracion_Trabajo_ProximoIntentoUtc] DEFAULT (sysutcdatetime()),
        [LeaseHastaUtc] datetime2(3) NULL,
        [Token] uniqueidentifier NULL,
        [UltimoError] nvarchar(2000) NULL,
        [CreadoUtc] datetime2(3) NOT NULL CONSTRAINT [DF_integracion_Trabajo_CreadoUtc] DEFAULT (sysutcdatetime()),
        [FinalizadoUtc] datetime2(3) NULL,
        [DocumentoId] bigint NULL,
        CONSTRAINT [PK_integracion_Trabajo] PRIMARY KEY CLUSTERED ([Id]),
        CONSTRAINT [UQ_Trabajo_LoteConsulta] UNIQUE ([LoteId],[ConsultaId]),
        CONSTRAINT [CK_integracion_Trabajo_01] CHECK ([Intentos]>=(0)),
        CONSTRAINT [CK_integracion_Trabajo_02] CHECK ([MaxIntentos]>=(1) AND [MaxIntentos]<=(10)),
        CONSTRAINT [CK_integracion_Trabajo_03] CHECK ([Estado]='Cancelado' OR [Estado]='YaCargada' OR [Estado]='Fallido' OR [Estado]='CompletadoSinDatos' OR [Estado]='Completado' OR [Estado]='EnCurso' OR [Estado]='Pendiente')
    );
END;
IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'integracion.Trabajo') AND name=N'IX_Trabajo_Cola')
    CREATE INDEX [IX_Trabajo_Cola] ON integracion.Trabajo([Estado],[ProximoIntentoUtc],[Id]) INCLUDE([LeaseHastaUtc],[Intentos],[MaxIntentos]);
GO

IF OBJECT_ID(N'integracion.Intento',N'U') IS NULL
BEGIN
    CREATE TABLE integracion.Intento(
        [Id] bigint IDENTITY(1,1) NOT NULL,
        [TrabajoId] bigint NOT NULL,
        [Numero] int NOT NULL,
        [Estado] varchar(24) NOT NULL CONSTRAINT [DF_integracion_Intento_Estado] DEFAULT ('EnCurso'),
        [InicioUtc] datetime2(3) NOT NULL CONSTRAINT [DF_integracion_Intento_InicioUtc] DEFAULT (sysutcdatetime()),
        [FinUtc] datetime2(3) NULL,
        [HttpStatus] int NULL,
        [Error] nvarchar(2000) NULL,
        [Etapa] nvarchar(40) NOT NULL CONSTRAINT [DF_integracion_Intento_Etapa] DEFAULT (N'Descarga'),
        [UrlSolicitada] nvarchar(1000) NOT NULL,
        [DocumentoId] bigint NULL,
        [RegistrosLeidos] int NULL,
        [RegistrosInsertados] int NULL,
        [RegistrosReutilizados] int NULL,
        [RegistrosRechazados] int NULL,
        [Observaciones] int NULL,
        [CreadoUtc] datetime2(3) NOT NULL CONSTRAINT [DF_integracion_Intento_CreadoUtc] DEFAULT (sysutcdatetime()),
        CONSTRAINT [PK_integracion_Intento] PRIMARY KEY CLUSTERED ([Id]),
        CONSTRAINT [UQ_Intento_Numero] UNIQUE ([TrabajoId],[Numero]),
        CONSTRAINT [CK_integracion_Intento_01] CHECK ([Estado]='Interrumpido' OR [Estado]='Error' OR [Estado]='Completado' OR [Estado]='EnCurso')
    );
END;
IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'integracion.Intento') AND name=N'IX_Intento_Trabajo')
    CREATE INDEX [IX_Intento_Trabajo] ON integracion.Intento([TrabajoId],[Numero] DESC) INCLUDE([HttpStatus],[Estado],[FinUtc]);
GO

IF OBJECT_ID(N'integracion.Documento',N'U') IS NULL
BEGIN
    CREATE TABLE integracion.Documento(
        [Id] bigint IDENTITY(1,1) NOT NULL,
        [ConsultaId] bigint NOT NULL,
        [IntentoId] bigint NOT NULL,
        [Sha256] char(64) NOT NULL,
        [Respuesta] varbinary(max) NOT NULL,
        [ContentType] nvarchar(200) NULL,
        [EsValido] bit NOT NULL CONSTRAINT [DF_integracion_Documento_EsValido] DEFAULT ((0)),
        [CantidadRegistros] int NULL,
        [ErrorValidacion] nvarchar(2000) NULL,
        [CreadoUtc] datetime2(3) NOT NULL CONSTRAINT [DF_integracion_Documento_CreadoUtc] DEFAULT (sysutcdatetime()),
        CONSTRAINT [PK_integracion_Documento] PRIMARY KEY CLUSTERED ([Id]),
        CONSTRAINT [UQ_Documento_ConsultaId] UNIQUE ([ConsultaId],[Id]),
        CONSTRAINT [UQ_Documento_Hash] UNIQUE ([ConsultaId],[Sha256]),
        CONSTRAINT [CK_integracion_Documento_01] CHECK ([CantidadRegistros]>=(0))
    );
END;
GO

IF OBJECT_ID(N'integracion.ObservacionDato',N'U') IS NULL
BEGIN
    CREATE TABLE integracion.ObservacionDato(
        [Id] bigint IDENTITY(1,1) NOT NULL,
        [DocumentoId] bigint NOT NULL,
        [OrdinalItem] int NOT NULL,
        [Campo] varchar(64) NOT NULL,
        [CodigoObservacion] varchar(64) NOT NULL,
        [Severidad] varchar(16) NOT NULL,
        [Detalle] nvarchar(1000) NOT NULL,
        [FechaUtc] datetime2(3) NOT NULL CONSTRAINT [DF_integracion_ObservacionDato_FechaUtc] DEFAULT (sysutcdatetime()),
        [CreadoUtc] datetime2(3) NOT NULL CONSTRAINT [DF_integracion_ObservacionDato_CreadoUtc] DEFAULT (sysutcdatetime()),
        CONSTRAINT [PK_integracion_ObservacionDato] PRIMARY KEY CLUSTERED ([Id]),
        CONSTRAINT [UQ_Observacion_Origen] UNIQUE ([DocumentoId],[OrdinalItem],[Campo],[CodigoObservacion]),
        CONSTRAINT [CK_integracion_ObservacionDato_01] CHECK ([Severidad]='Error' OR [Severidad]='Advertencia' OR [Severidad]='Info')
    );
END;
GO

IF OBJECT_ID(N'datos.Gasto',N'U') IS NULL
BEGIN
    CREATE TABLE datos.Gasto(
        [Id] bigint IDENTITY(1,1) NOT NULL,
        [DocumentoId] bigint NOT NULL,
        [Ordinal] int NOT NULL,
        [AnoEje] smallint NOT NULL,
        [MesEje] tinyint NOT NULL,
        [SecEjec] int NOT NULL,
        [TipoActProy] bigint NOT NULL,
        [IdNivelGobierno] varchar(32) NOT NULL,
        [Sub_tipo_gobierno] varchar(32) NOT NULL,
        [IdSector] varchar(32) NOT NULL,
        [IdPliego] varchar(32) NOT NULL,
        [IdEjecutora] varchar(32) NOT NULL,
        [Funcion] varchar(32) NOT NULL,
        [Programa] varchar(32) NOT NULL,
        [Programa_ppto] varchar(32) NOT NULL,
        [Categ_gasto] varchar(32) NOT NULL,
        [Tipo_transaccion] varchar(32) NOT NULL,
        [Generica] varchar(32) NOT NULL,
        [Subgenerica] varchar(32) NOT NULL,
        [Subgenerica_det] varchar(32) NOT NULL,
        [Especifica] varchar(32) NOT NULL,
        [Especifica_det] varchar(32) NOT NULL,
        [SecFunc] varchar(32) NOT NULL,
        [IdFuente] varchar(32) NOT NULL,
        [IdRubro] varchar(32) NOT NULL,
        [IdTipoRecurso] varchar(32) NOT NULL,
        [IdComponente] varchar(32) NOT NULL,
        [IdProyecto] varchar(32) NOT NULL,
        [IdMeta] varchar(32) NOT NULL,
        [IdFinalidad] varchar(32) NOT NULL,
        [IdProyectoSNIP] varchar(32) NOT NULL,
        [Departamento] varchar(32) NOT NULL,
        [Provincia] varchar(32) NOT NULL,
        [Distrito] varchar(32) NOT NULL,
        [Unidad_Medida] varchar(32) NULL,
        [PIA] decimal(19,4) NOT NULL,
        [PIM] decimal(19,4) NOT NULL,
        [Certificado] decimal(19,4) NOT NULL,
        [CompAnual] decimal(19,4) NOT NULL,
        [AtencionCompMensual] decimal(19,4) NOT NULL,
        [Devengado] decimal(19,4) NOT NULL,
        [Girado] decimal(19,4) NOT NULL,
        [CreadoUtc] datetime2(3) NOT NULL CONSTRAINT [DF_datos_Gasto_CreadoUtc] DEFAULT (sysutcdatetime()),
        CONSTRAINT [PK_datos_Gasto] PRIMARY KEY CLUSTERED ([Id]),
        CONSTRAINT [UQ_Gasto_DocumentoOrdinal] UNIQUE ([DocumentoId],[Ordinal]),
        CONSTRAINT [CK_datos_Gasto_01] CHECK ([AnoEje]>=(1900) AND [AnoEje]<=(2100)),
        CONSTRAINT [CK_datos_Gasto_02] CHECK ([MesEje]>=(0) AND [MesEje]<=(12)),
        CONSTRAINT [CK_datos_Gasto_03] CHECK ([Ordinal]>(0)),
        CONSTRAINT [CK_datos_Gasto_04] CHECK ([SecEjec]>(0))
    );
END;
IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'datos.Gasto') AND name=N'IX_Gasto_Consulta')
    CREATE INDEX [IX_Gasto_Consulta] ON datos.Gasto([AnoEje],[IdNivelGobierno],[SecEjec],[Id]) INCLUDE([DocumentoId],[TipoActProy],[PIA],[PIM],[Devengado]);
GO

IF OBJECT_ID(N'auditoria.CargaDocumento',N'U') IS NULL
BEGIN
    CREATE TABLE auditoria.CargaDocumento(
        [Id] bigint IDENTITY(1,1) NOT NULL,
        [DocumentoId] bigint NOT NULL,
        [LoteId] bigint NOT NULL,
        [UsuarioId] bigint NULL,
        [Rol] nvarchar(40) NOT NULL,
        [FilasInsertadas] int NOT NULL,
        [FilasReutilizadas] int NOT NULL,
        [FechaUtc] datetime2(3) NOT NULL CONSTRAINT [DF_auditoria_CargaDocumento_FechaUtc] DEFAULT (sysutcdatetime()),
        [CreadoUtc] datetime2(3) NOT NULL CONSTRAINT [DF_auditoria_CargaDocumento_CreadoUtc] DEFAULT (sysutcdatetime()),
        CONSTRAINT [PK_auditoria_CargaDocumento] PRIMARY KEY CLUSTERED ([Id]),
        CONSTRAINT [UQ_Carga_Documento] UNIQUE ([DocumentoId])
    );
END;
GO
-- Relaciones posteriores a las tablas para resolver referencias circulares.
IF NOT EXISTS(SELECT 1 FROM sys.foreign_keys WHERE parent_object_id=OBJECT_ID(N'seguridad.Usuario') AND name=N'FK_Usuario_Rol')
    ALTER TABLE seguridad.Usuario ADD CONSTRAINT [FK_Usuario_Rol] FOREIGN KEY([RolId]) REFERENCES seguridad.Rol([Id]);
IF NOT EXISTS(SELECT 1 FROM sys.foreign_keys WHERE parent_object_id=OBJECT_ID(N'seguridad.EventoAcceso') AND name=N'FK_EventoAcceso_Usuario')
    ALTER TABLE seguridad.EventoAcceso ADD CONSTRAINT [FK_EventoAcceso_Usuario] FOREIGN KEY([UsuarioId]) REFERENCES seguridad.Usuario([Id]);
IF NOT EXISTS(SELECT 1 FROM sys.foreign_keys WHERE parent_object_id=OBJECT_ID(N'auditoria.Cambio') AND name=N'FK_Cambio_Usuario')
    ALTER TABLE auditoria.Cambio ADD CONSTRAINT [FK_Cambio_Usuario] FOREIGN KEY([UsuarioId]) REFERENCES seguridad.Usuario([Id]);
IF NOT EXISTS(SELECT 1 FROM sys.foreign_keys WHERE parent_object_id=OBJECT_ID(N'integracion.Lote') AND name=N'FK_Lote_Usuario')
    ALTER TABLE integracion.Lote ADD CONSTRAINT [FK_Lote_Usuario] FOREIGN KEY([CreadoPorUsuarioId]) REFERENCES seguridad.Usuario([Id]);
IF NOT EXISTS(SELECT 1 FROM sys.foreign_keys WHERE parent_object_id=OBJECT_ID(N'integracion.Consulta') AND name=N'FK_Consulta_Servicio')
    ALTER TABLE integracion.Consulta ADD CONSTRAINT [FK_Consulta_Servicio] FOREIGN KEY([ServicioId]) REFERENCES integracion.Servicio([Id]);
IF NOT EXISTS(SELECT 1 FROM sys.foreign_keys WHERE parent_object_id=OBJECT_ID(N'integracion.Consulta') AND referenced_object_id=OBJECT_ID(N'integracion.Documento'))
    ALTER TABLE integracion.Consulta ADD CONSTRAINT [FK_Consulta_DocumentoActual] FOREIGN KEY([Id],[DocumentoActualId]) REFERENCES integracion.Documento([ConsultaId],[Id]);
IF NOT EXISTS(SELECT 1 FROM sys.foreign_keys WHERE parent_object_id=OBJECT_ID(N'integracion.Trabajo') AND name=N'FK_Trabajo_ConsultaId')
    ALTER TABLE integracion.Trabajo ADD CONSTRAINT [FK_Trabajo_ConsultaId] FOREIGN KEY([ConsultaId]) REFERENCES integracion.Consulta([Id]);
IF NOT EXISTS(SELECT 1 FROM sys.foreign_keys WHERE parent_object_id=OBJECT_ID(N'integracion.Trabajo') AND name=N'FK_Trabajo_Documento')
    ALTER TABLE integracion.Trabajo ADD CONSTRAINT [FK_Trabajo_Documento] FOREIGN KEY([ConsultaId],[DocumentoId]) REFERENCES integracion.Documento([ConsultaId],[Id]);
IF NOT EXISTS(SELECT 1 FROM sys.foreign_keys WHERE parent_object_id=OBJECT_ID(N'integracion.Trabajo') AND name=N'FK_Trabajo_LoteId')
    ALTER TABLE integracion.Trabajo ADD CONSTRAINT [FK_Trabajo_LoteId] FOREIGN KEY([LoteId]) REFERENCES integracion.Lote([Id]);
IF NOT EXISTS(SELECT 1 FROM sys.foreign_keys WHERE parent_object_id=OBJECT_ID(N'integracion.Intento') AND name=N'FK_Intento_Documento')
    ALTER TABLE integracion.Intento ADD CONSTRAINT [FK_Intento_Documento] FOREIGN KEY([DocumentoId]) REFERENCES integracion.Documento([Id]);
IF NOT EXISTS(SELECT 1 FROM sys.foreign_keys WHERE parent_object_id=OBJECT_ID(N'integracion.Intento') AND name=N'FK_Intento_TrabajoId')
    ALTER TABLE integracion.Intento ADD CONSTRAINT [FK_Intento_TrabajoId] FOREIGN KEY([TrabajoId]) REFERENCES integracion.Trabajo([Id]);
IF NOT EXISTS(SELECT 1 FROM sys.foreign_keys WHERE parent_object_id=OBJECT_ID(N'integracion.Documento') AND name=N'FK_Documento_ConsultaId')
    ALTER TABLE integracion.Documento ADD CONSTRAINT [FK_Documento_ConsultaId] FOREIGN KEY([ConsultaId]) REFERENCES integracion.Consulta([Id]);
IF NOT EXISTS(SELECT 1 FROM sys.foreign_keys WHERE parent_object_id=OBJECT_ID(N'integracion.Documento') AND name=N'FK_Documento_IntentoId')
    ALTER TABLE integracion.Documento ADD CONSTRAINT [FK_Documento_IntentoId] FOREIGN KEY([IntentoId]) REFERENCES integracion.Intento([Id]);
IF NOT EXISTS(SELECT 1 FROM sys.foreign_keys WHERE parent_object_id=OBJECT_ID(N'integracion.ObservacionDato') AND name=N'FK_Observacion_Documento')
    ALTER TABLE integracion.ObservacionDato ADD CONSTRAINT [FK_Observacion_Documento] FOREIGN KEY([DocumentoId]) REFERENCES integracion.Documento([Id]);
IF NOT EXISTS(SELECT 1 FROM sys.foreign_keys WHERE parent_object_id=OBJECT_ID(N'datos.Gasto') AND name=N'FK_datos_Gasto_DocumentoId')
    ALTER TABLE datos.Gasto ADD CONSTRAINT [FK_datos_Gasto_DocumentoId] FOREIGN KEY([DocumentoId]) REFERENCES integracion.Documento([Id]);
IF NOT EXISTS(SELECT 1 FROM sys.foreign_keys WHERE parent_object_id=OBJECT_ID(N'auditoria.CargaDocumento') AND name=N'FK_Carga_Usuario')
    ALTER TABLE auditoria.CargaDocumento ADD CONSTRAINT [FK_Carga_Usuario] FOREIGN KEY([UsuarioId]) REFERENCES seguridad.Usuario([Id]);
GO
INSERT seguridad.Rol(Nombre)
SELECT v.Nombre FROM (VALUES(N'Administrador'),(N'Operador'),(N'Consulta'))v(Nombre)
WHERE NOT EXISTS(SELECT 1 FROM seguridad.Rol r WHERE r.Nombre=v.Nombre);
IF NOT EXISTS(SELECT 1 FROM seguridad.Usuario WHERE NombreUsuario=N'sistema')
    INSERT seguridad.Usuario(NombreUsuario,NombreCompleto,HashContrasena,RolId,Activo)
    SELECT N'sistema',N'Proceso de integracion',N'!no-login!',Id,0 FROM seguridad.Rol WHERE Nombre=N'Administrador';
IF NOT EXISTS(SELECT 1 FROM integracion.Servicio)
    INSERT integracion.Servicio(Nombre,UrlBase,Ruta,VersionContrato)
    VALUES(N'MEF Gasto PIP',N'http://s3.mef.gob.pe',N'/servicios/WSPCM/SG/gastopipsg-old.asmx/ObtenerDataGastoPIP_old_2','1');
IF NOT EXISTS(SELECT 1 FROM catalogo.TipoActProy WHERE Id=2)
    INSERT catalogo.TipoActProy(Id,Nombre) VALUES(2,N'Proyecto');
IF NOT EXISTS(SELECT 1 FROM catalogo.TipoActProy WHERE Id=3)
    INSERT catalogo.TipoActProy(Id,Nombre) VALUES(3,N'Actividad');
GO
