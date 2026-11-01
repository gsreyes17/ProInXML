"""Punto unico de normalizacion, dentro de la transaccion de persistencia."""


def normalize_document(connection, document_id: int):
    connection.execute("EXEC modelo.NormalizarDocumento @DocumentoId=?", document_id)


def acquire_document_lock(connection):
    """Antes de escribir detalle: evita esperas circulares entre FK y normalizacion."""
    connection.execute(
        "DECLARE @r int; EXEC @r=sys.sp_getapplock "
        "@Resource=N'ProInXML:modelo:normalizacion',@LockMode='Exclusive',"
        "@LockOwner='Transaction',@LockTimeout=60000; "
        "IF @r<0 THROW 50200,'No se pudo bloquear la persistencia del documento.',1;"
    )
