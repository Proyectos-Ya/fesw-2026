from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.supplier_repository import ISupplierRepository
from app.domain.entities.supplier import Supplier
from app.domain.errors.supplier_errors import (
    SupplierAlreadyExists,
    UserAlreadyHasSupplier,
)
from app.infrastructure.repositories.supplier_model import SupplierModel


class SupplierRepository(ISupplierRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: SupplierModel) -> Supplier:
        # Convierte el modelo de BD a entidad de dominio
        return Supplier(**model.model_dump())

    def _to_model(self, entity: Supplier) -> SupplierModel:
        # Convierte la entidad de dominio a modelo de BD
        return SupplierModel(**entity.model_dump())

    async def get_by_rut(self, rut: str) -> Supplier | None:
        # Busca un proveedor por RUT para verificar duplicados
        result = await self.session.exec(
            select(SupplierModel).where(SupplierModel.rut == rut)
        )
        model = result.first()
        return self._to_entity(model) if model else None

    async def get_by_id(self, supplier_id: UUID) -> Supplier | None:
        # Busca un proveedor por su id interno
        model = await self.session.get(SupplierModel, supplier_id)
        return self._to_entity(model) if model else None

    async def get_by_user_id(self, user_id: UUID) -> Supplier | None:
        # Busca un proveedor por el id del usuario propietario
        result = await self.session.exec(
            select(SupplierModel).where(SupplierModel.user_id == user_id)
        )
        model = result.first()
        return self._to_entity(model) if model else None

    async def list_user_ids_with_profile(self) -> list[UUID]:
        # Usuarios que ya tienen un perfil de empresa. Lo usa el escaneo de
        # alertas: sin perfil no hay vector y el matching no tiene qué comparar.
        result = await self.session.exec(
            select(SupplierModel.user_id).where(col(SupplierModel.user_id).is_not(None))
        )
        return [user_id for user_id in result.all() if user_id is not None]

    async def save(self, supplier: Supplier) -> Supplier:
        # Persiste el proveedor y confirma en el mismo paso
        saved = await self.add(supplier)
        await self.commit()
        return saved

    async def update(self, supplier: Supplier) -> Supplier:
        # Actualiza un proveedor existente y confirma en el mismo paso
        updated = await self.stage_update(supplier)
        await self.commit()
        return updated

    async def add(self, supplier: Supplier) -> Supplier:
        # El flush manda el INSERT dentro de la transacción abierta: Postgres
        # evalúa ahí las restricciones de unicidad, pero nada queda confirmado
        # hasta `commit`.
        model = self._to_model(supplier)
        self.session.add(model)
        await self._flush_or_translate(supplier)
        return self._to_entity(model)

    async def stage_update(self, supplier: Supplier) -> Supplier:
        # Merge por primary key, pendiente hasta `commit`
        model = await self.session.merge(self._to_model(supplier))
        await self._flush_or_translate(supplier)
        return self._to_entity(model)

    async def commit(self) -> None:
        await self.session.commit()

    async def _flush_or_translate(self, supplier: Supplier) -> None:
        """Hace flush y convierte una violación de unicidad en error de dominio.

        La validación previa con SELECT no alcanza: entre la lectura y el INSERT
        pasan segundos —el embedding va en medio— y otra petición puede escribir
        la misma fila. Así ocurrió en producción el 3-sep, con un
        UniqueViolationError sin controlar que terminó en 500.
        """
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            constraint = _constraint_name(exc)
            if constraint == _RUT_INDEX:
                raise SupplierAlreadyExists(supplier.rut) from exc
            if constraint == _USER_INDEX and supplier.user_id is not None:
                raise UserAlreadyHasSupplier(supplier.user_id) from exc
            raise


# Nombres de los índices únicos de `supplier` (ver las migraciones de Alembic).
_RUT_INDEX = "ix_supplier_rut_normalizado"
_USER_INDEX = "ix_supplier_user_id"


def _constraint_name(exc: IntegrityError) -> str | None:
    """Nombre de la restricción violada, o None si no se puede determinar.

    asyncpg lo expone en la excepción original (`constraint_name`), que
    SQLAlchemy envuelve dos veces. El texto del mensaje queda como respaldo.
    """
    original = getattr(exc.orig, "__cause__", None) or exc.orig
    name = getattr(original, "constraint_name", None)
    if isinstance(name, str):
        return name
    mensaje = str(exc)
    for candidato in (_RUT_INDEX, _USER_INDEX):
        if candidato in mensaje:
            return candidato
    return None

    async def rollback(self) -> None:
        await self.session.rollback()
