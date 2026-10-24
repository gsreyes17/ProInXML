-- Normalizacion transaccional y vistas del modelo. Generado desde app/model_schema.py.

USE ProInXML;
GO
SET NOCOUNT ON;
GO


CREATE OR ALTER PROCEDURE modelo.NormalizarDocumento @DocumentoId bigint AS
BEGIN
 SET NOCOUNT ON;
 SET XACT_ABORT ON;
 BEGIN TRANSACTION;
 DECLARE @resultado int;
 EXEC @resultado=sys.sp_getapplock @Resource=N'ProInXML:modelo:normalizacion',
  @LockMode='Exclusive',@LockOwner='Transaction',@LockTimeout=60000;
 IF @resultado<0 THROW 50200,'No se pudo bloquear la normalizacion del documento.',1;
 SELECT * INTO #origen FROM datos.Gasto WHERE DocumentoId=@DocumentoId;
 IF NOT EXISTS(SELECT 1 FROM #origen) BEGIN COMMIT; RETURN; END;


INSERT modelo.[NivelGobierno]([Codigo])
SELECT s.[Codigo] FROM (
SELECT DISTINCT g.[IdNivelGobierno] AS [Codigo] FROM #origen g

) s
WHERE NOT EXISTS(SELECT 1 FROM modelo.[NivelGobierno] d WITH(UPDLOCK,HOLDLOCK) WHERE d.[Codigo]=s.[Codigo]);

INSERT modelo.[SubtipoGobierno]([NivelGobiernoId],[Codigo])
SELECT s.[NivelGobiernoId],s.[Codigo] FROM (
SELECT DISTINCT [NivelGobierno].Id AS [NivelGobiernoId],g.[Sub_tipo_gobierno] AS [Codigo] FROM #origen g
JOIN modelo.[NivelGobierno] [NivelGobierno] ON [NivelGobierno].[Codigo]=g.[IdNivelGobierno]
) s
WHERE NOT EXISTS(SELECT 1 FROM modelo.[SubtipoGobierno] d WITH(UPDLOCK,HOLDLOCK) WHERE d.[NivelGobiernoId]=s.[NivelGobiernoId] AND d.[Codigo]=s.[Codigo]);

INSERT modelo.[Sector]([SubtipoGobiernoId],[Codigo])
SELECT s.[SubtipoGobiernoId],s.[Codigo] FROM (
SELECT DISTINCT [SubtipoGobierno].Id AS [SubtipoGobiernoId],g.[IdSector] AS [Codigo] FROM #origen g
JOIN modelo.[NivelGobierno] [NivelGobierno] ON [NivelGobierno].[Codigo]=g.[IdNivelGobierno]
JOIN modelo.[SubtipoGobierno] [SubtipoGobierno] ON [SubtipoGobierno].[NivelGobiernoId]=[NivelGobierno].Id AND [SubtipoGobierno].[Codigo]=g.[Sub_tipo_gobierno]
) s
WHERE NOT EXISTS(SELECT 1 FROM modelo.[Sector] d WITH(UPDLOCK,HOLDLOCK) WHERE d.[SubtipoGobiernoId]=s.[SubtipoGobiernoId] AND d.[Codigo]=s.[Codigo]);

INSERT modelo.[Pliego]([SectorId],[Codigo])
SELECT s.[SectorId],s.[Codigo] FROM (
SELECT DISTINCT [Sector].Id AS [SectorId],g.[IdPliego] AS [Codigo] FROM #origen g
JOIN modelo.[NivelGobierno] [NivelGobierno] ON [NivelGobierno].[Codigo]=g.[IdNivelGobierno]
JOIN modelo.[SubtipoGobierno] [SubtipoGobierno] ON [SubtipoGobierno].[NivelGobiernoId]=[NivelGobierno].Id AND [SubtipoGobierno].[Codigo]=g.[Sub_tipo_gobierno]
JOIN modelo.[Sector] [Sector] ON [Sector].[SubtipoGobiernoId]=[SubtipoGobierno].Id AND [Sector].[Codigo]=g.[IdSector]
) s
WHERE NOT EXISTS(SELECT 1 FROM modelo.[Pliego] d WITH(UPDLOCK,HOLDLOCK) WHERE d.[SectorId]=s.[SectorId] AND d.[Codigo]=s.[Codigo]);

INSERT modelo.[Ejecutora]([PliegoId],[Codigo])
SELECT s.[PliegoId],s.[Codigo] FROM (
SELECT DISTINCT [Pliego].Id AS [PliegoId],g.[IdEjecutora] AS [Codigo] FROM #origen g
JOIN modelo.[NivelGobierno] [NivelGobierno] ON [NivelGobierno].[Codigo]=g.[IdNivelGobierno]
JOIN modelo.[SubtipoGobierno] [SubtipoGobierno] ON [SubtipoGobierno].[NivelGobiernoId]=[NivelGobierno].Id AND [SubtipoGobierno].[Codigo]=g.[Sub_tipo_gobierno]
JOIN modelo.[Sector] [Sector] ON [Sector].[SubtipoGobiernoId]=[SubtipoGobierno].Id AND [Sector].[Codigo]=g.[IdSector]
JOIN modelo.[Pliego] [Pliego] ON [Pliego].[SectorId]=[Sector].Id AND [Pliego].[Codigo]=g.[IdPliego]
) s
WHERE NOT EXISTS(SELECT 1 FROM modelo.[Ejecutora] d WITH(UPDLOCK,HOLDLOCK) WHERE d.[PliegoId]=s.[PliegoId] AND d.[Codigo]=s.[Codigo]);

INSERT modelo.[ContextoEjecutora]([EjecutoraId],[AnoEje],[SecEjec])
SELECT s.[EjecutoraId],s.[AnoEje],s.[SecEjec] FROM (
SELECT DISTINCT [Ejecutora].Id AS [EjecutoraId],g.[AnoEje] AS [AnoEje],g.[SecEjec] AS [SecEjec] FROM #origen g
JOIN modelo.[NivelGobierno] [NivelGobierno] ON [NivelGobierno].[Codigo]=g.[IdNivelGobierno]
JOIN modelo.[SubtipoGobierno] [SubtipoGobierno] ON [SubtipoGobierno].[NivelGobiernoId]=[NivelGobierno].Id AND [SubtipoGobierno].[Codigo]=g.[Sub_tipo_gobierno]
JOIN modelo.[Sector] [Sector] ON [Sector].[SubtipoGobiernoId]=[SubtipoGobierno].Id AND [Sector].[Codigo]=g.[IdSector]
JOIN modelo.[Pliego] [Pliego] ON [Pliego].[SectorId]=[Sector].Id AND [Pliego].[Codigo]=g.[IdPliego]
JOIN modelo.[Ejecutora] [Ejecutora] ON [Ejecutora].[PliegoId]=[Pliego].Id AND [Ejecutora].[Codigo]=g.[IdEjecutora]
) s
WHERE NOT EXISTS(SELECT 1 FROM modelo.[ContextoEjecutora] d WITH(UPDLOCK,HOLDLOCK) WHERE d.[EjecutoraId]=s.[EjecutoraId] AND d.[AnoEje]=s.[AnoEje] AND d.[SecEjec]=s.[SecEjec]);

INSERT modelo.[Funcion]([Codigo])
SELECT s.[Codigo] FROM (
SELECT DISTINCT g.[Funcion] AS [Codigo] FROM #origen g

) s
WHERE NOT EXISTS(SELECT 1 FROM modelo.[Funcion] d WITH(UPDLOCK,HOLDLOCK) WHERE d.[Codigo]=s.[Codigo]);

INSERT modelo.[ProgramaFuncional]([FuncionId],[Codigo])
SELECT s.[FuncionId],s.[Codigo] FROM (
SELECT DISTINCT [Funcion].Id AS [FuncionId],g.[Programa] AS [Codigo] FROM #origen g
JOIN modelo.[Funcion] [Funcion] ON [Funcion].[Codigo]=g.[Funcion]
) s
WHERE NOT EXISTS(SELECT 1 FROM modelo.[ProgramaFuncional] d WITH(UPDLOCK,HOLDLOCK) WHERE d.[FuncionId]=s.[FuncionId] AND d.[Codigo]=s.[Codigo]);

INSERT modelo.[ProgramaPresupuestal]([Codigo])
SELECT s.[Codigo] FROM (
SELECT DISTINCT g.[Programa_ppto] AS [Codigo] FROM #origen g

) s
WHERE NOT EXISTS(SELECT 1 FROM modelo.[ProgramaPresupuestal] d WITH(UPDLOCK,HOLDLOCK) WHERE d.[Codigo]=s.[Codigo]);

INSERT modelo.[CategoriaGasto]([Codigo])
SELECT s.[Codigo] FROM (
SELECT DISTINCT g.[Categ_gasto] AS [Codigo] FROM #origen g

) s
WHERE NOT EXISTS(SELECT 1 FROM modelo.[CategoriaGasto] d WITH(UPDLOCK,HOLDLOCK) WHERE d.[Codigo]=s.[Codigo]);

INSERT modelo.[TipoTransaccion]([Codigo])
SELECT s.[Codigo] FROM (
SELECT DISTINCT g.[Tipo_transaccion] AS [Codigo] FROM #origen g

) s
WHERE NOT EXISTS(SELECT 1 FROM modelo.[TipoTransaccion] d WITH(UPDLOCK,HOLDLOCK) WHERE d.[Codigo]=s.[Codigo]);

INSERT modelo.[Generica]([TipoTransaccionId],[Codigo])
SELECT s.[TipoTransaccionId],s.[Codigo] FROM (
SELECT DISTINCT [TipoTransaccion].Id AS [TipoTransaccionId],g.[Generica] AS [Codigo] FROM #origen g
JOIN modelo.[TipoTransaccion] [TipoTransaccion] ON [TipoTransaccion].[Codigo]=g.[Tipo_transaccion]
) s
WHERE NOT EXISTS(SELECT 1 FROM modelo.[Generica] d WITH(UPDLOCK,HOLDLOCK) WHERE d.[TipoTransaccionId]=s.[TipoTransaccionId] AND d.[Codigo]=s.[Codigo]);

INSERT modelo.[Subgenerica]([GenericaId],[Codigo])
SELECT s.[GenericaId],s.[Codigo] FROM (
SELECT DISTINCT [Generica].Id AS [GenericaId],g.[Subgenerica] AS [Codigo] FROM #origen g
JOIN modelo.[TipoTransaccion] [TipoTransaccion] ON [TipoTransaccion].[Codigo]=g.[Tipo_transaccion]
JOIN modelo.[Generica] [Generica] ON [Generica].[TipoTransaccionId]=[TipoTransaccion].Id AND [Generica].[Codigo]=g.[Generica]
) s
WHERE NOT EXISTS(SELECT 1 FROM modelo.[Subgenerica] d WITH(UPDLOCK,HOLDLOCK) WHERE d.[GenericaId]=s.[GenericaId] AND d.[Codigo]=s.[Codigo]);

INSERT modelo.[SubgenericaDetalle]([SubgenericaId],[Codigo])
SELECT s.[SubgenericaId],s.[Codigo] FROM (
SELECT DISTINCT [Subgenerica].Id AS [SubgenericaId],g.[Subgenerica_det] AS [Codigo] FROM #origen g
JOIN modelo.[TipoTransaccion] [TipoTransaccion] ON [TipoTransaccion].[Codigo]=g.[Tipo_transaccion]
JOIN modelo.[Generica] [Generica] ON [Generica].[TipoTransaccionId]=[TipoTransaccion].Id AND [Generica].[Codigo]=g.[Generica]
JOIN modelo.[Subgenerica] [Subgenerica] ON [Subgenerica].[GenericaId]=[Generica].Id AND [Subgenerica].[Codigo]=g.[Subgenerica]
) s
WHERE NOT EXISTS(SELECT 1 FROM modelo.[SubgenericaDetalle] d WITH(UPDLOCK,HOLDLOCK) WHERE d.[SubgenericaId]=s.[SubgenericaId] AND d.[Codigo]=s.[Codigo]);

INSERT modelo.[Especifica]([SubgenericaDetalleId],[Codigo])
SELECT s.[SubgenericaDetalleId],s.[Codigo] FROM (
SELECT DISTINCT [SubgenericaDetalle].Id AS [SubgenericaDetalleId],g.[Especifica] AS [Codigo] FROM #origen g
JOIN modelo.[TipoTransaccion] [TipoTransaccion] ON [TipoTransaccion].[Codigo]=g.[Tipo_transaccion]
JOIN modelo.[Generica] [Generica] ON [Generica].[TipoTransaccionId]=[TipoTransaccion].Id AND [Generica].[Codigo]=g.[Generica]
JOIN modelo.[Subgenerica] [Subgenerica] ON [Subgenerica].[GenericaId]=[Generica].Id AND [Subgenerica].[Codigo]=g.[Subgenerica]
JOIN modelo.[SubgenericaDetalle] [SubgenericaDetalle] ON [SubgenericaDetalle].[SubgenericaId]=[Subgenerica].Id AND [SubgenericaDetalle].[Codigo]=g.[Subgenerica_det]
) s
WHERE NOT EXISTS(SELECT 1 FROM modelo.[Especifica] d WITH(UPDLOCK,HOLDLOCK) WHERE d.[SubgenericaDetalleId]=s.[SubgenericaDetalleId] AND d.[Codigo]=s.[Codigo]);

INSERT modelo.[EspecificaDetalle]([EspecificaId],[Codigo])
SELECT s.[EspecificaId],s.[Codigo] FROM (
SELECT DISTINCT [Especifica].Id AS [EspecificaId],g.[Especifica_det] AS [Codigo] FROM #origen g
JOIN modelo.[TipoTransaccion] [TipoTransaccion] ON [TipoTransaccion].[Codigo]=g.[Tipo_transaccion]
JOIN modelo.[Generica] [Generica] ON [Generica].[TipoTransaccionId]=[TipoTransaccion].Id AND [Generica].[Codigo]=g.[Generica]
JOIN modelo.[Subgenerica] [Subgenerica] ON [Subgenerica].[GenericaId]=[Generica].Id AND [Subgenerica].[Codigo]=g.[Subgenerica]
JOIN modelo.[SubgenericaDetalle] [SubgenericaDetalle] ON [SubgenericaDetalle].[SubgenericaId]=[Subgenerica].Id AND [SubgenericaDetalle].[Codigo]=g.[Subgenerica_det]
JOIN modelo.[Especifica] [Especifica] ON [Especifica].[SubgenericaDetalleId]=[SubgenericaDetalle].Id AND [Especifica].[Codigo]=g.[Especifica]
) s
WHERE NOT EXISTS(SELECT 1 FROM modelo.[EspecificaDetalle] d WITH(UPDLOCK,HOLDLOCK) WHERE d.[EspecificaId]=s.[EspecificaId] AND d.[Codigo]=s.[Codigo]);

INSERT modelo.[FuenteFinanciamiento]([Codigo])
SELECT s.[Codigo] FROM (
SELECT DISTINCT g.[IdFuente] AS [Codigo] FROM #origen g

) s
WHERE NOT EXISTS(SELECT 1 FROM modelo.[FuenteFinanciamiento] d WITH(UPDLOCK,HOLDLOCK) WHERE d.[Codigo]=s.[Codigo]);

INSERT modelo.[Rubro]([FuenteFinanciamientoId],[Codigo])
SELECT s.[FuenteFinanciamientoId],s.[Codigo] FROM (
SELECT DISTINCT [FuenteFinanciamiento].Id AS [FuenteFinanciamientoId],g.[IdRubro] AS [Codigo] FROM #origen g
JOIN modelo.[FuenteFinanciamiento] [FuenteFinanciamiento] ON [FuenteFinanciamiento].[Codigo]=g.[IdFuente]
) s
WHERE NOT EXISTS(SELECT 1 FROM modelo.[Rubro] d WITH(UPDLOCK,HOLDLOCK) WHERE d.[FuenteFinanciamientoId]=s.[FuenteFinanciamientoId] AND d.[Codigo]=s.[Codigo]);

INSERT modelo.[TipoRecurso]([RubroId],[Codigo])
SELECT s.[RubroId],s.[Codigo] FROM (
SELECT DISTINCT [Rubro].Id AS [RubroId],g.[IdTipoRecurso] AS [Codigo] FROM #origen g
JOIN modelo.[FuenteFinanciamiento] [FuenteFinanciamiento] ON [FuenteFinanciamiento].[Codigo]=g.[IdFuente]
JOIN modelo.[Rubro] [Rubro] ON [Rubro].[FuenteFinanciamientoId]=[FuenteFinanciamiento].Id AND [Rubro].[Codigo]=g.[IdRubro]
) s
WHERE NOT EXISTS(SELECT 1 FROM modelo.[TipoRecurso] d WITH(UPDLOCK,HOLDLOCK) WHERE d.[RubroId]=s.[RubroId] AND d.[Codigo]=s.[Codigo]);

INSERT modelo.[Proyecto]([Codigo])
SELECT s.[Codigo] FROM (
SELECT DISTINCT g.[IdProyecto] AS [Codigo] FROM #origen g

) s
WHERE NOT EXISTS(SELECT 1 FROM modelo.[Proyecto] d WITH(UPDLOCK,HOLDLOCK) WHERE d.[Codigo]=s.[Codigo]);

INSERT modelo.[ProyectoSNIP]([Codigo])
SELECT s.[Codigo] FROM (
SELECT DISTINCT g.[IdProyectoSNIP] AS [Codigo] FROM #origen g

) s
WHERE NOT EXISTS(SELECT 1 FROM modelo.[ProyectoSNIP] d WITH(UPDLOCK,HOLDLOCK) WHERE d.[Codigo]=s.[Codigo]);

INSERT modelo.[Componente]([Codigo])
SELECT s.[Codigo] FROM (
SELECT DISTINCT g.[IdComponente] AS [Codigo] FROM #origen g

) s
WHERE NOT EXISTS(SELECT 1 FROM modelo.[Componente] d WITH(UPDLOCK,HOLDLOCK) WHERE d.[Codigo]=s.[Codigo]);

INSERT modelo.[Finalidad]([Codigo])
SELECT s.[Codigo] FROM (
SELECT DISTINCT g.[IdFinalidad] AS [Codigo] FROM #origen g

) s
WHERE NOT EXISTS(SELECT 1 FROM modelo.[Finalidad] d WITH(UPDLOCK,HOLDLOCK) WHERE d.[Codigo]=s.[Codigo]);

INSERT modelo.[UnidadMedida]([Codigo])
SELECT s.[Codigo] FROM (
SELECT DISTINCT g.[Unidad_Medida] AS [Codigo] FROM #origen g

WHERE g.Unidad_Medida IS NOT NULL) s
WHERE NOT EXISTS(SELECT 1 FROM modelo.[UnidadMedida] d WITH(UPDLOCK,HOLDLOCK) WHERE d.[Codigo]=s.[Codigo]);

SELECT DISTINCT [AnoEje],[IdEjecutora],[IdNivelGobierno],[IdPliego],[IdSector],[SecEjec],[SecFunc],[Sub_tipo_gobierno] INTO #SecuenciaFuncionalOrigen FROM #origen;

INSERT modelo.[SecuenciaFuncional]([ContextoEjecutoraId],[Codigo])
SELECT s.[ContextoEjecutoraId],s.[Codigo] FROM (
SELECT DISTINCT [ContextoEjecutora].Id AS [ContextoEjecutoraId],g.[SecFunc] AS [Codigo] FROM #SecuenciaFuncionalOrigen g
JOIN modelo.[NivelGobierno] [NivelGobierno] ON [NivelGobierno].[Codigo]=g.[IdNivelGobierno]
JOIN modelo.[SubtipoGobierno] [SubtipoGobierno] ON [SubtipoGobierno].[NivelGobiernoId]=[NivelGobierno].Id AND [SubtipoGobierno].[Codigo]=g.[Sub_tipo_gobierno]
JOIN modelo.[Sector] [Sector] ON [Sector].[SubtipoGobiernoId]=[SubtipoGobierno].Id AND [Sector].[Codigo]=g.[IdSector]
JOIN modelo.[Pliego] [Pliego] ON [Pliego].[SectorId]=[Sector].Id AND [Pliego].[Codigo]=g.[IdPliego]
JOIN modelo.[Ejecutora] [Ejecutora] ON [Ejecutora].[PliegoId]=[Pliego].Id AND [Ejecutora].[Codigo]=g.[IdEjecutora]
JOIN modelo.[ContextoEjecutora] [ContextoEjecutora] ON [ContextoEjecutora].[EjecutoraId]=[Ejecutora].Id AND [ContextoEjecutora].[AnoEje]=g.[AnoEje] AND [ContextoEjecutora].[SecEjec]=g.[SecEjec]
) s
WHERE NOT EXISTS(SELECT 1 FROM modelo.[SecuenciaFuncional] d WITH(UPDLOCK,HOLDLOCK) WHERE d.[ContextoEjecutoraId]=s.[ContextoEjecutoraId] AND d.[Codigo]=s.[Codigo]);

SELECT DISTINCT [AnoEje],[IdEjecutora],[IdFinalidad],[IdMeta],[IdNivelGobierno],[IdPliego],[IdSector],[SecEjec],[SecFunc],[Sub_tipo_gobierno],[Unidad_Medida] INTO #MetaOrigen FROM #origen;

INSERT modelo.[Meta]([SecuenciaFuncionalId],[Codigo],[FinalidadId],[UnidadMedidaId])
SELECT s.[SecuenciaFuncionalId],s.[Codigo],s.[FinalidadId],s.[UnidadMedidaId] FROM (
SELECT DISTINCT [SecuenciaFuncional].Id AS [SecuenciaFuncionalId],g.[IdMeta] AS [Codigo],[Finalidad].Id AS [FinalidadId],[UnidadMedida].Id AS [UnidadMedidaId] FROM #MetaOrigen g
JOIN modelo.[NivelGobierno] [NivelGobierno] ON [NivelGobierno].[Codigo]=g.[IdNivelGobierno]
JOIN modelo.[SubtipoGobierno] [SubtipoGobierno] ON [SubtipoGobierno].[NivelGobiernoId]=[NivelGobierno].Id AND [SubtipoGobierno].[Codigo]=g.[Sub_tipo_gobierno]
JOIN modelo.[Sector] [Sector] ON [Sector].[SubtipoGobiernoId]=[SubtipoGobierno].Id AND [Sector].[Codigo]=g.[IdSector]
JOIN modelo.[Pliego] [Pliego] ON [Pliego].[SectorId]=[Sector].Id AND [Pliego].[Codigo]=g.[IdPliego]
JOIN modelo.[Ejecutora] [Ejecutora] ON [Ejecutora].[PliegoId]=[Pliego].Id AND [Ejecutora].[Codigo]=g.[IdEjecutora]
JOIN modelo.[ContextoEjecutora] [ContextoEjecutora] ON [ContextoEjecutora].[EjecutoraId]=[Ejecutora].Id AND [ContextoEjecutora].[AnoEje]=g.[AnoEje] AND [ContextoEjecutora].[SecEjec]=g.[SecEjec]
JOIN modelo.[Finalidad] [Finalidad] ON [Finalidad].[Codigo]=g.[IdFinalidad]
LEFT JOIN modelo.[UnidadMedida] [UnidadMedida] ON [UnidadMedida].[Codigo]=g.[Unidad_Medida]
JOIN modelo.[SecuenciaFuncional] [SecuenciaFuncional] ON [SecuenciaFuncional].[ContextoEjecutoraId]=[ContextoEjecutora].Id AND [SecuenciaFuncional].[Codigo]=g.[SecFunc]
) s
WHERE NOT EXISTS(SELECT 1 FROM modelo.[Meta] d WITH(UPDLOCK,HOLDLOCK) WHERE d.[SecuenciaFuncionalId]=s.[SecuenciaFuncionalId] AND d.[Codigo]=s.[Codigo] AND d.[FinalidadId]=s.[FinalidadId] AND (d.[UnidadMedidaId]=s.[UnidadMedidaId] OR (d.[UnidadMedidaId] IS NULL AND s.[UnidadMedidaId] IS NULL)));

INSERT modelo.[Departamento]([Codigo])
SELECT s.[Codigo] FROM (
SELECT DISTINCT g.[Departamento] AS [Codigo] FROM #origen g

) s
WHERE NOT EXISTS(SELECT 1 FROM modelo.[Departamento] d WITH(UPDLOCK,HOLDLOCK) WHERE d.[Codigo]=s.[Codigo]);

INSERT modelo.[Provincia]([DepartamentoId],[Codigo])
SELECT s.[DepartamentoId],s.[Codigo] FROM (
SELECT DISTINCT [Departamento].Id AS [DepartamentoId],g.[Provincia] AS [Codigo] FROM #origen g
JOIN modelo.[Departamento] [Departamento] ON [Departamento].[Codigo]=g.[Departamento]
) s
WHERE NOT EXISTS(SELECT 1 FROM modelo.[Provincia] d WITH(UPDLOCK,HOLDLOCK) WHERE d.[DepartamentoId]=s.[DepartamentoId] AND d.[Codigo]=s.[Codigo]);

INSERT modelo.[Distrito]([ProvinciaId],[Codigo])
SELECT s.[ProvinciaId],s.[Codigo] FROM (
SELECT DISTINCT [Provincia].Id AS [ProvinciaId],g.[Distrito] AS [Codigo] FROM #origen g
JOIN modelo.[Departamento] [Departamento] ON [Departamento].[Codigo]=g.[Departamento]
JOIN modelo.[Provincia] [Provincia] ON [Provincia].[DepartamentoId]=[Departamento].Id AND [Provincia].[Codigo]=g.[Provincia]
) s
WHERE NOT EXISTS(SELECT 1 FROM modelo.[Distrito] d WITH(UPDLOCK,HOLDLOCK) WHERE d.[ProvinciaId]=s.[ProvinciaId] AND d.[Codigo]=s.[Codigo]);

SELECT g.Id,[Meta].Id AS [MetaId],[ProgramaFuncional].Id AS [ProgramaFuncionalId],[ProgramaPresupuestal].Id AS [ProgramaPresupuestalId],[CategoriaGasto].Id AS [CategoriaGastoId],[EspecificaDetalle].Id AS [EspecificaDetalleId],[TipoRecurso].Id AS [TipoRecursoId],[Proyecto].Id AS [ProyectoId],[ProyectoSNIP].Id AS [ProyectoSNIPId],[Componente].Id AS [ComponenteId],[Distrito].Id AS [DistritoId],g.[TipoActProy] AS [TipoActProyId],g.[MesEje] AS [MesEje],g.[PIA] AS [PIA],g.[PIM] AS [PIM],g.[Certificado] AS [Certificado],g.[CompAnual] AS [CompAnual],g.[AtencionCompMensual] AS [AtencionCompMensual],g.[Devengado] AS [Devengado],g.[Girado] AS [Girado] INTO #hechos FROM #origen g
JOIN modelo.[NivelGobierno] [NivelGobierno] ON [NivelGobierno].[Codigo]=g.[IdNivelGobierno]
JOIN modelo.[SubtipoGobierno] [SubtipoGobierno] ON [SubtipoGobierno].[NivelGobiernoId]=[NivelGobierno].Id AND [SubtipoGobierno].[Codigo]=g.[Sub_tipo_gobierno]
JOIN modelo.[Sector] [Sector] ON [Sector].[SubtipoGobiernoId]=[SubtipoGobierno].Id AND [Sector].[Codigo]=g.[IdSector]
JOIN modelo.[Pliego] [Pliego] ON [Pliego].[SectorId]=[Sector].Id AND [Pliego].[Codigo]=g.[IdPliego]
JOIN modelo.[Ejecutora] [Ejecutora] ON [Ejecutora].[PliegoId]=[Pliego].Id AND [Ejecutora].[Codigo]=g.[IdEjecutora]
JOIN modelo.[ContextoEjecutora] [ContextoEjecutora] ON [ContextoEjecutora].[EjecutoraId]=[Ejecutora].Id AND [ContextoEjecutora].[AnoEje]=g.[AnoEje] AND [ContextoEjecutora].[SecEjec]=g.[SecEjec]
JOIN modelo.[Funcion] [Funcion] ON [Funcion].[Codigo]=g.[Funcion]
JOIN modelo.[ProgramaFuncional] [ProgramaFuncional] ON [ProgramaFuncional].[FuncionId]=[Funcion].Id AND [ProgramaFuncional].[Codigo]=g.[Programa]
JOIN modelo.[ProgramaPresupuestal] [ProgramaPresupuestal] ON [ProgramaPresupuestal].[Codigo]=g.[Programa_ppto]
JOIN modelo.[CategoriaGasto] [CategoriaGasto] ON [CategoriaGasto].[Codigo]=g.[Categ_gasto]
JOIN modelo.[TipoTransaccion] [TipoTransaccion] ON [TipoTransaccion].[Codigo]=g.[Tipo_transaccion]
JOIN modelo.[Generica] [Generica] ON [Generica].[TipoTransaccionId]=[TipoTransaccion].Id AND [Generica].[Codigo]=g.[Generica]
JOIN modelo.[Subgenerica] [Subgenerica] ON [Subgenerica].[GenericaId]=[Generica].Id AND [Subgenerica].[Codigo]=g.[Subgenerica]
JOIN modelo.[SubgenericaDetalle] [SubgenericaDetalle] ON [SubgenericaDetalle].[SubgenericaId]=[Subgenerica].Id AND [SubgenericaDetalle].[Codigo]=g.[Subgenerica_det]
JOIN modelo.[Especifica] [Especifica] ON [Especifica].[SubgenericaDetalleId]=[SubgenericaDetalle].Id AND [Especifica].[Codigo]=g.[Especifica]
JOIN modelo.[EspecificaDetalle] [EspecificaDetalle] ON [EspecificaDetalle].[EspecificaId]=[Especifica].Id AND [EspecificaDetalle].[Codigo]=g.[Especifica_det]
JOIN modelo.[FuenteFinanciamiento] [FuenteFinanciamiento] ON [FuenteFinanciamiento].[Codigo]=g.[IdFuente]
JOIN modelo.[Rubro] [Rubro] ON [Rubro].[FuenteFinanciamientoId]=[FuenteFinanciamiento].Id AND [Rubro].[Codigo]=g.[IdRubro]
JOIN modelo.[TipoRecurso] [TipoRecurso] ON [TipoRecurso].[RubroId]=[Rubro].Id AND [TipoRecurso].[Codigo]=g.[IdTipoRecurso]
JOIN modelo.[Proyecto] [Proyecto] ON [Proyecto].[Codigo]=g.[IdProyecto]
JOIN modelo.[ProyectoSNIP] [ProyectoSNIP] ON [ProyectoSNIP].[Codigo]=g.[IdProyectoSNIP]
JOIN modelo.[Componente] [Componente] ON [Componente].[Codigo]=g.[IdComponente]
JOIN modelo.[Finalidad] [Finalidad] ON [Finalidad].[Codigo]=g.[IdFinalidad]
LEFT JOIN modelo.[UnidadMedida] [UnidadMedida] ON [UnidadMedida].[Codigo]=g.[Unidad_Medida]
JOIN modelo.[SecuenciaFuncional] [SecuenciaFuncional] ON [SecuenciaFuncional].[ContextoEjecutoraId]=[ContextoEjecutora].Id AND [SecuenciaFuncional].[Codigo]=g.[SecFunc]
JOIN modelo.[Meta] [Meta] ON [Meta].[SecuenciaFuncionalId]=[SecuenciaFuncional].Id AND [Meta].[Codigo]=g.[IdMeta] AND [Meta].[FinalidadId]=[Finalidad].Id AND ([Meta].[UnidadMedidaId]=[UnidadMedida].Id OR ([Meta].[UnidadMedidaId] IS NULL AND [UnidadMedida].Id IS NULL))
JOIN modelo.[Departamento] [Departamento] ON [Departamento].[Codigo]=g.[Departamento]
JOIN modelo.[Provincia] [Provincia] ON [Provincia].[DepartamentoId]=[Departamento].Id AND [Provincia].[Codigo]=g.[Provincia]
JOIN modelo.[Distrito] [Distrito] ON [Distrito].[ProvinciaId]=[Provincia].Id AND [Distrito].[Codigo]=g.[Distrito];

UPDATE d SET d.[MetaId]=s.[MetaId],d.[ProgramaFuncionalId]=s.[ProgramaFuncionalId],d.[ProgramaPresupuestalId]=s.[ProgramaPresupuestalId],d.[CategoriaGastoId]=s.[CategoriaGastoId],d.[EspecificaDetalleId]=s.[EspecificaDetalleId],d.[TipoRecursoId]=s.[TipoRecursoId],d.[ProyectoId]=s.[ProyectoId],d.[ProyectoSNIPId]=s.[ProyectoSNIPId],d.[ComponenteId]=s.[ComponenteId],d.[DistritoId]=s.[DistritoId],d.[TipoActProyId]=s.[TipoActProyId],d.[MesEje]=s.[MesEje],d.[PIA]=s.[PIA],d.[PIM]=s.[PIM],d.[Certificado]=s.[Certificado],d.[CompAnual]=s.[CompAnual],d.[AtencionCompMensual]=s.[AtencionCompMensual],d.[Devengado]=s.[Devengado],d.[Girado]=s.[Girado]
FROM modelo.Gasto d JOIN #hechos s ON s.Id=d.Id WHERE d.[MetaId]<>s.[MetaId] OR d.[ProgramaFuncionalId]<>s.[ProgramaFuncionalId] OR d.[ProgramaPresupuestalId]<>s.[ProgramaPresupuestalId] OR d.[CategoriaGastoId]<>s.[CategoriaGastoId] OR d.[EspecificaDetalleId]<>s.[EspecificaDetalleId] OR d.[TipoRecursoId]<>s.[TipoRecursoId] OR d.[ProyectoId]<>s.[ProyectoId] OR d.[ProyectoSNIPId]<>s.[ProyectoSNIPId] OR d.[ComponenteId]<>s.[ComponenteId] OR d.[DistritoId]<>s.[DistritoId] OR d.[TipoActProyId]<>s.[TipoActProyId] OR d.[MesEje]<>s.[MesEje] OR d.[PIA]<>s.[PIA] OR d.[PIM]<>s.[PIM] OR d.[Certificado]<>s.[Certificado] OR d.[CompAnual]<>s.[CompAnual] OR d.[AtencionCompMensual]<>s.[AtencionCompMensual] OR d.[Devengado]<>s.[Devengado] OR d.[Girado]<>s.[Girado];

INSERT modelo.Gasto(Id,[MetaId],[ProgramaFuncionalId],[ProgramaPresupuestalId],[CategoriaGastoId],[EspecificaDetalleId],[TipoRecursoId],[ProyectoId],[ProyectoSNIPId],[ComponenteId],[DistritoId],[TipoActProyId],[MesEje],[PIA],[PIM],[Certificado],[CompAnual],[AtencionCompMensual],[Devengado],[Girado]) SELECT s.[Id],s.[MetaId],s.[ProgramaFuncionalId],s.[ProgramaPresupuestalId],s.[CategoriaGastoId],s.[EspecificaDetalleId],s.[TipoRecursoId],s.[ProyectoId],s.[ProyectoSNIPId],s.[ComponenteId],s.[DistritoId],s.[TipoActProyId],s.[MesEje],s.[PIA],s.[PIM],s.[Certificado],s.[CompAnual],s.[AtencionCompMensual],s.[Devengado],s.[Girado] FROM #hechos s WHERE NOT EXISTS(SELECT 1 FROM modelo.Gasto d WHERE d.Id=s.Id);

IF (SELECT COUNT_BIG(*) FROM #origen)<>(SELECT COUNT_BIG(*) FROM #hechos) THROW 50201,'La normalizacion no conserva todas las filas.',1;
COMMIT;
END;
GO
GRANT EXECUTE ON modelo.NormalizarDocumento TO proinxml_app;
GO

CREATE OR ALTER VIEW modelo.GastoReconstruido AS
SELECT f.Id,[ContextoEjecutora].[AnoEje] AS [AnoEje],
f.[MesEje] AS [MesEje],
[NivelGobierno].[Codigo] AS [IdNivelGobierno],
[SubtipoGobierno].[Codigo] AS [Sub_tipo_gobierno],
[Sector].[Codigo] AS [IdSector],
[Pliego].[Codigo] AS [IdPliego],
[Ejecutora].[Codigo] AS [IdEjecutora],
[ContextoEjecutora].[SecEjec] AS [SecEjec],
[Funcion].[Codigo] AS [Funcion],
[ProgramaFuncional].[Codigo] AS [Programa],
[ProgramaPresupuestal].[Codigo] AS [Programa_ppto],
[CategoriaGasto].[Codigo] AS [Categ_gasto],
[TipoTransaccion].[Codigo] AS [Tipo_transaccion],
[Generica].[Codigo] AS [Generica],
[Subgenerica].[Codigo] AS [Subgenerica],
[SubgenericaDetalle].[Codigo] AS [Subgenerica_det],
[Especifica].[Codigo] AS [Especifica],
[EspecificaDetalle].[Codigo] AS [Especifica_det],
[SecuenciaFuncional].[Codigo] AS [SecFunc],
[FuenteFinanciamiento].[Codigo] AS [IdFuente],
[Rubro].[Codigo] AS [IdRubro],
[TipoRecurso].[Codigo] AS [IdTipoRecurso],
[Componente].[Codigo] AS [IdComponente],
[Proyecto].[Codigo] AS [IdProyecto],
f.[TipoActProyId] AS [TipoActProy],
[Meta].[Codigo] AS [IdMeta],
[Finalidad].[Codigo] AS [IdFinalidad],
[ProyectoSNIP].[Codigo] AS [IdProyectoSNIP],
[Departamento].[Codigo] AS [Departamento],
[Provincia].[Codigo] AS [Provincia],
[Distrito].[Codigo] AS [Distrito],
[UnidadMedida].[Codigo] AS [Unidad_Medida],
f.[PIA] AS [PIA],
f.[PIM] AS [PIM],
f.[Certificado] AS [Certificado],
f.[CompAnual] AS [CompAnual],
f.[AtencionCompMensual] AS [AtencionCompMensual],
f.[Devengado] AS [Devengado],
f.[Girado] AS [Girado]
FROM modelo.Gasto f
JOIN modelo.[Meta] [Meta] ON [Meta].Id=f.[MetaId]
JOIN modelo.[SecuenciaFuncional] [SecuenciaFuncional] ON [SecuenciaFuncional].Id=[Meta].[SecuenciaFuncionalId]
JOIN modelo.[ContextoEjecutora] [ContextoEjecutora] ON [ContextoEjecutora].Id=[SecuenciaFuncional].[ContextoEjecutoraId]
JOIN modelo.[Ejecutora] [Ejecutora] ON [Ejecutora].Id=[ContextoEjecutora].[EjecutoraId]
JOIN modelo.[Pliego] [Pliego] ON [Pliego].Id=[Ejecutora].[PliegoId]
JOIN modelo.[Sector] [Sector] ON [Sector].Id=[Pliego].[SectorId]
JOIN modelo.[SubtipoGobierno] [SubtipoGobierno] ON [SubtipoGobierno].Id=[Sector].[SubtipoGobiernoId]
JOIN modelo.[NivelGobierno] [NivelGobierno] ON [NivelGobierno].Id=[SubtipoGobierno].[NivelGobiernoId]
JOIN modelo.[Finalidad] [Finalidad] ON [Finalidad].Id=[Meta].[FinalidadId]
LEFT JOIN modelo.[UnidadMedida] [UnidadMedida] ON [UnidadMedida].Id=[Meta].[UnidadMedidaId]
JOIN modelo.[ProgramaFuncional] [ProgramaFuncional] ON [ProgramaFuncional].Id=f.[ProgramaFuncionalId]
JOIN modelo.[Funcion] [Funcion] ON [Funcion].Id=[ProgramaFuncional].[FuncionId]
JOIN modelo.[ProgramaPresupuestal] [ProgramaPresupuestal] ON [ProgramaPresupuestal].Id=f.[ProgramaPresupuestalId]
JOIN modelo.[CategoriaGasto] [CategoriaGasto] ON [CategoriaGasto].Id=f.[CategoriaGastoId]
JOIN modelo.[EspecificaDetalle] [EspecificaDetalle] ON [EspecificaDetalle].Id=f.[EspecificaDetalleId]
JOIN modelo.[Especifica] [Especifica] ON [Especifica].Id=[EspecificaDetalle].[EspecificaId]
JOIN modelo.[SubgenericaDetalle] [SubgenericaDetalle] ON [SubgenericaDetalle].Id=[Especifica].[SubgenericaDetalleId]
JOIN modelo.[Subgenerica] [Subgenerica] ON [Subgenerica].Id=[SubgenericaDetalle].[SubgenericaId]
JOIN modelo.[Generica] [Generica] ON [Generica].Id=[Subgenerica].[GenericaId]
JOIN modelo.[TipoTransaccion] [TipoTransaccion] ON [TipoTransaccion].Id=[Generica].[TipoTransaccionId]
JOIN modelo.[TipoRecurso] [TipoRecurso] ON [TipoRecurso].Id=f.[TipoRecursoId]
JOIN modelo.[Rubro] [Rubro] ON [Rubro].Id=[TipoRecurso].[RubroId]
JOIN modelo.[FuenteFinanciamiento] [FuenteFinanciamiento] ON [FuenteFinanciamiento].Id=[Rubro].[FuenteFinanciamientoId]
JOIN modelo.[Proyecto] [Proyecto] ON [Proyecto].Id=f.[ProyectoId]
JOIN modelo.[ProyectoSNIP] [ProyectoSNIP] ON [ProyectoSNIP].Id=f.[ProyectoSNIPId]
JOIN modelo.[Componente] [Componente] ON [Componente].Id=f.[ComponenteId]
JOIN modelo.[Distrito] [Distrito] ON [Distrito].Id=f.[DistritoId]
JOIN modelo.[Provincia] [Provincia] ON [Provincia].Id=[Distrito].[ProvinciaId]
JOIN modelo.[Departamento] [Departamento] ON [Departamento].Id=[Provincia].[DepartamentoId];
GO
