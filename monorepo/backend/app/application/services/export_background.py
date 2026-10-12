"""Puerto para terminar una exportación después de haber respondido (criterios 8 y 9).

Quien lo implementa se ocupa de lo que el caso de uso no debe saber: mantener
viva la tarea, abrir una sesión de base de datos propia —la de la petición ya se
cerró— y enviar el correo.
"""

import asyncio
from typing import Protocol

from app.domain.entities.export_job import ExportJob


class IExportBackground(Protocol):
    def schedule(
        self,
        job: ExportJob,
        render: "asyncio.Task[bytes]",
        recipient: str,
        tender_name: str,
    ) -> None: ...
