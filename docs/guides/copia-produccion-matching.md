# Copia de producción para pruebas de matching

Cómo darle a alguien del equipo acceso para copiar el catálogo de licitaciones de
producción a su entorno local y probar el matching semántico, sin consumir cuota
de la API de Mercado Público.

Necesitas un acceso de solo lectura a la base de producción (usuario
`matching_lectura`), que te entrega quien administra producción junto con la URI
de conexión. Con él exportas las licitaciones cuando quieras. Los vectores los
recalcula `cargar` con DeepInfra (`EMBEDDING_PROVIDER=deepinfra` y tu
`EMBEDDING_API_KEY`): no necesitas acceso a Qdrant Cloud.

Si solo quieres usar el dump que ya está en el repositorio, no necesitas nada de
esto: `python -m scripts.dump cargar` y listo.

---

## Qué incluye y qué no

| Incluye | No incluye |
|---|---|
| `tender` (todas sus columnas, incluidas dirección de entrega y coordenadas), `tender_item`, `buyer_institution`, `region`, `tender_status` (solo licitaciones **vigentes**) | Usuarios, empresas, invitaciones, chats, cotizaciones, notificaciones |
| Vectores de `tenders`, `tender_items` y `tender_lexical`, recalculados al cargar | La colección `suppliers` (cada uno crea su empresa en local) |
| | `matching_result` (se recalcula al entrar al dashboard) |

Todo lo que incluye es información pública de Mercado Público.

---

## 1. Preparar el entorno local (una vez)

Con Supabase local (`supabase start`), el `.venv` del backend activo y
`alembic upgrade head` aplicado.

**Levantar Qdrant.** Desde `monorepo/`:

```bash
docker compose up -d qdrant
```

`docker-compose.yml` usa la misma versión que producción (1.19.0). Si tenías
levantada una versión anterior, este comando recrea el contenedor con la nueva y
conserva el volumen: no hay que borrar nada.

---

## 2. Copiar el catálogo (cada vez que quieras refrescar)

Desde `monorepo/backend`, con el `.venv` activo.

**2.1. Exportar desde producción.** Toma `<project-ref>` y `<host>` de la URI que
te entregaron, y escribe la contraseña sin que quede en el historial:

```bash
read -s "PROD_RO_PASS?Password de matching_lectura: "
```

```bash
DATABASE_URL="postgresql://matching_lectura.<project-ref>:${PROD_RO_PASS}@<host>:5432/postgres" python -m scripts.dump exportar --limite 300
```

Sin `--limite` exporta todas las vigentes (miles). Con `--limite N`, `--limite N` (por ejemplo
`--limite 500`). Primero van las que traen dirección de entrega y, entre esas, las
que ya tienen coordenadas; el resto se reparte entre regiones. Para la misma base,
el pedazo sale siempre igual. `--archivo <ruta>` escribe en otro lugar sin pisar
el dump del repo. El export solo hace `SELECT`.

`DATABASE_URL` va delante del comando y **no con `export`**: así solo ese comando
apunta a producción y el resto de los scripts sigue usando tu `.env` local. Si la
contraseña tiene caracteres especiales (`@`, `#`, `/`, `:`, `%`), hay que
codificarlos (por ejemplo `@` → `%40`).

Sobrescribe `project-data/chiripa_tenders.xlsx`. Commitéalo solo cuando quieras
compartir un dump nuevo con el equipo: es un binario y cada versión queda para
siempre en el historial. Para descartarlo: `git restore project-data/chiripa_tenders.xlsx`.

**2.2. Cargarlo.** Un solo comando: carga el dump, corre sus fechas para que
quede vigente e indexa con el mismo código que la ingesta de producción.

**Borra todo el entorno local sin preguntar**: el catálogo, las cuentas (también
los logins de Supabase Auth), las empresas y lo que cuelga de ellas (guardadas,
kanban, chats, cotizaciones, alertas, vectores de `suppliers`). Después de
cargar hay que registrarse de nuevo en `/register`; si el navegador tenía una
sesión abierta, cierra sesión primero.

```bash
python -m scripts.dump cargar
```

Antes de borrar nada comprueba que el proveedor de embeddings responde. Se niega
a correr contra una base o un Qdrant que no sean locales.

**2.3. Cuando vuelva a vencer.** Las compras ágiles duran unos diez días. Sin
recargar nada:

```bash
python -m scripts.dump revivir
```

Corre todo el catálogo del dump los mismos días, hasta que la publicación más
reciente quede de hoy, y actualiza el payload de Qdrant sin recalcular vectores.
Las licitaciones que bajaste con la ingesta real no se tocan.

**2.4. Comprobar que Postgres y Qdrant cuadran.** Solo mide, no escribe:

```bash
python -m scripts.check_tender_vector_orphans
```

**2.5. Crear la cuenta** (después de cada `cargar`) en `/register`, confirmar el correo
en Mailpit (http://localhost:54324) y completar el perfil de la empresa.

---

## 3. Límites

- **Solo trae las vigentes.** El export descarta lo que ya cerró. Si en
  producción quedan pocas vigentes, la copia será chica; refrescarla más seguido
  no lo arregla.
- **Los vectores son equivalentes, no idénticos.** Salen del código de tu rama.
  Si tu rama cambia el texto que arma `TextBuilder`, el modelo o los campos del
  vector, estás midiendo tu versión, que es justo lo que se quiere al probar esos
  cambios.
