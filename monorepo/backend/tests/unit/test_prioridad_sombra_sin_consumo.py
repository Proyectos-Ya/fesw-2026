"""La prioridad de anexos está en sombra: se calcula y se guarda, nadie la consume.

Plan 233, decisión 8. La cola de la extensión no puede usarla hasta validarla
contra lo que pasó de verdad. Este test recorre lo que podría consumirla
(routers, matching, notificaciones, ingesta y la fórmula de compatibilidad) y
falla si aparece cualquiera de sus nombres.
"""

from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[2] / "app"

# Todo lo que podría leer la prioridad para decidir algo.
RUTAS_SIN_CONSUMO = [
    APP / "infrastructure" / "routers",
    APP / "application" / "use_cases" / "matching",
    APP / "application" / "use_cases" / "notifications",
    APP / "infrastructure" / "services" / "tenders",
    APP / "application" / "services" / "compatibility_scorer.py",
    APP / "application" / "services" / "compatibility_formula.py",
    APP / "application" / "use_cases" / "tender_ingestion_use_case.py",
]

NOMBRES_PROHIBIDOS = (
    "AttachmentPriorityShadow",
    "attachment_priority_shadow",
    "prioridad_sombra",
)


def _archivos(ruta: Path) -> list[Path]:
    return sorted(ruta.rglob("*.py")) if ruta.is_dir() else [ruta]


def buscar_consumos(rutas: list[Path]) -> list[str]:
    """Los archivos que nombran la prioridad en sombra, con el nombre que usan."""
    encontrados = []
    for ruta in rutas:
        for archivo in _archivos(ruta):
            texto = archivo.read_text(encoding="utf-8")
            encontrados.extend(
                f"{archivo.name} usa {nombre}"
                for nombre in NOMBRES_PROHIBIDOS
                if nombre in texto
            )
    return encontrados


def test_las_rutas_a_revisar_existen():
    # Si alguien las mueve, el test de abajo pasaría en vacío.
    for ruta in RUTAS_SIN_CONSUMO:
        assert ruta.exists(), f"{ruta} no existe: actualiza este test"


def test_nadie_consume_la_prioridad_en_sombra():
    assert buscar_consumos(RUTAS_SIN_CONSUMO) == [], (
        "La prioridad de anexos está en sombra: usarla para decidir algo exige un "
        "PR y un ADR aparte (plan 233, decisión 8)."
    )


@pytest.mark.parametrize("nombre", NOMBRES_PROHIBIDOS)
def test_el_detector_ve_un_consumo_cuando_lo_hay(tmp_path: Path, nombre: str):
    (tmp_path / "ruta.py").write_text(f"x = {nombre}\n", encoding="utf-8")

    assert buscar_consumos([tmp_path]) == [f"ruta.py usa {nombre}"]
