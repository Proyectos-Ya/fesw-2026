# Referencia: Cómo Redactar un Registro de Decisión Arquitectónica (ADR)

Un Architecture Decision Record (ADR) documenta una decisión técnica de diseño que tiene un impacto a largo plazo en la arquitectura o es costosa de revertir.

---

## ¿Cuándo Amerita un ADR?

Escribe un ADR cuando un cambio:
- Modifique la estructura de capas (Clean Architecture en backend o Screaming en frontend).
- Incorpore o reemplace una dependencia o servicio de infraestructura clave (ej. motor vectorial, proveedor de auth, base de datos).
- Introduzca un nuevo patrón de diseño transversal (ej. streaming, manejo global de errores, estrategia de caché).
- Defina políticas estrictas de seguridad o límites de cuotas de APIs externas.

*No amerita ADR*: Tareas rutinarias como agregar un nuevo endpoint estándar, corregir un bug o añadir componentes visuales que siguen patrones existentes.

---

## Procedimiento Paso a Paso

1. **Determinar la Numeración**:
   - Revisa los archivos existentes en `docs/decisions/` para encontrar el siguiente número correlativo de 4 dígitos (ejemplo: `0001`, `0002`, `0003`).

2. **Crear el Archivo**:
   - Copia la plantilla [plantilla-adr.md](../assets/plantilla-adr.md) a:
     `docs/decisions/<NNNN>-<slug>.md`
   - Ejemplo: `docs/decisions/0001-seleccion-motor-vectorial.md`.

3. **Completar las Secciones**:
   - **Título**: Claro y específico.
   - **Estado**: `Propuesto`, `Aceptado`, `Rechazado` o `Reemplazado por [ADR-XXXX]`.
   - **Contexto**: El problema que motiva la decisión y las restricciones existentes.
   - **Decisión**: La solución elegida con su debida justificación técnica.
   - **Alternativas Consideradas**: Opciones evaluadas y las razones de su descarte.
   - **Consecuencias**: Beneficios, riesgos, costos y compromisos aceptados (*trade-offs*).

4. **Actualizar el Índice**:
   - Agrega la entrada correspondiente en [docs/README.md](../../../docs/README.md).
