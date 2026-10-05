"""Providers de alertas de licitaciones (HdU 08)."""

from app.application.use_cases.notifications.manage_notifications import (
    CountUnreadNotificationsUseCase,
    GetNotificationPreferencesUseCase,
    ListDeliveriesUseCase,
    ListNotificationsUseCase,
    MarkAllNotificationsReadUseCase,
    MarkNotificationReadUseCase,
    UpdateNotificationPreferencesUseCase,
)
from app.bootstrap.repositories import (
    NotificationDeliveryRepoDep,
    NotificationPreferenceRepoDep,
    NotificationRepoDep,
    TenderRepoDep,
)


def get_list_notifications_use_case(
    notification_repo: NotificationRepoDep,
    tender_repo: TenderRepoDep,
) -> ListNotificationsUseCase:
    return ListNotificationsUseCase(
        notification_repo=notification_repo,
        tender_repo=tender_repo,
    )


def get_count_unread_use_case(
    notification_repo: NotificationRepoDep,
) -> CountUnreadNotificationsUseCase:
    return CountUnreadNotificationsUseCase(notification_repo=notification_repo)


def get_mark_notification_read_use_case(
    notification_repo: NotificationRepoDep,
) -> MarkNotificationReadUseCase:
    return MarkNotificationReadUseCase(notification_repo=notification_repo)


def get_mark_all_read_use_case(
    notification_repo: NotificationRepoDep,
) -> MarkAllNotificationsReadUseCase:
    return MarkAllNotificationsReadUseCase(notification_repo=notification_repo)


def get_notification_preferences_use_case(
    preference_repo: NotificationPreferenceRepoDep,
) -> GetNotificationPreferencesUseCase:
    return GetNotificationPreferencesUseCase(preference_repo=preference_repo)


def get_update_notification_preferences_use_case(
    preference_repo: NotificationPreferenceRepoDep,
) -> UpdateNotificationPreferencesUseCase:
    return UpdateNotificationPreferencesUseCase(preference_repo=preference_repo)


def get_list_deliveries_use_case(
    delivery_repo: NotificationDeliveryRepoDep,
) -> ListDeliveriesUseCase:
    return ListDeliveriesUseCase(delivery_repo=delivery_repo)
