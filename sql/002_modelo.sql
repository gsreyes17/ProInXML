-- Tablas del modelo relacional. Generado por scripts/desarrollo/build_model_sql.py.

USE ProInXML;
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
BEGIN TRANSACTION;

IF SCHEMA_ID(N'modelo') IS NULL EXEC(N'CREATE SCHEMA modelo AUTHORIZATION dbo');

IF OBJECT_ID(N'modelo.NivelGobierno',N'U') IS NULL
CREATE TABLE modelo.[NivelGobierno](
  Id bigint IDENTITY CONSTRAINT PK_modelo_NivelGobierno PRIMARY KEY,
  [Codigo] varchar(32) NOT NULL,
  CreadoUtc datetime2(3) NOT NULL CONSTRAINT DF_modelo_NivelGobierno_CreadoUtc DEFAULT SYSUTCDATETIME(),
  CONSTRAINT [UQ_NivelGobierno_Clave] UNIQUE([Codigo])
);

IF OBJECT_ID(N'modelo.SubtipoGobierno',N'U') IS NULL
CREATE TABLE modelo.[SubtipoGobierno](
  Id bigint IDENTITY CONSTRAINT PK_modelo_SubtipoGobierno PRIMARY KEY,
  [NivelGobiernoId] bigint NOT NULL CONSTRAINT FK_SubtipoGobierno_NivelGobiernoId REFERENCES modelo.[NivelGobierno](Id),
  [Codigo] varchar(32) NOT NULL,
  CreadoUtc datetime2(3) NOT NULL CONSTRAINT DF_modelo_SubtipoGobierno_CreadoUtc DEFAULT SYSUTCDATETIME(),
  CONSTRAINT [UQ_SubtipoGobierno_Clave] UNIQUE([NivelGobiernoId],[Codigo])
);

IF OBJECT_ID(N'modelo.Sector',N'U') IS NULL
CREATE TABLE modelo.[Sector](
  Id bigint IDENTITY CONSTRAINT PK_modelo_Sector PRIMARY KEY,
  [SubtipoGobiernoId] bigint NOT NULL CONSTRAINT FK_Sector_SubtipoGobiernoId REFERENCES modelo.[SubtipoGobierno](Id),
  [Codigo] varchar(32) NOT NULL,
  CreadoUtc datetime2(3) NOT NULL CONSTRAINT DF_modelo_Sector_CreadoUtc DEFAULT SYSUTCDATETIME(),
  CONSTRAINT [UQ_Sector_Clave] UNIQUE([SubtipoGobiernoId],[Codigo])
);

IF OBJECT_ID(N'modelo.Pliego',N'U') IS NULL
CREATE TABLE modelo.[Pliego](
  Id bigint IDENTITY CONSTRAINT PK_modelo_Pliego PRIMARY KEY,
  [SectorId] bigint NOT NULL CONSTRAINT FK_Pliego_SectorId REFERENCES modelo.[Sector](Id),
  [Codigo] varchar(32) NOT NULL,
  CreadoUtc datetime2(3) NOT NULL CONSTRAINT DF_modelo_Pliego_CreadoUtc DEFAULT SYSUTCDATETIME(),
  CONSTRAINT [UQ_Pliego_Clave] UNIQUE([SectorId],[Codigo])
);

IF OBJECT_ID(N'modelo.Ejecutora',N'U') IS NULL
CREATE TABLE modelo.[Ejecutora](
  Id bigint IDENTITY CONSTRAINT PK_modelo_Ejecutora PRIMARY KEY,
  [PliegoId] bigint NOT NULL CONSTRAINT FK_Ejecutora_PliegoId REFERENCES modelo.[Pliego](Id),
  [Codigo] varchar(32) NOT NULL,
  CreadoUtc datetime2(3) NOT NULL CONSTRAINT DF_modelo_Ejecutora_CreadoUtc DEFAULT SYSUTCDATETIME(),
  CONSTRAINT [UQ_Ejecutora_Clave] UNIQUE([PliegoId],[Codigo])
);

