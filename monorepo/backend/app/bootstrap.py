import logging
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.matching_result_repository import (
    IMatchingResultRepository,
)
from app.application.repositories.question_repository import IQuestionRepository
from app.application.repositories.saved_tender_repository import ISavedTenderRepository
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.supplier_vector_repository import (
    ISupplierVectorRepository,
)
from app.application.repositories.tender_repository import ITenderRepository
from app.application.repositories.tender_vector_repository import (
    ITenderVectorRepository,
)
from app.application.repositories.tender_chat_repository import (
    ITenderChatRepository,
)
from app.application.repositories.user_repository import IUserRepository
from app.application.services.deep_analysis_service import IDeepAnalysisService
from app.application.services.embedding_service import IEmbeddingService
from app.application.services.reranker_service import IRerankerService
from app.application.services.smart_question_service import ISmartQuestionService
from app.application.services.tender_assistant_ai_service import (
    ITenderAssistantAIService,
)
from app.application.services.document_validator_service import (
    IDocumentValidatorService,
)
from app.infrastructure.services.document_validator_service import (
    DocumentValidatorService,
)
from app.application.services.weighting_service import IWeightingService
from app.application.use_cases.ask_tender_assistant_use_case import (
    AskTenderAssistantUseCase,
)
from app.application.use_cases.deep_analysis.get_or_create_deep_analysis import (
    GetOrCreateDeepAnalysisUseCase,
)
from app.application.use_cases.create_tender_chat_session_use_case import (
    CreateTenderChatSessionUseCase,
)
from app.application.use_cases.delete_tender_chat_document_use_case import (
    DeleteTenderChatDocumentUseCase,
)
from app.application.use_cases.get_tender_chat_history_use_case import (
    GetTenderChatHistoryUseCase,
)

from app.application.use_cases.list_tender_chat_documents_use_case import (
    ListTenderChatDocumentsUseCase,
)
from app.application.use_cases.matching.rank_tenders import RankTendersUseCase
from app.application.use_cases.questions.answer_question_use_case import (
    AnswerQuestionUseCase,
)
from app.application.use_cases.questions.smart_question_use_case import (
    SmartQuestionUseCase,
)
from app.application.use_cases.saved_tenders.list_saved_tenders import (
    ListSavedTendersUseCase,
)
from app.application.use_cases.saved_tenders.save_tender import SaveTenderUseCase
from app.application.use_cases.saved_tenders.unsave_tender import UnsaveTenderUseCase
from app.application.use_cases.tender.search_tenders import SearchTendersUseCase
from app.application.use_cases.upload_tender_chat_document_use_case import (
    UploadTenderChatDocumentUseCase,
)
from app.config import settings
from app.infrastructure.auth.dependencies import build_get_current_user
from app.infrastructure.db import get_session
from app.infrastructure.repositories.matching_result_repository import (
    MatchingResultRepository,
)
from app.infrastructure.repositories.qdrant_supplier_repository import (
    QdrantSupplierRepository,
)
from app.infrastructure.repositories.qdrant_tender_repository import (
    QdrantTenderRepository,
)
from app.infrastructure.repositories.question_repository import QuestionRepositoryImpl
from app.infrastructure.repositories.saved_tender_repository import (
    SavedTenderRepository,
)
from app.infrastructure.repositories.sql_tender_chat_repository import (
    SQLTenderChatRepository,
)
from app.infrastructure.repositories.supplier_repository import SupplierRepository
from app.infrastructure.repositories.tender_repository import TenderRepository
from app.infrastructure.repositories.user_repository import UserRepository
from app.infrastructure.routers.router import create_router
from app.infrastructure.services.bge_m3_embedding_service import BgeM3EmbeddingService
from app.infrastructure.services.bge_reranker_service import BgeRerankerService
from app.infrastructure.services.field_weighting_service import FieldWeightingService
from app.infrastructure.services.gemini_deep_analysis_service import (
    GeminiDeepAnalysisService,
)
from app.infrastructure.services.gemini_tender_assistant_service import (
    GeminiTenderAssistantService,
)
from app.infrastructure.services.password_hasher import BcryptPasswordHasher
from app.infrastructure.services.smart_question_service import SmartQuestionServiceImpl
from app.infrastructure.services.token_service import JwtTokenService



def get_supplier_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ISupplierRepository:
    # Crea el repositorio concreto con la sesión de BD por petición
    return SupplierRepository(session)


