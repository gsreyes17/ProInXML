-- Base inicial compatible con instalaciones existentes. Repetible.
USE master;
GO
IF DB_ID(N'ProInXML') IS NULL EXEC(N'CREATE DATABASE ProInXML');
GO
USE ProInXML;
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
IF SCHEMA_ID(N'integracion') IS NULL EXEC(N'CREATE SCHEMA integracion AUTHORIZATION dbo');
IF SCHEMA_ID(N'datos') IS NULL EXEC(N'CREATE SCHEMA datos AUTHORIZATION dbo');
IF SCHEMA_ID(N'catalogo') IS NULL EXEC(N'CREATE SCHEMA catalogo AUTHORIZATION dbo');
IF SCHEMA_ID(N'auditoria') IS NULL EXEC(N'CREATE SCHEMA auditoria AUTHORIZATION dbo');
IF SCHEMA_ID(N'modelo') IS NULL EXEC(N'CREATE SCHEMA modelo AUTHORIZATION dbo');
IF SCHEMA_ID(N'seguridad') IS NULL EXEC(N'CREATE SCHEMA seguridad AUTHORIZATION dbo');
IF SCHEMA_ID(N'reportes') IS NULL EXEC(N'CREATE SCHEMA reportes AUTHORIZATION dbo');
GO
IF OBJECT_ID(N'integracion.Lote',N'U') IS NULL
BEGIN
BEGIN TRANSACTION;
CREATE TABLE auditoria.Cambio (
    Id bigint IDENTITY PRIMARY KEY,
    Tabla nvarchar(128) NOT NULL,
    RegistroId bigint NOT NULL,
    Operacion char(1) NOT NULL CHECK (Operacion IN ('I','U','D')),
    FechaUtc datetime2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
    Actor nvarchar(128) NOT NULL,
    LoginSql sysname NOT NULL,
    Correlacion uniqueidentifier NULL,
    Antes nvarchar(max) NULL CHECK (Antes IS NULL OR ISJSON(Antes)=1),
    Despues nvarchar(max) NULL CHECK (Despues IS NULL OR ISJSON(Despues)=1)
);
CREATE INDEX IX_Cambio_Registro ON auditoria.Cambio(Tabla,RegistroId,Id);
CREATE INDEX IX_Cambio_Correlacion ON auditoria.Cambio(Correlacion,Id);

CREATE TABLE catalogo.TipoActProy (
    Id bigint PRIMARY KEY CHECK (Id IN (2,3)),
    Nombre nvarchar(40) NOT NULL,
    CreadoUtc datetime2(3) NOT NULL DEFAULT SYSUTCDATETIME()
);
CREATE TABLE integracion.Lote (
    Id bigint IDENTITY PRIMARY KEY,
    Nombre nvarchar(260) NOT NULL,
    CreadoUtc datetime2(3) NOT NULL DEFAULT SYSUTCDATETIME()
);
CREATE TABLE integracion.Fuente (
    Id bigint IDENTITY PRIMARY KEY,
    Url nvarchar(1000) NOT NULL,
    AnoEje smallint NOT NULL CHECK (AnoEje BETWEEN 1900 AND 2100),
    NivelGobierno varchar(1) NOT NULL CHECK (NivelGobierno IN ('E','M','R')),
    SecEjec int NOT NULL CHECK (SecEjec > 0),
    DocumentoActualId bigint NULL,
    CreadoUtc datetime2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT UQ_Fuente_Parametros UNIQUE(AnoEje,NivelGobierno,SecEjec)
);
CREATE TABLE integracion.Trabajo (
    Id bigint IDENTITY PRIMARY KEY,
    LoteId bigint NOT NULL REFERENCES integracion.Lote(Id),
    FuenteId bigint NOT NULL REFERENCES integracion.Fuente(Id),
    DocumentoId bigint NULL,
    Estado varchar(16) NOT NULL DEFAULT 'PENDIENTE'
        CHECK (Estado IN ('PENDIENTE','PROCESANDO','REINTENTO','COMPLETADO','FALLIDO')),
    Intentos int NOT NULL DEFAULT 0 CHECK (Intentos >= 0),
    MaxIntentos int NOT NULL DEFAULT 4 CHECK (MaxIntentos BETWEEN 1 AND 10),
    ProximoIntentoUtc datetime2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
    LeaseHastaUtc datetime2(3) NULL,
    Token uniqueidentifier NULL,
    UltimoError nvarchar(2000) NULL,
    CreadoUtc datetime2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
    FinalizadoUtc datetime2(3) NULL,
    CONSTRAINT UQ_Trabajo_LoteFuente UNIQUE(LoteId,FuenteId)
);
CREATE INDEX IX_Trabajo_Cola ON integracion.Trabajo(Estado,ProximoIntentoUtc,Id)
    INCLUDE(LeaseHastaUtc,Intentos,MaxIntentos);