IF OBJECT_ID(N'modelo.ContextoEjecutora',N'U') IS NULL
CREATE TABLE modelo.[ContextoEjecutora](
  Id bigint IDENTITY CONSTRAINT PK_modelo_ContextoEjecutora PRIMARY KEY,
  [EjecutoraId] bigint NOT NULL CONSTRAINT FK_ContextoEjecutora_EjecutoraId REFERENCES modelo.[Ejecutora](Id),
  [AnoEje] smallint NOT NULL,
  [SecEjec] int NOT NULL,
  CreadoUtc datetime2(3) NOT NULL CONSTRAINT DF_modelo_ContextoEjecutora_CreadoUtc DEFAULT SYSUTCDATETIME(),
  CONSTRAINT [UQ_ContextoEjecutora_Clave] UNIQUE([EjecutoraId],[AnoEje],[SecEjec])
);

IF OBJECT_ID(N'modelo.Funcion',N'U') IS NULL
CREATE TABLE modelo.[Funcion](
  Id bigint IDENTITY CONSTRAINT PK_modelo_Funcion PRIMARY KEY,
  [Codigo] varchar(32) NOT NULL,
  CreadoUtc datetime2(3) NOT NULL CONSTRAINT DF_modelo_Funcion_CreadoUtc DEFAULT SYSUTCDATETIME(),
  CONSTRAINT [UQ_Funcion_Clave] UNIQUE([Codigo])
);

IF OBJECT_ID(N'modelo.ProgramaFuncional',N'U') IS NULL
CREATE TABLE modelo.[ProgramaFuncional](
  Id bigint IDENTITY CONSTRAINT PK_modelo_ProgramaFuncional PRIMARY KEY,
  [FuncionId] bigint NOT NULL CONSTRAINT FK_ProgramaFuncional_FuncionId REFERENCES modelo.[Funcion](Id),
  [Codigo] varchar(32) NOT NULL,
  CreadoUtc datetime2(3) NOT NULL CONSTRAINT DF_modelo_ProgramaFuncional_CreadoUtc DEFAULT SYSUTCDATETIME(),
  CONSTRAINT [UQ_ProgramaFuncional_Clave] UNIQUE([FuncionId],[Codigo])
);

IF OBJECT_ID(N'modelo.ProgramaPresupuestal',N'U') IS NULL
CREATE TABLE modelo.[ProgramaPresupuestal](
  Id bigint IDENTITY CONSTRAINT PK_modelo_ProgramaPresupuestal PRIMARY KEY,
  [Codigo] varchar(32) NOT NULL,
  CreadoUtc datetime2(3) NOT NULL CONSTRAINT DF_modelo_ProgramaPresupuestal_CreadoUtc DEFAULT SYSUTCDATETIME(),
  CONSTRAINT [UQ_ProgramaPresupuestal_Clave] UNIQUE([Codigo])
);

IF OBJECT_ID(N'modelo.CategoriaGasto',N'U') IS NULL
CREATE TABLE modelo.[CategoriaGasto](
  Id bigint IDENTITY CONSTRAINT PK_modelo_CategoriaGasto PRIMARY KEY,
  [Codigo] varchar(32) NOT NULL,
  CreadoUtc datetime2(3) NOT NULL CONSTRAINT DF_modelo_CategoriaGasto_CreadoUtc DEFAULT SYSUTCDATETIME(),
  CONSTRAINT [UQ_CategoriaGasto_Clave] UNIQUE([Codigo])
);

IF OBJECT_ID(N'modelo.TipoTransaccion',N'U') IS NULL
CREATE TABLE modelo.[TipoTransaccion](
  Id bigint IDENTITY CONSTRAINT PK_modelo_TipoTransaccion PRIMARY KEY,
  [Codigo] varchar(32) NOT NULL,
  CreadoUtc datetime2(3) NOT NULL CONSTRAINT DF_modelo_TipoTransaccion_CreadoUtc DEFAULT SYSUTCDATETIME(),
  CONSTRAINT [UQ_TipoTransaccion_Clave] UNIQUE([Codigo])
);