def get_supplier_vector_repo(request: Request) -> ISupplierVectorRepository:
    # Reutiliza el cliente Qdrant inicializado en el lifespan
    return QdrantSupplierRepository(request.app.state.qdrant_client)


def get_tender_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ITenderRepository:
    # Crea el repositorio concreto de licitaciones con la sesión de BD
    return TenderRepository(session)


def get_embedding_service(request: Request) -> IEmbeddingService:
    return request.app.state.embedding_service


def get_tender_vector_repo(request: Request) -> ITenderVectorRepository:
    return QdrantTenderRepository(
        client=request.app.state.qdrant_async_client,
        vector_size=settings.embedding_vector_size,
    )


def get_reranker_service(request: Request) -> IRerankerService:
    return request.app.state.reranker_service


def get_weighting_service(request: Request) -> IWeightingService:
    return request.app.state.weighting_service


def get_matching_result_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IMatchingResultRepository:
    return MatchingResultRepository(session)


def get_rank_tenders_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
    supplier_vector_repo: Annotated[
        ISupplierVectorRepository, Depends(get_supplier_vector_repo)
    ],
    tender_vector_repo: Annotated[
        ITenderVectorRepository, Depends(get_tender_vector_repo)
    ],
    reranker_service: Annotated[IRerankerService, Depends(get_reranker_service)],
    weighting_service: Annotated[IWeightingService, Depends(get_weighting_service)],
) -> RankTendersUseCase:
    return RankTendersUseCase(
        supplier_repo=SupplierRepository(session),
        supplier_vector_repo=supplier_vector_repo,
        tender_vector_repo=tender_vector_repo,
        tender_repo=TenderRepository(session),
        reranker_service=reranker_service,
        weighting_service=weighting_service,
        matching_result_repo=MatchingResultRepository(session),
        model_version=settings.embedding_model,
    )


def get_saved_tender_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ISavedTenderRepository:
    return SavedTenderRepository(session)


def get_list_saved_tenders_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ListSavedTendersUseCase:
    return ListSavedTendersUseCase(
        saved_tender_repo=SavedTenderRepository(session),
        tender_repo=TenderRepository(session),
        supplier_repo=SupplierRepository(session),
        matching_result_repo=MatchingResultRepository(session),
    )


def get_save_tender_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SaveTenderUseCase:
    return SaveTenderUseCase(
        saved_tender_repo=SavedTenderRepository(session),
        tender_repo=TenderRepository(session),
    )


def get_unsave_tender_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UnsaveTenderUseCase:
    return UnsaveTenderUseCase(saved_tender_repo=SavedTenderRepository(session))


def get_search_tenders_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
    supplier_vector_repo: Annotated[
        ISupplierVectorRepository, Depends(get_supplier_vector_repo)
    ],
    tender_vector_repo: Annotated[
        ITenderVectorRepository, Depends(get_tender_vector_repo)
    ],
    embedding_service: Annotated[IEmbeddingService, Depends(get_embedding_service)],
) -> SearchTendersUseCase:
    return SearchTendersUseCase(
        supplier_repo=SupplierRepository(session),
        supplier_vector_repo=supplier_vector_repo,
        tender_vector_repo=tender_vector_repo,
        tender_repo=TenderRepository(session),
        embedding_service=embedding_service,
    )


def get_user_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IUserRepository:
    return UserRepository(session)


def get_deep_analysis_service(request: Request) -> IDeepAnalysisService:
    return request.app.state.deep_analysis_service


def get_get_or_create_deep_analysis_use_case(
    session: Annotated[AsyncSession, Depends(get_session)],
    deep_analysis_service: Annotated[
        IDeepAnalysisService, Depends(get_deep_analysis_service)
    ],
) -> GetOrCreateDeepAnalysisUseCase:
    return GetOrCreateDeepAnalysisUseCase(
        supplier_repo=SupplierRepository(session),
        tender_repo=TenderRepository(session),
        matching_result_repo=MatchingResultRepository(session),
        deep_analysis_service=deep_analysis_service,
    )


def get_question_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IQuestionRepository:
    return QuestionRepositoryImpl(session)


def get_smart_question_service(
    question_repo: Annotated[IQuestionRepository, Depends(get_question_repo)],
) -> ISmartQuestionService:
    return SmartQuestionServiceImpl(question_repository=question_repo)


