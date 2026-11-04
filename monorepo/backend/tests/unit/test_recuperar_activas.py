"""Puesta al día de una sola vez de las activas con cambios sin ver (plan 305).

Del 2026-10-06 al 10-09 el cron de estados no vio los cambios de 30,6 h hábiles.
`ttl_cambio_ms` no admite cursor, así que esos cambios no se recuperan con el
listado de cambios. El script:

1. Toma las activas con cierre a futuro que no se escriben desde el corte.
2. Lista por publicación su rango de fechas y aplica estado y cierre como el
   cron de estados (que también deja el puntero de las que cambiaron).
3. Las que no aparecen como publicadas ya no lo están: se encolan para que su
   detalle confirme el estado.
"""

import argparse
from datetime import datetime, timedelta

from app.domain.models.cambio_estado import (
    CambioDeEstado,
    Intencion,
    PunteroDeCambio,
    ResultadoPunteros,
    ResultadoSyncEstados,
)
from scripts.recuperar_activas import Candidata, recuperar

PUB = datetime(2026, 10, 5, 12, 0)


def _cambio(code: str) -> CambioDeEstado:
    return CambioDeEstado(
        code=code,
        status_id=2,
        status_code="publicada",
        closing_at=PUB + timedelta(days=10),
    )


class Piezas:
    def __init__(self, candidatas: list[Candidata], listadas: list[str]) -> None:
        self.candidatas = candidatas
        self.listadas = listadas
        self.ventanas: list[tuple[datetime, datetime]] = []
        self.aplicados: list[str] = []
        self.forzadas: list[PunteroDeCambio] = []

    async def buscar(self, limite: int | None) -> list[Candidata]:
        return self.candidatas[:limite] if limite else self.candidatas

    async def listar(self, desde, hasta, al_recibir) -> bool:
        self.ventanas.append((desde, hasta))
        await al_recibir([_cambio(c) for c in self.listadas])
        return True

    async def aplicar(self, cambios: list[CambioDeEstado]) -> ResultadoSyncEstados:
        self.aplicados.extend(c.code for c in cambios)
        return ResultadoSyncEstados(conocidas=len(cambios), reencoladas=1)

    async def encolar(self, punteros: list[PunteroDeCambio]) -> ResultadoPunteros:
        self.forzadas.extend(punteros)
        return ResultadoPunteros(actualizar=len(punteros))

    async def correr(self, **extra) -> int:
        args = argparse.Namespace(dry_run=False, limite=None, **extra)
        return await recuperar(
            args,
            buscar=self.buscar,
            listar=self.listar,
            aplicar=self.aplicar,
            encolar=self.encolar,
        )


def _candidata(code: str, horas: int = 0) -> Candidata:
    return Candidata(code=code, published_at=PUB + timedelta(hours=horas))


async def test_lista_el_rango_de_publicacion_de_las_candidatas():
    piezas = Piezas([_candidata("A"), _candidata("B", horas=30)], listadas=["A", "B"])

    await piezas.correr()

    assert piezas.ventanas[0][0] == PUB
    assert piezas.ventanas[-1][1] > PUB + timedelta(hours=30)


async def test_aplica_lo_listado_como_el_cron_de_estados():
    piezas = Piezas([_candidata("A")], listadas=["A", "OTRA"])

    await piezas.correr()

    assert piezas.aplicados == ["A", "OTRA"]


async def test_encola_las_candidatas_que_ya_no_aparecen_publicadas():
    piezas = Piezas([_candidata("A"), _candidata("B")], listadas=["A"])

    await piezas.correr()

    assert [(p.code, p.intencion) for p in piezas.forzadas] == [
        ("B", Intencion.REABIERTA)
    ]


async def test_dry_run_solo_cuenta(capsys):
    piezas = Piezas([_candidata("A"), _candidata("B")], listadas=["A"])

    codigo = await recuperar(
        argparse.Namespace(dry_run=True, limite=None),
        buscar=piezas.buscar,
        listar=piezas.listar,
        aplicar=piezas.aplicar,
        encolar=piezas.encolar,
    )

    assert codigo == 0
    assert piezas.ventanas == [] and piezas.forzadas == []
    assert "2 candidatas" in capsys.readouterr().out


async def test_sin_candidatas_no_pide_nada():
    piezas = Piezas([], listadas=[])

    assert await piezas.correr() == 0
    assert piezas.ventanas == []


async def test_un_listado_incompleto_no_encola_a_ciegas():
    """Si el listado se cortó, "no aparece" no significa "ya no está publicada"."""
    piezas = Piezas([_candidata("A"), _candidata("B")], listadas=["A"])

    async def listar_incompleto(desde, hasta, al_recibir) -> bool:
        await al_recibir([_cambio("A")])
        return False

    piezas.listar = listar_incompleto  # type: ignore[method-assign]

    codigo = await piezas.correr()

    assert piezas.forzadas == []
    assert codigo == 1
