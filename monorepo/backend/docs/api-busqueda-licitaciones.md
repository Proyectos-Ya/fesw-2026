# Buscador de licitaciones — guía para el frontend

Endpoint de la HdU 07. Permite buscar en **todo** el catálogo, a diferencia del dashboard
de recomendaciones que solo muestra las 15 que el motor eligió.

```
GET /tenders/search
```

Requiere sesión. `apiFetch` ya manda la cookie (`credentials: "include"`), así que no hay
que hacer nada especial.

---

## Nota sobre ubicación

**El campo `province` ya no existe** — ninguna de las dos APIs de Mercado Público lo
entrega, así que siempre llegaba `null`. La granularidad geográfica llega hasta **región**.

Ya está quitado del frontend (tipo, tarjeta y vista de detalle), así que no tienes que
hacer nada. Solo tenlo presente al filtrar: `regions` es el único filtro geográfico.

---

## Tipos

```typescript
// src/features/matches/tenderTypes.ts

export interface TenderSearchResult {
  items: Tender[];
  /** Cuántas licitaciones cumplen los filtros. NO es items.length */
  total: number;
  /** true si quedaron licitaciones fuera del corte de 500 */
  is_truncated: boolean;
}

export interface TenderSearchParams {
  q?: string;
  regions?: string[];
  statusCodes?: string[];
  closingFrom?: string;   // ISO-8601
  closingTo?: string;
  publishedFrom?: string;
  publishedTo?: string;
  minAmount?: number;
  maxAmount?: number;
  offset?: number;
}
```

## El servicio

```typescript
// src/features/matches/services/tenderService.ts

export function searchTenders(
  params: TenderSearchParams = {},
): Promise<TenderSearchResult> {
  const qs = new URLSearchParams();

  if (params.q?.trim()) qs.set("q", params.q.trim());
  if (params.closingFrom) qs.set("closing_from", params.closingFrom);
  if (params.closingTo) qs.set("closing_to", params.closingTo);
  if (params.publishedFrom) qs.set("published_from", params.publishedFrom);
  if (params.publishedTo) qs.set("published_to", params.publishedTo);
  if (params.minAmount != null) qs.set("min_amount", String(params.minAmount));
  if (params.maxAmount != null) qs.set("max_amount", String(params.maxAmount));
  if (params.offset) qs.set("offset", String(params.offset));

  // OJO: repetidos, no separados por coma
  params.regions?.forEach((r) => qs.append("regions", r));
  params.statusCodes?.forEach((s) => qs.append("status_codes", s));

  return apiFetch<TenderSearchResult>(`/tenders/search?${qs.toString()}`);
}
```

**El detalle que más se equivoca:** `regions` y `status_codes` van **repetidos**.

```
✅  ?regions=Valparaíso&regions=Maule
❌  ?regions=Valparaíso,Maule     → responde 422 "Región desconocida"
```

Por eso se usa `qs.append(...)` y no `qs.set(...)`. `URLSearchParams` codifica los
acentos y espacios solo.

---

## Parámetros

| Parámetro | Notas |
|---|---|
| `q` | Texto libre, máx. **200** caracteres |
| `regions` | **Nombre** de región, no id. Tolera mayúsculas y espacios |
| `status_codes` | `publicada`, `cerrada`, `desierta`, `cancelada`, `adjudicada` |
| `closing_from` / `closing_to` | Rango de cierre, **ambos extremos inclusivos** |
| `published_from` / `published_to` | Rango de publicación, inclusivos |
| `min_amount` / `max_amount` | CLP, ≥ 0, inclusivos |
| `offset` | Solo cuando `is_truncated` es `true` |

Todos opcionales. Sin ninguno devuelve el catálogo ordenado por afinidad con la empresa.

---

## Los dos modos

| `q` | Cómo se ordenan los resultados |
|---|---|
| con texto | por **significado** de lo que escribió el usuario |
| vacío | por afinidad con el perfil de la empresa |

El segundo es a propósito: con filtros pero sin texto, el usuario ve *sus* recomendaciones
acotadas a lo que pidió. **No deshabilites el botón buscar cuando el campo esté vacío.**

Que la búsqueda sea por significado importa para el copy de la UI: buscar
`"muebles de cocina"` puede traer una licitación que dice *"KIT MUEBLE COCINA BLANCO"* y
también otra que no repite ninguna de esas palabras. No es un `LIKE`.

---

## Qué tiene que hacer la UI

**1. Paginar de 20 en 20.** El backend **no pagina**: manda hasta 500 resultados y tú los
repartes. Cambiar de página es instantáneo, sin viaje de red.

