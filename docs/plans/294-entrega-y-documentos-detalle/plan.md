# Plan Técnico: #294, entrega y documentos del detalle de Compra Ágil

**Issue asociada**: Closes #294  
**Estado**: Aprobado el 2026-10-26, en implementación  
**Fecha**: 2026-10-26  
**Tareas**: [task.md](./task.md)

---

## 1. Contexto y objetivo

El detalle de Compra Ágil (`GET /v2/compra-agil/{codigo}`) trae datos que la
ingesta descarta: la dirección y el plazo de entrega, y dos flags de requisitos.
HU-30 (#312) dejó en la ficha la sección "Entrega y requisitos" esperando la
dirección y el plazo. La recomendación de subir bases, en la pantalla de
postulación, no nombra los documentos oficiales aunque la pantalla ya los tiene.

Esta issue cubre los criterios 1, 2, 4 y 5:

1. La ingesta guarda la dirección, el plazo, los nombres de los documentos y
   los dos flags.
2. La ficha muestra la dirección y el plazo.
4. Si la Compra Ágil tiene documentos y el usuario no subió ninguno, la
   recomendación de subir bases los nombra.
5. Con detalles reales se verifica que el detalle trae
   `resumen.total_ofertas_recibidas` (§2).

**Fuera de alcance:**

- El criterio 3 (el análisis de factibilidad y la redacción los reciben). Pasa
  a una issue nueva.
- Llenar las licitaciones existentes. Se completan cuando la ingesta vuelve a
  bajar su detalle, normalmente al cambiar de estado.
- Mostrar los flags en la ficha. Se guardan, pero el criterio 2 no los pide.

## 2. Lo que ya existe

- **Forma del dato.** La guía oficial de la API (v3.0, mayo de 2026) documenta
  en el detalle `entrega.direccion_entrega` (string),
  `entrega.plazo_entrega_dias` (int|null) en §6.3, y
  `flags.considera_requisitos_medioambientales` y
  `flags.considera_requisitos_impacto_social_economico` (boolean) en §6.6. El
  listado no los trae, así que solo la ingesta los escribe.
- **Verificación con detalles reales (criterio 5, 2026-10-26).** Tres detalles
  de `GET /v2/compra-agil/{codigo}` (1224953-521-COT26, 557639-3334-COT26 y
  1078886-157-COT26) traen `entrega`, `flags`,
  `resumen.total_ofertas_recibidas` y `documentos` con la forma documentada, y
  `_parse_to_dto` los lee bien. El primero quedó como fixture en
  `tests/fixtures/mp_detalle_compra_agil.json`
  (`tests/unit/infrastructure/test_detalle_real.py`).
- **Cierres por llamado en el detalle.** Ahí vienen dentro de `convocatoria`, no
  en `fechas` como en el listado, y `leer_llamado` solo miraba `fechas`: desde
  el detalle quedaban en `None`. Se corrige en esta rama (decisión 6).
- **Nombres de los documentos.** Ya se guardan en `tender_attachment` desde el
  detalle (`_parse_to_dto` → `_sincronizar_anexos`) y desde el listado (plan
  233, decisión 1). Esa parte del criterio 1 está cumplida y no lleva columna
  nueva.
- **Lista oficial en la postulación.** `ProposalView.tsx` ya carga la lista
  oficial con `useTenderAttachments`, con `name` y `file` por anexo.

## 3. Cambios en BD

Una migración sobre `tender`, encadenada tras `2868884ba7ee`. Cuatro columnas
nullable y sin default, por la misma razón que las de HU-30: no reescriben la
tabla y la versión anterior del backend las ignora.

| Columna | Tipo | Origen |
| --- | --- | --- |
| `delivery_address` | text | `entrega.direccion_entrega`, sin espacios al borde. Vacía es `NULL` |
| `delivery_term_days` | integer | `entrega.plazo_entrega_dias`, entero mayor o igual a 0 |
| `requires_environmental_criteria` | boolean | `flags.considera_requisitos_medioambientales` |
| `requires_social_impact_criteria` | boolean | `flags.considera_requisitos_impacto_social_economico` |

`NULL` significa que la fuente no lo informó. En los flags, `false` es un dato
real y no es lo mismo que `NULL`.

## 4. Backend

- **Parser** en `app/infrastructure/services/tenders/entrega.py`, al lado de
  `llamados.py` y `ofertas.py`. `leer_entrega(detail)` devuelve `EntregaMp`
  (`direccion`, `plazo_dias`) y `leer_requisitos(detail)` devuelve
  `RequisitosMp` (`medioambientales`, `impacto_social`). Ante cualquier forma
  rara devuelven `None` en el campo: un bool en el plazo, un negativo, texto, o
  `entrega` y `flags` que no son objetos.
- **DTO.** Cuatro campos en `TenderIngestaDTO` con alias en español, que
  `_parse_to_dto` llena con los parsers.
- **Caso de uso.** El alta guarda los cuatro campos. En una actualización,
  `_entrega_cambio` y `_aplicar_entrega` siguen la regla de `_llamado_cambio` y
  `_aplicar_llamado`: un `None` no cuenta como cambio ni borra lo guardado. Si
  solo cambian estos datos, se escribe solo en SQL, sin mover `updated_at` ni
  tocar Qdrant, porque mover `updated_at` regeneraría el análisis de Gemini.
- **Entidad y API.** `Tender` expone los cuatro campos, y `TenderRepository`
  los copia en sus dos conversiones. El `GET` de la ficha los devuelve sin
  cambios en el router.

## 5. Frontend

- **Ficha.** En "Entrega y requisitos", antes de los cierres por llamado, se
  muestran "Dirección de entrega" y "Plazo de entrega". Sin dato, los textos
  son los que pide HU-22 (#314): "Dirección de entrega no disponible" y "Plazo
  de entrega no disponible". El plazo se escribe "1 día" o "N días", 0
  incluido.
- **Postulación.** `nombrarDocumentos` arma la lista ("A y B", "A, B y C"; con
  más de 5, "A, B, C, D, E y N más"). `basesNotice` recibe los nombres oficiales
  sin archivo. Si el análisis se hizo solo con la ficha y no hay subidas
  nuevas, la frase nombra esos documentos, con prioridad sobre el texto de
  `mentions_attachments`. El aviso previo al análisis también los nombra.
  Sin documentos oficiales pendientes, los dos textos quedan como hoy.

## 6. Plan de pruebas

El detalle, tarea por tarea y en orden TDD, está en [task.md](./task.md).

```bash
# Backend, desde monorepo/backend, con `supabase start`
pytest
python -m scripts.migraciones   # una sola cabeza

# Frontend, desde monorepo/frontend
pnpm run test && pnpm run lint && pnpm run build
```

Resultado de la tarea 6.1 (2026-10-26, Supabase local, sin `.env`):

- Backend: 3690 pruebas pasan y 7 fallan. Son las mismas 7 que fallan en
  `origin/develop`: 6 llaman a Gemini real y
  `test_un_admin_pide_la_url_y_la_lista_refleja_el_cupo` responde 503 sin
  storage. `python -m scripts.migraciones` da una sola cabeza (`e7123e26c0be`)
  y Ruff no marca nada en los archivos de la rama.
- Frontend: 1142 pruebas pasan, `pnpm run lint` da 0 errores (26 advertencias
  en archivos que esta issue no toca) y `pnpm run build` compila.

### Prueba manual

Resultado: _pendiente_ (tarea 6.2).

## 7. Despliegue y rollback

- La migración es compatible hacia atrás, y va en el mismo PR. Antes de abrirlo
  y antes de mergear se corre `python -m scripts.migraciones`.
- Desplegar en dev test aplica la migración sobre la base de producción, porque
  comparten base.
- **Rollback.** Revertir el PR sin el commit de la migración. El `downgrade`
  borra las cuatro columnas, y se corre solo después de revertir el código.

### Riesgos

1. **Un detalle puede no traer los campos.** Los tres detalles reales los
   traen, pero si alguno no, quedan en `NULL` y la ficha dice "no disponible".
2. **Las licitaciones existentes empiezan vacías.** Se completan cuando la
   ingesta vuelve a bajar su detalle.

## 8. Decisiones (2026-10-26)

1. **Criterios 1, 2, 4 y 5.** El 3 pasa a una issue nueva, y el PR usa
   `Closes #294`.
2. **Textos de HU-22** para la dirección y el plazo sin dato.
3. **Un cambio que solo toca la entrega o los flags se guarda solo en SQL**,
   sin `updated_at` ni Qdrant.
4. **Sin llenado inicial** de las licitaciones existentes.
5. **Los nombres de los documentos no llevan columna**: ya están en
   `tender_attachment`.
6. **`leer_llamado` busca los cierres en `fechas` y, si no hay uno legible, en
   `convocatoria`.** Así el listado y el detalle se leen con la misma función,
   y el listado manda si los trae en los dos lados.
