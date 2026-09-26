# Referencia: Cómo Generar un Changelog de Sprint

Al cierre de cada sprint se consolida el avance realizado en `docs/changelogs/sprint-<N>.md`.

---

## Procedimiento Paso a Paso

1. **Obtener las Fechas y Rango del Sprint**:
   - Solicita al equipo las fechas de inicio y término del sprint correspondiente.

2. **Recopilar los Pull Requests Mergeados**:
   - Utiliza GitHub CLI para listar los PRs integrados en `develop` dentro de ese rango:
     ```bash
     gh pr list --state merged --base develop --search "merged:YYYY-MM-DD..YYYY-MM-DD" --json number,title,body
     ```

3. **Revisar Commits Directos (si hubiese)**:
   - Inspecciona el historial de git en busca de commits que no formaron parte de un PR:
     ```bash
     git log --oneline --since="YYYY-MM-DD" --until="YYYY-MM-DD"
     ```

4. **Crear el Archivo**:
   - Copia la plantilla [plantilla-changelog.md](../assets/plantilla-changelog.md) a:
     `docs/changelogs/sprint-<N>.md`
   - Ejemplo: `docs/changelogs/sprint-1.md`.

5. **Redactar las Dos Secciones Principales**:
   - **Para Usuarios / Negocio**: Lenguaje claro, orientado a valor y libre de jerga técnica excesiva. Explica qué nuevas funcionalidades o mejoras pueden utilizar ahora.
   - **Técnico (Desarrollo)**: Lista clasificada por tipo de commit convencional (`feat`, `fix`, `refactor`, `perf`, `chore`), referenciando los números de PR (`#NNN`) e issues asociadas.

6. **Revisión y Publicación**:
   - Solicita la confirmación del equipo antes de commitear el documento final.
