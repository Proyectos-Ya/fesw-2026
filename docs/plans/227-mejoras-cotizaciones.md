# Plan Técnico: cantidades, importes CLP y PDF de cotizaciones

**Issue asociada**: Refs #227 (continuación solicitada por el usuario)  
**Estado**: Completado (plan aprobado por el usuario)  
**Fecha**: 2026-10-06

## 1. Contexto y Objetivo

Extender las cotizaciones actuales de develop según los ajustes solicitados. Implementación en rama separada basada en develop.

## 2. Decisiones Técnicas y Arquitectura

- Completar cantidades desde los ítems estructurados de la licitación cuando sean enteras y positivas. Mantenerlas editables; si faltan, dejar el campo vacío. Si el origen contiene una cantidad fraccionaria, informar que debe indicarse una cantidad entera y dejar pendiente su corrección, sin redondearla automáticamente. Una cotización guardada tiene prioridad sobre los datos de la licitación.
- Señalar descripción, unidad, cantidad y precio como obligatorios con texto visible y atributos accesibles. Mantener mensajes específicos al guardar o exportar.
- Exigir cantidades enteras mayores que cero y precios unitarios en pesos enteros mayores o iguales a cero, tanto en frontend como en API. Rechazar valores fraccionarios al guardar o exportar.
- Calcular cada subtotal como cantidad por precio unitario y sumar esos subtotales para el total, sin redondeo porque ambos factores son enteros. Usar aritmética exacta en backend y BigInt en frontend. Mostrar cantidades e importes CLP sin decimales en pantalla, CSV y PDF.
- Conservar lectura de cotizaciones antiguas. Si contienen cantidades o precios fraccionarios, pedir revisión antes de guardar o exportar, sin modificar silenciosamente los valores almacenados. No se prevé cambiar el esquema de base de datos.
- Añadir descarga directa de PDF, conservando CSV. Guardar y validar primero; generar el documento desde la respuesta guardada. Incluir licitación, identificación disponible de empresa, fecha, materiales, unidades, cantidades, precios, subtotales, total y nota sobre impuestos y recargos.
- Encapsular la generación PDF en la feature quotations. Usar jsPDF 4.2.1 y jsPDF-AutoTable 5.0.8; cargarla solo al exportar. El documento deberá admitir tildes, descripciones largas, hasta 200 materiales y paginación con encabezados repetidos.

## 3. Desglose de Tareas

### Backend
- [x] Pruebas de cantidades y precios enteros, rechazo de fracciones, cálculo exacto y lectura de datos anteriores.
- [x] Implementar validación de escritura y cálculo consistente sin romper la lectura histórica.

### Frontend
- [x] Pruebas de precarga, campos obligatorios, rechazo de fracciones, cálculo exacto y cotizaciones guardadas.
- [x] Implementar precarga de cantidades y presentación de importes enteros.
- [x] Implementar descarga PDF y conservar CSV con los mismos importes.
- [x] Verificar errores de guardado/exportación y conservación del borrador.

## 4. Plan de Verificación y Pruebas

Desde backend: `pytest`. Desde frontend: `pnpm run test`, `pnpm exec tsc --noEmit` y el flujo Playwright de cotizaciones disponible en package.json. Verificar escritorio y móvil; descargar y revisar visualmente PDF corto y de varias páginas, con acentos y descripciones largas. Comprobar que el total coincida entre API, pantalla, CSV y PDF. Registrar cualquier limitación de entorno y no presentar comprobaciones pendientes como aprobadas.

## 5. Evidencia y límites

- Base: develop local b84771c; rama `227-mejoras-cotizaciones-enteros-pdf` en copia local independiente por permisos de Windows en el .git original.
- Backend: 1881 pruebas aprobadas, 162 excluidas con `-m "not integration and not network"`. Lectura histórica y persistencia probadas con SQLite. No se ejecutaron servicios reales de PostgreSQL/Supabase.
- Frontend: suite completa de 695 pruebas aprobada; después, las 20 pruebas de cotizaciones aprobadas (incluyen dos casos adicionales de normalización y fallo al guardar para PDF). TypeScript y lint de archivos modificados sin errores.
- Compilación Next de producción aprobada con variables públicas de prueba y BACKEND_ORIGIN local; no es un despliegue ni prueba de autenticación real.
- Playwright: 4 casos aprobados entre escritorio y móvil, con API simulada. Descarga CSV y PDF corto y de 200 materiales comprobada. El proceso servidor de pruebas se detuvo después de completar los casos.
- Revisión visual: formulario móvil y PDF corto; primera y última página del PDF largo (51 páginas) con tildes, encabezados y total legibles.
- Sin cambios de esquema ni migraciones nuevas. No se modificaron datos locales ni remotos.
- Dependencias PDF: carga diferida en navegador, sin servicios externos. Documentación consultada: https://github.com/parallax/jsPDF y https://github.com/simonbengtsson/jsPDF-AutoTable .
