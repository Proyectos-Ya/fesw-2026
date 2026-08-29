from uuid import UUID

from app.application.repositories.supplier_repository import ISupplierRepository
from app.shared.datetime_utils import utc_now_naive


class AnswerQuestionUseCase:
    def __init__(self, supplier_repo: ISupplierRepository):
        self.supplier_repo = supplier_repo

    async def execute(self, user_id: UUID, field_name: str, answer: str) -> None:
        """Guarda la respuesta en las keywords de la empresa de `user_id`.

        La empresa se resuelve **desde la sesión** y no desde un identificador
        que mande el cliente. Antes se recibía un `supplier_id` del cuerpo de la
        petición y se buscaba por id de empresa o, al no encontrarlo, por id de
        usuario: cualquiera que conociera el UUID de otra empresa podía escribir
        en sus keywords, que alimentan la consulta del reranker y el servicio de
        ponderación. Con la identidad fuera del alcance del cliente el problema
        deja de existir, en vez de depender de una comprobación que alguien
        pueda olvidar replicar en el próximo endpoint.
        """
        supplier = await self.supplier_repo.get_by_user_id(user_id)

        if supplier is None:
            raise ValueError("El usuario no tiene una empresa asociada.")

        if supplier.keywords is None:
            supplier.keywords = []

        new_keyword = f"{field_name}:{answer}"

        supplier.keywords = [
            kw for kw in supplier.keywords if not kw.startswith(f"{field_name}:")
        ]

        supplier.keywords.append(new_keyword)
        supplier.updated_at = utc_now_naive()

        await self.supplier_repo.update(supplier)
