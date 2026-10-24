"""Coordina el mantenimiento con todas las escrituras de la cola y del worker."""


def integration_lock(connection, *, exclusive=False):
    mode = 'Exclusive' if exclusive else 'Shared'
    connection.execute(
        "DECLARE @r int; EXEC @r=sys.sp_getapplock "
        "@Resource=N'ProInXML:integracion:mantenimiento',@LockMode=?,"
        "@LockOwner='Transaction',@LockTimeout=5000; "
        "IF @r<0 THROW 50201,'Otra operacion mantiene ocupada la integracion. Intenta nuevamente.',1;",
        mode,
    )
