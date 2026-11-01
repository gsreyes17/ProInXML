-- ProInXML 1.0: tablas base, relaciones, indices y semillas del sistema.
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
IF SCHEMA_ID(N'auditoria') IS NULL EXEC(N'CREATE SCHEMA auditoria AUTHORIZATION dbo');
IF SCHEMA_ID(N'integracion') IS NULL EXEC(N'CREATE SCHEMA integracion AUTHORIZATION dbo');
IF SCHEMA_ID(N'staging') IS NULL EXEC(N'CREATE SCHEMA staging AUTHORIZATION dbo');
IF SCHEMA_ID(N'modelo') IS NULL EXEC(N'CREATE SCHEMA modelo AUTHORIZATION dbo');
IF SCHEMA_ID(N'reportes') IS NULL EXEC(N'CREATE SCHEMA reportes AUTHORIZATION dbo');
IF SCHEMA_ID(N'analisis') IS NULL EXEC(N'CREATE SCHEMA analisis AUTHORIZATION dbo');
IF DATABASE_PRINCIPAL_ID(N'proinxml_app') IS NULL CREATE ROLE proinxml_app AUTHORIZATION dbo;
GO
-- Conserva las filas y la identidad de la tabla antigua al actualizar una base existente.
IF OBJECT_ID(N'datos.Gasto',N'U') IS NOT NULL AND OBJECT_ID(N'staging.Gasto',N'U') IS NULL
    ALTER SCHEMA staging TRANSFER datos.Gasto;
GO

-- Unificar siglas de columnas existentes antes de recrear vistas y procedimientos.
-- En una base nueva las tablas aun no existen, por lo que este bloque no cambia nada.
IF EXISTS(SELECT 1 FROM sys.columns
    WHERE object_id=OBJECT_ID(N'analisis.MetricaIntento')
      AND name COLLATE Latin1_General_100_CS_AS=N'EsperaSqlMs')
    AND OBJECT_ID(N'analisis.CK_Metrica_Tiempos', N'C') IS NOT NULL
    ALTER TABLE analisis.MetricaIntento DROP CONSTRAINT CK_Metrica_Tiempos;
DECLARE @ColumnaObjeto nvarchar(776), @ColumnaNueva sysname;
DECLARE columnas_siglas CURSOR LOCAL FAST_FORWARD FOR
    SELECT QUOTENAME(s.name) + N'.' + QUOTENAME(t.name) + N'.' + QUOTENAME(c.name),
        REPLACE(REPLACE(REPLACE(REPLACE(
            c.name COLLATE Latin1_General_100_CS_AS,
            N'Utc', N'UTC'), N'Sql', N'SQL'), N'Http', N'HTTP'), N'Url', N'URL')
    FROM sys.columns c
    JOIN sys.tables t ON t.object_id = c.object_id
    JOIN sys.schemas s ON s.schema_id = t.schema_id
    WHERE s.name IN (N'integracion',N'staging',N'modelo',
        N'seguridad',N'auditoria',N'analisis')
      AND (c.name COLLATE Latin1_General_100_CS_AS LIKE N'%Utc%'
        OR c.name COLLATE Latin1_General_100_CS_AS LIKE N'%Sql%'
        OR c.name COLLATE Latin1_General_100_CS_AS LIKE N'%Http%'
        OR c.name COLLATE Latin1_General_100_CS_AS LIKE N'%Url%');
OPEN columnas_siglas;
FETCH NEXT FROM columnas_siglas INTO @ColumnaObjeto, @ColumnaNueva;
WHILE @@FETCH_STATUS = 0
BEGIN
    EXEC sys.sp_rename @objname=@ColumnaObjeto, @newname=@ColumnaNueva, @objtype=N'COLUMN';
    FETCH NEXT FROM columnas_siglas INTO @ColumnaObjeto, @ColumnaNueva;
