/*
  REINICIO COMPLETO DE DATOS DE PROINXML (uso personal de laboratorio).

  Elimina XML, modelo, cola, lotes, intentos, auditoria, metricas y usuarios.
  Conserva tablas, vistas, procedimientos, permisos e indices.
  Restaura tres roles, dos cuentas de laboratorio, la identidad tecnica sistema
  (sin acceso interactivo) y el servicio MEF.
  Reinicia las identidades para que las siguientes inserciones comiencen en 1.
  No modifica otras bases ni dbo.sysdiagrams.

  Antes: detener API, worker y Vue; guardar respaldo de la base.
  Ejecutar con sysadmin o db_owner desde SSMS como un lote completo.
  Por defecto SOLO muestra conteos. Para borrar, cambiar @Ejecutar a 1
  y completar @Confirmacion con el texto indicado. No usar el instalador SQL.

  Despues, desde la raiz del proyecto:
    .\.venv\Scripts\python.exe scripts/cargar_ubigeo.py --sin-auditoria
    .\iniciar.cmd
*/
USE [ProInXML];
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;

DECLARE @Ejecutar bit = 0;
DECLARE @Confirmacion nvarchar(100) = N'';
DECLARE @BaseEsperada sysname = N'ProInXML';

IF DB_NAME() <> @BaseEsperada
    THROW 50300, 'La base actual no coincide con la base esperada.', 1;
IF @@TRANCOUNT <> 0
    THROW 50301, 'Ejecutar fuera de una transaccion previa.', 1;
IF OBJECT_ID(N'integracion.Consulta', N'U') IS NULL
    OR OBJECT_ID(N'modelo.Gasto', N'U') IS NULL
    OR OBJECT_ID(N'analisis.MetricaIntento', N'U') IS NULL
    THROW 50302, 'Se requiere el esquema completo ProInXML 1.0.', 1;

DROP TABLE IF EXISTS #TablasReinicio;
DROP TABLE IF EXISTS #RelacionesReinicio;
DROP TABLE IF EXISTS #TriggersReinicio;
CREATE TABLE #TablasReinicio (
    ObjectId int PRIMARY KEY,
    Nombre nvarchar(517) NOT NULL,
    FilasAntes bigint NULL,
    FilasDespues bigint NULL
);

INSERT #TablasReinicio(ObjectId, Nombre)
SELECT t.object_id, QUOTENAME(s.name) + N'.' + QUOTENAME(t.name)
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE t.is_ms_shipped = 0 AND s.name IN
    (N'integracion', N'staging', N'modelo', N'seguridad', N'auditoria', N'analisis');

-- No alterar dependencias de tablas ajenas al proyecto.
IF EXISTS (
    SELECT 1 FROM sys.foreign_keys fk
    JOIN #TablasReinicio destino ON destino.ObjectId = fk.referenced_object_id
    LEFT JOIN #TablasReinicio origen ON origen.ObjectId = fk.parent_object_id
    WHERE origen.ObjectId IS NULL
)
    THROW 50303, 'Hay referencias externas al alcance del reinicio; revisar antes de borrar.', 1;

DECLARE @Tabla nvarchar(517), @SQL nvarchar(max), @Filas bigint;
DECLARE conteos CURSOR LOCAL FAST_FORWARD FOR
    SELECT Nombre FROM #TablasReinicio ORDER BY Nombre;
OPEN conteos;
FETCH NEXT FROM conteos INTO @Tabla;
WHILE @@FETCH_STATUS = 0
BEGIN
    SET @SQL = N'SELECT @Cantidad = COUNT_BIG(*) FROM ' + @Tabla + N';';
    EXEC sys.sp_executesql @SQL, N'@Cantidad bigint OUTPUT', @Cantidad = @Filas OUTPUT;
    UPDATE #TablasReinicio SET FilasAntes = @Filas WHERE Nombre = @Tabla;
    FETCH NEXT FROM conteos INTO @Tabla;
END;
CLOSE conteos;
DEALLOCATE conteos;

SELECT DB_NAME() AS BaseDeDatos, Nombre AS Tabla, FilasAntes
FROM #TablasReinicio ORDER BY Nombre;

IF @Ejecutar = 0
BEGIN
    PRINT N'SOLO VISTA PREVIA: no se elimino ningun dato.';
    PRINT N'Para borrar: detener los procesos, respaldar, poner @Ejecutar = 1';
    PRINT N'y @Confirmacion = N''VACIAR COMPLETAMENTE ProInXML''.';
    RETURN;
