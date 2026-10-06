"""Composition root: el único lugar que conoce las clases concretas.

`bootstrap(app)` construye los servicios que viven en `app.state` y monta las
rutas. El resto del paquete se reparte así:

- `repositories`: un provider por repositorio SQL y su alias `*RepoDep`.
- `services`: acceso por petición a lo que vive en `app.state`.
- `builders`: construcción al arrancar de los servicios con proveedor configurable.
- un módulo por feature (`matching`, `proposals`, `calendar`, ...): los providers
  de sus casos de uso.
- `runners`: lo que corre fuera del ciclo de petición (schedulers, exportaciones).
- `routes`: el mapa de la API.

Los tests sustituyen dependencias con `app.dependency_overrides[provider]`, así
que importan cada provider desde su módulo.
"""

from fastapi import FastAPI

from app.bootstrap.builders import (
    build_calendar_providers,
    build_company_lookup_service,
    build_embedding_service,
    build_reranker_service,
)
from app.bootstrap.routes import register_routes
from app.bootstrap.runners import (
    build_export_background,
    build_milestone_extraction_background,
)
from app.config import settings
from app.infrastructure.services.field_weighting_service import FieldWeightingService
from app.infrastructure.services.gemini_deep_analysis_service import (
    GeminiDeepAnalysisService,
)
from app.infrastructure.services.gemini_milestone_extraction_service import (
    GeminiMilestoneExtractionService,
)
from app.infrastructure.services.gemini_proposal_service import GeminiProposalService
from app.infrastructure.services.gemini_tender_assistant_service import (
    GeminiTenderAssistantService,
)
from app.infrastructure.services.notifications.smtp_email_service import (
    SmtpEmailService,
)
from app.infrastructure.services.security.fernet_token_cipher import (
    FernetTokenCipher,
    UnconfiguredTokenCipher,
)
from app.infrastructure.services.supabase_token_service import (
    SupabaseJwtService,
    descargar_jwks,
)


def bootstrap(app: FastAPI) -> None:
    # El backend ya no emite sesiones: las verifica. La instancia vive en
    # app.state porque cachea el JWKS de Supabase, y una por petición
    # descargaría las claves en cada llamada.
    app.state.token_verifier = SupabaseJwtService(
        jwks_source=lambda: descargar_jwks(settings.jwks_url),
        issuer=settings.jwt_issuer,
        audience=settings.supabase_jwt_audience,
        cache_seconds=settings.supabase_jwks_cache_seconds,
    )

    app.state.embedding_service = build_embedding_service()

    app.state.deep_analysis_service = GeminiDeepAnalysisService(
        api_key=settings.gemini_api_key,
        model_name=settings.gemini_model,
    )
    app.state.proposal_ai_service = GeminiProposalService(
        api_key=settings.gemini_api_key,
        model_name=settings.gemini_model,
    )
    app.state.tender_assistant_ai_service = GeminiTenderAssistantService(
        api_key=settings.gemini_api_key,
        model_name=settings.gemini_model,
    )
    app.state.milestone_extraction_service = GeminiMilestoneExtractionService(
        api_key=settings.gemini_api_key,
        model_name=settings.gemini_model,
    )
    # Una llave inválida corta el arranque acá, no al guardar el primer token.
    app.state.token_cipher = (
        FernetTokenCipher(settings.token_encryption_key)
        if settings.token_encryption_key
        else UnconfiguredTokenCipher()
    )
    app.state.calendar_providers = build_calendar_providers()

    app.state.reranker_service = build_reranker_service()

    app.state.company_lookup_service = build_company_lookup_service()

    # El envío de correo es stateless y barato de construir, pero vive en
    # app.state igual que el resto: así el scheduler y los endpoints usan
    # exactamente la misma instancia configurada.
    app.state.email_service = SmtpEmailService(
        host=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user,
        password=settings.smtp_password,
        sender=settings.smtp_from,
        use_tls=settings.smtp_use_tls,
    )

    app.state.export_background = build_export_background(app)
    app.state.milestone_extraction_background = build_milestone_extraction_background(app)

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

    register_routes(app)
