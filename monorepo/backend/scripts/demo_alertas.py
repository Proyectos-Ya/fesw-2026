"""Fuerza los estados de las alertas que no se alcanzan esperando (HdU 08).

Contexto
--------
Tres criterios de aceptación de la HdU 08 describen situaciones que el sistema
está diseñado para que **no** ocurran, así que no basta con dejar la aplicación
corriendo:

* **Licitación ya cerrada.** `RankTendersUseCase` descarta lo que tenga
  `closing_at` en el pasado, así que un aviso siempre nace apuntando a una
  licitación abierta. Y el dump de prueba refuerza el efecto: `date_shift.py`
  empuja al futuro toda licitación vencida para que el dashboard no salga
  vacío. Hay que cerrar una a propósito.

* **Resumen diario.** Lo arma un bucle atado a `NOTIFICATION_DIGEST_HOUR`
  (08:00 de Chile). Si esa hora ya pasó, espera hasta mañana.

* **Reintento tras la caída del correo.** El backoff es exponencial: tras unos
  pocos fallos el siguiente intento queda a decenas de minutos, inservible para
  una demostración en vivo.

Este script no es código de producción ni lo toca: solo lee y escribe filas de
las tablas de notificaciones. Vive en `scripts/` en vez de exponerse como
endpoints `/dev/...` justamente para no dejar superficie de simulación en el
despliegue.

Uso
---
En esta máquina no hay Python 3.12 fuera del contenedor, así que se ejecuta
dentro de él (el bind mount hace que el archivo esté disponible sin
reconstruir la imagen):

    docker compose exec api python -m scripts.demo_alertas estado
    docker compose exec api python -m scripts.demo_alertas cerrar-licitacion
    docker compose exec api python -m scripts.demo_alertas resumen-ahora
    docker compose exec api python -m scripts.demo_alertas reintentar-ahora
    docker compose exec api python -m scripts.demo_alertas marcar-rebote

Con el entorno virtual activado, `python -m scripts.demo_alertas ...`.

Casi todos aceptan `--email` para elegir la cuenta; sin él se usa la primera
que tenga avisos. Los que escriben aceptan `--dry-run`.
"""

import argparse
import asyncio
from datetime import timedelta

from sqlmodel import col, desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.use_cases.notifications.build_daily_digest import (
    BuildDailyDigestUseCase,
)
from app.infrastructure.db import async_session_maker
from app.infrastructure.repositories.notification_model import (
    NotificationDeliveryModel,
    NotificationModel,
)
from app.infrastructure.repositories.notification_repository import (
    NotificationDeliveryRepository,
    NotificationPreferenceRepository,
    NotificationRepository,
)
from app.infrastructure.repositories.tender_model import TenderModel
from app.infrastructure.repositories.user_model import UserModel
from app.shared.datetime_utils import utc_now_naive


class SinDatos(Exception):
    """No hay con qué trabajar: el mensaje explica qué falta y cómo conseguirlo."""


# --------------------------------------------------------------------------
# Resolución de la cuenta sobre la que se opera
# --------------------------------------------------------------------------


async def _resolver_usuario(session: AsyncSession, email: str | None) -> UserModel:
    """Devuelve el usuario indicado, o el primero que tenga avisos."""
    if email:
        resultado = await session.exec(
            select(UserModel).where(UserModel.email == email.strip().lower())
        )
        usuario = resultado.first()
        if usuario is None:
            raise SinDatos(f"No existe ninguna cuenta con el correo {email!r}.")
        return usuario

    # Sin `--email`, la cuenta interesante es la que ya tiene alertas.
    resultado = await session.exec(
        select(UserModel)
        .join(NotificationModel, col(NotificationModel.user_id) == col(UserModel.id))
        .order_by(desc(col(NotificationModel.created_at)))
        .limit(1)
    )
    usuario = resultado.first()
    if usuario is None:
        raise SinDatos(
            "Ninguna cuenta tiene avisos todavía.\n"
            "  1. Entra a /configuracion/notificaciones y baja el umbral.\n"
            "  2. Reinicia la API para forzar un escaneo inmediato:\n"
            "       docker compose restart api"
        )
    return usuario


# --------------------------------------------------------------------------
# Subcomandos
# --------------------------------------------------------------------------