END;
CLOSE columnas_siglas;
DEALLOCATE columnas_siglas;
IF COL_LENGTH(N'analisis.MetricaIntento', N'EsperaSQLMs') IS NOT NULL
    AND OBJECT_ID(N'analisis.CK_Metrica_Tiempos', N'C') IS NULL
    ALTER TABLE analisis.MetricaIntento WITH CHECK ADD CONSTRAINT CK_Metrica_Tiempos CHECK(
        (DescargaMs IS NULL OR DescargaMs>=0) AND (OriginalMs IS NULL OR OriginalMs>=0) AND
        (EsperaSQLMs IS NULL OR EsperaSQLMs>=0) AND (ValidacionMs IS NULL OR ValidacionMs>=0) AND
        (InsercionMs IS NULL OR InsercionMs>=0) AND (NormalizacionMs IS NULL OR NormalizacionMs>=0) AND
        (ConfirmacionMs IS NULL OR ConfirmacionMs>=0) AND (TotalMs IS NULL OR TotalMs>=0));
GO

-- Mueve los codigos observados a modelo.TipoActProy sin inventar nombres.
-- Durante la migracion se conserva el Id usado por los hechos ya existentes.
IF OBJECT_ID(N'modelo.Gasto',N'U') IS NOT NULL
BEGIN
    IF OBJECT_ID(N'modelo.TipoActProy',N'U') IS NULL
        CREATE TABLE modelo.TipoActProy(
            Id bigint IDENTITY CONSTRAINT PK_modelo_TipoActProy PRIMARY KEY,
            Codigo bigint NOT NULL CONSTRAINT UQ_TipoActProy_Clave UNIQUE
        );
    IF COL_LENGTH(N'modelo.Gasto',N'TipoActProy') IS NOT NULL
        AND COL_LENGTH(N'modelo.Gasto',N'TipoActProyId') IS NOT NULL
        THROW 50211,'El modelo tiene ambas columnas TipoActProy; revisar migracion.',1;
    IF COL_LENGTH(N'modelo.Gasto',N'TipoActProy') IS NOT NULL
    BEGIN
        IF OBJECT_ID(N'modelo.GastoReconstruido',N'V') IS NOT NULL DROP VIEW modelo.GastoReconstruido;
        IF OBJECT_ID(N'modelo.GastoActual',N'V') IS NOT NULL DROP VIEW modelo.GastoActual;
        SET IDENTITY_INSERT modelo.TipoActProy ON;
        EXEC(N'INSERT modelo.TipoActProy(Id,Codigo)
               SELECT DISTINCT g.TipoActProy,g.TipoActProy FROM modelo.Gasto g
               WHERE NOT EXISTS(SELECT 1 FROM modelo.TipoActProy t WHERE t.Id=g.TipoActProy)');
        SET IDENTITY_INSERT modelo.TipoActProy OFF;
        EXEC sys.sp_rename N'modelo.Gasto.TipoActProy',N'TipoActProyId',N'COLUMN';
    END;
    IF COL_LENGTH(N'modelo.Gasto',N'TipoActProyId') IS NOT NULL
    BEGIN
        IF OBJECT_ID(N'modelo.FK_modelo_Gasto_TipoActProy',N'F') IS NOT NULL
            ALTER TABLE modelo.Gasto DROP CONSTRAINT FK_modelo_Gasto_TipoActProy;
        SET IDENTITY_INSERT modelo.TipoActProy ON;
        INSERT modelo.TipoActProy(Id,Codigo)
        SELECT DISTINCT g.TipoActProyId,g.TipoActProyId FROM modelo.Gasto g
        WHERE NOT EXISTS(SELECT 1 FROM modelo.TipoActProy t WHERE t.Id=g.TipoActProyId);
        SET IDENTITY_INSERT modelo.TipoActProy OFF;
        IF OBJECT_ID(N'modelo.FK_Gasto_TipoActProyId',N'F') IS NULL
            ALTER TABLE modelo.Gasto WITH CHECK ADD CONSTRAINT FK_Gasto_TipoActProyId
                FOREIGN KEY(TipoActProyId) REFERENCES modelo.TipoActProy(Id);
    END;
END;
IF OBJECT_ID(N'catalogo.TipoActProy',N'U') IS NOT NULL
    DROP TABLE catalogo.TipoActProy;
IF SCHEMA_ID(N'catalogo') IS NOT NULL
    AND NOT EXISTS(SELECT 1 FROM sys.objects WHERE schema_id=SCHEMA_ID(N'catalogo'))
    EXEC(N'DROP SCHEMA catalogo');
GO

-- AnoEje y MesEje pertenecen al gasto, no a la clave institucional.
-- Una instalación anterior con hechos requiere una migración específica de sus
-- claves dependientes; detenerse antes de alterar datos evita mezclarlas.
IF OBJECT_ID(N'modelo.ContextoEjecutora',N'U') IS NOT NULL
   AND COL_LENGTH(N'modelo.ContextoEjecutora',N'AnoEje') IS NOT NULL
BEGIN
    IF EXISTS(SELECT 1 FROM modelo.ContextoEjecutora)
       OR (OBJECT_ID(N'modelo.Gasto',N'U') IS NOT NULL
           AND EXISTS(SELECT 1 FROM modelo.Gasto))
        THROW 50212,'Mover AnoEje al gasto requiere migrar los datos existentes; el esquema no se altero.',1;
    BEGIN TRANSACTION;
    IF OBJECT_ID(N'modelo.GastoReconstruido',N'V') IS NOT NULL DROP VIEW modelo.GastoReconstruido;
    IF OBJECT_ID(N'modelo.UQ_ContextoEjecutora_Clave',N'UQ') IS NOT NULL
        ALTER TABLE modelo.ContextoEjecutora DROP CONSTRAINT UQ_ContextoEjecutora_Clave;
    ALTER TABLE modelo.ContextoEjecutora DROP COLUMN AnoEje;
    ALTER TABLE modelo.ContextoEjecutora ADD CONSTRAINT UQ_ContextoEjecutora_Clave UNIQUE(EjecutoraId,SecEjec);
    IF OBJECT_ID(N'modelo.Gasto',N'U') IS NOT NULL
       AND COL_LENGTH(N'modelo.Gasto',N'AnoEje') IS NULL
        ALTER TABLE modelo.Gasto ADD AnoEje smallint NOT NULL;
    COMMIT;
END;
GO

IF OBJECT_ID(N'seguridad.Rol',N'U') IS NULL
BEGIN
    CREATE TABLE seguridad.Rol(
        [Id] bigint IDENTITY(1,1) NOT NULL,
        [Nombre] nvarchar(40) NOT NULL,
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
        [CreadoUTC] datetime2(3) NOT NULL CONSTRAINT [DF_seguridad_Usuario_CreadoUTC] DEFAULT (sysutcdatetime()),
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
        [FechaUTC] datetime2(3) NOT NULL CONSTRAINT [DF_seguridad_EventoAcceso_FechaUTC] DEFAULT (sysutcdatetime()),
        CONSTRAINT [PK_seguridad_EventoAcceso] PRIMARY KEY CLUSTERED ([Id])
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
        [FechaUTC] datetime2(3) NOT NULL CONSTRAINT [DF_auditoria_Cambio_FechaUTC] DEFAULT (sysutcdatetime()),
        [Actor] nvarchar(128) NOT NULL,
        [LoginSQL] nvarchar(128) NOT NULL,
        [Correlacion] uniqueidentifier NULL,
        [Antes] nvarchar(max) NULL,
        [Despues] nvarchar(max) NULL,
        [UsuarioId] bigint NULL,
        [Rol] nvarchar(40) NOT NULL CONSTRAINT [DF_auditoria_Cambio_Rol] DEFAULT (N'Sin identificar'),
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
    CREATE INDEX [IX_Cambio_Fecha] ON auditoria.Cambio([FechaUTC],[Id]);
GO

IF OBJECT_ID(N'integracion.Servicio',N'U') IS NULL
BEGIN
    CREATE TABLE integracion.Servicio(
        [Id] bigint IDENTITY(1,1) NOT NULL,
        [Nombre] nvarchar(160) NOT NULL,
        [URLBase] nvarchar(200) NOT NULL,
        [Ruta] nvarchar(400) NOT NULL,
        [VersionContrato] varchar(32) NOT NULL,
        [Activo] bit NOT NULL CONSTRAINT [DF_integracion_Servicio_Activo] DEFAULT ((1)),
        CONSTRAINT [PK_integracion_Servicio] PRIMARY KEY CLUSTERED ([Id]),
        CONSTRAINT [UQ_Servicio_Endpoint] UNIQUE ([URLBase],[Ruta])
    );
END;
GO

IF OBJECT_ID(N'integracion.Lote',N'U') IS NULL
BEGIN
    CREATE TABLE integracion.Lote(
        [Id] bigint IDENTITY(1,1) NOT NULL,
        [Nombre] nvarchar(260) NOT NULL,
        [CreadoUTC] datetime2(3) NOT NULL CONSTRAINT [DF_integracion_Lote_CreadoUTC] DEFAULT (sysutcdatetime()),
        [CreadoPorUsuarioId] bigint NOT NULL,
        CONSTRAINT [PK_integracion_Lote] PRIMARY KEY CLUSTERED ([Id])
    );
END;
GO

IF OBJECT_ID(N'integracion.Consulta',N'U') IS NULL
BEGIN
    CREATE TABLE integracion.Consulta(
        [Id] bigint IDENTITY(1,1) NOT NULL,
        [URL] nvarchar(1000) NOT NULL,
        [AnoEje] smallint NOT NULL,
        [NivelGobierno] varchar(8) NOT NULL,
        [SecEjec] int NOT NULL,
        [DocumentoActualId] bigint NULL,
        [CreadoUTC] datetime2(3) NOT NULL CONSTRAINT [DF_integracion_Consulta_CreadoUTC] DEFAULT (sysutcdatetime()),
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
        [ProximoIntentoUTC] datetime2(3) NOT NULL CONSTRAINT [DF_integracion_Trabajo_ProximoIntentoUTC] DEFAULT (sysutcdatetime()),
        [LeaseHastaUTC] datetime2(3) NULL,
        [Token] uniqueidentifier NULL,
        [UltimoError] nvarchar(2000) NULL,
        [CreadoUTC] datetime2(3) NOT NULL CONSTRAINT [DF_integracion_Trabajo_CreadoUTC] DEFAULT (sysutcdatetime()),
        [FinalizadoUTC] datetime2(3) NULL,
        [DocumentoId] bigint NULL,
        CONSTRAINT [PK_integracion_Trabajo] PRIMARY KEY CLUSTERED ([Id]),
        CONSTRAINT [UQ_Trabajo_LoteConsulta] UNIQUE ([LoteId],[ConsultaId]),
        CONSTRAINT [CK_integracion_Trabajo_01] CHECK ([Intentos]>=(0)),
        CONSTRAINT [CK_integracion_Trabajo_02] CHECK ([MaxIntentos]>=(1) AND [MaxIntentos]<=(10)),
        CONSTRAINT [CK_integracion_Trabajo_03] CHECK ([Estado]='Cancelado' OR [Estado]='YaCargada' OR [Estado]='Fallido' OR [Estado]='CompletadoSinDatos' OR [Estado]='Completado' OR [Estado]='EnCurso' OR [Estado]='Pendiente')
    );
END;
IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'integracion.Trabajo') AND name=N'IX_Trabajo_Cola')
    CREATE INDEX [IX_Trabajo_Cola] ON integracion.Trabajo([Estado],[ProximoIntentoUTC],[Id]) INCLUDE([LeaseHastaUTC],[Intentos],[MaxIntentos]);