END;

IF @Confirmacion <> N'VACIAR COMPLETAMENTE ProInXML'
    THROW 50304, 'Falta la confirmacion exacta del reinicio completo.', 1;
IF COALESCE(IS_SRVROLEMEMBER(N'sysadmin'), 0) <> 1
    AND COALESCE(IS_MEMBER(N'db_owner'), 0) <> 1
    THROW 50305, 'Este reinicio requiere sysadmin o db_owner, no el rol de aplicacion.', 1;

-- Guardar el estado para restaurar solamente protecciones originalmente activas.
SELECT t.Nombre AS Tabla, QUOTENAME(fk.name) AS Restriccion,
    fk.is_not_trusted AS NoConfiable
INTO #RelacionesReinicio
FROM sys.foreign_keys fk
JOIN #TablasReinicio t ON t.ObjectId = fk.parent_object_id
WHERE fk.is_disabled = 0;

SELECT t.Nombre AS Tabla, QUOTENAME(OBJECT_SCHEMA_NAME(tr.object_id))
    + N'.' + QUOTENAME(tr.name) AS Nombre
INTO #TriggersReinicio
FROM sys.triggers tr
JOIN #TablasReinicio t ON t.ObjectId = tr.parent_id
WHERE tr.is_disabled = 0 AND tr.is_ms_shipped = 0;

