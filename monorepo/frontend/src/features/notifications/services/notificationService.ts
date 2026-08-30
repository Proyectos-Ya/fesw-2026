import { apiFetch } from "@/features/shared/api/client";
import type {
  NotificationDelivery,
  NotificationItem,
  NotificationPreferences,
  UnreadCount,
  UpdatePreferencesPayload,
} from "../notificationTypes";

/** Backend: GET /notifications */
export function getNotifications(onlyUnread = false): Promise<NotificationItem[]> {
  const params = new URLSearchParams();
  if (onlyUnread) params.set("only_unread", "true");
  const query = params.toString();
  return apiFetch<NotificationItem[]>(`/notifications${query ? `?${query}` : ""}`);
}

/** Backend: GET /notifications/unread-count */
export function getUnreadCount(): Promise<UnreadCount> {
  return apiFetch<UnreadCount>("/notifications/unread-count");
}

/** Backend: POST /notifications/{id}/read */
export function markNotificationRead(
  notificationId: string,
): Promise<NotificationItem> {
  return apiFetch<NotificationItem>(
    `/notifications/${encodeURIComponent(notificationId)}/read`,
    { method: "POST" },
  );
}

/** Backend: POST /notifications/read-all */
export function markAllNotificationsRead(): Promise<{ updated: number }> {
  return apiFetch<{ updated: number }>("/notifications/read-all", {
    method: "POST",
  });
}

/** Backend: GET /notifications/preferences */
export function getNotificationPreferences(): Promise<NotificationPreferences> {
  return apiFetch<NotificationPreferences>("/notifications/preferences");
}

/** Backend: PATCH /notifications/preferences */
export function updateNotificationPreferences(
  payload: UpdatePreferencesPayload,
): Promise<NotificationPreferences> {
  return apiFetch<NotificationPreferences>("/notifications/preferences", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

/**
 * Backend: POST /notifications/preferences/reactivate-email
 *
 * El sistema desactiva el envío cuando el correo rebota; esta es la vuelta
 * atrás una vez que el usuario corrigió su dirección.
 */
export function reactivateEmailDelivery(): Promise<NotificationPreferences> {
  return apiFetch<NotificationPreferences>(
    "/notifications/preferences/reactivate-email",
    { method: "POST" },
  );
}

/** Backend: GET /notifications/deliveries */
export function getDeliveries(): Promise<NotificationDelivery[]> {
  return apiFetch<NotificationDelivery[]>("/notifications/deliveries");
}
