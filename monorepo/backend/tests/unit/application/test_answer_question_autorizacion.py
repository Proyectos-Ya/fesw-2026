"""La respuesta a una pregunta solo puede modificar el perfil de quien la envía.

El defecto que estos tests fijan: `POST /questions/answer` tomaba `supplier_id`
del cuerpo de la petición y nunca lo comparaba con el usuario autenticado, y el
caso de uso aceptaba **tanto un id de empresa como un id de usuario** —buscaba
por uno y, al no encontrarlo, por el otro—. Cualquier usuario registrado que
conociera el UUID de otra empresa podía escribir en sus `keywords`, que alimentan
la consulta del reranker y el servicio de ponderación: degradar el matching de un
competidor desde la propia sesión.

El arreglo no es comprobar el id que manda el cliente, es **dejar de aceptarlo**:
la empresa se resuelve desde la sesión y no hay identidad que suplantar.
"""

from uuid import uuid4

import pytest

from app.application.use_cases.questions.answer_question_use_case import (
    AnswerQuestionUseCase,
)
from app.domain.entities.supplier import Supplier
from tests.unit.application.fakes import InMemorySupplierRepository

VALID_RUT = "76086428-5"


async def _con_empresa(user_id) -> tuple[AnswerQuestionUseCase, InMemorySupplierRepository, Supplier]:
    repo = InMemorySupplierRepository()
    supplier = Supplier(
        id=uuid4(), user_id=user_id, rut=VALID_RUT, legal_name="Empresa Test SpA",
        keywords=[],
    )
    await repo.save(supplier)
    return AnswerQuestionUseCase(supplier_repo=repo), repo, supplier


class TestSoloSuPropioPerfil:
    @pytest.mark.asyncio
    async def test_escribe_en_la_empresa_del_usuario_de_la_sesion(self):
        user_id = uuid4()
        use_case, repo, supplier = await _con_empresa(user_id)

        await use_case.execute(
            user_id=user_id, field_name="bim_capabilities", answer="Sí"
        )

        assert "bim_capabilities:Sí" in (await repo.get_by_id(supplier.id)).keywords

    @pytest.mark.asyncio
    async def test_el_id_de_otra_empresa_ya_no_es_un_parametro(self):
        """La firma no acepta `supplier_id`: no hay identidad que suplantar."""
        import inspect

        firma = inspect.signature(AnswerQuestionUseCase.execute)

        assert "supplier_id" not in firma.parameters
        assert "user_id" in firma.parameters

    @pytest.mark.asyncio
    async def test_un_usuario_sin_empresa_no_puede_escribir_en_ninguna(self):
        """Antes, un id que no era de empresa se reintentaba como id de usuario.

        Esa doble búsqueda es lo que permitía que un id de usuario filtrado
        —más fácil de conseguir que uno de empresa— sirviera igual.
        """
        use_case, repo, otra = await _con_empresa(uuid4())

        with pytest.raises(ValueError, match="empresa"):
            await use_case.execute(
                user_id=uuid4(), field_name="sectors", answer="construcción"
            )

        assert (await repo.get_by_id(otra.id)).keywords == []
