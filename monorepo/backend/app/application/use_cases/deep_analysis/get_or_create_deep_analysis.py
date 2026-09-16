from dataclasses import dataclass
from uuid import UUID

from app.application.repositories.matching_result_repository import (
    IMatchingResultRepository,
)
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.services.compatibility_scorer import CompatibilityScorer
from app.application.services.deep_analysis_service import IDeepAnalysisService
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender
from app.domain.errors.supplier_errors import SupplierNotFoundForUser
from app.domain.errors.tender_errors import TenderClosedForAnalysis, TenderNotFound


@dataclass
class DeepAnalysisResult:
    """Lo que hay guardado y si dejó de estar al día.

    `is_outdated` existe para la ficha, que consulta sin generar: necesita poder
    decir "esto se escribió con datos anteriores" y ofrecer el botón, en vez de
    mostrar como vigente una justificación escrita sobre otro perfil.
    """

    analysis: DeepAnalysis | None
    is_outdated: bool = False


class GetOrCreateDeepAnalysisUseCase:
    def __init__(
        self,
        supplier_repo: ISupplierRepository,
        tender_repo: ITenderRepository,
        matching_result_repo: IMatchingResultRepository,
        deep_analysis_service: IDeepAnalysisService,
        scorer: CompatibilityScorer,
    ):
        self.supplier_repo = supplier_repo
        self.tender_repo = tender_repo
        self.matching_result_repo = matching_result_repo
        self.deep_analysis_service = deep_analysis_service
        self.scorer = scorer

    async def execute(
        self,
        tender_id: UUID,
        user_id: UUID,
        force_regenerate: bool = False,
        prompt_instruction: str | None = None,
        only_if_exists: bool = False,
    ) -> DeepAnalysisResult:
        """
        Orquesta la recuperación o generación de un análisis de compatibilidad IA.

        1. Obtiene el perfil de proveedor del usuario.
        2. Obtiene los detalles de la licitación.
        3. Decide si generar/regenerar o retornar el análisis guardado.
        4. Solo si hay que generar resuelve el puntaje, calculándolo si falta.

        El puntaje se resuelve al final y no al principio a propósito: antes se
        exigía tener una fila de matching para cualquier cosa, así que una
        licitación fuera del top-N no podía analizarse **ni mostrar el análisis
        que ya tenía guardado**.
        """
        # 1. Obtener el proveedor por user_id
        supplier = await self.supplier_repo.get_by_user_id(user_id)
        if not supplier:
            raise SupplierNotFoundForUser(user_id)

        # 2. Obtener la licitación por tender_id
        tenders = await self.tender_repo.get_tenders(TenderFilters(ids=[tender_id]))
        if not tenders:
            raise TenderNotFound(tender_id)
        tender = tenders[0]

        # 3. Buscar si ya existe un análisis de compatibilidad previo
        existing_analysis = await self.tender_repo.get_deep_analysis(
            tender_id=tender_id, supplier_id=supplier.id
        )
        cerrada = tender.esta_cerrada()
        desactualizado = self._quedo_desactualizado(existing_analysis, supplier, tender)

        # La ficha consulta con only_if_exists: mira, nunca genera. Marcar como
        # desactualizado algo que no se puede regenerar sería ofrecer un botón
        # que no va a funcionar.
        if only_if_exists:
            return DeepAnalysisResult(
                analysis=existing_analysis,
                is_outdated=desactualizado and not cerrada,
            )

        debe_generar = (
            force_regenerate or existing_analysis is None or desactualizado
        )

        if debe_generar and cerrada:
            # Lo ya generado se sigue mostrando: es el registro de lo que se
            # evaluó cuando todavía se podía postular.
            if existing_analysis is None:
                raise TenderClosedForAnalysis(tender_id)
            return DeepAnalysisResult(analysis=existing_analysis)

        if not debe_generar:
            return DeepAnalysisResult(analysis=existing_analysis)

        if force_regenerate:
            # Regeneración manual forzada: se usa el prompt de esta petición
            active_prompt = prompt_instruction
        elif existing_analysis is not None:
            # Regeneración automática silenciosa.
            # Se mantiene la instrucción de refinamiento previa del usuario para
            # conservar personalización.
            active_prompt = existing_analysis.prompt_instruction
        else:
            active_prompt = prompt_instruction

        matching_score = await self._resolver_puntaje(
            supplier, tender, recalcular=force_regenerate or desactualizado
        )

        new_analysis = await self.deep_analysis_service.analyze_compatibility(
            tender=tender,
            supplier=supplier,
            matching_score=matching_score,
            prompt_instruction=active_prompt,
        )
        saved_analysis = await self.tender_repo.save_deep_analysis(new_analysis)
        return DeepAnalysisResult(analysis=saved_analysis)

    async def _resolver_puntaje(
        self, supplier: Supplier, tender: Tender, recalcular: bool
    ) -> float:
        """Devuelve el porcentaje (0-100) que el análisis debe justificar.

        Se prefiere la fila guardada para que el número del análisis sea el
        mismo que ve el usuario en la ficha y en el dashboard.

        Las filas del ranking no se recalculan acá aunque se pida regenerar: su
        pipeline ya las refresca solo, y sobrescribirlas desde este camino las
        convertiría en un cálculo a pedido, sacando la licitación de las
        recomendaciones.
        """
        fila = await self.matching_result_repo.get_by_proveedor_and_licitacion(
            proveedor_id=supplier.id, licitacion_id=tender.id
        )
        if (
            fila is not None
            and fila.final_score is not None
            and (fila.source == "ranking" or not recalcular)
        ):
            return fila.final_score * 100.0

        return await self.scorer.score_pct_and_persist(supplier, tender)

    @staticmethod
    def _quedo_desactualizado(
        existing_analysis: DeepAnalysis | None, supplier: Supplier, tender: Tender
    ) -> bool:
        """Si el perfil o la licitación cambiaron después de escribir el análisis.

        La licitación también cambia, desde que la ingesta refresca las
        existentes en vez de descartarlas (6.3). Sin esta comparación, una
        licitación cuyo alcance cambió seguiría mostrando una justificación
        escrita sobre el contenido anterior: eso no es un dato viejo, es
        contenido incorrecto presentado como vigente, y el usuario lo lee y le
        cree.
        """
        if existing_analysis is None:
            return False

        ana_updated = (
            existing_analysis.updated_at.replace(tzinfo=None)
            if existing_analysis.updated_at
            else None
        )
        if ana_updated is None:
            return False

        sup_updated = (
            supplier.updated_at.replace(tzinfo=None) if supplier.updated_at else None
        )
        lic_updated = (
            tender.updated_at.replace(tzinfo=None) if tender.updated_at else None
        )

        cambio_el_proveedor = bool(sup_updated and sup_updated > ana_updated)
        cambio_la_licitacion = bool(lic_updated and lic_updated > ana_updated)
        return cambio_el_proveedor or cambio_la_licitacion