def get_smart_question_use_case(
    smart_question_service: Annotated[
        ISmartQuestionService, Depends(get_smart_question_service)
    ],
    supplier_repo: Annotated[ISupplierRepository, Depends(get_supplier_repo)],
) -> SmartQuestionUseCase:
    return SmartQuestionUseCase(
        smart_question_service=smart_question_service,
        supplier_repository=supplier_repo,
    )


def get_answer_question_use_case(
    supplier_repo: Annotated[ISupplierRepository, Depends(get_supplier_repo)],
) -> AnswerQuestionUseCase:
    # Inyectar el caso de uso que procesa las respuestas
    return AnswerQuestionUseCase(supplier_repo=supplier_repo)


def get_tender_chat_repo(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ITenderChatRepository:
    return SQLTenderChatRepository(session)


def get_tender_assistant_ai_service(request: Request) -> ITenderAssistantAIService:
    return request.app.state.tender_assistant_ai_service


def get_document_validator_service() -> IDocumentValidatorService:
    return DocumentValidatorService()


def get_upload_tender_chat_doc_use_case(
    chat_repo: Annotated[ITenderChatRepository, Depends(get_tender_chat_repo)],
    validator_service: Annotated[
        IDocumentValidatorService, Depends(get_document_validator_service)
    ],
) -> UploadTenderChatDocumentUseCase:
    return UploadTenderChatDocumentUseCase(
        chat_repo=chat_repo, validator_service=validator_service
    )


def get_list_tender_chat_docs_use_case(
    chat_repo: Annotated[ITenderChatRepository, Depends(get_tender_chat_repo)],
) -> ListTenderChatDocumentsUseCase:
    return ListTenderChatDocumentsUseCase(chat_repo=chat_repo)


def get_delete_tender_chat_doc_use_case(
    chat_repo: Annotated[ITenderChatRepository, Depends(get_tender_chat_repo)],
) -> DeleteTenderChatDocumentUseCase:
    return DeleteTenderChatDocumentUseCase(chat_repo=chat_repo)


def get_ask_tender_assistant_use_case(
    chat_repo: Annotated[ITenderChatRepository, Depends(get_tender_chat_repo)],
    ai_service: Annotated[
        ITenderAssistantAIService, Depends(get_tender_assistant_ai_service)
    ],
    supplier_repo: Annotated[ISupplierRepository, Depends(get_supplier_repo)],
    validator_service: Annotated[
        IDocumentValidatorService, Depends(get_document_validator_service)
    ],
) -> AskTenderAssistantUseCase:
    return AskTenderAssistantUseCase(
        chat_repo=chat_repo,
        ai_service=ai_service,
        supplier_repo=supplier_repo,
        validator_service=validator_service,
    )



def get_create_tender_chat_session_use_case(
    chat_repo: Annotated[ITenderChatRepository, Depends(get_tender_chat_repo)],
) -> CreateTenderChatSessionUseCase:
    return CreateTenderChatSessionUseCase(chat_repo=chat_repo)


def get_tender_chat_history_use_case(
    chat_repo: Annotated[ITenderChatRepository, Depends(get_tender_chat_repo)],
) -> GetTenderChatHistoryUseCase:
    return GetTenderChatHistoryUseCase(chat_repo=chat_repo)



class MockRerankerService(IRerankerService):
    """Reranker neutro para cuando está desactivado o falta ONNX en local/tests."""

    async def rerank(self, query_text, candidates, limit):
        return [(c[0], 1.0) for c in candidates][:limit]


logger = logging.getLogger(__name__)


def build_reranker_service() -> IRerankerService:
    """Construye el reranker, o decide qué hacer si no se puede.

    `MockRerankerService` devuelve 1.0 para todas las candidatas: con él la
    aplicación responde igual, pero el orden de las recomendaciones es
    arbitrario. Es una degradación que no se nota desde afuera, así que la
    única defensa es que quede escrita en los logs.

    Por eso el fallback vive solo en desarrollo. Fuera de ahí un reranker que
    no arranca es un fallo de arranque: mejor no levantar que servir
    recomendaciones en orden aleatorio sin que nadie se entere.
    """
    if settings.disable_reranker:
        logger.warning(
            "Reranker desactivado por configuración (DISABLE_RERANKER). "
            "Se usa MockRerankerService y las recomendaciones no van ordenadas."
        )
        return MockRerankerService()

    try:
        return BgeRerankerService()
    except Exception as exc:
        # En producción no se traga: relanza y el arranque falla con la traza.
        if not settings.is_dev:
            logger.exception(
                "El reranker no se pudo construir (%s) y IS_DEV=false, así que "
                "la aplicación no arranca. Degradarse en silencio serviría "
                "recomendaciones en orden arbitrario.",
                exc,
            )
            raise

        # En local sí: falta de RAM u ONNX no debería impedir levantar la API.
        logger.exception(
            "El reranker no se pudo construir (%s). Se continúa con "
            "MockRerankerService porque IS_DEV=true, pero las recomendaciones "
            "van en orden arbitrario hasta que esto se resuelva.",
            exc,
        )
        return MockRerankerService()


def bootstrap(app: FastAPI) -> None:
    # Servicios sin estado: se construyen una vez
    hasher = BcryptPasswordHasher()
    token_service = JwtTokenService(
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        expire_minutes=settings.access_token_expire_minutes,
    )

    try:
        app.state.embedding_service = BgeM3EmbeddingService(
            model_name=settings.embedding_model
        )
    except Exception as e:
        logger.warning(
            "[Bootstrap] No se pudo cargar BgeM3EmbeddingService (%s). Usando MockEmbeddingService.",
            e,
        )

        class MockEmbeddingService(IEmbeddingService):
            async def embed(self, texts: list[str]) -> list[list[float]]:
                return [[0.0] * settings.embedding_vector_size for _ in texts]

        app.state.embedding_service = MockEmbeddingService()

    app.state.deep_analysis_service = GeminiDeepAnalysisService(
        api_key=settings.gemini_api_key,
        model_name=settings.gemini_model,
    )
    app.state.tender_assistant_ai_service = GeminiTenderAssistantService(
        api_key=settings.gemini_api_key,
        model_name=settings.gemini_model,
    )

    app.state.reranker_service = build_reranker_service()


    # La región no pondera: `RankTendersUseCase` ya descarta las licitaciones
    # fuera de las regiones del proveedor, así que un bono adicional se lo
    # llevarían todas las que sobreviven al filtro y no ordenaría nada.
    # Estos son los pesos con que se calibró el reranker en
    # tests/matching_evaluation.
    app.state.weighting_service = FieldWeightingService(
        reranker_weight=0.50,
        sector_weight=0.25,
        keyword_weight=0.25,
        region_weight=0.0,
    )

    # Una sola instancia de la dependencia → FastAPI cachea el usuario por request
    get_current_user = build_get_current_user(
        get_user_repo=get_user_repo,
        token_service=token_service,
        cookie_name=settings.auth_cookie_name,
    )

    router = create_router(
        get_rank_tenders_use_case=get_rank_tenders_use_case,
        get_smart_question_use_case=get_smart_question_use_case,
        get_answer_question_use_case=get_answer_question_use_case,
        get_supplier_repo=get_supplier_repo,
        get_supplier_vector_repo=get_supplier_vector_repo,
        get_embedding_service=get_embedding_service,
        get_user_repo=get_user_repo,
        get_current_user=get_current_user,
        hasher=hasher,
        token_service=token_service,
        cookie_name=settings.auth_cookie_name,
        # `_derivar_cookie_secure` ya le dio valor; el `bool()` solo cierra el
        # `bool | None` que el tipo del campo deja abierto.
        cookie_secure=bool(settings.auth_cookie_secure),
        cookie_max_age=settings.access_token_expire_minutes * 60,
        get_get_or_create_deep_analysis_use_case=get_get_or_create_deep_analysis_use_case,
        get_list_saved_tenders_use_case=get_list_saved_tenders_use_case,
        get_save_tender_use_case=get_save_tender_use_case,
        get_unsave_tender_use_case=get_unsave_tender_use_case,
        get_search_tenders_use_case=get_search_tenders_use_case,
        get_upload_tender_chat_doc_use_case=get_upload_tender_chat_doc_use_case,
        get_list_tender_chat_docs_use_case=get_list_tender_chat_docs_use_case,
        get_delete_tender_chat_doc_use_case=get_delete_tender_chat_doc_use_case,
        get_ask_tender_assistant_use_case=get_ask_tender_assistant_use_case,
        get_tender_chat_history_use_case=get_tender_chat_history_use_case,
        get_create_tender_chat_session_use_case=get_create_tender_chat_session_use_case,
    )
    app.include_router(router)