GO

IF OBJECT_ID(N'integracion.Intento',N'U') IS NULL
BEGIN
    CREATE TABLE integracion.Intento(
        [Id] bigint IDENTITY(1,1) NOT NULL,
        [TrabajoId] bigint NOT NULL,
        [Numero] int NOT NULL,
        [Estado] varchar(24) NOT NULL CONSTRAINT [DF_integracion_Intento_Estado] DEFAULT ('EnCurso'),
        [InicioUTC] datetime2(3) NOT NULL CONSTRAINT [DF_integracion_Intento_InicioUTC] DEFAULT (sysutcdatetime()),
        [FinUTC] datetime2(3) NULL,
        [HTTPStatus] int NULL,
        [Error] nvarchar(2000) NULL,
        [Etapa] nvarchar(40) NOT NULL CONSTRAINT [DF_integracion_Intento_Etapa] DEFAULT (N'Descarga'),
        [URLSolicitada] nvarchar(1000) NOT NULL,
        [DocumentoId] bigint NULL,
        [RegistrosLeidos] int NULL,
        [RegistrosInsertados] int NULL,
        [RegistrosReutilizados] int NULL,
        [RegistrosRechazados] int NULL,
        [Observaciones] int NULL,
        CONSTRAINT [PK_integracion_Intento] PRIMARY KEY CLUSTERED ([Id]),
        CONSTRAINT [UQ_Intento_Numero] UNIQUE ([TrabajoId],[Numero]),
        CONSTRAINT [CK_integracion_Intento_01] CHECK ([Estado]='Interrumpido' OR [Estado]='Error' OR [Estado]='Completado' OR [Estado]='EnCurso')
    );
