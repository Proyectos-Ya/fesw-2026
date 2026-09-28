"""Rubros del producto: el vocabulario cerrado de `Supplier.sectors`.

Copia de `frontend/src/features/company-profile/data/sectors.ts`, que es la lista
que el usuario ve en el wizard. Hay que mantener las dos sincronizadas: un rubro
que exista acá y no allá se guarda igual, pero en el wizard aparece sin marcar.

**Provisionales.** Se definieron a mano para el formulario y no salen de las
categorías de Mercado Público; están pendientes de revisar contra ellas. El
diccionario de actividades y el clasificador de rubro
(`app/application/services/company_profiling/`) dependen de esta lista, y un test
exige que todo rubro que sugieran exista acá.
"""

PRODUCT_SECTORS: tuple[str, ...] = (
    "Obras de Construcción e Infraestructura",
    "Mantención y Reparación",
    "Arquitectura e Ingeniería",
    "Tecnología y Telecomunicaciones",
    "Desarrollo de Software",
    "Consultoría y Asesoría Técnica",
    "Salud y Equipamiento Médico",
    "Educación y Capacitación",
    "Transporte y Logística",
    "Alimentación y Gastronomía",
    "Limpieza y Aseo Industrial",
    "Seguridad y Vigilancia",
    "Medio Ambiente y Sustentabilidad",
    "Energía y Electricidad",
    "Servicios de Imprenta y Diseño",
    "Jardinería y Paisajismo",
    "Equipos e Insumos Industriales",
    "Recursos Humanos",
    "Contabilidad y Auditoría",
)
