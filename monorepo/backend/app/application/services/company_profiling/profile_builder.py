"""Del registro de una fuente externa al borrador de perfil que ve el usuario.

Equivale a `construir_perfil` del spike 1: cada fuente resuelve su propio formato y
llega hasta acá como `CompanyRecord`; de acá en adelante la lógica es idéntica sin
importar de dónde vino el dato.
"""

import logging

from app.application.services.company_profiling import (
    activity_catalog,
    activity_dictionary,
    sector_classifier,
)
from app.domain.entities.company_profile import CompanyProfileDraft, CompanyRecord
from app.shared.regions import to_front_region_name

logger = logging.getLogger(__name__)


def build_profile_draft(record: CompanyRecord) -> CompanyProfileDraft:
    codes = list(dict.fromkeys(activity.code for activity in record.activities))
    descriptions = {activity.code: activity.description for activity in record.activities}

    sectors = activity_dictionary.curated_sectors(codes)
    for code in codes:
        if activity_dictionary.entry_for(code) is not None:
            continue
        # La glosa oficial va primero: la de la fuente puede venir vacía (SRE) o
        # con la codificación rota (Web Empresario).
        description = activity_catalog.official_description(code) or descriptions[code]
        for sector in sector_classifier.sectors_from_description(description):
            if sector not in sectors:
                sectors.append(sector)

    keywords = activity_dictionary.keywords_for(codes)

    regions: list[str] = []
    for raw_region in record.raw_regions:
        region = to_front_region_name(raw_region)
        if region is None:
            logger.info("Región no reconocida desde %s: %r", record.source, raw_region)
        elif region not in regions:
            regions.append(region)

    return CompanyProfileDraft(
        source=record.source,
        rut=record.rut,
        legal_name=record.legal_name,
        is_active=record.is_active,
        regions=regions,
        sectors=sectors,
        keywords=keywords,
        notices=_notices(record, codes, sectors, keywords, regions),
    )


def _notices(
    record: CompanyRecord,
    codes: list[int],
    sectors: list[str],
    keywords: list[str],
    regions: list[str],
) -> list[str]:
    notices: list[str] = []

    if record.is_active is False:
        notices.append("El SII registra término de giro para esta empresa.")

    if not regions:
        notices.append(
            "La fuente consultada no informa la dirección de tu empresa: "
            "selecciona tus regiones a mano."
        )

    if not codes:
        notices.append(
            "La fuente no informa actividades económicas para esta empresa, "
            "así que no hay rubros ni palabras clave que sugerir."
        )
        return notices

    if not sectors:
        notices.append(
            "No pudimos deducir tus rubros desde tus actividades económicas: "
            "selecciónalos a mano."
        )
    elif len(sectors) > 2:
        notices.append(
            f"Tus actividades económicas abarcan {len(sectors)} rubros distintos: "
            "desmarca los que no correspondan."
        )

    if not keywords:
        notices.append(
            "Todavía no tenemos palabras clave sugeridas para tus actividades "
            "económicas: agrégalas a mano."
        )
    elif activity_dictionary.codes_without_keywords(codes):
        notices.append(
            "Algunas de tus actividades económicas aún no tienen palabras clave "
            "sugeridas: revisa si falta alguna."
        )

    return notices
