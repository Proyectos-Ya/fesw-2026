# Documentación de la API (OpenAPI / Swagger)

FastAPI genera la especificación OpenAPI y la interfaz Swagger (`/docs`) a partir del propio código. No hay un documento aparte que mantener: **documentar la API es escribir bien la ruta**. Si la ruta carece de metadatos, Swagger muestra un nombre de función genérico y un esquema vacío, obligando al frontend a leer el código interno del backend para deducir qué datos enviar o recibir.

---

## Qué debe llevar toda ruta

| Metadato | Para qué sirve | Ejemplo |
|---|---|---|
| `summary` | Título en Swagger. Corto, en español, comienza con verbo en infinitivo. | `summary="Listar licitaciones guardadas"` |
| `response_model` | Esquema de la respuesta: documenta en OpenAPI **y** filtra campos que no deben exponerse. | `response_model=list[SavedTenderResponse]` |
| `tags` | Agrupa rutas en Swagger. Se define a nivel de `APIRouter(...)` en cada router. | `APIRouter(prefix="/tenders", tags=["Tenders"])` |
| `status_code` | Obligatorio si no es 200 (creación → 201, borrado sin contenido → 204). | `status_code=status.HTTP_201_CREATED` |
| `responses` | Diccionario de errores esperables que el cliente debe manejar. | `responses={404: {"description": "Licitación no encontrada"}}` |
| Docstring | Descripción extendida en Swagger para reglas de negocio complejas (permisos, filtros, efectos). | `"""Busca licitaciones aplicando ponderación semántica..."""` |

> [!NOTE]
> Las rutas auxiliares sin cuerpo útil (e.g. `/health`, redirecciones) deben incluir al menos `summary` y un modelo simple o `response_model=None` explícito para mantener la consistencia en el catálogo.

---

## Flujo de trabajo al crear o modificar una ruta (TDD)

1. **Test primero (Red)**: Si cambias el contrato (campos, query params, status codes), actualiza o crea primero el test de la ruta en `monorepo/backend/tests/`.
2. **Modelo de respuesta**: Define o reutiliza un esquema en `app/application/schemas/`. Evita duplicar esquemas idénticos entre routers para mantener limpia la especificación.
3. **Firma de la ruta**: Declara la ruta con sus metadatos de Swagger y usa `Annotated` para dependencias e inyecciones.
4. **Verificación visual**: Levanta el backend y visita `http://localhost:8000/docs` para confirmar que el título, tags, parámetros y esquemas se visualizan correctamente.
5. **Ejecutar tests**: Corre `pytest` para asegurar que las pruebas sigan pasando y que los contratos no se rompan.
6. **Coordinación con Frontend**: Si el cambio altera campos existentes o códigos de retorno, especifícalo claramente en el PR para coordinar con el equipo de frontend.

---

## Swagger en entornos de despliegue

Por seguridad, la documentación interactiva (`/docs`, `/redoc` y `/openapi.json`) debe exponerse en entornos de desarrollo y restringirse en entornos de producción pública según las variables de configuración del backend. Si se requiere modificar variables en entornos gestionados (como Railway), se debe solicitar autorización explícita previa.