IF OBJECT_ID(N'modelo.Generica',N'U') IS NULL
CREATE TABLE modelo.[Generica](
  Id bigint IDENTITY CONSTRAINT PK_modelo_Generica PRIMARY KEY,
  [TipoTransaccionId] bigint NOT NULL CONSTRAINT FK_Generica_TipoTransaccionId REFERENCES modelo.[TipoTransaccion](Id),
  [Codigo] varchar(32) NOT NULL,
  CreadoUtc datetime2(3) NOT NULL CONSTRAINT DF_modelo_Generica_CreadoUtc DEFAULT SYSUTCDATETIME(),
  CONSTRAINT [UQ_Generica_Clave] UNIQUE([TipoTransaccionId],[Codigo])
);

IF OBJECT_ID(N'modelo.Subgenerica',N'U') IS NULL
CREATE TABLE modelo.[Subgenerica](
  Id bigint IDENTITY CONSTRAINT PK_modelo_Subgenerica PRIMARY KEY,
  [GenericaId] bigint NOT NULL CONSTRAINT FK_Subgenerica_GenericaId REFERENCES modelo.[Generica](Id),
  [Codigo] varchar(32) NOT NULL,
  CreadoUtc datetime2(3) NOT NULL CONSTRAINT DF_modelo_Subgenerica_CreadoUtc DEFAULT SYSUTCDATETIME(),
  CONSTRAINT [UQ_Subgenerica_Clave] UNIQUE([GenericaId],[Codigo])
);

IF OBJECT_ID(N'modelo.SubgenericaDetalle',N'U') IS NULL
CREATE TABLE modelo.[SubgenericaDetalle](
  Id bigint IDENTITY CONSTRAINT PK_modelo_SubgenericaDetalle PRIMARY KEY,
  [SubgenericaId] bigint NOT NULL CONSTRAINT FK_SubgenericaDetalle_SubgenericaId REFERENCES modelo.[Subgenerica](Id),
  [Codigo] varchar(32) NOT NULL,
  CreadoUtc datetime2(3) NOT NULL CONSTRAINT DF_modelo_SubgenericaDetalle_CreadoUtc DEFAULT SYSUTCDATETIME(),
  CONSTRAINT [UQ_SubgenericaDetalle_Clave] UNIQUE([SubgenericaId],[Codigo])
);

IF OBJECT_ID(N'modelo.Especifica',N'U') IS NULL
CREATE TABLE modelo.[Especifica](
  Id bigint IDENTITY CONSTRAINT PK_modelo_Especifica PRIMARY KEY,
  [SubgenericaDetalleId] bigint NOT NULL CONSTRAINT FK_Especifica_SubgenericaDetalleId REFERENCES modelo.[SubgenericaDetalle](Id),
  [Codigo] varchar(32) NOT NULL,
  CreadoUtc datetime2(3) NOT NULL CONSTRAINT DF_modelo_Especifica_CreadoUtc DEFAULT SYSUTCDATETIME(),
  CONSTRAINT [UQ_Especifica_Clave] UNIQUE([SubgenericaDetalleId],[Codigo])
);

IF OBJECT_ID(N'modelo.EspecificaDetalle',N'U') IS NULL
CREATE TABLE modelo.[EspecificaDetalle](
  Id bigint IDENTITY CONSTRAINT PK_modelo_EspecificaDetalle PRIMARY KEY,
  [EspecificaId] bigint NOT NULL CONSTRAINT FK_EspecificaDetalle_EspecificaId REFERENCES modelo.[Especifica](Id),
  [Codigo] varchar(32) NOT NULL,
  CreadoUtc datetime2(3) NOT NULL CONSTRAINT DF_modelo_EspecificaDetalle_CreadoUtc DEFAULT SYSUTCDATETIME(),
  CONSTRAINT [UQ_EspecificaDetalle_Clave] UNIQUE([EspecificaId],[Codigo])
);