END;
IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'integracion.Intento') AND name=N'IX_Intento_Trabajo')
    CREATE INDEX [IX_Intento_Trabajo] ON integracion.Intento([TrabajoId],[Numero] DESC) INCLUDE([HTTPStatus],[Estado],[FinUTC]);
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
        [CreadoUTC] datetime2(3) NOT NULL CONSTRAINT [DF_integracion_Documento_CreadoUTC] DEFAULT (sysutcdatetime()),
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
        [FechaUTC] datetime2(3) NOT NULL CONSTRAINT [DF_integracion_ObservacionDato_FechaUTC] DEFAULT (sysutcdatetime()),
        CONSTRAINT [PK_integracion_ObservacionDato] PRIMARY KEY CLUSTERED ([Id]),
        CONSTRAINT [UQ_Observacion_Origen] UNIQUE ([DocumentoId],[OrdinalItem],[Campo],[CodigoObservacion]),
        CONSTRAINT [CK_integracion_ObservacionDato_01] CHECK ([Severidad]='Error' OR [Severidad]='Advertencia' OR [Severidad]='Info')
    );
END;
GO

IF OBJECT_ID(N'staging.Gasto',N'U') IS NULL
BEGIN
    CREATE TABLE staging.Gasto(
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
        CONSTRAINT [PK_staging_Gasto] PRIMARY KEY CLUSTERED ([Id]),
        CONSTRAINT [UQ_Gasto_DocumentoOrdinal] UNIQUE ([DocumentoId],[Ordinal]),
        CONSTRAINT [CK_staging_Gasto_01] CHECK ([AnoEje]>=(1900) AND [AnoEje]<=(2100)),
        CONSTRAINT [CK_staging_Gasto_02] CHECK ([MesEje]>=(0) AND [MesEje]<=(12)),
        CONSTRAINT [CK_staging_Gasto_03] CHECK ([Ordinal]>(0)),
        CONSTRAINT [CK_staging_Gasto_04] CHECK ([SecEjec]>(0))
    );
