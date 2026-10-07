"""Mapa de la API: qué routers se montan y con qué providers.

Vive dentro del composition root, así que importa los providers directamente en
vez de recibirlos por parámetro. Cada router recibe solo lo que usa.
"""

from fastapi import FastAPI

from app.bootstrap.calendar import (
    get_calendar_connections_use_case,
    get_complete_calendar_authorization_use_case,
    get_disconnect_calendar_use_case,
    get_extract_tender_milestones_use_case,
    get_set_milestone_reminder_use_case,
    get_start_calendar_authorization_use_case,
    get_sync_milestones_use_case,
    get_tender_milestones_use_case,
)
from app.bootstrap.capabilities import (
    get_add_capability_evidence_use_case,
    get_answer_capability_question_use_case,
    get_build_experience_catalog_use_case,
    get_quotation_use_case,
)
from app.bootstrap.exports import (
    get_create_share_link_use_case,
    get_download_export_file_use_case,
    get_export_job_use_case,
    get_export_tender_use_case,
    get_list_share_links_use_case,
    get_revoke_share_link_use_case,
    get_shared_tender_use_case,
)
from app.bootstrap.kanban import (
    get_add_tender_to_board_use_case,
    get_archive_tender_from_board_use_case,
    get_create_kanban_column_use_case,
    get_delete_kanban_column_use_case,
    get_list_archived_tenders_use_case,
    get_list_kanban_cards_use_case,
    get_list_kanban_columns_use_case,
    get_move_kanban_card_use_case,
    get_remove_tender_from_board_use_case,
    get_restore_tender_use_case,
    get_update_kanban_column_use_case,
)
from app.bootstrap.matching import (
    get_get_or_create_deep_analysis_use_case,
    get_list_saved_tenders_use_case,
    get_rank_tenders_use_case,
    get_save_tender_use_case,
    get_score_tender_on_demand_use_case,
    get_search_tenders_use_case,
    get_tender_detail_use_case,
    get_unsave_tender_use_case,
)
from app.bootstrap.notifications import (
    get_count_unread_use_case,
    get_list_deliveries_use_case,
    get_list_notifications_use_case,
    get_mark_all_read_use_case,
    get_mark_notification_read_use_case,
    get_notification_preferences_use_case,
    get_update_notification_preferences_use_case,
)
from app.bootstrap.proposals import (
    get_answer_proposal_question_use_case,
    get_decide_discrepancy_use_case,
    get_export_proposal_use_case,
    get_generate_proposal_use_case,
    get_list_pending_capability_questions_use_case,
    get_proposal_use_case,
    get_regenerate_proposal_use_case,
    get_resume_proposal_use_case,
    get_start_feasibility_use_case,
    get_sync_proposal_answers_use_case,
)
from app.bootstrap.questions import (
    get_answer_question_use_case,
    get_smart_question_use_case,
)
from app.bootstrap.repositories import (
    get_supplier_invitation_repo,
    get_supplier_member_repo,
    get_supplier_repo,
    get_user_repo,
)
from app.bootstrap.services import (
    get_company_lookup_service,
    get_email_service,
    get_embedding_service,
    get_identity_directory,
    get_milestone_extraction_background,
    get_supplier_vector_repo,
    get_token_verifier,
)
from app.bootstrap.tender_chat import (
    get_ask_tender_assistant_use_case,
    get_create_tender_chat_session_use_case,
    get_delete_tender_chat_doc_use_case,
    get_list_tender_chat_docs_use_case,
    get_tender_chat_history_use_case,
    get_upload_tender_chat_doc_use_case,
)
from app.infrastructure.auth.dependencies import (
    build_get_current_user,
    build_get_current_workspace_context,
    build_get_optional_workspace_context,
)
from app.infrastructure.routers.auth import create_auth_router
from app.infrastructure.routers.calendar import (
    create_calendar_router,
    create_milestone_sync_router,
)
from app.infrastructure.routers.capability import create_capability_router
from app.infrastructure.routers.catalog import create_catalog_router
from app.infrastructure.routers.exports import create_exports_router
from app.infrastructure.routers.health import create_health_router
from app.infrastructure.routers.kanban import create_kanban_router
from app.infrastructure.routers.milestones import create_milestones_router
from app.infrastructure.routers.notification import create_notification_router
from app.infrastructure.routers.proposal import create_proposal_router
from app.infrastructure.routers.question import create_question_router
from app.infrastructure.routers.quotation import create_quotation_router
from app.infrastructure.routers.sharing import (
    create_public_sharing_router,
    create_sharing_router,
)
from app.infrastructure.routers.supplier import create_supplier_router
from app.infrastructure.routers.tender import create_tender_router
from app.infrastructure.routers.tender_chat import create_tender_chat_router
from app.infrastructure.routers.workspace import create_workspace_router