CREATE TABLE integracion.Intento (
    Id bigint IDENTITY PRIMARY KEY,
    TrabajoId bigint NOT NULL REFERENCES integracion.Trabajo(Id),
    Numero int NOT NULL,
    Estado varchar(16) NOT NULL DEFAULT 'PROCESANDO'
        CHECK (Estado IN ('PROCESANDO','COMPLETADO','ERROR','ABANDONADO')),
    InicioUtc datetime2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
    FinUtc datetime2(3) NULL,
    HttpStatus int NULL,
    Error nvarchar(2000) NULL,
    CONSTRAINT UQ_Intento_Numero UNIQUE(TrabajoId,Numero)
);
CREATE TABLE integracion.Documento (
    Id bigint IDENTITY PRIMARY KEY,
    FuenteId bigint NOT NULL REFERENCES integracion.Fuente(Id),
    IntentoId bigint NOT NULL REFERENCES integracion.Intento(Id),
    Sha256 binary(32) NOT NULL,
    Respuesta varbinary(max) NOT NULL,
    ContentType nvarchar(200) NULL,
    EsValido bit NOT NULL DEFAULT 0,
    CantidadRegistros int NULL CHECK (CantidadRegistros >= 0),
    ErrorValidacion nvarchar(2000) NULL,
    CreadoUtc datetime2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT UQ_Documento_Hash UNIQUE(FuenteId,Sha256),
    CONSTRAINT UQ_Documento_FuenteId UNIQUE(FuenteId,Id)
);
-- FK compuesta: una fuente nunca puede apuntar al documento de otra fuente.
ALTER TABLE integracion.Fuente ADD CONSTRAINT FK_Fuente_DocumentoActual
    FOREIGN KEY(Id,DocumentoActualId) REFERENCES integracion.Documento(FuenteId,Id);
ALTER TABLE integracion.Trabajo ADD CONSTRAINT FK_Trabajo_Documento
    FOREIGN KEY(FuenteId,DocumentoId) REFERENCES integracion.Documento(FuenteId,Id);

CREATE TABLE datos.Gasto (
    Id bigint IDENTITY PRIMARY KEY,
    DocumentoId bigint NOT NULL REFERENCES integracion.Documento(Id),
    Ordinal int NOT NULL CHECK (Ordinal > 0),
    AnoEje smallint NOT NULL CHECK (AnoEje BETWEEN 1900 AND 2100),
    MesEje tinyint NOT NULL CHECK (MesEje BETWEEN 0 AND 12),
    SecEjec int NOT NULL CHECK (SecEjec > 0),
    TipoActProy bigint NOT NULL REFERENCES catalogo.TipoActProy(Id),
    IdNivelGobierno varchar(32) NOT NULL,
    Sub_tipo_gobierno varchar(32) NOT NULL,
    IdSector varchar(32) NOT NULL,
    IdPliego varchar(32) NOT NULL,
    IdEjecutora varchar(32) NOT NULL,
    Funcion varchar(32) NOT NULL,
    Programa varchar(32) NOT NULL,
    Programa_ppto varchar(32) NOT NULL,
    Categ_gasto varchar(32) NOT NULL,
    Tipo_transaccion varchar(32) NOT NULL,
    Generica varchar(32) NOT NULL,
    Subgenerica varchar(32) NOT NULL,
    Subgenerica_det varchar(32) NOT NULL,
    Especifica varchar(32) NOT NULL,
    Especifica_det varchar(32) NOT NULL,
    SecFunc varchar(32) NOT NULL,
    IdFuente varchar(32) NOT NULL,
    IdRubro varchar(32) NOT NULL,
    IdTipoRecurso varchar(32) NOT NULL,
    IdComponente varchar(32) NOT NULL,
    IdProyecto varchar(32) NOT NULL,
    IdMeta varchar(32) NOT NULL,
    IdFinalidad varchar(32) NOT NULL,
    IdProyectoSNIP varchar(32) NOT NULL,
    Departamento varchar(32) NOT NULL,
    Provincia varchar(32) NOT NULL,
    Distrito varchar(32) NOT NULL,
    Unidad_Medida varchar(32) NOT NULL,
    PIA decimal(19,4) NOT NULL,
    PIM decimal(19,4) NOT NULL,
    Certificado decimal(19,4) NOT NULL,
    CompAnual decimal(19,4) NOT NULL,
    AtencionCompMensual decimal(19,4) NOT NULL,
    Devengado decimal(19,4) NOT NULL,
    Girado decimal(19,4) NOT NULL,
    CreadoUtc datetime2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT UQ_Gasto_DocumentoOrdinal UNIQUE(DocumentoId,Ordinal)
);
CREATE INDEX IX_Gasto_Consulta ON datos.Gasto(AnoEje,IdNivelGobierno,SecEjec,Id)
    INCLUDE(DocumentoId,TipoActProy,PIA,PIM,Devengado);


COMMIT;
END;
GO