IF OBJECT_ID(N'modelo.FuenteFinanciamiento',N'U') IS NULL
CREATE TABLE modelo.[FuenteFinanciamiento](
  Id bigint IDENTITY CONSTRAINT PK_modelo_FuenteFinanciamiento PRIMARY KEY,
  [Codigo] varchar(32) NOT NULL,
  CreadoUtc datetime2(3) NOT NULL CONSTRAINT DF_modelo_FuenteFinanciamiento_CreadoUtc DEFAULT SYSUTCDATETIME(),
  CONSTRAINT [UQ_FuenteFinanciamiento_Clave] UNIQUE([Codigo])
);

IF OBJECT_ID(N'modelo.Rubro',N'U') IS NULL
CREATE TABLE modelo.[Rubro](
  Id bigint IDENTITY CONSTRAINT PK_modelo_Rubro PRIMARY KEY,
  [FuenteFinanciamientoId] bigint NOT NULL CONSTRAINT FK_Rubro_FuenteFinanciamientoId REFERENCES modelo.[FuenteFinanciamiento](Id),
  [Codigo] varchar(32) NOT NULL,
  CreadoUtc datetime2(3) NOT NULL CONSTRAINT DF_modelo_Rubro_CreadoUtc DEFAULT SYSUTCDATETIME(),
  CONSTRAINT [UQ_Rubro_Clave] UNIQUE([FuenteFinanciamientoId],[Codigo])
);

IF OBJECT_ID(N'modelo.TipoRecurso',N'U') IS NULL
CREATE TABLE modelo.[TipoRecurso](
  Id bigint IDENTITY CONSTRAINT PK_modelo_TipoRecurso PRIMARY KEY,
  [RubroId] bigint NOT NULL CONSTRAINT FK_TipoRecurso_RubroId REFERENCES modelo.[Rubro](Id),
  [Codigo] varchar(32) NOT NULL,
  CreadoUtc datetime2(3) NOT NULL CONSTRAINT DF_modelo_TipoRecurso_CreadoUtc DEFAULT SYSUTCDATETIME(),
  CONSTRAINT [UQ_TipoRecurso_Clave] UNIQUE([RubroId],[Codigo])
);

IF OBJECT_ID(N'modelo.Proyecto',N'U') IS NULL
CREATE TABLE modelo.[Proyecto](
  Id bigint IDENTITY CONSTRAINT PK_modelo_Proyecto PRIMARY KEY,
  [Codigo] varchar(32) NOT NULL,
  CreadoUtc datetime2(3) NOT NULL CONSTRAINT DF_modelo_Proyecto_CreadoUtc DEFAULT SYSUTCDATETIME(),
  CONSTRAINT [UQ_Proyecto_Clave] UNIQUE([Codigo])
);

IF OBJECT_ID(N'modelo.ProyectoSNIP',N'U') IS NULL
CREATE TABLE modelo.[ProyectoSNIP](
  Id bigint IDENTITY CONSTRAINT PK_modelo_ProyectoSNIP PRIMARY KEY,
  [Codigo] varchar(32) NOT NULL,
  CreadoUtc datetime2(3) NOT NULL CONSTRAINT DF_modelo_ProyectoSNIP_CreadoUtc DEFAULT SYSUTCDATETIME(),
  CONSTRAINT [UQ_ProyectoSNIP_Clave] UNIQUE([Codigo])
);

IF OBJECT_ID(N'modelo.Componente',N'U') IS NULL
CREATE TABLE modelo.[Componente](
  Id bigint IDENTITY CONSTRAINT PK_modelo_Componente PRIMARY KEY,
  [Codigo] varchar(32) NOT NULL,
  CreadoUtc datetime2(3) NOT NULL CONSTRAINT DF_modelo_Componente_CreadoUtc DEFAULT SYSUTCDATETIME(),
  CONSTRAINT [UQ_Componente_Clave] UNIQUE([Codigo])
);