def register_routes(app: FastAPI) -> None:
    # Una sola instancia de la dependencia → FastAPI cachea el usuario por request
    get_current_user = build_get_current_user(
        get_user_repo=get_user_repo,
        get_token_verifier=get_token_verifier,
        get_identity_directory=get_identity_directory,
    )

    get_current_workspace_context = build_get_current_workspace_context(
        get_current_user=get_current_user,
        get_member_repo=get_supplier_member_repo,
        get_supplier_repo=get_supplier_repo,
    )
    get_optional_workspace_context = build_get_optional_workspace_context(
        get_current_user=get_current_user,
        get_member_repo=get_supplier_member_repo,
        get_supplier_repo=get_supplier_repo,
    )

    # Cada router recibe solo los providers que usa. El orden de registro es el
    # orden en que FastAPI prueba las rutas, así que no se reordena a la ligera.
    app.include_router(create_health_router(), tags=["Health"])
    app.include_router(create_auth_router(get_current_user=get_current_user))
    app.include_router(
        create_supplier_router(
            get_supplier_repo=get_supplier_repo,
            get_supplier_vector_repo=get_supplier_vector_repo,
            get_embedding_service=get_embedding_service,
            get_company_lookup_service=get_company_lookup_service,
            get_current_user=get_current_user,
            get_supplier_member_repo=get_supplier_member_repo,
            get_current_workspace_context=get_optional_workspace_context,
        )
    )
    app.include_router(
        create_workspace_router(
            get_current_user=get_current_user,
            get_current_workspace_context=get_current_workspace_context,
            get_supplier_member_repo=get_supplier_member_repo,
            get_supplier_invitation_repo=get_supplier_invitation_repo,
            get_supplier_repo=get_supplier_repo,
            get_user_repo=get_user_repo,
            get_email_service=get_email_service,
        )
    )
    app.include_router(
        create_tender_router(
            get_rank_tenders_use_case=get_rank_tenders_use_case,
            get_current_user=get_current_user,
            get_get_or_create_deep_analysis_use_case=get_get_or_create_deep_analysis_use_case,
            get_list_saved_tenders_use_case=get_list_saved_tenders_use_case,
            get_save_tender_use_case=get_save_tender_use_case,
            get_unsave_tender_use_case=get_unsave_tender_use_case,
            get_search_tenders_use_case=get_search_tenders_use_case,
            get_tender_detail_use_case=get_tender_detail_use_case,
            get_current_workspace_context=get_optional_workspace_context,
            get_score_tender_on_demand_use_case=get_score_tender_on_demand_use_case,
        )
    )
    app.include_router(
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
    app.include_router(
        create_question_router(
            get_smart_question_use_case=get_smart_question_use_case,
            get_answer_question_use_case=get_answer_question_use_case,
            get_current_user=get_current_user,
        )
    )
    app.include_router(create_catalog_router(get_current_user=get_current_user))
    app.include_router(
        create_tender_chat_router(
            get_current_user=get_current_user,
            get_upload_doc_use_case=get_upload_tender_chat_doc_use_case,
            get_list_docs_use_case=get_list_tender_chat_docs_use_case,
            get_delete_doc_use_case=get_delete_tender_chat_doc_use_case,
            get_ask_assistant_use_case=get_ask_tender_assistant_use_case,
            get_chat_history_use_case=get_tender_chat_history_use_case,
            get_create_chat_session_use_case=get_create_tender_chat_session_use_case,
            get_current_workspace_context=get_optional_workspace_context,
        )
    )
    app.include_router(
        create_kanban_router(
            get_current_user=get_current_user,
            get_list_kanban_columns_use_case=get_list_kanban_columns_use_case,
            get_create_kanban_column_use_case=get_create_kanban_column_use_case,
            get_update_kanban_column_use_case=get_update_kanban_column_use_case,
            get_delete_kanban_column_use_case=get_delete_kanban_column_use_case,
            get_list_kanban_cards_use_case=get_list_kanban_cards_use_case,
            get_add_tender_to_board_use_case=get_add_tender_to_board_use_case,
            get_move_kanban_card_use_case=get_move_kanban_card_use_case,
            get_remove_tender_from_board_use_case=get_remove_tender_from_board_use_case,
            get_archive_tender_from_board_use_case=get_archive_tender_from_board_use_case,
            get_list_archived_tenders_use_case=get_list_archived_tenders_use_case,
            get_restore_tender_use_case=get_restore_tender_use_case,
        )
    )
    app.include_router(
        create_capability_router(
            get_current_user=get_current_user,
            get_build_catalog_use_case=get_build_experience_catalog_use_case,
            get_answer_use_case=get_answer_capability_question_use_case,
            get_add_evidence_use_case=get_add_capability_evidence_use_case,
            get_list_pending_use_case=get_list_pending_capability_questions_use_case,
            get_current_workspace_context=get_optional_workspace_context,
        )
    )
    app.include_router(
        create_proposal_router(
            get_current_user=get_current_user,
            get_start_feasibility_use_case=get_start_feasibility_use_case,
            get_proposal_use_case=get_proposal_use_case,
            get_answer_proposal_question_use_case=get_answer_proposal_question_use_case,
            get_decide_discrepancy_use_case=get_decide_discrepancy_use_case,
            get_resume_proposal_use_case=get_resume_proposal_use_case,
            get_sync_proposal_answers_use_case=get_sync_proposal_answers_use_case,
            get_generate_proposal_use_case=get_generate_proposal_use_case,
            get_regenerate_proposal_use_case=get_regenerate_proposal_use_case,
            get_export_proposal_use_case=get_export_proposal_use_case,
            get_current_workspace_context=get_optional_workspace_context,
        )
    )
    app.include_router(
        create_quotation_router(
            get_current_user,
            get_quotation_use_case,
            get_current_workspace_context=get_optional_workspace_context,
        )
    )
    app.include_router(
        create_sharing_router(
            get_current_workspace_context,
            get_create_share_link_use_case,
            get_list_share_links_use_case,
            get_revoke_share_link_use_case,
        )
    )
    # Sin sesión a propósito: es lo que abre un tercero (criterio 2).
    app.include_router(create_public_sharing_router(get_shared_tender_use_case))
    app.include_router(
        create_exports_router(
            get_current_workspace_context,
            get_current_user,
            get_export_tender_use_case,
            get_export_job_use_case,
            get_download_export_file_use_case,
        )
    )
    app.include_router(
        create_milestones_router(
            get_current_user,
            get_tender_milestones_use_case,
            get_extract_tender_milestones_use_case,
            get_set_milestone_reminder_use_case,
            get_milestone_extraction_background,
        )
    )
    app.include_router(
        create_calendar_router(
            get_current_user,
            get_calendar_connections_use_case,
            get_start_calendar_authorization_use_case,
            get_complete_calendar_authorization_use_case,
            get_disconnect_calendar_use_case,
        )
    )
    app.include_router(
        create_milestone_sync_router(get_current_user, get_sync_milestones_use_case)
    )

