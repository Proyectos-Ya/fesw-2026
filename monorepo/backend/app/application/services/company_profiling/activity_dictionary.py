"""Diccionario curado: código de actividad económica → rubros y palabras clave.

Portado de `spikes/spike-1/poc/perfilamiento/diccionario.py` (rama
`155-spike-1-onboarding-y-validacion-documental`, commit `2ed42d7`).

El problema que resuelve
------------------------
La glosa del SII está en lenguaje tributario ("programación informática") y las
licitaciones en lenguaje de compra ("desarrollo de plataforma web"). Como el
matching de palabras clave es literal, sugerir la glosa no engancha con nada. Por
eso las palabras clave se escriben a mano, código por código, y **solo** salen de
acá: un código sin curar no aporta palabras clave (el spike quitó a propósito el
respaldo con la glosa oficial).

Rubros y palabras clave se **unen** entre actividades: lo que engancha con una
licitación es la capacidad puntual ("pintura", "servicio técnico"), no lo que las
actividades tengan en común.

Del diccionario original se omite el eje `objeto` (dominio común), que el producto
todavía no usa.

Procedencia y estado
--------------------
* 433000, 479100 y 952200: verificados contra un payload real.
* El resto: escritos leyendo la glosa oficial, sin verificar con empresas reales.
* 53 códigos agregados el 2026-10-27 desde los 15 rubros con más gasto público. Las
  palabras clave salen del vocabulario de productos de ChileCompra
  (`Listado_rubros_ONU.xlsx`) y no se verificaron contra payloads reales.
* Los rubros son los de Mercado Público (`app/shared/sectors.py`). Se reapuntaron
  desde los provisionales con la tabla de correspondencia del plan 311 (§2.1).
  Dos códigos se apartan de la tabla porque su glosa es más precisa: 464907
  (farmacéuticos) va a "Medicamentos y productos farmacéuticos" y 952200
  (reparación doméstica) a "Servicios de cuidado personal y domésticos".
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ActivityEntry:
    # Rubros del producto; deben existir en `PRODUCT_SECTORS`. Vacío significa que
    # la actividad no tiene lugar en compras públicas.
    sectors: tuple[str, ...] = ()
    # Cómo lo pediría un comprador público.
    keywords: tuple[str, ...] = ()


ACTIVITY_DICTIONARY: dict[int, ActivityEntry] = {
    # --- Verificados contra un payload real ---
    433000: ActivityEntry(  # Terminación y acabado de edificios
        sectors=("Servicios de construcción y mantenimiento",),
        keywords=(
            "pintura",
            "revestimiento",
            "habilitación de oficinas",
            "terminaciones",
            "obras menores",
        ),
    ),
    479100: ActivityEntry(  # Venta al por menor por correo, internet y teléfono
        sectors=("Artículos de fabricación y producción",),
        keywords=("venta en línea", "distribución", "despacho a domicilio", "suministro"),
    ),
    952200: ActivityEntry(  # Reparación de aparatos de uso doméstico y de jardinería
        sectors=("Servicios de cuidado personal y domésticos",),
        keywords=(
            "reparación de electrodomésticos",
            "mantención de equipos",
            "servicio técnico",
        ),
    ),
    # --- Provisionales, sin verificar contra empresas reales ---
    620100: ActivityEntry(  # Programación informática
        sectors=("Tecnologías de la información, telecomunicaciones y radiodifusión",),
        keywords=(
            "desarrollo de software",
            "plataforma web",
            "mantención de sistemas",
            "aplicación móvil",
        ),
    ),
    620200: ActivityEntry(  # Consultoría informática
        sectors=(
            "Tecnologías de la información, telecomunicaciones y radiodifusión",
            "Servicios profesionales, administrativos y consultorías de gestión empresarial",
        ),
        keywords=("consultoría informática", "soporte TI", "mesa de ayuda"),
    ),
    702000: ActivityEntry(  # Consultoría de gestión
        sectors=("Servicios profesionales, administrativos y consultorías de gestión empresarial",),
        keywords=("consultoría de gestión", "asesoría organizacional", "estudios"),
    ),
    812100: ActivityEntry(  # Limpieza general de edificios
        sectors=("Servicios de limpieza industrial",),
        keywords=("servicio de aseo", "limpieza de dependencias", "sanitización"),
    ),
    492300: ActivityEntry(  # Transporte de carga por carretera
        sectors=("Servicios de transporte, almacenaje y correo",),
        keywords=("transporte de carga", "flete", "distribución logística"),
    ),
    801001: ActivityEntry(  # Servicios de seguridad privada prestados por empresas
        sectors=("Servicios de defensa nacional, orden público y seguridad",),
        keywords=(
            "guardias de seguridad",
            "vigilancia privada",
            "rondas de seguridad",
            "control de acceso",
        ),
    ),
    813000: ActivityEntry(  # Paisajismo, servicios de jardinería y conexos
        sectors=("Servicios agrícolas, pesqueros, forestales y relacionados con la fauna",),
        keywords=("mantención de áreas verdes", "paisajismo", "poda", "jardinería"),
    ),
    561000: ActivityEntry(  # Restaurantes y servicio móvil de comidas
        sectors=("Servicios de Viajes, alimentación, alojamiento y entretenimiento",),
        keywords=("servicio de alimentación", "catering", "banquetería", "comida preparada"),
    ),
    692000: ActivityEntry(  # Contabilidad, teneduría de libros y auditoría
        sectors=("Servicios financieros, pensiones y seguros",),
        keywords=(
            "servicios contables",
            "auditoría",
            "asesoría tributaria",
            "teneduría de libros",
        ),
    ),
    781000: ActivityEntry(  # Agencias de empleo
        sectors=("Servicios profesionales, administrativos y consultorías de gestión empresarial",),
        keywords=(
            "reclutamiento",
            "selección de personal",
            "búsqueda de talento",
            "agencia de empleo",
        ),
    ),
    464907: ActivityEntry(  # Venta al por mayor de productos farmacéuticos
        sectors=("Medicamentos y productos farmacéuticos",),
        keywords=(
            "suministro de medicamentos",
            "insumos farmacéuticos",
            "distribución médica",
        ),
    ),
    181200: ActivityEntry(  # Servicios relacionados con la impresión
        sectors=("Servicios editoriales, de diseño, publicidad, gráficos y artistas",),
        keywords=(
            "servicios de impresión",
            "imprenta",
            "diseño gráfico",
            "material publicitario",
        ),
    ),
    351030: ActivityEntry(  # Distribución de energía eléctrica
        sectors=("Maquinaria para generación y distribución de energía",),
        keywords=(
            "suministro eléctrico",
            "distribución de energía",
            "instalaciones eléctricas",
        ),
    ),
    390000: ActivityEntry(  # Descontaminación y gestión de desechos
        sectors=("Servicios medioambientales",),
        keywords=(
            "gestión de residuos",
            "descontaminación",
            "manejo ambiental",
            "disposición de desechos",
        ),
    ),
    855000: ActivityEntry(  # Apoyo a la enseñanza
        sectors=("Educación, formación, entrenamiento y capacitación",),
        keywords=(
            "capacitación",
            "cursos de formación",
            "apoyo educativo",
            "material didáctico",
        ),
    ),
    # --- Obras civiles
    421000: ActivityEntry(  # Construcción de carreteras y líneas de ferrocarril
        sectors=("Servicios de construcción y mantenimiento",),
        keywords=(
            "pavimentación de caminos",
            "obras viales",
            "obras civiles",
            "construcción de obras civiles",
        ),
    ),
    422000: ActivityEntry(  # Construcción de proyectos de servicio público
        sectors=("Servicios de construcción y mantenimiento",),
        keywords=("obras civiles", "infraestructura", "excavación", "tendido de cables"),
    ),
    429000: ActivityEntry(  # Construcción de otras obras de ingeniería civil
        sectors=("Servicios de construcción y mantenimiento",),
        keywords=(
            "obras civiles",
            "infraestructura",
            "trabajo en hormigón",
            "obras de ingeniería",
        ),
    ),
    431100: ActivityEntry(  # Demolición
        sectors=("Servicios de construcción y mantenimiento",),
        keywords=("demolición", "desmonte de terrenos", "excavación"),
    ),
    431200: ActivityEntry(  # Preparación del terreno
        sectors=("Servicios de construcción y mantenimiento",),
        keywords=(
            "preparación de terreno",
            "nivelado de terrenos",
            "desmonte de terrenos",
            "excavación",
        ),
    ),
    432100: ActivityEntry(  # Instalaciones eléctricas
        sectors=("Servicios de construcción y mantenimiento",),
        keywords=(
            "instalaciones eléctricas",
            "sistemas de energía eléctrica",
            "tendido de cables",
            "controles electrónicos",
        ),
    ),
    432200: ActivityEntry(  # Instalaciones de gasfitería, calefacción y aire acondicionado
        sectors=("Servicios de construcción y mantenimiento",),
        keywords=(
            "gasfitería",
            "sistemas de calefacción",
            "aire acondicionado",
            "mantención de calderas",
        ),
    ),
    432900: ActivityEntry(  # Otras instalaciones para obras de construcción
        sectors=("Servicios de construcción y mantenimiento",),
        keywords=(
            "andamios",
            "mantención de ascensores",
            "servicios de cerrajería",
            "apoyo a la construcción",
        ),
    ),
    # --- Construcción residencial
    410010: ActivityEntry(  # Construcción de edificios para uso residencial
        sectors=("Servicios de construcción y mantenimiento",),
        keywords=(
            "construcción de casas",
            "construcción de edificios",
            "construcción residencial",
            "departamentos",
        ),
    ),
    410020: ActivityEntry(  # Construcción de edificios para uso no residencial
        sectors=("Servicios de construcción y mantenimiento",),
        keywords=(
            "construcción de edificios",
            "construcción comercial",
            "construcción de locales",
            "plantas industriales",
        ),
    ),
    439000: ActivityEntry(  # Otras actividades especializadas de construcción
        sectors=("Servicios de construcción y mantenimiento",),
        keywords=(
            "albañilería",
            "carpintería",
            "trabajo en hormigón",
            "restauración de edificios",
        ),
    ),
    # --- Especialidades médicas
    861020: ActivityEntry(  # Actividades de hospitales y clínicas privadas
        sectors=("Salud, servicios sanitarios y alimentación",),
        keywords=(
            "servicios hospitalarios",
            "atención de urgencia",
            "servicios clínicos",
            "consulta médica",
        ),
    ),
    862021: ActivityEntry(  # Centros médicos privados (establecimientos de atención ambulatoria)
        sectors=("Salud, servicios sanitarios y alimentación",),
        keywords=(
            "consulta médica",
            "atención ambulatoria",
            "atención primaria",
            "médicos a domicilio",
        ),
    ),
    862022: ActivityEntry(  # Centros de atención odontológica privados (establecimientos de atención ambulatoria)
        sectors=("Salud, servicios sanitarios y alimentación",),
        keywords=("servicios dentales", "atención odontológica", "ortodoncia", "cirugía bucal"),
    ),
    862031: ActivityEntry(  # Servicios de médicos prestados de forma independiente
        sectors=("Salud, servicios sanitarios y alimentación",),
        keywords=(
            "especialidades médicas",
            "servicios de cardiología",
            "servicios oftalmológicos",
            "servicios psiquiátricos",
            "servicios pediátricos",
        ),
    ),
    266000: ActivityEntry(  # Fabricación de equipo de irradiación y equipo electrónico de uso médico y terapéutico
        sectors=("Equipamiento y suministros médicos",),
        keywords=(
            "equipo radiográfico",
            "tomografía computarizada",
            "resonancia magnética",
            "ultrasonido médico",
            "radioterapia",
            "electrocardiógrafo",
        ),
    ),
    325009: ActivityEntry(  # Fabricación de instrumentos y materiales médicos, oftalmológicos y odontológicos n.c.p.
        sectors=("Equipamiento y suministros médicos",),
        keywords=(
            "instrumental quirúrgico",
            "insumos odontológicos",
            "prótesis",
            "artículos ortopédicos",
            "anteojos",
        ),
    ),
    # --- Farmacia
    477201: ActivityEntry(  # Venta al por menor de productos farmacéuticos y medicinales en comercios especializados
        sectors=("Medicamentos y productos farmacéuticos",),
        keywords=("farmacia", "recetario magistral", "medicamentos", "productos farmacéuticos"),
    ),
    477202: ActivityEntry(  # Venta al por menor de artículos ortopédicos en comercios especializados
        sectors=("Equipamiento y suministros médicos",),
        keywords=("artículos ortopédicos", "muletas", "órtesis", "prótesis", "ayudas técnicas"),
    ),
    210000: ActivityEntry(  # Fabricación de productos farmacéuticos, sustancias químicas medicinales y productos botánicos
        sectors=("Medicamentos y productos farmacéuticos",),
        keywords=(
            "medicamentos",
            "antibióticos",
            "analgésicos",
            "antiinflamatorios",
            "homeopatía",
        ),
    ),
    # --- Alimentación, comedor y banquetes
    562100: ActivityEntry(  # Suministro de comidas por encargo (servicios de banquetería)
        sectors=("Servicios de Viajes, alimentación, alojamiento y entretenimiento",),
        keywords=("banquetería", "servicio de banquetes", "catering", "servicio de comedor"),
    ),
    562900: ActivityEntry(  # Suministro industrial de comidas por encargo; concesión de servicios de alimentación
        sectors=("Servicios de Viajes, alimentación, alojamiento y entretenimiento",),
        keywords=(
            "concesión de casino",
            "servicio de alimentación",
            "servicio de comedor",
            "platos combinados",
        ),
    ),
    107500: ActivityEntry(  # Elaboración de comidas y platos preparados envasados, rotulados y con información nutricional
        sectors=("Alimentos, bebidas y tabaco",),
        keywords=(
            "platos combinados",
            "comidas preparadas",
            "alimentos preparados",
            "ensaladas preparadas",
        ),
    ),
    107100: ActivityEntry(  # Elaboración de productos de panadería y pastelería
        sectors=("Alimentos, bebidas y tabaco",),
        keywords=("pan fresco", "pastelería", "galletas", "empanadas", "repostería"),
    ),
    # --- Leche y mantequilla
    105000: ActivityEntry(  # Elaboración de productos lácteos
        sectors=("Alimentos, bebidas y tabaco",),
        keywords=("leche", "mantequilla", "queso", "productos lácteos"),
    ),
    463019: ActivityEntry(  # Venta al por mayor de huevos, lácteos, abarrotes y de otros alimentos n.c.p.
        sectors=("Alimentos, bebidas y tabaco",),
        keywords=(
            "huevos",
            "productos lácteos",
            "abarrotes",
            "cereales",
            "legumbres",
            "aceites comestibles",
        ),
    ),
    # --- Desechos
    381100: ActivityEntry(  # Recogida de desechos no peligrosos
        sectors=("Servicios de limpieza industrial", "Servicios medioambientales",),
        keywords=(
            "recolección de basura",
            "limpieza de calles",
            "retiro de residuos",
            "vertedero",
        ),
    ),
    381200: ActivityEntry(  # Recogida de desechos peligrosos
        sectors=("Servicios de limpieza industrial", "Servicios medioambientales",),
        keywords=(
            "residuos peligrosos",
            "residuos médicos",
            "residuos ácidos",
            "retiro de residuos",
        ),
    ),
    382100: ActivityEntry(  # Tratamiento y eliminación de desechos no peligrosos
        sectors=("Servicios de limpieza industrial", "Servicios medioambientales",),
        keywords=(
            "eliminación de residuos",
            "vertedero",
            "tratamiento de aguas servidas",
            "eliminación de lodos",
        ),
    ),
    382200: ActivityEntry(  # Tratamiento y eliminación de desechos peligrosos
        sectors=("Servicios de limpieza industrial", "Servicios medioambientales",),
        keywords=(
            "residuos peligrosos",
            "descontaminación de materiales peligrosos",
            "residuos médicos",
            "vertidos tóxicos",
        ),
    ),
    383009: ActivityEntry(  # Recuperación y reciclamiento de otros desperdicios y desechos n.c.p.
        sectors=("Servicios medioambientales", "Servicios de limpieza industrial",),
        keywords=(
            "reciclaje",
            "desechos plásticos",
            "papel usado",
            "residuos de vidrio",
            "chatarra",
        ),
    ),
    # --- Limpieza
    812909: ActivityEntry(  # Otras actividades de limpieza de edificios e instalaciones industriales n.c.p.
        sectors=("Servicios de limpieza industrial",),
        keywords=(
            "limpieza de ventanas",
            "limpieza de alfombras",
            "limpieza de conductos de aire",
            "limpieza de vehículos",
        ),
    ),
    812901: ActivityEntry(  # Desratización, desinfección y exterminio de plagas no agrícolas
        sectors=("Servicios de limpieza industrial",),
        keywords=(
            "desratización",
            "control de roedores",
            "fumigación",
            "control de plagas",
            "desinfección",
        ),
    ),
    960100: ActivityEntry(  # Lavado y limpieza, incluida la limpieza en seco, de productos textiles y de piel
        sectors=("Servicios de cuidado personal y domésticos",),
        keywords=(
            "servicio de lavandería",
            "lavado de ropa",
            "limpieza en seco",
            "lavandería industrial",
        ),
    ),
    # --- Personal temporal y contratación
    782000: ActivityEntry(  # Actividades de agencias de empleo temporal (incluye empresas de servicios transitorios)
        sectors=("Servicios profesionales, administrativos y consultorías de gestión empresarial",),
        keywords=(
            "personal temporal",
            "personal administrativo temporal",
            "mano de obra temporal",
            "choferes temporales",
            "personal técnico temporal",
        ),
    ),
    783000: ActivityEntry(  # Otras actividades de dotación de recursos humanos
        sectors=("Servicios profesionales, administrativos y consultorías de gestión empresarial",),
        keywords=(
            "contratación de personal",
            "dotación de personal",
            "personal técnico",
            "personal médico",
            "comprobación de antecedentes",
        ),
    ),
    # --- Transporte de pasajeros
    492120: ActivityEntry(  # Transporte urbano y suburbano de pasajeros vía locomoción colectiva
        sectors=("Servicios de transporte, almacenaje y correo",),
        keywords=(
            "transporte de pasajeros",
            "servicio de buses",
            "recorridos fijos",
            "transporte colectivo",
        ),
    ),
    492190: ActivityEntry(  # Otras actividades de transporte urbano y suburbano de pasajeros por vía terrestre n.c.p.
        sectors=("Servicios de transporte, almacenaje y correo",),
        keywords=(
            "transporte de pasajeros",
            "buses contratados",
            "servicio de buses",
            "arriendo de vehículos",
        ),
    ),
    492250: ActivityEntry(  # Transporte de pasajeros en buses interurbanos
        sectors=("Servicios de transporte, almacenaje y correo",),
        keywords=(
            "buses interurbanos",
            "transporte interurbano",
            "transporte de pasajeros",
            "servicio de buses",
        ),
    ),
    492290: ActivityEntry(  # Otras actividades de transporte de pasajeros por vía terrestre n.c.p.
        sectors=("Servicios de transporte, almacenaje y correo",),
        keywords=(
            "buses contratados",
            "transporte de pasajeros",
            "arriendo de vehículos",
            "traslado de personal",
        ),
    ),
    492230: ActivityEntry(  # Servicios de transporte de pasajeros en taxis libres y radiotaxis
        sectors=("Servicios de transporte, almacenaje y correo",),
        keywords=("servicio de taxi", "taxis", "radiotaxi", "traslado de pasajeros"),
    ),
    # --- Consultorías al Estado
    711002: ActivityEntry(  # Empresas de servicios de ingeniería y actividades conexas de consultoría técnica
        sectors=(
            "Servicios basados en ingeniería, ciencias sociales y tecnología de la información",
        ),
        keywords=(
            "ingeniería civil",
            "ingeniería estructural",
            "ingeniería eléctrica",
            "estudios de ingeniería",
            "consultoría técnica",
        ),
    ),
    711003: ActivityEntry(  # Servicios profesionales de ingeniería y actividades conexas de consultoría técnica
        sectors=(
            "Servicios basados en ingeniería, ciencias sociales y tecnología de la información",
        ),
        keywords=(
            "ingeniería mecánica",
            "ingeniería civil",
            "ingeniería eléctrica",
            "ingeniería de carreteras",
            "dibujo técnico",
        ),
    ),
    722000: ActivityEntry(  # Investigaciones y desarrollo experimental en el campo de las ciencias sociales y las humanidades
        sectors=(
            "Organizaciones y consultorías políticas, demográficas, económicas, sociales y de administración pública",
        ),
        keywords=(
            "desarrollo social",
            "política social",
            "planificación social",
            "bienestar social",
            "desarrollo comunitario",
        ),
    ),
    732000: ActivityEntry(  # Estudios de mercado y encuestas de opinión pública
        sectors=("Servicios profesionales, administrativos y consultorías de gestión empresarial",),
        keywords=(
            "estudios de mercado",
            "encuestas en terreno",
            "encuestas telefónicas",
            "focus group",
            "análisis de mercado",
        ),
    ),
    691001: ActivityEntry(  # Servicios de asesoramiento y representación jurídica
        sectors=("Servicios profesionales, administrativos y consultorías de gestión empresarial",),
        keywords=(
            "asesoría jurídica",
            "derecho laboral",
            "derecho civil",
            "derecho comercial",
            "derecho penal",
            "derecho de familia",
        ),
    ),
    # --- Seguridad
    801003: ActivityEntry(  # Servicios de seguridad privada prestados por independientes
        sectors=("Servicios de defensa nacional, orden público y seguridad",),
        keywords=(
            "servicios de vigilancia",
            "guardias de seguridad",
            "seguridad personal",
            "guardaespaldas",
        ),
    ),
    802000: ActivityEntry(  # Actividades de servicios de sistemas de seguridad (incluye servicios de cerrajería)
        sectors=("Servicios de defensa nacional, orden público y seguridad",),
        keywords=(
            "sistemas de seguridad",
            "mantención de alarmas",
            "cámaras de seguridad",
            "servicios de cerrajería",
            "alarmas contra incendios",
        ),
    ),
    # --- Parques y jardines
    13000: ActivityEntry(  # Cultivo de plantas vivas incluida la producción en viveros (excepto viveros forestales)
        sectors=("Servicios agrícolas, pesqueros, forestales y relacionados con la fauna",),
        keywords=("plantas ornamentales", "árboles ornamentales", "plantas de flores", "vivero"),
    ),
    21002: ActivityEntry(  # Silvicultura y otras actividades forestales (excepto explotación de viveros forestales)
        sectors=("Servicios agrícolas, pesqueros, forestales y relacionados con la fauna",),
        keywords=(
            "silvicultura",
            "administración forestal",
            "repoblación forestal",
            "control de plagas forestales",
        ),
    ),
    24001: ActivityEntry(  # Servicios de forestación a cambio de una retribución o por contrata
        sectors=("Servicios agrícolas, pesqueros, forestales y relacionados con la fauna",),
        keywords=(
            "forestación",
            "repoblación forestal",
            "cosecha forestal",
            "conservación forestal",
        ),
    ),
    24003: ActivityEntry(  # Servicios de extinción y prevención de incendios forestales
        sectors=(
            "Servicios agrícolas, pesqueros, forestales y relacionados con la fauna",
            "Servicios de defensa nacional, orden público y seguridad",
        ),
        keywords=(
            "brigadas contra incendios forestales",
            "prevención de incendios forestales",
            "prevención de incendios",
            "combate de incendios",
        ),
    ),
    773002: ActivityEntry(  # Alquiler de maquinaria y equipo agropecuario, forestal, de construcción e ing. civil, sin operarios
        sectors=(
            "Maquinaria para construcción y edificación",
            "Maquinaria para agricultura, pesca y silvicultura",
        ),
        keywords=(
            "arriendo de maquinaria",
            "maquinaria pesada",
            "retroexcavadora",
            "excavadora",
            "maquinaria agrícola",
        ),
    ),
    # --- Fuera de alcance: existe, pero no aparece en compras públicas ---
    970000: ActivityEntry(),  # Hogares como empleadores de personal doméstico
}


def entry_for(code: int) -> ActivityEntry | None:
    return ACTIVITY_DICTIONARY.get(code)


def is_out_of_scope(code: int) -> bool:
    entry = entry_for(code)
    return entry is not None and not entry.sectors


def _union(codes: list[int], field: str) -> list[str]:
    """Unión conservando el orden de aparición y sin repetir."""
    result: list[str] = []
    for code in codes:
        entry = entry_for(code)
        if entry is None:
            continue
        for value in getattr(entry, field):
            if value not in result:
                result.append(value)
    return result


def curated_sectors(codes: list[int]) -> list[str]:
    return _union(codes, "sectors")


def keywords_for(codes: list[int]) -> list[str]:
    return _union(codes, "keywords")


def codes_without_keywords(codes: list[int]) -> list[int]:
    """Códigos que no aportan palabras clave, sin contar los fuera de alcance."""
    return [
        code for code in codes if not keywords_for([code]) and not is_out_of_scope(code)
    ]
