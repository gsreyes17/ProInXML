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
  NombreLote nvarchar(260) NOT NULL,UrlSolicitada nvarchar(1000) NOT NULL,
  AnoEje smallint NOT NULL,SecEjec int NOT NULL,
  Concurrencia smallint NOT NULL CONSTRAINT CK_Metrica_Concurrencia CHECK(Concurrencia BETWEEN 1 AND 20),
  Estado varchar(16) NOT NULL DEFAULT 'EnCurso'
    CONSTRAINT CK_Metrica_Estado CHECK(Estado IN('EnCurso','Completado','Error','Interrumpido')),
  Etapa nvarchar(40) NOT NULL DEFAULT N'Descarga',HttpStatus int NULL,
  BytesRecibidos bigint NOT NULL DEFAULT 0,
  RegistrosLeidos int NOT NULL DEFAULT 0,RegistrosInsertados int NOT NULL DEFAULT 0,
  RegistrosReutilizados int NOT NULL DEFAULT 0,RegistrosNormalizados int NOT NULL DEFAULT 0,
  DescargaMs decimal(19,3) NULL,OriginalMs decimal(19,3) NULL,EsperaSqlMs decimal(19,3) NULL,
  ValidacionMs decimal(19,3) NULL,InsercionMs decimal(19,3) NULL,NormalizacionMs decimal(19,3) NULL,
  ConfirmacionMs decimal(19,3) NULL,TotalMs decimal(19,3) NULL,
  InicioUtc datetime2(3) NOT NULL DEFAULT SYSUTCDATETIME(),FinUtc datetime2(3) NULL,
  MedicionFinalizada bit NOT NULL DEFAULT 0,Error nvarchar(2000) NULL,
  CreadoUtc datetime2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
  CONSTRAINT CK_Metrica_Bytes CHECK(BytesRecibidos>=0),
  CONSTRAINT CK_Metrica_Filas CHECK(RegistrosLeidos>=0 AND RegistrosInsertados>=0 AND RegistrosReutilizados>=0 AND RegistrosNormalizados>=0),
  CONSTRAINT CK_Metrica_Tiempos CHECK(
   (DescargaMs IS NULL OR DescargaMs>=0) AND (OriginalMs IS NULL OR OriginalMs>=0) AND
   (EsperaSqlMs IS NULL OR EsperaSqlMs>=0) AND (ValidacionMs IS NULL OR ValidacionMs>=0) AND
   (InsercionMs IS NULL OR InsercionMs>=0) AND (NormalizacionMs IS NULL OR NormalizacionMs>=0) AND
   (ConfirmacionMs IS NULL OR ConfirmacionMs>=0) AND (TotalMs IS NULL OR TotalMs>=0))
 );
 CREATE INDEX IX_Metrica_Lote ON analisis.MetricaIntento(LoteId,Id DESC);
 CREATE INDEX IX_Metrica_Estado ON analisis.MetricaIntento(Estado,IntentoId) INCLUDE(FinUtc);
END;
-- Identificadores historicos SIN FK: las mediciones sobreviven a la limpieza
-- del laboratorio para comparar ensayos. No se reinician las identidades.
GRANT SELECT,INSERT,UPDATE ON SCHEMA::analisis TO proinxml_app;
DENY DELETE,ALTER ON SCHEMA::analisis TO proinxml_app;
COMMIT;
GO
