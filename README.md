# Guia de Desarrollo: HdU 01 y Flujo de Trabajo Git/GitHub

Este documento establece las directrices tecnicas para completar la HdU 01: Completar perfil de empresa y el flujo de trabajo estandar en GitHub que implementaremos como equipo para el MVP de ProyectosYa.

---

## 1. Especificaciones de la HdU 01 (Perfil de Empresa)

**Estimacion:** 3 Story Points  
**Objetivo:** Permitir que los proveedores configuren su perfil comercial para habilitar el posterior matching semantico de licitaciones.

### 1.1 Frontend (Responsable: Octavia Jara)
* **Tecnologia:** Next.js + Tailwind CSS.
* **Entregable:** Formulario de registro en la ruta /perfil o equivalente que capture el nombre de la empresa, descripcion, anos de experiencia, cantidad de empleados, regiones de operacion, rubros comerciales y palabras clave de experiencia.
* **Criterio de Aceptacion:** Validacion de campos obligatorios en el cliente y envio de datos en formato JSON optimizado hacia el Backend al presionar "Guardar perfil".

### 1.2 Backend y MLOps (Responsables: Benjamin Ulloa / Octavia Jara)
* **Tecnologia:** FastAPI (Python) + PostgreSQL (Prisma.io) + Qdrant.
* **Entregables:**
    1. `POST /providers`: Endpoint en FastAPI para recibir y validar el payload del formulario.
    2. `ProvidersRepository`: Persistencia de datos estructurados en PostgreSQL.
    3. `VectorDatabaseService`: Indexacion del perfil del proveedor en la base de datos vectorial Qdrant.
    4. `embedProvider`: Servicio de MLOps con sentence-transformers utilizando el modelo BGE-M3 para generar los embeddings del perfil antes de guardarlo en Qdrant.

### 1.3 Contrato de API y Coordinacion Obligatoria
Antes de iniciar la programacion en Next.js y FastAPI, Octavia y Benjamin deben definir en conjunto el esquema JSON exacto para la transmision de datos. Cualquier discrepancia en el nombre o tipo de los atributos provocara errores de validacion en las solicitudes del MVP.

La estructura base acordada para el JSON de la HdU 01 es la siguiente:

```json
{
  "business_name": "string (Nombre de la empresa)",
  "description": "string (Minimo X caracteres)",
  "years_of_experience": "integer (Anos de experiencia)",
  "employee_count": "integer (Cantidad de colaboradores)",
  "operating_regions": ["string (Lista de regiones)"],
  "business_sectors": ["string (Lista de rubros comerciales)"],
  "experience_keywords": ["string (Palabras clave para embeddings)"]
}

## 2. Flujo de Trabajo en GitHub (Git Feature Branch Workflow)

Para asegurar la calidad del código y mantener el orden en nuestro único repositorio, todo desarrollo deberá seguir estrictamente este flujo automatizado.

### Las Ramas Base
* **`main` (Producción):** Código 100% estable, probado y funcional. Nadie sube código directo aquí.
* **`develop` (Desarrollo):** Rama de integración diaria. Es la base para iniciar cualquier tarea.

### Paso a Paso para Desarrolladores (Octavia y Benjamín)

1.  **Sincronizar Local:** Antes de empezar, ve a `develop` y descarga lo último:
    git checkout develop
    git pull origin develop
2.  **Crear Rama de Tarea:** Crea una rama temporal desde `develop` usando la nomenclatura `feat/hdu1-[nombre-tarea]` o `fix/[nombre-bug]`:
    git checkout -b feat/hdu1-frontend-form
3.  **Desarrollar y Commitear:** Trabaja en tu carpeta (`/frontend` o `/backend`). Haz commits descriptivos:
    git add .
    git commit -m "feat: implementado formulario con validaciones de cliente"
4.  **Mover Tarjeta (Manual):** En el tablero de GitHub Projects, arrastra tu tarjeta a **In Progress**.
5.  **Subir Rama:** Sube tus cambios al repositorio remoto:
    git push -u origin feat/hdu1-frontend-form
6.  **Abrir Pull Request (PR):**
    * Entra a GitHub Web y haz clic en **Compare & pull request**.
    * **CRUCIAL:** Cambia la rama base para que apunte a **`develop`** (NO a `main`). Debe quedar: `base: develop ⬅ compare: feat/hdu1-...`.
    * En la descripción, enlaza el Issue escribiendo **`Closes #X`** (donde X es el número de la tarea).
    * *La tarjeta se moverá automáticamente en el tablero a **In Review / QA**.*

---

##  3. Control de Calidad y Aprobación (Responsable: Alfredo Iturra)

Apenas una tarjeta entre a la columna **In Review / QA**, se iniciará el proceso de revisión:

1.  **Testing Local:** Alfredo descargará la rama correspondiente en su entorno local para realizar pruebas de caja negra, validación de inputs y manejo de errores (ej. simulación de timeouts).
    git fetch origin
    git checkout feat/hdu1-frontend-form
2.  **Revisión de Código:** Se revisará la limpieza del código en la pestaña **Files changed** del PR en GitHub.
3.  **Dictamen:**
    * Si hay fallas, Alfredo comentará las líneas afectadas y seleccionará **Request changes** (vuelve a desarrollo).
    * Si cumple los criterios de aceptación, Alfredo seleccionará **Approve**.
4.  **Cierre (Merge):** Con el visto bueno de QA, el Scrum Master (Luis) o el Tech Lead (Benjamín) presionarán **Merge pull request**. 
    * *El código se unirá a `develop`, la rama temporal se borrará y la tarjeta pasará automáticamente a **Done**.*
