# Guía de testing — HU-22: mapa de las direcciones de entrega

Cómo probar a mano el mapa de licitaciones en tu máquina. Criterios de aceptación:
[issue #314](https://github.com/Proyectos-Ya/fesw-2026/issues/314). Diseño técnico:
[plan.md](../plans/314-hu-22-mapa-licitaciones/plan.md).

Esta guía **no repite la instalación**. Si es tu primera vez con el proyecto, monta el
entorno con [`testing-hdu08.md`](./testing-hdu08.md) §0 a §2 (variables, Supabase,
API, frontend) y vuelve acá. Lo de abajo es solo lo propio de HU-22.

---

## 0. Antes de empezar

| Requisito | Por qué |
|---|---|
| El entorno de `testing-hdu08.md` levantado | Base, API y frontend |
| Internet | Las direcciones se ubican consultando a Nominatim (OpenStreetMap) |
| `pnpm install` en `monorepo/frontend` | HU-22 agrega Leaflet; sin instalar, `/mapa` no compila |
| `alembic upgrade head` | Agrega las columnas de coordenadas y la tabla `geocoding_cache` |

No necesitas ninguna clave nueva: Nominatim es un servicio público y gratuito.

**Lo que hace el sistema, en una línea:** Mercado Público entrega la dirección de
entrega como texto ("Yerbas Buenas 915"), sin coordenadas. Una tarea en segundo plano
le pregunta a Nominatim dónde queda cada dirección y guarda el punto. El mapa solo
dibuja lo que quedó guardado.

---

## 1. Encender la geocodificación

Viene **apagada**. En `monorepo/.env`:

```bash
GEOCODING_PROVIDER=nominatim
GEOCODING_CONTACT_EMAIL=tu-correo@ejemplo.cl
GEOCODING_INTERVAL_SECONDS=30
```

`GEOCODING_CONTACT_EMAIL` es obligatorio: la política de uso de Nominatim exige
identificar a quien consulta, y el correo viaja en cada petición. Para probar en local
sirve el tuyo.

`GEOCODING_INTERVAL_SECONDS=30` es solo para la prueba. El valor normal es 300 (5
minutos) y te haría esperar de más.

La API **no relee el `.env` al reiniciar**. Desde `monorepo/`:

```bash
docker compose up -d --force-recreate api
```

Confirma que quedó encendida:

```bash
docker compose logs api | grep -i geocodif
```

Debe decir `Geocodificación de entregas servida por nominatim`. Si dice
`desactivada (GEOCODING_PROVIDER=none)`, el `.env` no se tomó.

---

## 2. Conseguir licitaciones con dirección de entrega

**Esta es la trampa de la prueba.** El dump de datos del repositorio
(`chiripa_tenders.xlsx`) **no trae la dirección de entrega**: es anterior a #294, que
agregó esa columna. Si cargas el dump y entras al mapa, lo vas a ver vacío. No está
roto; no hay direcciones que mostrar.

Hay dos caminos.

### Camino A — datos reales (necesita la clave de Mercado Público)

Con `MERCADO_PUBLICO_API_KEY` en el `.env`, desde `monorepo/backend/` con el entorno
virtual activo:

```bash
python -m scripts.sync_diaria --limite 100
```

Baja licitaciones de verdad con su dirección. Es lo más parecido a producción, pero
las direcciones quedan repartidas por todo Chile y puede que ninguna caiga en tu zona.

### Camino B — direcciones a mano (más rápido y controlado)

Le pone dirección a 8 licitaciones abiertas de la Región Metropolitana: cinco en el
centro de Santiago, que deben agruparse, y tres separadas. Es el camino que mejor
permite probar el criterio 4.

```bash
docker exec -i supabase_db_fesw-2026 psql -U postgres -d postgres <<'SQL'
WITH abiertas AS (
  SELECT t.id, row_number() OVER (ORDER BY t.closing_at) AS n
  FROM tender t
  JOIN tender_status s ON s.id = t.status_id
  JOIN buyer_institution b ON b.rut = t.buyer_rut
  WHERE s.code = 'publicada'
    AND t.closing_at > now()
    AND b.region_id = 13
  LIMIT 8
), direcciones (n, calle) AS (
  VALUES
    (1, 'Plaza de Armas'),
    (2, 'Alameda 1449'),
    (3, 'Moneda 975'),
    (4, 'Agustinas 1137'),
    (5, 'Bandera 361'),
    (6, 'Avenida Apoquindo 3000'),
    (7, 'Gran Avenida 4500'),
    (8, 'Avenida Vicuna Mackenna 4860')
)
UPDATE tender
SET delivery_address       = d.calle,
    delivery_lat           = NULL,
    delivery_lng           = NULL,
    delivery_geo_precision = NULL,
    delivery_geocoded_at   = NULL
FROM abiertas a
JOIN direcciones d ON d.n = a.n
WHERE tender.id = a.id;
SQL
```

Si devuelve `UPDATE 0`, no hay licitaciones abiertas de la RM en tu base: carga el dump
primero, o cambia `b.region_id = 13` por la región que tengas.

---

## 3. Comprobar que se ubicaron

La tarea corre **dentro de la API**, y geocodifica apenas arranca. Si pusiste las
direcciones después de levantarla, espera lo que diga `GEOCODING_INTERVAL_SECONDS` o
recrea el contenedor.

```bash
docker compose logs -f api | grep -i "ubicadas en el mapa"
```

Debería aparecer `8 licitaciones ubicadas en el mapa`, con el detalle de cuántas
consultas salieron a la red y cuántas resolvió la caché.

**Tarda unos dos minutos**, y es lo esperado: la política de Nominatim limita a un
proceso como este a 4 consultas por minuto, o sea una cada 15 segundos. Las
direcciones repetidas no esperan, porque las resuelve la caché.

El estado completo:

```bash
docker exec -i supabase_db_fesw-2026 psql -U postgres -d postgres <<'SQL'
SELECT coalesce(delivery_geo_precision, 'pendiente') AS estado, count(*)
FROM tender
WHERE delivery_address IS NOT NULL
GROUP BY 1 ORDER BY 2 DESC;
SQL
```

| Estado | Qué significa |
|---|---|
| `direccion` | Nominatim encontró la dirección exacta. Marcador normal |
| `comuna` | No la encontró; el punto es la comuna del organismo. Sale como "ubicación aproximada" |
| `no_encontrada` | No se pudo ubicar y no hay comuna. **No aparece en el mapa**, a propósito |
| `pendiente` | Todavía no se intenta |

---

## 4. Recorrido por criterio

Entra a la aplicación con tu cuenta. La empresa debe tener al menos una región.

### Criterio 1 — Entrada en el menú y mapa centrado en la zona

En el menú lateral, en la sección **Descubrimiento** y debajo de **Matches**, debe
aparecer **Mapa de licitaciones**, con su ícono. Haz clic.

Esperado: se abre `/mapa`, el selector **Zona** muestra la primera región de tu empresa
y el mapa aparece centrado ahí, con un marcador por cada licitación ubicada.

### Criterio 2 — Sin zona en el perfil

Deja a tu empresa sin regiones y recarga `/mapa`:

```bash
docker exec -i supabase_db_fesw-2026 psql -U postgres -d postgres \
  -c "SELECT id, legal_name, regions FROM supplier;"
docker exec -i supabase_db_fesw-2026 psql -U postgres -d postgres \
  -c "UPDATE supplier SET regions = '[]'::json WHERE id = '<tu-id>';"
```

Esperado: no se dibuja el mapa. Aparece *"Elige una zona para ver las licitaciones en el
mapa"* y un enlace **Completa tu zona en el perfil** que lleva a `/empresa`. Al elegir
una zona en el selector, el mapa se carga igual.

Déjala como estaba cuando termines:

```bash
docker exec -i supabase_db_fesw-2026 psql -U postgres -d postgres \
  -c "UPDATE supplier SET regions = '[\"Metropolitana\"]'::json WHERE id = '<tu-id>';"
```

### Criterio 3 — Resumen al hacer clic en un marcador

Haz clic en un marcador suelto (los de Apoquindo, Gran Avenida o Vicuña Mackenna).

Esperado: una ventanita con nombre de la licitación, organismo, dirección de entrega y
fecha de cierre, más un enlace **Ver detalle**. El enlace debe abrir la ficha de esa
misma licitación.

### Criterio 4 — Agrupación de marcadores cercanos

Mira el centro de Santiago: los cinco marcadores del centro deben verse como **un solo
círculo con el número 5**.

Haz clic en el círculo, o acerca el mapa con la rueda o el botón `+`.

Esperado: el grupo se abre y aparecen los marcadores por separado. Al alejar, vuelven a
juntarse.

### Criterio 5 — Cambiar de zona

Con el selector **Zona**, cambia a otra región (por ejemplo, Los Lagos).

Esperado: el mapa se desplaza hasta la región nueva y los marcadores se actualizan. Si
ahí no hay licitaciones ubicadas, verás el mensaje del criterio 6.

### Criterio 6 — Zona sin resultados

Elige una región donde no hayas puesto direcciones (Ñuble, por ejemplo).

Esperado: *"No hay licitaciones con dirección de entrega en Ñuble"* y, debajo, *"Prueba
con otra zona"*. El mapa igual se centra en esa región, vacío.

### Criterio 7 — La dirección en el detalle de la licitación

Abre la ficha de una licitación (`/matches/{id}`) y busca la sección **Entrega y
requisitos**.

Esperado: con dirección, la muestra tal cual. Sin dirección, dice exactamente
*"Dirección de entrega no disponible"*. Para ver el segundo caso, entra a una
licitación a la que no le pusiste dirección en el paso 2.

### Criterio 8 — Error al cargar, con reintento

La forma rápida, con las herramientas del navegador: pestaña **Red**, botón derecho
sobre la petición `map?region=...` → **Bloquear URL de la petición**, y recarga.

La otra forma, desde la terminal: `docker compose stop api` y recarga `/mapa`.

Esperado: en lugar del mapa, un recuadro rojo que dice **"No se pudo cargar el mapa"**
con un botón **Reintentar**.

Ahora desbloquea la petición (o `docker compose start api`, esperando a que `/health`
responda; la API tarda un par de minutos en cargar sus modelos) y aprieta
**Reintentar**. El mapa debe cargar sin recargar la página.

---

## 5. Lo que no es un error

Antes de reportar algo, revisa si está en esta lista. Son decisiones tomadas, no fallas.

| Lo que ves | Por qué |
|---|---|
| El mapa sale casi vacío con datos reales | Las licitaciones anteriores al 2026-10-26 no tienen dirección guardada. Se completan solas cuando la ingesta vuelve a bajar su detalle |
| Un marcador dice "ubicación aproximada" | Nominatim no encontró esa dirección y se usó la comuna del organismo |
| Una licitación con dirección no aparece | No se pudo ubicar y su organismo no tiene comuna. La issue pide explícitamente no inventar una ubicación |
| Dice "Se muestran 3.000 de N" | Hay un tope de 3.000 marcadores por zona. Se muestran las que cierran antes. Con el corpus actual (~9.000 en todo Chile) no debería alcanzarse nunca: si lo ves, repórtalo |
| Al elegir "Elige una zona" vuelve a la zona del perfil | El selector vacío no borra la zona: cae de nuevo en la de tu empresa |
| Una licitación desaparece del mapa | Solo se muestran las abiertas. Al cerrarse, su marcador se va solo |
| Los marcadores no se mueven al cambiar la dirección en la base | Si editas `delivery_address` a mano, pon también las cuatro columnas de ubicación en `NULL`, como hace el SQL del paso 2 |

---

## 6. Qué reportar

| Criterio | Resultado |
|---|---|
| 1. Menú y mapa centrado en la zona | |
| 2. Sin zona: pide elegir y enlaza al perfil | |
| 3. Resumen y enlace al detalle | |
| 4. Agrupa cercanas y las separa al acercar | |
| 5. Cambiar de zona recentra y actualiza | |
| 6. Zona sin resultados | |
| 7. Dirección en el detalle, o "no disponible" | |
| 8. "No se pudo cargar el mapa" con reintento | |

Si algo falla, adjunta la captura y:

```bash
docker compose logs api --tail 100
```

```bash
docker exec -i supabase_db_fesw-2026 psql -U postgres -d postgres \
  -c "SELECT coalesce(delivery_geo_precision,'pendiente'), count(*) FROM tender WHERE delivery_address IS NOT NULL GROUP BY 1;"
```

---

## 7. Si algo no anda

| Síntoma | Causa habitual |
|---|---|
| El mapa sale vacío en todas las zonas | Ninguna licitación tiene dirección. Haz el paso 2 |
| Las licitaciones quedan en `pendiente` | La geocodificación está apagada o la API no se recreó tras tocar el `.env` (paso 1) |
| En los logs: `Nominatim respondió 429` | Te pasaste del límite. Espera unos minutos; el sistema reintenta solo en la vuelta siguiente |
| En los logs: `Geocodificación interrumpida` | Nominatim no respondió. Las licitaciones quedan pendientes y se reintentan |
| Todo queda en `no_encontrada` | Sin internet desde el contenedor, o direcciones inventadas que no existen |
| `/mapa` da error al compilar | Falta `pnpm install` tras los cambios de HU-22 |
| Los marcadores salen como imágenes rotas | No debería pasar: el proyecto usa íconos propios. Si ocurre, repórtalo |
| Cambié el `.env` y no pasa nada | `docker compose restart api` no basta: usa `up -d --force-recreate api` |
