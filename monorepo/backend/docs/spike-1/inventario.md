# Corpus del Spike 1 — inventario y cómo conseguirlo

Fase 0 de [#156](https://github.com/Proyectos-Ya/fesw-2026/issues/156) y
[#157](https://github.com/Proyectos-Ya/fesw-2026/issues/157).

Ambas sub-áreas piden **medir tasas de éxito** sobre documentos reales. Sin corpus no hay
medición y el spike no concluye nada, así que conseguirlo es el primer bloqueante.

---

## Hallazgo 1 — La API **no** permite descargar los documentos de una licitación

**Fecha:** 23 de agosto de 2026 · **Estado:** cerrado, con evidencia.

La API de Compra Ágil **sí lista** los adjuntos de cada licitación:

```json
"documentos": [{ "id": 1815870, "nombre": "REQUERIMIENTO PLATOS_PREPARADOS_CAFETERIA.pdf" }]
```

Aparecen en 13 de 20 licitaciones muestreadas, y el campo viene tanto en el listado como en
el detalle. Los nombres confirman que hay material útil: `BASES (5).pdf`,
`ADJUNTO TÉCNICO.docx`, `EETT_SERV PRODUCCION.pdf`.

**Pero no hay forma de obtener el contenido.** Tres verificaciones independientes:

1. **No hay ninguna URL en el payload.** Se recorrió la respuesta completa del detalle
   (7.094 caracteres) buscando URLs absolutas y cualquier campo cuyo nombre contuviera
   `url`, `link`, `href`, `descarga`, `download`, `ruta`, `path`, `archivo` o `file`.
   Resultado: **ninguno**. El objeto documento es literalmente `{id, nombre}` y nada más.

2. **Doce rutas probadas, todas inexistentes.** Se distinguió el 403 del gateway
   (`{"message":"Missing Authentication Token"}`, que AWS API Gateway devuelve para rutas
   que no existen) de un error propio de la API. Las doce cayeron en el primer caso:

   ```
   /v2/compra-agil/{codigo}/documentos          /v2/documento/{id}
   /v2/compra-agil/{codigo}/documentos/{id}     /v2/documentos/{id}
   /v2/compra-agil/{codigo}/documento/{id}      /v2/adjuntos/{id}
   /v2/compra-agil/{codigo}/adjuntos/{id}       /v2/archivos/{id}
   /v2/compra-agil/{codigo}/archivos/{id}       /v2/files/{id}
   /v2/compra-agil/documento/{id}               /v2/compra-agil/{codigo}/documentos/{id}/descargar
   ```

3. **La guía oficial lo confirma.** *Documentación API Compra Ágil* declara que la API
   expone **exactamente dos endpoints**:

   | Endpoint | Qué hace |
   |---|---|
   | `GET /v2/compra-agil` | Listado y búsqueda con filtros |
   | `GET /v2/compra-agil/{codigo}` | Detalle de una Compra Ágil |

   Describe `documentos[].id` como *"identificador del documento adjunto"* pero **ningún
   endpoint lo consume**.

**La API de licitaciones tampoco sirve.** Sus únicas menciones a "documento" son metadatos
del acto administrativo de adjudicación (tipo, fecha, número), no adjuntos. Su detalle de
54 campos no tiene ninguno de archivos.

**Discrepancia menor, anotada por si confunde a alguien:** la guía declara
`documentos[].id` como `string (UUID)`, pero la API real devuelve un **entero**
(`1815870`).

### Consecuencia

El corpus de bases y anexos **no se puede automatizar con la API**. Queda:

| Vía | Evaluación |
|---|---|
| **Portal web, manual** | Viable para armar una muestra de 20-30. Es lo recomendado para el spike |
| Portal web, automatizado | Es scraping. Sirve para el spike, **no** como mecanismo de producción |
| Consultar a ChileCompra | Vale la pena preguntar si existe un canal oficial; respuesta lenta pero cierra el tema |

> **Esto afecta más allá del spike.** Las HdU 04, 05.1 y 05.2 —18 SP del Sprint 1— asumen
> un asistente que responde citando las bases. Si los documentos solo se obtienen a mano,
> esas historias no tienen cómo alimentarse en producción. Hay que levantarlo con el
> equipo, no dejarlo solo acá.

---

## Hallazgo 2 — Sí existe consulta oficial de empresa por RUT

**Estado:** resuelto para identidad, pendiente para vigencia. Detalle en `1.1-onboarding.md`.

`GET /servicios/v1/Publico/Empresas/BuscarProveedor?rutempresaproveedor=76.086.428-5`
devuelve el nombre de la empresa, usando el mismo ticket del proyecto. El RUT **debe ir
con puntos**; sin ellos responde lo mismo que para una empresa inexistente.

Cubre 2 de 10 campos del perfil y **no entrega vigencia**.

---

## Inventario del corpus

Se completa a medida que se consiguen los documentos. Etiquetas de calidad:

| Etiqueta | Qué es |
|---|---|
| `digital` | PDF con capa de texto — se lee sin OCR |
| `escaneado-limpio` | imagen nítida y derecha |
| `escaneado-malo` | torcido, con ruido, baja resolución, foto de celular |

**Meta:** ~30 documentos con presencia de las tres categorías. Con menos de ~20 la tasa de
éxito no es representativa.

| # | Archivo | Tipo | Origen | Calidad | Datos esperados (etiquetados a mano) |
|---|---|---|---|---|---|
| — | *(pendiente)* | | | | |

Tipos a cubrir: **bases de licitación** (para derivar qué documentos se exigen), **E-RUT**,
**certificado de vigencia**.

> **Privacidad:** un E-RUT o un certificado llevan datos de una empresa real. Los archivos
> de `corpus/` **no se versionan** (ver `.gitignore` de esta carpeta); en el repo queda
> solo este inventario. Preferir documentos del propio equipo.