async def mostrar_estado(email: str | None) -> None:
    """Imprime avisos, entregas y preferencias. Útil para narrar la demostración."""
    async with async_session_maker() as session:
        usuario = await _resolver_usuario(session, email)
        print(f"\nCuenta: {usuario.email}  ({usuario.full_name})\n", flush=True)

        preferencia = await NotificationPreferenceRepository(session).get_by_user_id(
            usuario.id
        )
        if preferencia is None:
            print(
                "Preferencias: sin guardar (rigen los valores por defecto:", flush=True
            )
            print(
                "              alertas activas, umbral 70%, aviso inmediato)",
                flush=True,
            )
        else:
            correo = "activo" if preferencia.email_delivery_enabled else "DESACTIVADO"
            print(
                f"Preferencias: alertas {'activas' if preferencia.enabled else 'apagadas'} · "
                f"umbral {round(preferencia.threshold * 100)}% · "
                f"{preferencia.delivery_mode} · correo {correo}",
                flush=True,
            )
            if preferencia.last_failure_reason:
                print(
                    f"              último fallo: {preferencia.last_failure_reason}",
                    flush=True,
                )

        avisos = await NotificationRepository(session).list_by_user(usuario.id)
        print(f"\nAvisos ({len(avisos)}):", flush=True)
        ahora = utc_now_naive()
        for aviso in avisos[:10]:
            tender = await session.get(TenderModel, aviso.tender_id)
            titulo = tender.name[:48] if tender else "(licitación ausente)"
            cerrada = tender is not None and tender.closing_at <= ahora
            marca = "CERRADA" if cerrada else "abierta"
            leido = " " if aviso.read_at else "*"
            print(
                f"  {leido} {round(aviso.score * 100):>3}%  {marca:<8} {titulo}",
                flush=True,
            )
        if len(avisos) > 10:
            print(f"  … y {len(avisos) - 10} más", flush=True)

        entregas = await NotificationDeliveryRepository(session).list_by_user(
            usuario.id
        )
        print(f"\nEntregas de correo ({len(entregas)}):", flush=True)
        for entrega in entregas[:10]:
            detalle = ""
            if entrega.status == "pending":
                detalle = f"próximo intento {entrega.next_attempt_at:%H:%M:%S}"
            elif entrega.status == "sent" and entrega.sent_at:
                detalle = f"enviado {entrega.sent_at:%H:%M:%S}"
            elif entrega.last_error:
                detalle = entrega.last_error[:50]
            print(
                f"  {entrega.status:<17} {entrega.kind:<10} "
                f"intentos={entrega.attempts}  {detalle}",
                flush=True,
            )
        print("", flush=True)


async def cerrar_licitacion(
    email: str | None, aviso_id: str | None, dry_run: bool
) -> None:
    """Deja vencida la licitación de un aviso, para el criterio de plazo cerrado."""
    async with async_session_maker() as session:
        usuario = await _resolver_usuario(session, email)
        avisos = await NotificationRepository(session).list_by_user(usuario.id)
        if not avisos:
            raise SinDatos(f"La cuenta {usuario.email} no tiene avisos que cerrar.")

        if aviso_id:
            elegido = next((a for a in avisos if str(a.id) == aviso_id), None)
            if elegido is None:
                raise SinDatos(f"La cuenta no tiene ningún aviso con id {aviso_id}.")
        else:
            # El primero que siga abierto: cerrar uno ya vencido no muestra nada.
            ahora = utc_now_naive()
            elegido = None
            for aviso in avisos:
                tender = await session.get(TenderModel, aviso.tender_id)
                if tender is not None and tender.closing_at > ahora:
                    elegido = aviso
                    break
            if elegido is None:
                raise SinDatos(
                    "Todos los avisos de esta cuenta ya apuntan a licitaciones "
                    "cerradas. No hay nada que hacer."
                )

        tender = await session.get(TenderModel, elegido.tender_id)
        if tender is None:
            raise SinDatos(
                "El aviso apunta a una licitación que ya no está en la base."
            )

        nueva_fecha = utc_now_naive() - timedelta(days=1)
        print(f"Licitación : {tender.name}", flush=True)
        print(f"Cierre     : {tender.closing_at}  ->  {nueva_fecha}", flush=True)

        if dry_run:
            print("\n[dry-run] No se escribió nada.", flush=True)
            return

        tender.closing_at = nueva_fecha
        session.add(tender)
        await session.commit()
        print(
            "\nListo. Abre /alertas: el aviso debe mostrar la insignia «Cerrada», "
            "y su ficha el banner de plazo vencido.",
            flush=True,
        )


async def resumen_ahora() -> None:
    """Arma el resumen diario sin esperar a la hora programada."""
    async with async_session_maker() as session:
        use_case = BuildDailyDigestUseCase(
            preference_repo=NotificationPreferenceRepository(session),
            notification_repo=NotificationRepository(session),
            delivery_repo=NotificationDeliveryRepository(session),
        )
        encoladas = await use_case.execute()

    if encoladas == 0:
        print(
            "No se encoló ningún resumen. Revisa que:\n"
            "  - la cuenta tenga el modo «Resumen diario» en "
            "/configuracion/notificaciones,\n"
            "  - tenga avisos que no hayan salido ya en otro correo.",
            flush=True,
        )
        return

    print(
        f"{encoladas} resumen(es) encolado(s).\n"
        "El bucle de entrega los manda en menos de 30 segundos: míralos en "
        "http://localhost:54324",
        flush=True,
    )


