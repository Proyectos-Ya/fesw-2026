# Guía de testing — HdU 08: alertas de licitaciones con alta compatibilidad

Recorrido completo para revisar la funcionalidad en tu máquina, desde el clone hasta el
reporte. No hace falta que conozcas el proyecto.

Si algo del entorno falla, el detalle técnico está en
[`backend/README.md`](backend/README.md); esta guía enlaza a la sección que corresponda.

---

## 0. Antes de empezar

| Requisito | Mínimo |
|---|---|
| Docker Desktop | Instalado y con **≥4 GB de memoria asignados** |
| Disco libre | ~10 GB — los modelos pesan 4,9 GB (bge-m3 4,3 GB + reranker 588 MB) |
| Supabase CLI | [Instalación](https://supabase.com/docs/guides/local-development) |
| Node | Con `corepack` habilitado (trae pnpm) |
| Python | 3.12 o superior |

> **En Windows: clona el repositorio dentro de WSL2**, no en `C:\`. Sobre el disco de
> Windows los eventos de archivo no llegan al contenedor y el I/O es mucho más lento.
> Tampoco lo pongas dentro de una carpeta que sincronice OneDrive o Drive.

Con menos de 4 GB asignados, Docker mata el contenedor durante el arranque sin un mensaje
claro. Si la API se cae sola al iniciar, revisa eso primero.

---

## 1. Instalación (una sola vez)

### 1.1 Variables de entorno

Desde `monorepo/`:

```bash
cp .env.example .env
```

Completa las obligatorias. Sin ellas la aplicación no arranca:

| Variable | Valor |
|---|---|
| `DATABASE_URL` | `postgresql://postgres:postgres@127.0.0.1:54322/postgres` |
| `MERCADO_PUBLICO_API_KEY` | Cualquier valor si vas a usar el dump (no se consume cuota) |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | Pídeselos al equipo |
| `JWT_SECRET_KEY` | Genera la tuya, ver abajo |
| `POSTGRES_PASSWORD` | `postgres` |

`JWT_SECRET_KEY` es una credencial personal y debe tener al menos 32 bytes o la
aplicación se niega a arrancar:

```bash
python -c "import secrets; print(f'JWT_SECRET_KEY={secrets.token_urlsafe(48)}')"
```

Deja además `RUN_AUTO_INGESTION=false`: vas a usar el corpus de prueba del repositorio en
vez de descargar licitaciones reales.

Verifica que `RUN_NOTIFICATION_SCAN` **no** esté en `false`. Es la variable que enciende
la detección de alertas; con ella apagada no se genera ni un aviso y parecerá que la
funcionalidad no existe.

### 1.2 Entorno de Python

Desde `monorepo/backend/`:

```bash
python -m venv .venv
```

Actívalo (`.venv\Scripts\Activate.ps1` en PowerShell, `source .venv/bin/activate` en
macOS/Linux) y luego:

```bash
pip install -r requirements-dev.txt
```

### 1.3 Base de datos y datos de prueba

```bash
supabase start
docker compose up -d qdrant
```

Desde `monorepo/backend/`, con el venv activo:

```bash
alembic upgrade head
python tests/matching_evaluation/load_postgres_robust.py
python tests/matching_evaluation/load_dataset.py
python tests/matching_evaluation/crear_perfiles_demo.py
```

El segundo comando genera los embeddings e indexa en Qdrant: tarda un par de minutos. El
último crea tres cuentas de prueba de rubros distintos, todas con contraseña `demo1234`.

---

## 2. Levantar la aplicación

El orden importa: `docker compose` ya no levanta Postgres, así que si Supabase no está
corriendo la API falla al aplicar las migraciones.

```bash
supabase start
```

```bash
cd monorepo && docker compose up -d
```

```bash
cd monorepo/frontend && pnpm dev
```

**El primer arranque tarda varios minutos** descargando los modelos. Espera a que la API
responda antes de abrir el navegador, o el frontend mostrará `Failed to fetch`:

```bash
curl http://localhost:8000/health
```

Cuando devuelva `{"status":"healthy"}`, ya puedes entrar.

| Servicio | URL |
|---|---|
| Aplicación | http://localhost:3000 |
| Bandeja de correo (Mailpit) | http://localhost:54324 |
| API (Swagger) | http://localhost:8000/docs |
| Supabase Studio | http://localhost:54323 |

---

## 3. Dos trampas que cuestan tiempo

Léelas antes de empezar; las vas a necesitar.

**Reiniciar la API fuerza un escaneo inmediato.** El bucle de detección ejecuta *antes* de
dormir, así que no hace falta esperar los 5 minutos del intervalo. Cada vez que quieras
provocar avisos nuevos:

```bash
docker compose restart api
```

**Cambiar el `.env` exige reiniciar el contenedor.** La API corre con `uvicorn --reload`,
que recarga el código pero **no** relee las variables de entorno. Es el error más habitual
al probar esto: cambias `SMTP_PORT`, no reinicias, y concluyes que no funciona.

---

## 4. Recorrido por criterio

Entra en http://localhost:3000/login con **`salud@demo.invalid`** y contraseña
**`demo1234`**.

Las alertas viven en el menú lateral: la entrada **Alertas** (icono de campana) lleva el
contador de no leídas, y el engranaje **Preferencias de alertas** abre la configuración.

---

### Criterio 1 — Detecta licitaciones compatibles y avisa por los dos canales

1. Abre **Preferencias de alertas** (`/configuracion/notificaciones`).
2. Baja el **Umbral de compatibilidad** con el deslizador hasta 40 % o menos. Se guarda solo al soltarlo.
3. Reinicia la API: `docker compose restart api`.
4. Espera a que `/health` vuelva a responder.

**Esperado:** la entrada *Alertas* del menú muestra un contador. En `/alertas` aparecen los
avisos, cada uno con su porcentaje de compatibilidad y el organismo comprador. En
http://localhost:54324 hay un correo por cada aviso.

- [ ] Aprobado

---

### Criterio 2 — El aviso lleva al detalle de la licitación

1. En `/alertas`, haz clic en un aviso.
2. Vuelve, y ahora abre el correo en Mailpit y haz clic en su enlace.

**Esperado:** ambos llevan a la ficha de esa licitación. Al abrir el aviso desaparece la
marca **Sin leer** y el contador del menú baja.

- [ ] Aprobado

---

### Criterio 3 — Umbral y frecuencia configurables

1. En **Preferencias de alertas**, mueve el umbral y recarga la página: el valor debe persistir.
2. Cambia el modo de entrega a **Resumen diario**.
3. El resumen se arma a las 08:00 hora de Chile. Para no esperar:

```bash
docker compose exec api python -m scripts.demo_alertas resumen-ahora
```

**Esperado:** el umbral persiste tras recargar. Con *Resumen diario* seleccionado, el
comando produce **un solo correo** con todos los avisos agrupados, y en la bandeja de
salida de esa misma página aparece una entrega marcada como *Resumen diario*.

- [ ] Aprobado

---

### Criterio 4 — Aviso de una licitación que ya cerró

```bash
docker compose exec api python -m scripts.demo_alertas cerrar-licitacion
```

**Esperado:** en `/alertas`, ese aviso sigue visible pero marcado **Cerrada**. No
desaparece: el usuario debe poder ver que la oportunidad venció.

- [ ] Aprobado

---

### Criterio 5 — El servicio de correo se cae y el envío se reintenta

> **No uses `supabase stop`.** Mailpit vive dentro del stack de Supabase, así que ese
> comando se lleva también a Postgres: verías un error de base de datos, que es otro
> problema distinto.

1. En `monorepo/.env`, cambia `SMTP_PORT` a `59999` (un puerto muerto).
2. `docker compose restart api`
3. Baja el umbral para provocar avisos nuevos y reinicia otra vez la API.
4. Mira la bandeja de salida en **Preferencias de alertas**.

**Esperado:** las entregas quedan en **Pendiente**, con su contador de intentos y la hora
del próximo reintento, que se aleja en cada fallo.

5. Restaura `SMTP_PORT=54325` y reinicia la API.
6. Para no esperar el backoff exponencial:

```bash
docker compose exec api python -m scripts.demo_alertas reintentar-ahora
```

**Esperado:** las entregas pasan a **Enviado** y los correos aparecen en Mailpit.

- [ ] Aprobado

---

### Criterio 6 — Correo inexistente: se desactiva el envío ⚠️

**Este criterio no se puede comprobar del todo en local.** Mailpit acepta cualquier
destinatario por diseño y nunca devuelve un rechazo definitivo, así que la *detección* del
rebote no ocurre.

Lo que sí puedes revisar es el estado resultante:

```bash
docker compose exec api python -m scripts.demo_alertas marcar-rebote
```

**Esperado:** en **Preferencias de alertas** aparece el aviso de que el sistema desactivó
el envío de correos, con el motivo, y un botón para reactivarlo. Al reactivarlo, la
advertencia desaparece.

> Marca este criterio como **No aplica**, no como aprobado: estás viendo el estado
> reproducido a mano, no la detección real. Comprobarla requiere apuntar el `.env` a un
> proveedor real (Brevo o SendGrid); las cuentas demo ya usan `@demo.invalid`, un TLD
> reservado que nunca resuelve, así que el rebote sería inmediato y genuino.

- [ ] No aplica en local — estado visible correcto

---

### Criterio 7 — Pide sesión antes de mostrar los datos

1. Cierra sesión.
2. Copia el enlace de un correo desde Mailpit y ábrelo en una ventana privada.

**Esperado:** te redirige al login en vez de mostrar la licitación. Tras iniciar sesión,
llegas a la ficha que pedías.

- [ ] Aprobado

---

## 5. Comando de diagnóstico

En cualquier momento, para ver en qué estado está la cuenta —preferencias, avisos y
entregas—:

```bash
docker compose exec api python -m scripts.demo_alertas estado
```

Casi todos los subcomandos aceptan `--email` para elegir la cuenta (`resumen-ahora` es la
excepción: trabaja sobre todos los usuarios en modo resumen). Los que escriben aceptan
`--dry-run`.

---

## 6. Qué reportar

| Criterio | Resultado |
|---|---|
| 1. Detecta y avisa (panel + correo) | |
| 2. El aviso lleva al detalle | |
| 3. Umbral y frecuencia configurables | |
| 4. Licitación ya cerrada | |
| 5. Correo caído y reintento | |
| 6. Correo inexistente | No aplica en local |
| 7. Pide sesión | |

Si algo falla, adjunta:

```bash
docker compose logs api --tail 100
```

```bash
docker compose exec api python -m scripts.demo_alertas estado
```

y una captura de la vista donde lo viste.

---

## 7. Si algo no arranca

| Síntoma | Causa habitual |
|---|---|
| `Failed to fetch` en el navegador | La API todavía está cargando modelos. Espera a que `/health` responda. |
| La API se cae sola al iniciar | Docker con menos de 4 GB asignados. |
| No llega ningún correo | `smtp_port = 54325` comentado en `supabase/config.toml`, o `SMTP_PORT` mal en `.env`. Reinicia con `supabase stop && supabase start`. |
| No aparece ningún aviso | `RUN_NOTIFICATION_SCAN=false` en el `.env`, o el umbral está muy alto. |
| Cambié una variable y no pasa nada | `uvicorn --reload` no relee el `.env`: `docker compose restart api`. |
| El dashboard sale vacío | Falta cargar el dump (paso 1.3). |
