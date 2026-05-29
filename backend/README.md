# ProyectosYa — Backend

## Requisitos previos

- Python 3.12+
- Docker Desktop

---

## Inicialización del proyecto

### 1. Clonar el repositorio

```bash
git clone <url-del-repo>
cd backend
```

### 2. Crear y activar el entorno virtual

```bash
python -m venv venv
```

```bash
# Mac / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

```bash
cp .env.example .env
```

El `.env` ya viene con las credenciales de desarrollo, no necesitas cambiar nada.

### 5. Levantar la base de datos

```bash
docker compose up -d
```

Verifica que el contenedor esté corriendo:

```bash
docker ps
```

Deberías ver `proyectosya-db` con status `Up`.

### 6. Levantar el servidor

```bash
uvicorn app.main:app --reload
```

### 7. Verificar que todo funciona

- API: http://localhost:8000/health → `{"status": "ok"}`
- Documentación automática: http://localhost:8000/docs

---

## Comandos útiles

| Comando | Descripción |
|---|---|
| `docker compose up -d` | Inicia la base de datos |
| `docker compose down` | Detiene la base de datos |
| `uvicorn app.main:app --reload` | Inicia el servidor en modo desarrollo |

---