async def reintentar_ahora(email: str | None, dry_run: bool) -> None:
    """Adelanta el reintento de las entregas pendientes, saltándose el backoff."""
    async with async_session_maker() as session:
        usuario = await _resolver_usuario(session, email)
        resultado = await session.exec(
            select(NotificationDeliveryModel).where(
                NotificationDeliveryModel.user_id == usuario.id,
                NotificationDeliveryModel.status == "pending",
            )
        )
        pendientes = list(resultado.all())
        if not pendientes:
            raise SinDatos(
                f"La cuenta {usuario.email} no tiene entregas pendientes.\n"
                "Para provocarlas, apunta el SMTP a un puerto muerto:\n"
                "  SMTP_PORT=59999 en monorepo/.env  →  docker compose restart api"
            )

        ahora = utc_now_naive()
        print(f"{len(pendientes)} entrega(s) pendiente(s):", flush=True)
        for entrega in pendientes:
            print(
                f"  intentos={entrega.attempts}  "
                f"{entrega.next_attempt_at}  ->  {ahora}",
                flush=True,
            )

        if dry_run:
            print("\n[dry-run] No se escribió nada.", flush=True)
            return

        for entrega in pendientes:
            entrega.next_attempt_at = ahora
            session.add(entrega)
        await session.commit()
        print(
            "\nListo. Si el servidor de correo ya está de vuelta, salen en el "
            "próximo ciclo (30 segundos).",
            flush=True,
        )


async def marcar_rebote(email: str | None, motivo: str, dry_run: bool) -> None:
    """Deja la cuenta como si su correo hubiera rebotado de forma definitiva."""
    print(
        "AVISO: esto reproduce el ESTADO VISIBLE del criterio (el banner rojo y "
        "el botón de reactivar),\n"
        "       pero NO la detección del rebote. Mailpit acepta cualquier "
        "destinatario y nunca\n"
        "       devuelve un rechazo, así que esa mitad solo se demuestra con un "
        "proveedor real\n"
        "       (Brevo o SendGrid). No lo presentes como el criterio completo.\n",
        flush=True,
    )

    async with async_session_maker() as session:
        usuario = await _resolver_usuario(session, email)
        repo = NotificationPreferenceRepository(session)
        preferencia = await repo.get_by_user_id(usuario.id)
        if preferencia is None:
            raise SinDatos(
                f"La cuenta {usuario.email} nunca guardó preferencias.\n"
                "Entra una vez a /configuracion/notificaciones y cambia algo, "
                "para que exista la fila."
            )

        print(f"Cuenta: {usuario.email}", flush=True)
        print(f"Motivo: {motivo}", flush=True)

        if dry_run:
            print("\n[dry-run] No se escribió nada.", flush=True)
            return

        preferencia.email_delivery_enabled = False
        preferencia.last_failure_reason = motivo
        preferencia.last_failure_at = utc_now_naive()
        await repo.save(preferencia)
        print(
            "\nListo. Abre /configuracion/notificaciones: debe verse el aviso de "
            "envío desactivado con su motivo y el botón para reactivarlo.",
            flush=True,
        )


# --------------------------------------------------------------------------
# Entrada
# --------------------------------------------------------------------------


def _construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    def con_email(p: argparse.ArgumentParser) -> argparse.ArgumentParser:
        p.add_argument(
            "--email",
            help="Cuenta sobre la que operar. Por defecto, la primera con avisos.",
        )
        return p

    def con_dry_run(p: argparse.ArgumentParser) -> argparse.ArgumentParser:
        p.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra el cambio sin escribir en la base.",
        )
        return p

    con_email(sub.add_parser("estado", help="Avisos, entregas y preferencias."))

    cerrar = con_dry_run(
        con_email(
            sub.add_parser(
                "cerrar-licitacion",
                help="Deja vencida la licitación de un aviso (criterio de plazo cerrado).",
            )
        )
    )
    cerrar.add_argument(
        "--aviso", help="Id del aviso. Por defecto, el primero abierto."
    )

    sub.add_parser(
        "resumen-ahora",
        help="Arma el resumen diario sin esperar a la hora programada.",
    )

    con_dry_run(
        con_email(
            sub.add_parser(
                "reintentar-ahora",
                help="Adelanta el reintento de las entregas pendientes.",
            )
        )
    )

    rebote = con_dry_run(
        con_email(
            sub.add_parser(
                "marcar-rebote",
                help="Deja la cuenta como si su correo hubiera rebotado (solo el estado visible).",
            )
        )
    )
    rebote.add_argument(
        "--motivo",
        default="Destinatario rechazado: la dirección no existe",
        help="Texto que se muestra como causa del fallo.",
    )

    return parser


async def _despachar(args: argparse.Namespace) -> None:
    if args.comando == "estado":
        await mostrar_estado(args.email)
    elif args.comando == "cerrar-licitacion":
        await cerrar_licitacion(args.email, args.aviso, args.dry_run)
    elif args.comando == "resumen-ahora":
        await resumen_ahora()
    elif args.comando == "reintentar-ahora":
        await reintentar_ahora(args.email, args.dry_run)
    elif args.comando == "marcar-rebote":
        await marcar_rebote(args.email, args.motivo, args.dry_run)


def main() -> None:
    args = _construir_parser().parse_args()
    try:
        asyncio.run(_despachar(args))
    except SinDatos as e:
        # Falta de datos, no un error del script: mensaje claro y salida 1.
        raise SystemExit(f"\n{e}\n") from None


if __name__ == "__main__":
    main()