IF OBJECT_ID(N'modelo.Finalidad',N'U') IS NULL
CREATE TABLE modelo.[Finalidad](
  Id bigint IDENTITY CONSTRAINT PK_modelo_Finalidad PRIMARY KEY,
  [Codigo] varchar(32) NOT NULL,
  CreadoUtc datetime2(3) NOT NULL CONSTRAINT DF_modelo_Finalidad_CreadoUtc DEFAULT SYSUTCDATETIME(),
  CONSTRAINT [UQ_Finalidad_Clave] UNIQUE([Codigo])
);

IF OBJECT_ID(N'modelo.UnidadMedida',N'U') IS NULL
CREATE TABLE modelo.[UnidadMedida](
  Id bigint IDENTITY CONSTRAINT PK_modelo_UnidadMedida PRIMARY KEY,
  [Codigo] varchar(32) NOT NULL,
  CreadoUtc datetime2(3) NOT NULL CONSTRAINT DF_modelo_UnidadMedida_CreadoUtc DEFAULT SYSUTCDATETIME(),
  CONSTRAINT [UQ_UnidadMedida_Clave] UNIQUE([Codigo])
);

IF OBJECT_ID(N'modelo.SecuenciaFuncional',N'U') IS NULL
CREATE TABLE modelo.[SecuenciaFuncional](
  Id bigint IDENTITY CONSTRAINT PK_modelo_SecuenciaFuncional PRIMARY KEY,
  [ContextoEjecutoraId] bigint NOT NULL CONSTRAINT FK_SecuenciaFuncional_ContextoEjecutoraId REFERENCES modelo.[ContextoEjecutora](Id),
  [Codigo] varchar(32) NOT NULL,
  CreadoUtc datetime2(3) NOT NULL CONSTRAINT DF_modelo_SecuenciaFuncional_CreadoUtc DEFAULT SYSUTCDATETIME(),
  CONSTRAINT [UQ_SecuenciaFuncional_Clave] UNIQUE([ContextoEjecutoraId],[Codigo])
);

IF OBJECT_ID(N'modelo.Meta',N'U') IS NULL
CREATE TABLE modelo.[Meta](
  Id bigint IDENTITY CONSTRAINT PK_modelo_Meta PRIMARY KEY,
  [SecuenciaFuncionalId] bigint NOT NULL CONSTRAINT FK_Meta_SecuenciaFuncionalId REFERENCES modelo.[SecuenciaFuncional](Id),
  [Codigo] varchar(32) NOT NULL,
  [FinalidadId] bigint NOT NULL CONSTRAINT FK_Meta_FinalidadId REFERENCES modelo.[Finalidad](Id),
  [UnidadMedidaId] bigint NULL CONSTRAINT FK_Meta_UnidadMedidaId REFERENCES modelo.[UnidadMedida](Id),
  CreadoUtc datetime2(3) NOT NULL CONSTRAINT DF_modelo_Meta_CreadoUtc DEFAULT SYSUTCDATETIME(),
  CONSTRAINT [UQ_Meta_Clave] UNIQUE([SecuenciaFuncionalId],[Codigo],[FinalidadId],[UnidadMedidaId])
);

IF OBJECT_ID(N'modelo.Departamento',N'U') IS NULL
CREATE TABLE modelo.[Departamento](
  Id bigint IDENTITY CONSTRAINT PK_modelo_Departamento PRIMARY KEY,
  [Codigo] varchar(32) NOT NULL,
  CreadoUtc datetime2(3) NOT NULL CONSTRAINT DF_modelo_Departamento_CreadoUtc DEFAULT SYSUTCDATETIME(),
  CONSTRAINT [UQ_Departamento_Clave] UNIQUE([Codigo])
);

