class NotificationNotFound(Exception):
    def __init__(self, identifier: str):
        super().__init__(f"Notificación {identifier} no encontrada")
        self.identifier = identifier


class EmailDeliveryError(Exception):
    """Base de los fallos de envío de correo.

    La distinción entre transitorio y permanente no es cosmética: decide si el
    aviso queda en la cola para reintentarse o si se desactivan las alertas del
    usuario. Son dos criterios de aceptación distintos de la HdU 08.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class TransientEmailError(EmailDeliveryError):
    """El servicio de correo no respondió, pero el destinatario puede ser válido.

    Conexión rechazada, timeout, o un 4xx del servidor. El envío se reintenta.
    """


class PermanentEmailError(EmailDeliveryError):
    """El destinatario no existe o fue rechazado de forma definitiva.

    Un 5xx sobre la dirección. Reintentar no cambiaría nada, así que se registra
    el fallo y se desactiva el envío para ese usuario.
    """