END;
IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'staging.Gasto') AND name=N'IX_Gasto_Consulta')
    CREATE INDEX [IX_Gasto_Consulta] ON staging.Gasto([AnoEje],[IdNivelGobierno],[SecEjec],[Id]) INCLUDE([DocumentoId],[TipoActProy],[PIA],[PIM],[Devengado]);
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
        [FechaUTC] datetime2(3) NOT NULL CONSTRAINT [DF_auditoria_CargaDocumento_FechaUTC] DEFAULT (sysutcdatetime()),
        [CreadoUTC] datetime2(3) NOT NULL CONSTRAINT [DF_auditoria_CargaDocumento_CreadoUTC] DEFAULT (sysutcdatetime()),
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
IF NOT EXISTS(SELECT 1 FROM sys.foreign_keys WHERE parent_object_id=OBJECT_ID(N'staging.Gasto') AND name IN(N'FK_datos_Gasto_DocumentoId',N'FK_staging_Gasto_DocumentoId'))
    ALTER TABLE staging.Gasto ADD CONSTRAINT [FK_staging_Gasto_DocumentoId] FOREIGN KEY([DocumentoId]) REFERENCES integracion.Documento([Id]);
IF NOT EXISTS(SELECT 1 FROM sys.foreign_keys WHERE parent_object_id=OBJECT_ID(N'auditoria.CargaDocumento') AND name=N'FK_Carga_Usuario')
    ALTER TABLE auditoria.CargaDocumento ADD CONSTRAINT [FK_Carga_Usuario] FOREIGN KEY([UsuarioId]) REFERENCES seguridad.Usuario([Id]);
GO
-- Retirar fechas redundantes de instalaciones anteriores. Las fechas de eventos
-- y de documentos permanecen en sus tablas correspondientes.
DECLARE @quitar TABLE(Esquema sysname,Tabla sysname);
INSERT @quitar(Esquema,Tabla) VALUES
 (N'staging',N'Gasto'),(N'seguridad',N'Rol'),(N'seguridad',N'EventoAcceso'),
 (N'auditoria',N'Cambio'),(N'integracion',N'Servicio'),
 (N'integracion',N'Intento'),(N'integracion',N'ObservacionDato');
