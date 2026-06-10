from typing import Optional
from uuid import UUID

from app.application.repositories.tender_repository import ITenderRepository, TenderFilters
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.matching_result_repository import IMatchingResultRepository
from app.application.services.deep_analysis_service import IDeepAnalysisService
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.errors.supplier_errors import SupplierNotFoundForUser
from app.domain.errors.tender_errors import TenderNotFound
from app.domain.errors.matching_errors import ScoreMatchingNoEncontrado


class GetOrCreateDeepAnalysisUseCase:
    def __init__(
        self,
        supplier_repo: ISupplierRepository,
        tender_repo: ITenderRepository,
        matching_result_repo: IMatchingResultRepository,
        deep_analysis_service: IDeepAnalysisService,
    ):
        self.supplier_repo = supplier_repo
        self.tender_repo = tender_repo
        self.matching_result_repo = matching_result_repo
        self.deep_analysis_service = deep_analysis_service

    async def execute(
        self,
        tender_id: UUID,
        user_id: UUID,
        force_regenerate: bool = False,
        prompt_instruction: Optional[str] = None
    ) -> DeepAnalysis:
        """
        Orquesta la recuperación o generación de un análisis de compatibilidad IA.
        
        1. Obtiene el perfil de proveedor del usuario.
        2. Obtiene los detalles de la licitación.
        3. Obtiene el resultado de matching para extraer el score base.
        4. Decide si generar/regenerar o retornar el análisis guardado.
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

        # 3. Obtener el resultado de matching para rescatar el final_score (matching_score)
        matching_result = await self.matching_result_repo.get_by_proveedor_and_licitacion(
            proveedor_id=supplier.id, licitacion_id=tender_id
        )
        if not matching_result:
            raise ScoreMatchingNoEncontrado(str(supplier.id), str(tender_id))

        # El compatibility_score en DeepAnalysis es porcentual (0-100), se multiplica final_score (0-1) por 100
        matching_score = matching_result.final_score * 100.0

        # 4. Buscar si ya existe un análisis de compatibilidad previo
        existing_analysis = await self.tender_repo.get_deep_analysis(
            tender_id=tender_id, supplier_id=supplier.id
        )

        should_generate = False
        active_prompt = prompt_instruction

        if force_regenerate:
            # Regeneración manual forzada: se usa el prompt de esta petición
            should_generate = True
        elif not existing_analysis:
            # No existe análisis: se genera por primera vez
            should_generate = True
        else:
            # Existe análisis: verificar si el perfil del proveedor se actualizó después de la última generación
            sup_updated = supplier.updated_at.replace(tzinfo=None) if supplier.updated_at else None
            ana_updated = existing_analysis.updated_at.replace(tzinfo=None) if existing_analysis.updated_at else None

            if sup_updated and ana_updated and sup_updated > ana_updated:
                # Regeneración automática silenciosa por cambio de perfil.
                # Se mantiene la instrucción de refinamiento previa del usuario para conservar personalización.
                should_generate = True
                active_prompt = existing_analysis.prompt_instruction

        if should_generate:
            new_analysis = await self.deep_analysis_service.analyze_compatibility(
                tender=tender,
                supplier=supplier,
                matching_score=matching_score,
                prompt_instruction=active_prompt
            )
            saved_analysis = await self.tender_repo.save_deep_analysis(new_analysis)
            return saved_analysis

        return existing_analysis
