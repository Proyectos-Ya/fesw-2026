from abc import ABC, abstractmethod

from app.domain.models.cambio_estado import PunteroDeCambio, ResultadoPunteros


class ITenderIngestionQueue(ABC):
    """La cola de ingesta (`tender_metadata`), vista desde quien la alimenta."""

    @abstractmethod
    async def reencolar(self, codigos: list[str]) -> int:
        """Devuelve esos códigos a la cola para que el ingest baje su detalle.

        Sirve para licitaciones **ya procesadas**: el listado normal las inserta
        con `ON CONFLICT DO NOTHING` y nunca las vuelve a mirar. Una que ya está
        pendiente queda igual, así que repetir la llamada es seguro. Devuelve
        cuántas filas quedaron pendientes.
        """
        ...

    @abstractmethod
    async def registrar_punteros(
        self, punteros: list[PunteroDeCambio]
    ) -> ResultadoPunteros:
        """Deja en la cola lo que el ingest tiene que bajar y por qué (plan 305).

        Por cada código guarda el estado y la `fecha_ultimo_cambio` del listado,
        y según la intención:

        - `NUEVA`: la encola como `nueva` si no estaba en la cola.
        - `ACTUALIZAR_SI_CAMBIO`: la encola como `actualizar` solo si el cambio
          es posterior a la última bajada de su detalle (con margen).
        - `REABIERTA`: la encola como `actualizar` sin condición.
        - `INACTIVA`: si estaba pendiente, la pasa a terminal.

        Una fila terminal no se reactiva, salvo una reapertura de algo que se
        descartó por inactivo. Repetir la llamada no cambia nada.
        """
        ...
