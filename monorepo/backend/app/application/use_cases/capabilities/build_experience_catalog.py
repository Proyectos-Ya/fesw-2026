from collections.abc import Iterator
from uuid import UUID

from app.application.repositories.capability_repository import (
    ICapabilityAnswerRepository,
    ICapabilityEvidenceRepository,
    ICapabilityQuestionRepository,
)
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.use_cases.capabilities._empresa import empresa_o_error
from app.domain.entities.capability import (
    CapabilityAnswer,
    CapabilityEvidence,
    CapabilityQuestion,
    ExperienceCatalog,
    ExperienceItem,
)
from app.domain.entities.supplier import Supplier
from app.shared.datetime_utils import utc_now_naive
from app.shared.slug import slugify


def _item_de_perfil(item_id: str, kind: str, title: str, detail: str) -> ExperienceItem:
    return ExperienceItem(
        id=item_id, origin="perfil", kind=kind, title=title, detail=detail
    )


def _items_de_lista(
    prefijo: str, kind: str, title: str, valores: list[str] | None
) -> Iterator[ExperienceItem]:
    vistos: set[str] = set()
    for valor in valores or []:
        clave = slugify(valor)
        if not clave or clave in vistos:
            continue
        vistos.add(clave)
        yield _item_de_perfil(f"perfil:{prefijo}:{clave}", kind, title, valor)


def _items_del_perfil(supplier: Supplier) -> Iterator[ExperienceItem]:
    if supplier.years_experience is not None:
        anios = supplier.years_experience
        yield _item_de_perfil(
            "perfil:anios-experiencia",
            "capacidad",
            "Años de experiencia",
            f"{anios} año" if anios == 1 else f"{anios} años",
        )
    if supplier.description and supplier.description.strip():
        yield _item_de_perfil(
            "perfil:descripcion",
            "capacidad",
            "Descripción de la empresa",
            supplier.description.strip(),
        )
    yield from _items_de_lista(
        "certificacion", "certificacion", "Certificación", supplier.certifications
    )
    yield from _items_de_lista("sector", "sector", "Rubro", supplier.sectors)
    # Las regiones son las que permiten detectar una contradicción de cobertura
    # ("entrega en Arica" contra una empresa que opera solo en la RM).
    yield from _items_de_lista(
        "region", "region", "Región de operación", supplier.regions
    )


def _pesos(monto: int) -> str:
    return "$" + f"{monto:,}".replace(",", ".")


def _detalle_de_proyecto(evidence: CapabilityEvidence) -> str:
    partes = [p for p in (evidence.buyer, str(evidence.year)) if p]
    if evidence.amount_clp is not None:
        partes.append(_pesos(evidence.amount_clp))
    detalle = " · ".join(partes)
    if evidence.description and evidence.description.strip():
        detalle = f"{detalle}. {evidence.description.strip()}"
    return detalle


def compose_experience_catalog(
    supplier: Supplier,
    answers: list[CapabilityAnswer],
    questions_by_id: dict[UUID, CapabilityQuestion],
    evidences: list[CapabilityEvidence],
) -> ExperienceCatalog:
    """Arma el catálogo a partir de datos ya cargados. No copia ni guarda nada.

    - Las `keywords` no entran: las que tienen formato `campo:respuesta` son las
      respuestas del banner del home, que aún no migran al banco (plan 230, §5).
    - Las respuestas negativas **sí** entran, con su polaridad: "no tiene
      certificación SEC" también es un dato que la factibilidad necesita.
    - Una respuesta vencida no entra: la pregunta vuelve a quedar por responder.
    - Solo entran los proyectos `manual`. Los importados esperan a que exista su
      confirmación (plan 230, §5 punto 10).
    """
    now = utc_now_naive()
    items = list(_items_del_perfil(supplier))

    vigentes = [a for a in answers if a.is_current(now)]
    for answer in vigentes:
        question = questions_by_id.get(answer.question_id)
        if question is None or answer.answer is None:
            continue
        items.append(
            ExperienceItem(
                id=f"capacidad:{question.id}",
                origin="capacidad",
                kind=question.kind,
                title=question.question,
                detail=answer.answer,
                polarity=question.polarity_of(answer.answer),
                answered_by_user_id=answer.answered_by_user_id,
                tender_id=answer.tender_id,
            )
        )

    manuales = [e for e in evidences if e.origin == "manual"]
    for evidence in manuales:
        items.append(
            ExperienceItem(
                id=f"evidencia:{evidence.id}",
                origin="evidencia",
                kind="experiencia_proyecto",
                title=evidence.title,
                detail=_detalle_de_proyecto(evidence),
            )
        )

    fechas = (
        [supplier.updated_at]
        + [a.answered_at for a in vigentes if a.answered_at is not None]
        + [e.created_at for e in manuales]
    )
    return ExperienceCatalog(items=items, last_changed_at=max(fechas))


class BuildExperienceCatalogUseCase:
    """Lo que el sistema sabe que la empresa activa puede acreditar."""

    def __init__(
        self,
        supplier_repo: ISupplierRepository,
        question_repo: ICapabilityQuestionRepository,
        answer_repo: ICapabilityAnswerRepository,
        evidence_repo: ICapabilityEvidenceRepository,
    ):
        self.supplier_repo = supplier_repo
        self.question_repo = question_repo
        self.answer_repo = answer_repo
        self.evidence_repo = evidence_repo

    async def execute(
        self, user_id: UUID, supplier_id: UUID | None
    ) -> ExperienceCatalog:
        supplier = await empresa_o_error(self.supplier_repo, user_id, supplier_id)

        answers = await self.answer_repo.list_by_supplier(supplier.id)
        # Por id y no por categoría: una respuesta a una pregunta de otro rubro,
        # o ya desactivada, sigue siendo experiencia declarada.
        questions = await self.question_repo.list_by_ids(
            [a.question_id for a in answers]
        )
        evidences = await self.evidence_repo.list_by_supplier(supplier.id)
        return compose_experience_catalog(
            supplier=supplier,
            answers=answers,
            questions_by_id={q.id: q for q in questions},
            evidences=evidences,
        )
