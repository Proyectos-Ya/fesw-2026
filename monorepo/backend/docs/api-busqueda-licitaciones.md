# Buscador de licitaciones

```
GET /tenders/search
```

Busca en **todo** el catálogo de licitaciones. El dashboard de recomendaciones muestra
solo las 15 que el motor eligió; esto permite que el usuario busque por su cuenta.

Requiere sesión. `apiFetch` ya manda la cookie, así que no hay que configurar nada.

---

## Cómo funciona

**Busca por significado, no por palabras.** Si el usuario escribe *"muebles de cocina"*,
puede aparecer una licitación que dice *"KIT MUEBLE COCINA BLANCO"* y también otra que no
repite ninguna de esas palabras. No es un `LIKE`.

**Los filtros acotan, el texto ordena.** Primero se descartan las licitaciones que no
cumplen los filtros (región, monto, fechas, estado) y después las que quedan se ordenan
por relevancia.

**Si el campo de texto va vacío, ordena por afinidad con la empresa.** O sea: los filtros
acotan y el usuario ve sus recomendaciones dentro de ese subconjunto. Por eso **el botón
buscar debe funcionar aunque no haya texto**.

---

## Parámetros

Todos opcionales. Todos van en la query string.

| Parámetro | Tipo | Ejemplo |
|---|---|---|
| `q` | texto, máx. 200 | `q=muebles de cocina` |
| `regions` | nombre de región | `regions=Metropolitana de Santiago` |
| `status_codes` | estado | `status_codes=publicada` |
| `closing_from` | fecha ISO | `closing_from=2026-09-01T00:00:00` |
| `closing_to` | fecha ISO | `closing_to=2026-09-30T00:00:00` |
| `published_from` | fecha ISO | |
| `published_to` | fecha ISO | |
| `min_amount` | número (CLP) | `min_amount=100000` |
| `max_amount` | número (CLP) | `max_amount=5000000` |
| `limit` | número, 1 a 500 | por defecto **100** |
| `offset` | número | ver *truncado* abajo |

Estados válidos: `publicada`, `cerrada`, `desierta`, `cancelada`, `adjudicada`.

Los rangos de fecha y monto incluyen ambos extremos.

### ⚠️ Regiones y estados van repetidos

```
✅  ?regions=Valparaíso&regions=Maule
❌  ?regions=Valparaíso,Maule      →  error 422
```

En código: `params.append("regions", r)`, **no** `params.set(...)`.

---

## Respuesta

```json
{
  "items": [ ... ],
  "total": 137,
  "is_truncated": true
}
```

| Campo | Qué es |
|---|---|
| `items` | las licitaciones, **ya ordenadas por relevancia** (no reordenar) |
| `total` | cuántas cumplen los filtros — **no** es `items.length` |
| `is_truncated` | `true` si quedaron licitaciones fuera |

Cada licitación trae los mismos campos que ya usas en el dashboard: `code`, `name`,
`description`, `status_code`, `closing_at`, `buyer_name`, `region`,
`available_amount_clp` e `items`.

Las fechas vienen en UTC con `Z` al final, así que `new Date(...)` las convierte sola.
`region` y `available_amount_clp` pueden ser `null`.

---

## Cuatro cosas a tener en cuenta

**1. La paginación la puedes hacer tú.** Por defecto el backend manda 100 resultados y tú
los repartes en 5 páginas de 20: cambiar de página es instantáneo, sin llamar de nuevo a
la API.

Si prefieres que el backend pagine, usa `limit=20&offset=40` y pides página por página.
Funciona, pero **cada petición vuelve a procesar el texto de búsqueda** (~70 ms o más),
así que cada clic tiene latencia. Por eso el valor por defecto trae 100 de una vez.

**2. Muestra `total`, no `items.length`.** Son distintos cuando hay truncado.

**3. Si `is_truncated` es `true`**, algo como *"mostrando 100 de 1.340, afina tus
filtros"*. Si el usuario insiste, repite la búsqueda con `offset=100`.

**4. Cero resultados llega como 200**, con `items: []` y `total: 0`. No es un error: hay
que avisarlo y sugerir sacar algún filtro.

---

## Errores

| Código | Qué pasó | Qué hacer |
|---|---|---|
| 401 | sin sesión | redirigir a login |
| 422 | filtro inválido (rango al revés, monto negativo, región que no existe) | mostrar el `detail`, es texto legible |
| 503 | el buscador no está disponible | avisar, sin bloquear el resto de la app |

`apiFetch` ya lanza `ApiError` con el `status` y el mensaje.

---

## Probarlo

```bash
docker compose up -d
```

Abre `http://localhost:8000/docs`: tiene un formulario con todos los parámetros.

En Postman: **Import → Link → `http://localhost:8000/openapi.json`** arma la colección
sola. Para varias regiones, agrega la fila `regions` dos veces.

> Con pocas licitaciones cargadas el buscador devuelve casi todas y el orden dice poco.
> Para ver el ranking funcionando hace falta el corpus completo.