DECLARE @Bloqueo int;
BEGIN TRY
    BEGIN TRANSACTION;
    EXEC @Bloqueo = sys.sp_getapplock
        @Resource = N'ProInXML:integracion:mantenimiento',
        @LockMode = 'Exclusive', @LockOwner = 'Transaction', @LockTimeout = 5000;
    IF @Bloqueo < 0
        THROW 50306, 'La integracion esta ocupada; detener los procesos y volver a intentar.', 1;
    EXEC @Bloqueo = sys.sp_getapplock
        @Resource = N'ProInXML:modelo:normalizacion',
        @LockMode = 'Exclusive', @LockOwner = 'Transaction', @LockTimeout = 5000;
    IF @Bloqueo < 0
        THROW 50307, 'La normalizacion esta ocupada; detener los procesos y volver a intentar.', 1;

    -- Se suspenden la generacion de auditoria y sus protecciones de inmutabilidad
    -- solo dentro de esta transaccion administrativa; no cambian los permisos.
    SET @SQL = N'';
    SELECT @SQL = @SQL + N'DISABLE TRIGGER ' + Nombre + N' ON ' + Tabla + N';'
    FROM #TriggersReinicio;
    EXEC sys.sp_executesql @SQL;

    -- Las referencias circulares Consulta/Documento/Intento impiden un borrado
    -- lineal. Se suspenden solo las FK de las tablas incluidas, no los CHECK.
    SET @SQL = N'';
    SELECT @SQL = @SQL + N'ALTER TABLE ' + Tabla + N' NOCHECK CONSTRAINT ' + Restriccion + N';'
    FROM #RelacionesReinicio;
    EXEC sys.sp_executesql @SQL;

    DECLARE borrar CURSOR LOCAL FAST_FORWARD FOR
        SELECT Nombre FROM #TablasReinicio ORDER BY Nombre;
    OPEN borrar;
    FETCH NEXT FROM borrar INTO @Tabla;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @SQL = N'DELETE FROM ' + @Tabla + N';';
        EXEC sys.sp_executesql @SQL;
        RAISERROR(N'Vaciada: %s', 10, 1, @Tabla) WITH NOWAIT;
        FETCH NEXT FROM borrar INTO @Tabla;
    END;
    CLOSE borrar;
    DEALLOCATE borrar;

    -- DELETE conserva el contador IDENTITY. Todas las identidades del proyecto
    -- usan semilla 1 e incremento 1; con la tabla vacia, RESEED 0 hace que
    -- la siguiente fila reciba Id = 1.
    IF EXISTS (
        SELECT 1 FROM sys.identity_columns ic
        JOIN #TablasReinicio t ON t.ObjectId = ic.object_id
        WHERE CONVERT(decimal(38, 0), ic.seed_value) <> 1
           OR CONVERT(decimal(38, 0), ic.increment_value) <> 1
    )
        THROW 50308, 'Una identidad no usa semilla 1 e incremento 1; revisar el reinicio.', 1;

    DECLARE reiniciar_identidad CURSOR LOCAL FAST_FORWARD FOR
        SELECT t.Nombre FROM #TablasReinicio t
        JOIN sys.identity_columns ic ON ic.object_id = t.ObjectId
        ORDER BY t.Nombre;
    OPEN reiniciar_identidad;
    FETCH NEXT FROM reiniciar_identidad INTO @Tabla;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @SQL = N'DBCC CHECKIDENT (''' + REPLACE(@Tabla, N'''', N'''''')
            + N''', RESEED, 0) WITH NO_INFOMSGS;';
        EXEC sys.sp_executesql @SQL;
        FETCH NEXT FROM reiniciar_identidad INTO @Tabla;
    END;
    CLOSE reiniciar_identidad;
    DEALLOCATE reiniciar_identidad;

    -- Semillas equivalentes a la instalacion; las cuentas 1 y 2 pueden iniciar sesion.
    INSERT seguridad.Rol(Nombre)
    VALUES (N'Administrador'), (N'Operador'), (N'Consulta');
    INSERT seguridad.Usuario(NombreUsuario, NombreCompleto, HashContrasena, RolId)
    SELECT N'administrador', N'Administrador del laboratorio',
        N'$argon2id$v=19$m=65536,t=3,p=4$rcbB6kOYofzQoPAaUwiedQ$j00zAhNMEIALKDSvlQghMLbqAm8LdyVtyaOnE5vGHjk', Id
    FROM seguridad.Rol WHERE Nombre = N'Administrador';
    INSERT seguridad.Usuario(NombreUsuario, NombreCompleto, HashContrasena, RolId)
    SELECT N'operador', N'Operador del laboratorio',
        N'$argon2id$v=19$m=65536,t=3,p=4$ivlnttTqyrNeYp9kHoSLnQ$iLf1BKzExbgUfC+aYLTlKJyjrjW3+XmQEcsZL2m6WJM', Id
    FROM seguridad.Rol WHERE Nombre = N'Operador';
    INSERT seguridad.Usuario(NombreUsuario, NombreCompleto, HashContrasena, RolId, Activo)
    SELECT N'sistema', N'Proceso de integracion', N'!no-login!', Id, 0
    FROM seguridad.Rol WHERE Nombre = N'Administrador';
    INSERT integracion.Servicio(Nombre, URLBase, Ruta, VersionContrato)
    VALUES (N'MEF Gasto PIP', N'http://s3.mef.gob.pe',
        N'/servicios/WSPCM/SG/gastopipsg-old.asmx/ObtenerDataGastoPIP_old_2', '1');

    -- Restaurar FK y confianza previa. Las deshabilitadas inicialmente no cambian.
    SET @SQL = N'';
    SELECT @SQL = @SQL + N'ALTER TABLE ' + Tabla
        + CASE WHEN NoConfiable = 0 THEN N' WITH CHECK CHECK CONSTRAINT '
            ELSE N' WITH NOCHECK CHECK CONSTRAINT ' END + Restriccion + N';'
    FROM #RelacionesReinicio;
    EXEC sys.sp_executesql @SQL;

    SET @SQL = N'';
    SELECT @SQL = @SQL + N'ENABLE TRIGGER ' + Nombre + N' ON ' + Tabla + N';'
    FROM #TriggersReinicio;
    EXEC sys.sp_executesql @SQL;

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    -- SQL Server tambien revierte los cambios de estado de FK y triggers.
    THROW;
END CATCH;

DECLARE resultado CURSOR LOCAL FAST_FORWARD FOR
    SELECT Nombre FROM #TablasReinicio ORDER BY Nombre;
OPEN resultado;
FETCH NEXT FROM resultado INTO @Tabla;
WHILE @@FETCH_STATUS = 0
BEGIN
    SET @SQL = N'SELECT @Cantidad = COUNT_BIG(*) FROM ' + @Tabla + N';';
    EXEC sys.sp_executesql @SQL, N'@Cantidad bigint OUTPUT', @Cantidad = @Filas OUTPUT;
    UPDATE #TablasReinicio SET FilasDespues = @Filas WHERE Nombre = @Tabla;
    FETCH NEXT FROM resultado INTO @Tabla;
END;
CLOSE resultado;
DEALLOCATE resultado;
SELECT Nombre AS Tabla, FilasAntes, FilasDespues
FROM #TablasReinicio ORDER BY Nombre;
PRINT N'Reinicio completo confirmado. Auditoria borrada e identidades reiniciadas.';
PRINT N'Cargar ubigeos con scripts/cargar_ubigeo.py antes de procesar XML.';
