from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.application.schemas.notification_schema import (
    MarkAllReadResponse,
    NotificationDeliveryResponse,
    NotificationPreferenceResponse,
    NotificationResponse,
    UnreadCountResponse,
    UpdateNotificationPreferencesRequest,
)
from app.application.use_cases.notifications.manage_notifications import (
    CountUnreadNotificationsUseCase,
    GetNotificationPreferencesUseCase,
    ListDeliveriesUseCase,
    ListNotificationsUseCase,
    MarkAllNotificationsReadUseCase,
    MarkNotificationReadUseCase,
    UpdateNotificationPreferencesUseCase,
)
from app.domain.entities.notification import NotificationPreference
from app.domain.entities.user import User
from app.domain.errors.notification_errors import NotificationNotFound


def _to_preference_response(
    preference: NotificationPreference,
) -> NotificationPreferenceResponse:
    return NotificationPreferenceResponse(
        enabled=preference.enabled,
        # El dominio guarda 0..1; la interfaz muestra 0–100.
        threshold_pct=round(preference.threshold * 100),
        delivery_mode=preference.delivery_mode,
        email_delivery_enabled=preference.email_delivery_enabled,
        last_failure_reason=preference.last_failure_reason,
        last_failure_at=preference.last_failure_at,
    )


def create_notification_router(
    get_current_user: Callable,
    get_list_notifications_use_case: Callable,
    get_count_unread_use_case: Callable,
    get_mark_notification_read_use_case: Callable,
    get_mark_all_read_use_case: Callable,
    get_notification_preferences_use_case: Callable,
    get_update_notification_preferences_use_case: Callable,
    get_list_deliveries_use_case: Callable,
) -> APIRouter:
    """Fábrica del router de alertas. Todas las rutas requieren sesión activa."""
    router = APIRouter(
        prefix="/notifications",
        tags=["Notifications"],
        dependencies=[Depends(get_current_user)],
    )

    # Las rutas estáticas van antes que cualquier `/{notification_id}`: si no,
    # FastAPI intentaría interpretar "preferences" como UUID.
    @router.get("/unread-count", response_model=UnreadCountResponse)
    async def get_unread_count(
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[
            CountUnreadNotificationsUseCase, Depends(get_count_unread_use_case)
        ],
    ):
        """Contador para el badge de la campanita."""
        return UnreadCountResponse(count=await use_case.execute(current_user.id))

    @router.get("/preferences", response_model=NotificationPreferenceResponse)
    async def get_preferences(
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[
            GetNotificationPreferencesUseCase,
            Depends(get_notification_preferences_use_case),
        ],
    ):
        return _to_preference_response(await use_case.execute(current_user.id))

    @router.patch("/preferences", response_model=NotificationPreferenceResponse)
    async def update_preferences(
        payload: UpdateNotificationPreferencesRequest,
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[
            UpdateNotificationPreferencesUseCase,
            Depends(get_update_notification_preferences_use_case),
        ],
    ):
        """Umbral propio, activación y modo de entrega."""
        try:
            preference = await use_case.execute(
                user_id=current_user.id,
                enabled=payload.enabled,
                threshold=(
                    payload.threshold_pct / 100
                    if payload.threshold_pct is not None
                    else None
                ),
                delivery_mode=payload.delivery_mode,
                reactivate_email=payload.reactivate_email,
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)
            ) from e
        return _to_preference_response(preference)

    @router.post(
        "/preferences/reactivate-email",
        response_model=NotificationPreferenceResponse,
    )
    async def reactivate_email(
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[
            UpdateNotificationPreferencesUseCase,
            Depends(get_update_notification_preferences_use_case),
        ],
    ):
        """Vuelve a habilitar el correo tras corregir la dirección.

        El sistema lo desactiva solo cuando el proveedor rechaza la dirección;
        sin esta ruta el usuario quedaría sin forma de volver.
        """
        preference = await use_case.execute(
            user_id=current_user.id, reactivate_email=True
        )
        return _to_preference_response(preference)

    @router.get("/deliveries", response_model=list[NotificationDeliveryResponse])
    async def list_deliveries(
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[
            ListDeliveriesUseCase, Depends(get_list_deliveries_use_case)
        ],
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ):
        """Bandeja de salida: qué correos salieron y cuáles esperan reintento."""
        entregas = await use_case.execute(current_user.id, limit=limit)
        return [
            NotificationDeliveryResponse(
                id=e.id,
                kind=e.kind,
                status=e.status,
                attempts=e.attempts,
                last_error=e.last_error,
                next_attempt_at=e.next_attempt_at,
                sent_at=e.sent_at,
                created_at=e.created_at,
                notification_ids=e.notification_ids,
            )
            for e in entregas
        ]

    @router.post("/read-all", response_model=MarkAllReadResponse)
    async def mark_all_read(
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[
            MarkAllNotificationsReadUseCase, Depends(get_mark_all_read_use_case)
        ],
    ):
        return MarkAllReadResponse(updated=await use_case.execute(current_user.id))

    @router.get("", response_model=list[NotificationResponse])
    async def list_notifications(
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[
            ListNotificationsUseCase, Depends(get_list_notifications_use_case)
        ],
        only_unread: bool = False,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ):
        """Avisos del usuario, del más reciente al más antiguo."""
        avisos = await use_case.execute(
            current_user.id, only_unread=only_unread, limit=limit
        )
        return [
            NotificationResponse(
                id=a.notification.id,
                tender_id=a.notification.tender_id,
                score_pct=round(a.notification.score * 100),
                read_at=a.notification.read_at,
                created_at=a.notification.created_at,
                is_closed=a.is_closed,
                tender=a.tender,
            )
            for a in avisos
        ]

    @router.post("/{notification_id}/read", response_model=NotificationResponse)
    async def mark_read(
        notification_id: UUID,
        current_user: Annotated[User, Depends(get_current_user)],
        use_case: Annotated[
            MarkNotificationReadUseCase, Depends(get_mark_notification_read_use_case)
        ],
    ):
        try:
            aviso = await use_case.execute(current_user.id, notification_id)
        except NotificationNotFound as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        return NotificationResponse(
            id=aviso.id,
            tender_id=aviso.tender_id,
            score_pct=round(aviso.score * 100),
            read_at=aviso.read_at,
            created_at=aviso.created_at,
            # Marcar leído no consulta la licitación: el panel ya trae ese dato
            # y esta respuesta solo confirma el cambio de estado.
            is_closed=False,
        )

    return router
