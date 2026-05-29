## Flujo de Trabajo en GitHub 

Para asegurar la calidad del código y mantener el orden en nuestro repositorio, todo desarrollo deberá seguir estrictamente este flujo automatizado.

### Las Ramas Base
* **`main` (Producción):** Código 100% estable, probado y funcional. Nadie sube código directo aquí.
* **`develop` (Desarrollo):** Rama de integración diaria. Es la base para iniciar cualquier tarea.

### Paso a Paso para Desarrolladores (Octavia y Benjamín)

1.  **Sincronizar Local:** Antes de empezar, vayan a `develop` y ejecuten lo último:
    ```bash
    git checkout develop
    git pull origin develop
    ```
2.  **Crear Rama de Tarea:** Creen una rama temporal desde `develop` usando la nomenclatura `feat/hdu1-[nombre-tarea]` o `fix/[nombre-bug]`:
    ```bash
    git checkout -b feat/hdu1-frontend-form
    ```
3.  **Desarrollar y Commitear:** Trabajen en su carpeta (`/frontend` o `/backend`). Hagan commits descriptivos:
    ```bash
    git add .
    git commit -m "feat: implementado formulario con validaciones de cliente"
    ```
4.  **Mover Tarjeta (Manual):** En el tablero de GitHub Projects, arrastren su tarjeta a **In Progress**.
5.  **Subir Rama:** Subam sus cambios al repositorio remoto:
    ```bash
    git push -u origin feat/hdu1-frontend-form
    ```
6.  **Abrir Pull Request (PR):**
    * Entren a GitHub Web y hagan clic en **Compare & pull request**.
    * **CRUCIAL:** Cambien la rama base para que apunte a **`develop`** (NO a `main`). Debe quedar: `base: develop ⬅ compare: feat/hdu1-...`.
    * En la descripción, enlazen el Issue escribiendo **`Closes #X`** (donde X es el número de la tarea).
    * *La tarjeta se moverá automáticamente en el tablero a **In Review / QA**.*

---

## 🧪 3. Control de Calidad y Aprobación (Responsable: Alfredo Iturra)

Apenas una tarjeta entre a la columna **In Review / QA**, se iniciará el proceso de revisión:

1.  **Testing Local:** Alfredo descargará la rama correspondiente en su entorno local para realizar pruebas de caja negra, validación de inputs y manejo de errores (ej. simulación de timeouts).
    ```bash
    git fetch origin
    git checkout feat/hdu1-frontend-form
    ```
2.  **Revisión de Código:** Se revisará la limpieza del código en la pestaña **Files changed** del PR en GitHub.
3.  **Dictamen:**
    * Si hay fallas, Alfredo comentará las líneas afectadas y seleccionará **Request changes** (vuelve a desarrollo).
    * Si cumple los criterios de aceptación, Alfredo seleccionará **Approve**.
4.  **Cierre (Merge):** Con el visto bueno de QA, el Scrum Master (Luis) o el Tech Lead (Benjamín) presionarán **Merge pull request**. 
    * *El código se unirá a `develop`, la rama temporal se borrará y la tarjeta pasará automáticamente a **Done**.*
