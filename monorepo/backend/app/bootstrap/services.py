"""Acceso por petición a los servicios y clientes que viven en `app.state`."""

from typing import Annotated

from fastapi import Depends, Request

from app.application.repositories.supplier_vector_repository import (
    ISupplierVectorRepository,
)
from app.application.repositories.tender_vector_repository import (
    ITenderVectorRepository,
)
from app.application.services.calendar_provider_client import CalendarProviders
from app.application.services.company_lookup_service import ICompanyLookupService
from app.application.services.deep_analysis_service import IDeepAnalysisService
from app.application.services.document_validator_service import (
    IDocumentValidatorService,
)
from app.application.services.email_service import IEmailService
from app.application.services.embedding_service import IEmbeddingService
from app.application.services.export_background import IExportBackground
from app.application.services.identity_directory import IIdentityDirectory
from app.application.services.milestone_extraction_ai_service import (
    IMilestoneExtractionAIService,
)
from app.application.services.proposal_ai_service import IProposalAIService
from app.application.services.reranker_service import IRerankerService
from app.application.services.tender_assistant_ai_service import (
    ITenderAssistantAIService,
)
from app.application.services.token_cipher import ITokenCipher
from app.application.services.token_verifier import IAuthTokenVerifier
from app.application.services.weighting_service import IWeightingService
from app.bootstrap.repositories import SessionDep
from app.config import settings
from app.infrastructure.repositories.qdrant_supplier_repository import (
    QdrantSupplierRepository,
)
from app.infrastructure.repositories.qdrant_tender_repository import (
    QdrantTenderRepository,
)
from app.infrastructure.services.document_validator_service import (
    DocumentValidatorService,
)
from app.infrastructure.services.supabase_identity_directory import (
    SupabaseIdentityDirectory,
)


def get_supplier_vector_repo(request: Request) -> ISupplierVectorRepository:
    # Reutiliza el cliente Qdrant inicializado en el lifespan
    return QdrantSupplierRepository(request.app.state.qdrant_async_client)


def get_tender_vector_repo(request: Request) -> ITenderVectorRepository:
    return QdrantTenderRepository(
        client=request.app.state.qdrant_async_client,
        vector_size=settings.embedding_vector_size,
    )


def get_embedding_service(request: Request) -> IEmbeddingService:
    return request.app.state.embedding_service


def get_company_lookup_service(request: Request) -> ICompanyLookupService | None:
    # `None` cuando COMPANY_LOOKUP_PROVIDER=none: el caso de uso responde 503.
    return request.app.state.company_lookup_service


def get_reranker_service(request: Request) -> IRerankerService:
    return request.app.state.reranker_service


def get_weighting_service(request: Request) -> IWeightingService:
    return request.app.state.weighting_service


def get_email_service(request: Request) -> IEmailService:
    return request.app.state.email_service


def get_token_verifier(request: Request) -> IAuthTokenVerifier:
    """El verificador de tokens, como dependencia y no como objeto capturado.

    Que pase por el sistema de dependencias es lo que permite sustituirlo en los
    tests con `app.dependency_overrides`, y así ejercitar la verificación real
    contra un JWKS de prueba sin levantar Supabase.
    """
    return request.app.state.token_verifier


def get_identity_directory(session: SessionDep) -> IIdentityDirectory:
    return SupabaseIdentityDirectory(session)


def get_deep_analysis_service(request: Request) -> IDeepAnalysisService:
    return request.app.state.deep_analysis_service


def get_tender_assistant_ai_service(request: Request) -> ITenderAssistantAIService:
    return request.app.state.tender_assistant_ai_service


def get_milestone_extraction_service(request: Request) -> IMilestoneExtractionAIService:
    return request.app.state.milestone_extraction_service


def get_calendar_providers(request: Request) -> CalendarProviders:
    return request.app.state.calendar_providers


def get_token_cipher(request: Request) -> ITokenCipher:
    return request.app.state.token_cipher


def get_export_background(request: Request) -> IExportBackground:
    return request.app.state.export_background


def get_proposal_ai_service(request: Request) -> IProposalAIService:
    return request.app.state.proposal_ai_service


def get_document_validator_service() -> IDocumentValidatorService:
    return DocumentValidatorService()


SupplierVectorRepoDep = Annotated[
    ISupplierVectorRepository, Depends(get_supplier_vector_repo)
]


TenderVectorRepoDep = Annotated[ITenderVectorRepository, Depends(get_tender_vector_repo)]


EmbeddingServiceDep = Annotated[IEmbeddingService, Depends(get_embedding_service)]


CalendarProvidersDep = Annotated[CalendarProviders, Depends(get_calendar_providers)]


DocumentValidatorDep = Annotated[
    IDocumentValidatorService, Depends(get_document_validator_service)
]


ProposalAIServiceDep = Annotated[IProposalAIService, Depends(get_proposal_ai_service)]
