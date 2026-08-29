"""Detección en segundo plano de licitaciones compatibles (HdU 08)."""

from uuid import UUID, uuid4

from app.application.use_cases.notifications.scan_supplier_for_alerts import (
    ScanSupplierForAlertsUseCase,
)
from app.domain.entities.matching_result import MatchingResult
from app.domain.entities.notification import Notification, NotificationPreference
from tests.unit.application.fakes import (
    InMemoryNotificationDeliveryRepository,
    InMemoryNotificationPreferenceRepository,
    InMemoryNotificationRepository,
)


class FakeRankTenders:
    """Sustituye al pipeline de matching: acá solo importan los scores."""

    def __init__(self, results: list[MatchingResult]) -> None:
        self.results = results
        self.calls: list[UUID] = []

    async def execute(self, user_id: UUID, **_kwargs) -> list[MatchingResult]:
        self.calls.append(user_id)
        return self.results


def match(score: float, tender_id: UUID | None = None) -> MatchingResult:
    return MatchingResult(
        supplier_id=uuid4(),
        tender_id=tender_id or uuid4(),
        similarity_score=score,
        final_score=score,
        model_version="test",
    )


def build_use_case(
    results: list[MatchingResult],
) -> tuple[
    ScanSupplierForAlertsUseCase,
    InMemoryNotificationPreferenceRepository,
    InMemoryNotificationRepository,
    InMemoryNotificationDeliveryRepository,
]:
    preference_repo = InMemoryNotificationPreferenceRepository()
    notification_repo = InMemoryNotificationRepository()
    delivery_repo = InMemoryNotificationDeliveryRepository()
    use_case = ScanSupplierForAlertsUseCase(
        rank_tenders_use_case=FakeRankTenders(results),  # type: ignore[arg-type]
        preference_repo=preference_repo,
        notification_repo=notification_repo,
        delivery_repo=delivery_repo,
    )
    return use_case, preference_repo, notification_repo, delivery_repo


class TestScanSupplierForAlerts:
    async def test_avisa_de_una_licitacion_sobre_el_umbral(self):
        user_id = uuid4()
        use_case, _, notification_repo, delivery_repo = build_use_case([match(0.85)])

        nuevos = await use_case.execute(user_id)

        assert len(nuevos) == 1
        assert nuevos[0].score == 0.85
        # El criterio pide las dos cosas: aviso en el panel y correo.
        assert await notification_repo.count_unread(user_id) == 1
        assert len(delivery_repo.deliveries) == 1

    async def test_no_avisa_bajo_el_umbral(self):
        user_id = uuid4()
        use_case, _, notification_repo, delivery_repo = build_use_case([match(0.69)])

        nuevos = await use_case.execute(user_id)

        assert nuevos == []
        assert await notification_repo.count_unread(user_id) == 0
        assert delivery_repo.deliveries == {}

    async def test_el_umbral_es_inclusivo(self):
        # El criterio dice "igual o superior al umbral verde (≥70%)".
        use_case, _, _, _ = build_use_case([match(0.70)])

        assert len(await use_case.execute(uuid4())) == 1

    async def test_respeta_el_umbral_personalizado_del_usuario(self):
        user_id = uuid4()
        use_case, preference_repo, _, _ = build_use_case([match(0.55)])
        await preference_repo.save(
            NotificationPreference(user_id=user_id, threshold=0.50)
        )

        assert len(await use_case.execute(user_id)) == 1

    async def test_no_avisa_si_el_usuario_desactivo_las_alertas(self):
        user_id = uuid4()
        use_case, preference_repo, _, _ = build_use_case([match(0.95)])
        await preference_repo.save(
            NotificationPreference(user_id=user_id, enabled=False)
        )

        assert await use_case.execute(user_id) == []

    async def test_no_repite_el_aviso_de_una_licitacion_ya_notificada(self):
        # Sin esto, cada ciclo del scheduler volvería a avisar de lo mismo.
        user_id = uuid4()
        tender_id = uuid4()
        use_case, _, notification_repo, _ = build_use_case(
            [match(0.9, tender_id=tender_id)]
        )
        await notification_repo.save(
            Notification(user_id=user_id, tender_id=tender_id, score=0.9)
        )

        assert await use_case.execute(user_id) == []

    async def test_un_segundo_escaneo_no_duplica_avisos(self):
        user_id = uuid4()
        use_case, _, notification_repo, _ = build_use_case([match(0.9)])

        await use_case.execute(user_id)
        segundos = await use_case.execute(user_id)

        assert segundos == []
        assert len(await notification_repo.list_by_user(user_id)) == 1

    async def test_en_modo_resumen_diario_no_encola_correo_inmediato(self):
        user_id = uuid4()
        use_case, preference_repo, notification_repo, delivery_repo = build_use_case(
            [match(0.9)]
        )
        await preference_repo.save(
            NotificationPreference(user_id=user_id, delivery_mode="daily_digest")
        )

        await use_case.execute(user_id)

        # El aviso in-app existe igual; el correo lo arma el resumen diario.
        assert await notification_repo.count_unread(user_id) == 1
        assert delivery_repo.deliveries == {}

    async def test_no_encola_correo_si_el_envio_esta_desactivado(self):
        # El usuario cuyo correo rebotó sigue viendo los avisos en la
        # plataforma, pero no se le vuelve a escribir.
        user_id = uuid4()
        use_case, preference_repo, notification_repo, delivery_repo = build_use_case(
            [match(0.9)]
        )
        await preference_repo.save(
            NotificationPreference(user_id=user_id, email_delivery_enabled=False)
        )

        await use_case.execute(user_id)

        assert await notification_repo.count_unread(user_id) == 1
        assert delivery_repo.deliveries == {}

    async def test_agrupa_varias_licitaciones_en_un_solo_correo(self):
        # Cuando la ingesta trae varias de golpe, un correo por licitación
        # llenaría la bandeja del usuario.
        use_case, _, _, delivery_repo = build_use_case(
            [match(0.9), match(0.85), match(0.8)]
        )

        await use_case.execute(uuid4())

        assert len(delivery_repo.deliveries) == 1
        entrega = next(iter(delivery_repo.deliveries.values()))
        assert len(entrega.notification_ids) == 3

    async def test_sin_matches_no_hace_nada(self):
        use_case, _, _, delivery_repo = build_use_case([])

        assert await use_case.execute(uuid4()) == []
        assert delivery_repo.deliveries == {}
