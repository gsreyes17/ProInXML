-- Historial de tiempos por intento. Se conserva en la limpieza desde la interfaz.
USE ProInXML;
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
BEGIN TRANSACTION;
IF SCHEMA_ID(N'analisis') IS NULL EXEC(N'CREATE SCHEMA analisis AUTHORIZATION dbo');
IF OBJECT_ID(N'analisis.MetricaIntento',N'U') IS NULL
BEGIN
 CREATE TABLE analisis.MetricaIntento(
  Id bigint IDENTITY PRIMARY KEY,
  IntentoId bigint NOT NULL CONSTRAINT UQ_Metrica_Intento UNIQUE,
  TrabajoId bigint NOT NULL,LoteId bigint NOT NULL,DocumentoId bigint NULL,
  NombreLote nvarchar(260) NOT NULL,URLSolicitada nvarchar(1000) NOT NULL,
  AnoEje smallint NOT NULL,SecEjec int NOT NULL,
  Concurrencia smallint NOT NULL CONSTRAINT CK_Metrica_Concurrencia CHECK(Concurrencia BETWEEN 1 AND 20),
  Estado varchar(16) NOT NULL DEFAULT 'EnCurso'
    CONSTRAINT CK_Metrica_Estado CHECK(Estado IN('EnCurso','Completado','Error','Interrumpido')),
  Etapa nvarchar(40) NOT NULL DEFAULT N'Descarga',HTTPStatus int NULL,
  BytesRecibidos bigint NOT NULL DEFAULT 0,
  RegistrosLeidos int NOT NULL DEFAULT 0,RegistrosInsertados int NOT NULL DEFAULT 0,
  RegistrosReutilizados int NOT NULL DEFAULT 0,RegistrosNormalizados int NOT NULL DEFAULT 0,
  DescargaMs decimal(19,3) NULL,OriginalMs decimal(19,3) NULL,EsperaSQLMs decimal(19,3) NULL,
  ValidacionMs decimal(19,3) NULL,InsercionMs decimal(19,3) NULL,NormalizacionMs decimal(19,3) NULL,
  ConfirmacionMs decimal(19,3) NULL,TotalMs decimal(19,3) NULL,
  InicioUTC datetime2(3) NOT NULL DEFAULT SYSUTCDATETIME(),FinUTC datetime2(3) NULL,
  MedicionFinalizada bit NOT NULL DEFAULT 0,Error nvarchar(2000) NULL,
  CONSTRAINT CK_Metrica_Bytes CHECK(BytesRecibidos>=0),
  CONSTRAINT CK_Metrica_Filas CHECK(RegistrosLeidos>=0 AND RegistrosInsertados>=0 AND RegistrosReutilizados>=0 AND RegistrosNormalizados>=0),
  CONSTRAINT CK_Metrica_Tiempos CHECK(
   (DescargaMs IS NULL OR DescargaMs>=0) AND (OriginalMs IS NULL OR OriginalMs>=0) AND
   (EsperaSQLMs IS NULL OR EsperaSQLMs>=0) AND (ValidacionMs IS NULL OR ValidacionMs>=0) AND
   (InsercionMs IS NULL OR InsercionMs>=0) AND (NormalizacionMs IS NULL OR NormalizacionMs>=0) AND
   (ConfirmacionMs IS NULL OR ConfirmacionMs>=0) AND (TotalMs IS NULL OR TotalMs>=0))
 );
 CREATE INDEX IX_Metrica_Lote ON analisis.MetricaIntento(LoteId,Id DESC);
 CREATE INDEX IX_Metrica_Estado ON analisis.MetricaIntento(Estado,IntentoId) INCLUDE(FinUTC);
END;
-- La tabla historica puede contener una fecha de creacion redundante.
IF COL_LENGTH(N'analisis.MetricaIntento',N'CreadoUTC') IS NOT NULL
BEGIN
 DECLARE @default sysname,@sql nvarchar(max);
 SELECT @default=dc.name FROM sys.default_constraints dc
 JOIN sys.columns c ON c.object_id=dc.parent_object_id AND c.column_id=dc.parent_column_id
 WHERE dc.parent_object_id=OBJECT_ID(N'analisis.MetricaIntento') AND c.name=N'CreadoUTC';
 IF @default IS NOT NULL
 BEGIN
  SET @sql=N'ALTER TABLE analisis.MetricaIntento DROP CONSTRAINT '+QUOTENAME(@default);
  EXEC sys.sp_executesql @sql;
 END;
 ALTER TABLE analisis.MetricaIntento DROP COLUMN CreadoUTC;
END;
-- Identificadores historicos SIN FK: las mediciones sobreviven a la limpieza
-- desde la interfaz para comparar ensayos. El reinicio total si las elimina.
GRANT SELECT,INSERT,UPDATE ON SCHEMA::analisis TO proinxml_app;
DENY DELETE,ALTER ON SCHEMA::analisis TO proinxml_app;
COMMIT;
GO
