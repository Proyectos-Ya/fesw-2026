"""Set workspace match threshold (HU-18).

Permite al admin del workspace fijar un umbral de match a nivel de empresa.
Pasa None para volver al fallback por preferencia individual.
"""

from uuid import UUID

from app.application.repositories.supplier_member_repository import (
    ISupplierMemberRepository,
)
from app.application.repositories.supplier_repository import ISupplierRepository
from app.domain.entities.supplier import Supplier
from app.domain.entities.supplier_member import MemberStatus
from app.domain.errors.membership_errors import UnauthorizedWorkspaceAction
from app.domain.errors.supplier_errors import SupplierNotFound


class SetWorkspaceMatchThresholdUseCase:
    def __init__(
        self,
        supplier_repo: ISupplierRepository,
        member_repo: ISupplierMemberRepository,
    ):
        self.supplier_repo = supplier_repo
        self.member_repo = member_repo

    async def execute(
        self, user_id: UUID, supplier_id: UUID, threshold: float | None
    ) -> Supplier:
        supplier = await self.supplier_repo.get_by_id(supplier_id)
        if supplier is None:
            raise SupplierNotFound(str(supplier_id))

        # Autorización: solo admins activos del workspace pueden tocar esto.
        member = await self.member_repo.get_by_user_and_supplier(
            user_id, supplier_id
        )
        is_admin = (
            member is not None
            and member.status == MemberStatus.ACTIVE
            and member.is_admin()
        )
        # Compat legacy: el "dueño" histórico sin membresía también es admin.
        if not is_admin and supplier.user_id != user_id:
            raise UnauthorizedWorkspaceAction(
                "Solo el administrador del workspace puede modificar el umbral de match."
            )

        # Pydantic valida solo en construcción (sin validate_assignment), así
        # que replicamos el rango acá para fallar antes de tocar DB.
        if threshold is not None and not 0 < threshold <= 1:
            # Mismo mensaje y tipo que Supplier.validate_match_threshold para
            # que el handler de FastAPI lo mapee a 422 igual que en entidades.
            from pydantic import ValidationError
            from pydantic_core import InitErrorDetails, PydanticCustomError

            raise ValidationError.from_exception_data(
                "Supplier",
                [
                    InitErrorDetails(
                        type=PydanticCustomError(
                            "value_error",
                            "match_threshold debe estar en el rango (0, 1]",
                        ),
                        loc=("match_threshold",),
                        input=threshold,
                    )
                ],
            )
        supplier.match_threshold = threshold
        return await self.supplier_repo.update(supplier)
