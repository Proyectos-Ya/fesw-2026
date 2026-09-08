from collections.abc import Callable

from fastapi import APIRouter

from app.infrastructure.routers.auth import create_auth_router
from app.infrastructure.routers.catalog import create_catalog_router
from app.infrastructure.routers.health import create_health_router
from app.infrastructure.routers.notification import create_notification_router
from app.infrastructure.routers.question import create_question_router
from app.infrastructure.routers.supplier import create_supplier_router
from app.infrastructure.routers.tender import create_tender_router
from app.infrastructure.routers.tender_chat import create_tender_chat_router


def create_router(
    get_rank_tenders_use_case: Callable,
    get_smart_question_use_case: Callable,
    get_answer_question_use_case: Callable,
    get_supplier_repo: Callable,
    get_supplier_vector_repo: Callable,
    get_embedding_service: Callable,
    get_user_repo: Callable,
    get_current_user: Callable,
    get_get_or_create_deep_analysis_use_case: Callable,
    get_list_saved_tenders_use_case: Callable,
    get_save_tender_use_case: Callable,
    get_unsave_tender_use_case: Callable,
    get_search_tenders_use_case: Callable,
    get_tender_detail_use_case: Callable,
    get_list_notifications_use_case: Callable,
    get_count_unread_use_case: Callable,
    get_mark_notification_read_use_case: Callable,
    get_mark_all_read_use_case: Callable,
    get_notification_preferences_use_case: Callable,
    get_update_notification_preferences_use_case: Callable,
    get_list_deliveries_use_case: Callable,
    get_upload_tender_chat_doc_use_case: Callable,
    get_list_tender_chat_docs_use_case: Callable,
    get_delete_tender_chat_doc_use_case: Callable,
    get_ask_tender_assistant_use_case: Callable,
    get_tender_chat_history_use_case: Callable,
    get_create_tender_chat_session_use_case: Callable,
) -> APIRouter:
    """Ensambla todos los sub-routers con sus dependencias inyectadas.

    Público: health (root + /health). El registro y el inicio de sesión los
    atiende Supabase Auth desde el navegador, así que ya no hay rutas públicas
    de autenticación acá.

    Protegidos (requieren sesión): /auth/me, suppliers, tenders, questions,
    tender chat, notificaciones.
    """
    root = APIRouter()

    # --- Ruta pública ---
    root.include_router(create_health_router(), tags=["Health"])
    root.include_router(
        create_auth_router(get_current_user=get_current_user)
    )

    # --- Rutas protegidas (la auth se aplica dentro de cada fábrica) ---
    root.include_router(
        create_supplier_router(
            get_supplier_repo=get_supplier_repo,
            get_supplier_vector_repo=get_supplier_vector_repo,
            get_embedding_service=get_embedding_service,
            get_current_user=get_current_user,
        )
    )
    root.include_router(
        create_tender_router(
            get_rank_tenders_use_case=get_rank_tenders_use_case,
            get_current_user=get_current_user,
            get_get_or_create_deep_analysis_use_case=get_get_or_create_deep_analysis_use_case,
            get_list_saved_tenders_use_case=get_list_saved_tenders_use_case,
            get_save_tender_use_case=get_save_tender_use_case,
            get_unsave_tender_use_case=get_unsave_tender_use_case,
            get_search_tenders_use_case=get_search_tenders_use_case,
            get_tender_detail_use_case=get_tender_detail_use_case,
        )
    )

    root.include_router(
        create_notification_router(
            get_current_user=get_current_user,
            get_list_notifications_use_case=get_list_notifications_use_case,
            get_count_unread_use_case=get_count_unread_use_case,
            get_mark_notification_read_use_case=get_mark_notification_read_use_case,
            get_mark_all_read_use_case=get_mark_all_read_use_case,
            get_notification_preferences_use_case=get_notification_preferences_use_case,
            get_update_notification_preferences_use_case=get_update_notification_preferences_use_case,
            get_list_deliveries_use_case=get_list_deliveries_use_case,
        )
    )

    root.include_router(
        create_question_router(
            get_smart_question_use_case=get_smart_question_use_case,
            get_current_user=get_current_user,
        )
    )

    root.include_router(
        create_catalog_router(
            get_current_user=get_current_user,
        )
    )

    root.include_router(
        create_tender_chat_router(
            get_current_user=get_current_user,
            get_upload_doc_use_case=get_upload_tender_chat_doc_use_case,
            get_list_docs_use_case=get_list_tender_chat_docs_use_case,
            get_delete_doc_use_case=get_delete_tender_chat_doc_use_case,
            get_ask_assistant_use_case=get_ask_tender_assistant_use_case,
            get_chat_history_use_case=get_tender_chat_history_use_case,
            get_create_chat_session_use_case=get_create_tender_chat_session_use_case,
        )
    )

    return root