IF OBJECT_ID(N'modelo.Provincia',N'U') IS NULL
CREATE TABLE modelo.[Provincia](
  Id bigint IDENTITY CONSTRAINT PK_modelo_Provincia PRIMARY KEY,
  [DepartamentoId] bigint NOT NULL CONSTRAINT FK_Provincia_DepartamentoId REFERENCES modelo.[Departamento](Id),
  [Codigo] varchar(32) NOT NULL,
  CreadoUtc datetime2(3) NOT NULL CONSTRAINT DF_modelo_Provincia_CreadoUtc DEFAULT SYSUTCDATETIME(),
  CONSTRAINT [UQ_Provincia_Clave] UNIQUE([DepartamentoId],[Codigo])
);

IF OBJECT_ID(N'modelo.Distrito',N'U') IS NULL
CREATE TABLE modelo.[Distrito](
  Id bigint IDENTITY CONSTRAINT PK_modelo_Distrito PRIMARY KEY,
  [ProvinciaId] bigint NOT NULL CONSTRAINT FK_Distrito_ProvinciaId REFERENCES modelo.[Provincia](Id),
  [Codigo] varchar(32) NOT NULL,
  CreadoUtc datetime2(3) NOT NULL CONSTRAINT DF_modelo_Distrito_CreadoUtc DEFAULT SYSUTCDATETIME(),
  CONSTRAINT [UQ_Distrito_Clave] UNIQUE([ProvinciaId],[Codigo])
);

IF OBJECT_ID(N'modelo.Gasto',N'U') IS NULL
CREATE TABLE modelo.Gasto(
  Id bigint CONSTRAINT PK_modelo_Gasto PRIMARY KEY CONSTRAINT FK_modelo_Gasto_Origen REFERENCES datos.Gasto(Id),
  [MetaId] bigint NOT NULL CONSTRAINT FK_Gasto_MetaId REFERENCES modelo.[Meta](Id),
  [ProgramaFuncionalId] bigint NOT NULL CONSTRAINT FK_Gasto_ProgramaFuncionalId REFERENCES modelo.[ProgramaFuncional](Id),
  [ProgramaPresupuestalId] bigint NOT NULL CONSTRAINT FK_Gasto_ProgramaPresupuestalId REFERENCES modelo.[ProgramaPresupuestal](Id),
  [CategoriaGastoId] bigint NOT NULL CONSTRAINT FK_Gasto_CategoriaGastoId REFERENCES modelo.[CategoriaGasto](Id),
  [EspecificaDetalleId] bigint NOT NULL CONSTRAINT FK_Gasto_EspecificaDetalleId REFERENCES modelo.[EspecificaDetalle](Id),
  [TipoRecursoId] bigint NOT NULL CONSTRAINT FK_Gasto_TipoRecursoId REFERENCES modelo.[TipoRecurso](Id),
  [ProyectoId] bigint NOT NULL CONSTRAINT FK_Gasto_ProyectoId REFERENCES modelo.[Proyecto](Id),
  [ProyectoSNIPId] bigint NOT NULL CONSTRAINT FK_Gasto_ProyectoSNIPId REFERENCES modelo.[ProyectoSNIP](Id),
  [ComponenteId] bigint NOT NULL CONSTRAINT FK_Gasto_ComponenteId REFERENCES modelo.[Componente](Id),
  [DistritoId] bigint NOT NULL CONSTRAINT FK_Gasto_DistritoId REFERENCES modelo.[Distrito](Id),
  [TipoActProyId] bigint NOT NULL CONSTRAINT FK_modelo_Gasto_TipoActProy REFERENCES catalogo.TipoActProy(Id),
  [MesEje] tinyint NOT NULL,
  [PIA] decimal(19,4) NOT NULL,
  [PIM] decimal(19,4) NOT NULL,
  [Certificado] decimal(19,4) NOT NULL,
  [CompAnual] decimal(19,4) NOT NULL,
  [AtencionCompMensual] decimal(19,4) NOT NULL,
  [Devengado] decimal(19,4) NOT NULL,
  [Girado] decimal(19,4) NOT NULL,
  CreadoUtc datetime2(3) NOT NULL DEFAULT SYSUTCDATETIME()
);

COMMIT;
GO