**2. Mostrar el total.** Usa `total`, no `items.length`. Son distintos cuando hay
truncado.

**3. Manejar `is_truncated`.** Si viene `true`, algo como *"mostrando 500 de 1.340 —
afina tus filtros"*. Si el usuario insiste, repite la búsqueda con `offset=500`.

**4. Sin resultados no es un error.** Llega **200** con `items: []` y `total: 0`. Hay que
decirlo con claridad y sugerir flexibilizar los filtros.

**5. Conservar criterios al volver.** Guarda los filtros en la URL (query params). Como
ya tienes los 500 resultados en memoria, volver a la sección no necesita repetir la
búsqueda.

---

## Respuesta

```json
{
  "items": [
    {
      "id": "2d58619d-615c-4c33-ae7e-1c720aec6a6f",
      "code": "1057539-228-COT26",
      "name": "ADQUISICIÓN DE KIT MUEBLE DE COCINA",
      "description": "Mueble de cocina color blanco...",
      "status_id": 1,
      "status_code": "publicada",
      "published_at": "2026-08-17T22:04:00Z",
      "closing_at": "2026-08-25T12:00:00Z",
      "last_change_at": "2026-08-17T22:04:00Z",
      "buyer_rut": "60.911.000-7",
      "buyer_name": "UNIVERSIDAD DE SANTIAGO DE CHILE",
      "buyer_unit": "DEPARTAMENTO DE COORDINACIÓN INSTITUCIONAL",
      "region": "Metropolitana de Santiago",
      "available_amount_clp": 1500000.0,
      "created_at": "2026-08-17T22:05:33Z",
      "updated_at": "2026-08-17T22:05:33Z",
      "items": [
        {
          "id": "...",
          "tender_id": "...",
          "product_code": "52141500",
          "name": "Mueble de cocina",
          "description": null,
          "quantity": 1.0,
          "unit_of_measure": "UN"
        }
      ]
    }
  ],
  "total": 137,
  "is_truncated": true
}
```

Tres cosas:

- **`items` viene ordenado por relevancia.** No reordenes salvo que el usuario lo pida.
- **Las fechas son UTC con sufijo `Z`.** `new Date(...)` las convierte solo a la zona del
  navegador. Ya tienes helpers en `matches/utils/format.ts`.
- **`region` y `available_amount_clp` pueden ser `null`.** Hay licitaciones sin monto
  publicado.

---

## Errores

| Código | Cuándo | Qué mostrar |
|---|---|---|
| **200** | siempre que la búsqueda corrió | resultados o el mensaje de vacío |
| **401** | sin sesión | redirigir a login |
| **422** | rango invertido, monto negativo, región desconocida, `q` > 200 | el `detail` es texto para el usuario |
| **503** | el motor de búsqueda no responde | advertencia **sin bloquear la navegación** |

`apiFetch` ya normaliza `{ detail }` de FastAPI y lanza `ApiError` con el `status`:

```typescript
try {
  const resultado = await searchTenders({ q, regions });
  // ...
} catch (e) {
  if (e instanceof ApiError && e.status === 422) {
    mostrarError(e.message);          // el detalle es legible para el usuario
  } else if (e instanceof ApiError && e.status === 503) {
    mostrarAviso("No pudimos completar la búsqueda. Intenta en unos minutos.");
  }
}
```

El 503 está acotado a este endpoint: el resto de la plataforma sigue funcionando.

---

## Diferencia con el filtro del dashboard

El dashboard filtra en el navegador sobre las 15 recomendaciones ya cargadas
(`filterMatchesByBudget` / `filterMatchesByRegion`). Este endpoint filtra **dentro** de la
búsqueda, sobre el catálogo completo.

| | Dashboard | Buscador |
|---|---|---|
| Universo | 15 recomendaciones | catálogo completo |
| Regiones que se pueden elegir | las que ya aparecen | las 16 |
| Total de coincidencias | no aplica | exacto |

**Dos reglas que ya existen en el dashboard y el backend replica** — no las cambies sin
avisar, porque hoy coinciden:

- Los rangos de monto son inclusivos en ambos extremos.
- Una licitación **sin monto queda fuera** cuando el filtro de presupuesto está activo.

---

## Probarlo

```bash
docker compose up -d
```

Documentación interactiva con formulario para probar cada parámetro:

```
http://localhost:8000/docs
```

En Postman: **Import → Link → `http://localhost:8000/openapi.json`** genera la colección
completa. Para varias regiones, agrega la fila `regions` dos veces en la tabla de Params.

> Con pocas licitaciones en la base el buscador devuelve casi todas y el orden dice poco.
> Para ver el ranking funcionando de verdad hace falta el corpus grande.
