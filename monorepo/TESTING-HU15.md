# HU-15 — Cotizaciones de materiales (#227)

Implementación sobre `develop` (`9cd77c0c`). Issue: https://github.com/Proyectos-Ya/fesw-2026/issues/227.

## Uso

1. Iniciar sesión con un usuario que tenga una empresa registrada.
2. Abrir el detalle de una licitación y seleccionar **Generar cotización**.
3. Los materiales se precargan desde los productos de la licitación (descripción o nombre y unidad de medida, cuando exista). Completar la unidad si falta, cantidad y precio unitario; **Agregar material** permite incorporar faltantes. Si no hay productos detallados, se inicia una fila manual.
4. Seleccionar **Guardar cotización**. Volver a abrirla permite consultar y editar los materiales guardados.
5. **Descargar CSV** guarda primero los cambios y descarga el archivo; si falla el guardado no descarga una versión divergente.

Existe una cotización por combinación empresa/licitación. Las cotizaciones guardadas tienen prioridad sobre la precarga y conservan sus cambios. Se usan los productos estructurados disponibles en la ficha, sin inferir materiales de documentos adjuntos. La empresa se obtiene del usuario autenticado; la API no acepta un identificador de empresa enviado por el cliente.

Los criterios 5 y 6 de la issue están duplicados. Se implementó además la descarga solicitada en su descripción, en CSV UTF-8 con BOM, separador punto y coma, identificadores de licitación/empresa, CLP, materiales, subtotales y total, con columna de unidad. Los campos de texto se escapan para evitar fórmulas al abrir el archivo en una hoja de cálculo.

## Cálculos y límites

- Moneda fija: CLP, sin selector. Las cotizaciones antiguas de otra moneda no se convierten ni se sobrescriben automáticamente.
- El total suma los subtotales redondeados a dos decimales (mitades hacia arriba), sin IVA ni recargos automáticos.
- El servidor usa `Decimal`; el navegador usa aritmética entera escalada para evitar errores binarios.
- Entre 1 y 200 materiales; descripción de hasta 500 caracteres. Unidad obligatoria de hasta 40 caracteres, precargada cuando la licitación la informa. No requiere una migración nueva.
- Cantidad positiva, con hasta 9 enteros y 3 decimales. Precio no negativo, con hasta 12 enteros y 2 decimales. El precio cero es válido.
- Se valida tanto en el navegador como en el servidor. El total se calcula, nunca se acepta como entrada.
- Cerrar el panel conserva el borrador durante la visita; los cambios guardados persisten entre visitas.

## API y migración

- `GET /tenders/{tender_id}/quotation`: consulta la cotización de la empresa del usuario.
- `PUT /tenders/{tender_id}/quotation`: crea o reemplaza sus materiales en una transacción.
- Respuestas: 401 sin sesión, 403 sin empresa, 404 sin licitación/cotización, 422 para datos inválidos.
- Migración `a227c0150001`, posterior a `d7f2a9c41b58`: crea `quotation` y `quotation_material`. No modifica las tablas existentes.
- Restricción única por empresa/licitación y bloqueo de la fila de empresa al guardar para serializar creaciones simultáneas.

Antes de levantar la API, aplicar `alembic upgrade head` desde el backend con el entorno configurado. El compose del proyecto ya ejecuta ese paso al arrancar. Esta implementación no resetea bases ni modifica datos existentes.

## Verificación reproducible

Backend, después de instalar `requirements-test.txt`:

```sh
pytest -q -m "not integration and not network"
alembic heads
```

Frontend:

```sh
pnpm install --frozen-lockfile
pnpm test
pnpm exec tsc --noEmit
pnpm exec playwright install chromium
pnpm test:e2e:quotation
```

La prueba de navegador usa el componente real con una API simulada: verifica validación, guardado, recuperación tras recargar, edición y contenido del CSV descargado. La persistencia se verifica por separado con sesiones nuevas sobre SQLite y las tablas creadas por la migración de Alembic. La concurrencia y la aplicación real de la migración en PostgreSQL requieren un entorno con PostgreSQL disponible.