DECLARE @esquema sysname,@tabla sysname,@objeto nvarchar(517),@default sysname,@sql nvarchar(max);
DECLARE fechas CURSOR LOCAL FAST_FORWARD FOR SELECT Esquema,Tabla FROM @quitar;
OPEN fechas;
FETCH NEXT FROM fechas INTO @esquema,@tabla;
WHILE @@FETCH_STATUS=0
BEGIN
    SET @objeto=QUOTENAME(@esquema)+N'.'+QUOTENAME(@tabla);
    IF COL_LENGTH(@objeto,N'CreadoUTC') IS NOT NULL
    BEGIN
        SELECT @default=dc.name FROM sys.default_constraints dc
        JOIN sys.columns c ON c.object_id=dc.parent_object_id AND c.column_id=dc.parent_column_id
        WHERE dc.parent_object_id=OBJECT_ID(@objeto) AND c.name=N'CreadoUTC';
        IF @default IS NOT NULL
        BEGIN
            SET @sql=N'ALTER TABLE '+@objeto+N' DROP CONSTRAINT '+QUOTENAME(@default);
            EXEC sys.sp_executesql @sql;
        END;
        SET @sql=N'ALTER TABLE '+@objeto+N' DROP COLUMN CreadoUTC';
        EXEC sys.sp_executesql @sql;
    END;
    SET @default=NULL;
    FETCH NEXT FROM fechas INTO @esquema,@tabla;
END;
CLOSE fechas;
DEALLOCATE fechas;
IF OBJECT_ID(N'staging.FK_datos_Gasto_DocumentoId',N'F') IS NOT NULL
   AND OBJECT_ID(N'staging.FK_staging_Gasto_DocumentoId',N'F') IS NULL
    EXEC sys.sp_rename N'staging.FK_datos_Gasto_DocumentoId',
                       N'FK_staging_Gasto_DocumentoId',N'OBJECT';
GO
INSERT seguridad.Rol(Nombre)
SELECT v.Nombre FROM (VALUES(N'Administrador'),(N'Operador'),(N'Consulta'))v(Nombre)
WHERE NOT EXISTS(SELECT 1 FROM seguridad.Rol r WHERE r.Nombre=v.Nombre);
-- Cuentas de demostracion: hashes Argon2id, nunca contrasenas en claro en la base.
IF NOT EXISTS(SELECT 1 FROM seguridad.Usuario WHERE NombreUsuario=N'administrador')
    INSERT seguridad.Usuario(NombreUsuario,NombreCompleto,HashContrasena,RolId)
    SELECT N'administrador',N'Administrador del laboratorio',
        N'$argon2id$v=19$m=65536,t=3,p=4$rcbB6kOYofzQoPAaUwiedQ$j00zAhNMEIALKDSvlQghMLbqAm8LdyVtyaOnE5vGHjk',Id
    FROM seguridad.Rol WHERE Nombre=N'Administrador';
IF NOT EXISTS(SELECT 1 FROM seguridad.Usuario WHERE NombreUsuario=N'operador')
    INSERT seguridad.Usuario(NombreUsuario,NombreCompleto,HashContrasena,RolId)
    SELECT N'operador',N'Operador del laboratorio',
        N'$argon2id$v=19$m=65536,t=3,p=4$ivlnttTqyrNeYp9kHoSLnQ$iLf1BKzExbgUfC+aYLTlKJyjrjW3+XmQEcsZL2m6WJM',Id
    FROM seguridad.Rol WHERE Nombre=N'Operador';
IF NOT EXISTS(SELECT 1 FROM seguridad.Usuario WHERE NombreUsuario=N'sistema')
    INSERT seguridad.Usuario(NombreUsuario,NombreCompleto,HashContrasena,RolId,Activo)
    SELECT N'sistema',N'Proceso de integracion',N'!no-login!',Id,0 FROM seguridad.Rol WHERE Nombre=N'Administrador';
IF NOT EXISTS(SELECT 1 FROM integracion.Servicio)
    INSERT integracion.Servicio(Nombre,URLBase,Ruta,VersionContrato)
    VALUES(N'MEF Gasto PIP',N'http://s3.mef.gob.pe',N'/servicios/WSPCM/SG/gastopipsg-old.asmx/ObtenerDataGastoPIP_old_2','1');
GO
