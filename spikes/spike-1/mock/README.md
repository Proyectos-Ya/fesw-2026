# SPIKE 1.3 — Mock de comparación documental

Prototipo independiente: no está conectado al backend ni al frontend del repositorio.
No modifica PostgreSQL, Supabase, Docker ni la rama actual. Solo usar localmente.

## Ejecutar en Windows

Abra PowerShell en esta carpeta. Requiere Python 3.12 o posterior.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe mock_api.py
```

No necesita activar el entorno ni cambiar la política de ejecución de PowerShell.
Si ya tiene un entorno con FastAPI y Uvicorn, puede usarlo sin crear otro.

Abra http://127.0.0.1:8013/docs para explorar los endpoints. En cada petición
protegida use el mismo `X-Demo-User`, por ejemplo
`11111111-1111-1111-1111-111111111111`.
Es una identidad **simulada y falsificable**, no autenticación real.

## Probar por HTTP sin pytest

Con la API corriendo, abra una segunda terminal en esta carpeta:

```powershell
python probar_mock.py --escenario completa
python probar_mock.py --escenario vencido
python probar_mock.py --escenario sin-firma
python probar_mock.py --escenario faltante
python probar_mock.py --escenario ilegible
python probar_mock.py --escenario revision
python probar_mock.py --escenario error
```

El script solo usa la biblioteca estándar. Crea un expediente nuevo en cada
ejecución, genera y sube PDFs de muestra, procesa bases, confirma requisitos,
sube propuesta y consulta el reporte. Termina con código 1 si no se obtiene
lo esperado. Estos son smoke tests del contrato HTTP del mock, no pruebas de
integración con Mercado Público, OCR ni la base de datos real.

## Contrato del flujo

Todas las rutas están bajo `/mock` para distinguirlas del producto.

1. `POST /mock/expedientes` con `{"name":"Demo"}`.
2. `POST /mock/expedientes/{id}/uploads`: registre cada archivo con `kind`,
   `fixture`, `filename`, `size_bytes` y, opcionalmente, `checksum_sha256`.
3. `PUT` a la `upload_url` devuelta con los bytes PDF como cuerpo, no multipart.
4. `POST /mock/expedientes/{id}/process` con `{"kind":"bases"}`.
5. Consulte dos veces la `job_url`: primero `processing`, luego `completed`.
   El resultado contiene requisitos y evidencias simuladas.
6. `POST /mock/expedientes/{id}/requirements/confirm` con la `version`
   exacta de bases procesada. En esta demo solo se confirma, no se editan requisitos.
7. Repita registro, carga y procesamiento con `kind: "propuesta"`.
8. `POST /mock/expedientes/{id}/evaluations` y consulte la `job_url` dos veces.

`GET /mock/fixtures` enumera las extracciones disponibles. Para bases use
`bases_demo`; para propuesta use los nombres mostrados por ese endpoint.
El fixture se elige explícitamente en los metadatos: **el contenido del PDF
no determina el resultado**. Los textos, páginas y firmas son evidencia ficticia.
Aunque se pueden cargar varias bases, el fixture devuelve dos requisitos fijos
con referencia al primer archivo; no interpreta ni consolida anexos reales.

## Requisitos simulados

- R1: certificado vigente al cierre fijo **15/10/2026**. No se compara con hoy.
- R2: declaración jurada con presencia de firma.

Las reglas comparan fechas y campos de las extracciones simuladas; no limitan
el reporte a devolver un resultado global prefijado. Estados: `cumple`,
`no_cumple`, `faltante`, `requiere_revision` y `no_evaluable`.
Si hay archivos ilegibles que podrían cubrir un requisito, no se declara
automáticamente que falta. Varios documentos del mismo tipo requieren revisión.

## Versiones, fallos y reemplazos

- Registrar un archivo incrementa la versión de su grupo e invalida su procesamiento.
- Cambiar bases también invalida su confirmación.
- Para reemplazar, incluya `replaces_document_id` en el registro de la nueva carga.
  El anterior queda inactivo pero conserva sus metadatos. Termine la nueva carga
  y vuelva a procesar; si son bases, vuelva a confirmar antes de evaluar.
- Los reportes anteriores conservan sus versiones exactas y no se sobrescriben.
- `simulate_failure: true` en `/process` produce un trabajo fallido. Puede
  solicitar otro con `false`. No hay reintentos automáticos ni worker real.
- Una extracción antigua no marca como lista una versión posterior.
- Reiniciar el proceso borra expedientes, metadatos, trabajos y reportes.

## Qué se prueba y qué no

Se prueba: secuencia HTTP, validación de metadatos/cabecera/tamaño/hash, reglas
sobre datos simulados, estados, errores, separación por identidad de demo,
confirmación, invalidación de versiones y reportes con referencias de evidencia.

No se implementa: OCR, IA, almacenamiento persistente, cola/worker real,
autenticación del producto, revisión humana editable, firma criptográfica,
validación de identidad, antivirus ni validación estructural completa de PDFs.
La firma visible no demuestra autenticidad y el reporte no certifica admisibilidad.
Los bytes recibidos se descartan tras verificar tamaño, cabecera y hash.

La extracción y comparación se calculan dentro del proceso; la asincronía
solo se simula mediante consultas de estado. Use **un proceso**, sin múltiples
workers. No despliegue esta aplicación ni monte sus rutas en producción.

Límites de demo: 5 MiB por carga, 20 registros por expediente, 100 expedientes
y 1000 trabajos por proceso. Reinicie para limpiar el estado.

## Pruebas automatizadas del prototipo

Opcionales; tampoco requieren pytest:

```powershell
.\.venv\Scripts\python.exe -m pip install httpx
.\.venv\Scripts\python.exe -m unittest test_mock -v
```

`mock_api.py` implementa el contrato HTTP y el coordinador simulado.
`engine.py` separa fixtures de extracción y reglas de comparación.
`test_mock.py` comprueba el contrato en memoria, y `probar_mock.py` usa HTTP real.

Verificación realizada: 11 pruebas automatizadas correctas y los 7 escenarios
del script correctos contra un servidor HTTP local. No se ejecutaron pruebas
del repositorio ni de proveedores externos porque el prototipo es independiente.
