"""SupplierRepository sin base de datos: que la implementación cumpla el contrato.

Los casos de uso y los tests e2e usan el doble en memoria, así que un método
del contrato mal ubicado en la clase real —fuera de ella por una indentación—
pasaba todos esos tests y rompía cada ruta de /suppliers en producción, porque
la clase quedaba abstracta. Los tests de integración lo detectan, pero solo con
Postgres levantado; este lo detecta siempre.
"""

from unittest.mock import AsyncMock, MagicMock

from app.infrastructure.repositories.supplier_repository import SupplierRepository


def test_supplier_repository_implements_the_whole_contract() -> None:
    """La clase concreta se puede instanciar: no le falta ningún método abstracto."""
    assert SupplierRepository.__abstractmethods__ == frozenset()
    SupplierRepository(MagicMock())


async def test_rollback_delegates_to_the_session() -> None:
    session = MagicMock()
    session.rollback = AsyncMock()

    await SupplierRepository(session).rollback()

    session.rollback.assert_awaited_once()
