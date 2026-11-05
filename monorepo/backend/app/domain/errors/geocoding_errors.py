class GeocodingUnavailable(Exception):
    """El servicio de geocodificación no respondió o respondió algo inutilizable.

    No es "no encontrado": eso es un `None`. Ante este error la licitación queda
    pendiente y se vuelve a intentar en la vuelta siguiente.
    """
