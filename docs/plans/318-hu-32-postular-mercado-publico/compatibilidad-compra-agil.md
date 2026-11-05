# Compatibilidad del formulario actual de Compra Ágil

Refs #318 · Alcance del ajuste pendiente de revisión humana

En la cotización 5626-943-COT26, la ficha aparece antes que la sección «Participar de la Compra Ágil». El código figura en un h2 sin ID, y los campos de precio y detalle observados no tienen name ni IDs estables. La vigencia tiene un ID generado y el adjunto usa un input de archivo sin nombre. El adaptador actual busca selectores del formulario clásico y el content script decide si es un formulario una sola vez al arrancar.

REA analizó el content script compilado de Firefox de forma estática (evidencia ev_e76e103e0b517ceb99f793d0e64f99009264f1632330a47a58a9f3003ac5188b). El DOM y la captura de la cotización proceden de la sesión del navegador. La observación no comprobó el autocompletado ni el origen del RUT de la empresa de la sesión.

1. Para códigos COT, abrir la ruta de detalle observada en compra-agil.mercadopublico.cl cuando falte una URL explícita. Conservar la ruta existente para los demás casos y comprobar qué ocurre al volver del inicio de sesión.
2. Reconocer la ruta, validar su código contra el encabezado y esperar de forma acotada a que aparezca la sección de participación. Limpiar la observación al vencer el plazo o cambiar de ruta. Mantener los selectores clásicos como un camino separado.
3. Identificar controles por su contexto visible y los ítems por el ID de producto solo cuando sea inequívoco. Dejar pendientes los controles ambiguos o sin correspondencia. Validar que la aplicación acepte el cambio y recalcule antes de marcar un campo como completado.
4. Verificar una fuente del RUT de la empresa de la sesión. La ficha muestra el RUT del comprador y no sirve para esta validación. Mantener el bloqueo por discrepancia y no habilitar el llenado de Compra Ágil mientras la identidad de sesión no se pueda verificar.
5. Primero reproducir la falla con una fixture reducida y saneada. Cubrir hidratación tardía, código incorrecto, identidad no verificada, campos ambiguos y conservación del formulario clásico. Luego comprobar en una extensión cargada que los controles de la página reaccionen y que el envío siga siendo manual.
