# Copia de producción para pruebas de matching

Cómo darle a alguien del equipo acceso para copiar el catálogo de licitaciones de
producción a su entorno local y probar el matching semántico, sin consumir cuota
de la API de Mercado Público.

Necesitas un acceso de solo lectura a la base de producción (usuario
`matching_lectura`), que te entrega quien administra producción junto con la URI
de conexión. Con él exportas las licitaciones cuando quieras. Los vectores los
recalculas en tu máquina: no necesitas acceso a Qdrant Cloud.

---

## Qué incluye y qué no

| Incluye | No incluye |
|---|---|
| `tender`, `tender_item`, `buyer_institution`, `region`, `tender_status` (solo licitaciones **vigentes**) | Usuarios, empresas, invitaciones, chats, cotizaciones, notificaciones |
| Vectores de la colección `tenders`, recalculados en local | La colección `suppliers` (cada uno crea su empresa en local) |
| | `matching_result` (se recalcula al entrar al dashboard) |

Todo lo que incluye es información pública de Mercado Público.

---

## 1. Preparar el entorno local (una vez)

Con Supabase local (`supabase start`), el `.venv` del backend activo y
`alembic upgrade head` aplicado.

**Recrear el volumen de Qdrant.** `docker-compose.yml` usa la misma versión que
producción (1.19.0). Los volúmenes locales se crearon con la 1.17, y Qdrant migra
su almacenamiento de a una versión menor: con el volumen viejo, la 1.19 puede no
arrancar. Borrarlo elimina también la colección `suppliers`, que se regenera al
completar el perfil. Desde `monorepo/`:

```bash
docker compose rm -sf qdrant
```

```bash
docker volume ls | grep qdrant_data
```

```bash
docker volume rm <nombre-del-volumen>
```

```bash
docker compose up -d qdrant
```

---

## 2. Copiar el catálogo (cada vez que quieras refrescar)

Desde `monorepo/backend`, con el `.venv` activo.

**2.1. Exportar desde producción.** Toma `<project-ref>` y `<host>` de la URI que
te entregaron, y escribe la contraseña sin que quede en el historial:

```bash
read -s "PROD_RO_PASS?Password de matching_lectura: "
```

```bash
DATABASE_URL="postgresql://matching_lectura.<project-ref>:${PROD_RO_PASS}@<host>:5432/postgres" python tests/matching_evaluation/export_dataset.py
```

`DATABASE_URL` va delante del comando y **no con `export`**: así solo ese comando
apunta a producción y el resto de los scripts sigue usando tu `.env` local. Si la
contraseña tiene caracteres especiales (`@`, `#`, `/`, `:`, `%`), hay que
codificarlos (por ejemplo `@` → `%40`).

Sobrescribe `project-data/chiripa_tenders.xlsx`. **No lo commitees en cada
refresco**: es un binario y cada versión queda para siempre en el historial.
Para descartarlo después: `git restore project-data/chiripa_tenders.xlsx`.

**2.2. Vaciar el catálogo local:**

```bash
docker exec supabase_db_fesw-2026 psql -U postgres -c "truncate tender_item, tender, tender_metadata, matching_result, buyer_institution cascade;"
```

```bash
curl -X DELETE http://localhost:6333/collections/tenders
```

**2.3. Cargar Postgres:**

```bash
python tests/matching_evaluation/load_postgres_robust.py
```

**2.4. Calcular los vectores.** Indexa en tu Qdrant local con el mismo modelo y
el mismo código que la ingesta de producción. Tarda un rato: calcula BGE-M3 en
CPU.

```bash
python tests/matching_evaluation/load_dataset.py
```

**2.5. Comprobar que Postgres y Qdrant cuadran.** Solo mide, no escribe:

```bash
python -m scripts.check_tender_vector_orphans
```

**2.6. Crear la cuenta** (solo la primera vez) en `/register`, confirmar el correo
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
