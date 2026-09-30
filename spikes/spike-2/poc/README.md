# spike-2 · PoC de volumetría

El arnés **no vive acá**: es `monorepo/backend/scripts/volumetria_api.py`, dentro
del backend, porque reutiliza `MercadoPublicoClient` —con sus reintentos y su
manejo de 429— en vez de hablar con la API por su cuenta. Duplicarlo habría sido
la forma de que la volumetría midiera una ventana distinta de la que se ingesta.

Este directorio guarda solo las salidas de las corridas, que **no se versionan**
(ver `.gitignore`). Las cifras y su lectura están en `../2.1-volumetria-ingesta.md`.

## Reproducir

Desde `monorepo/backend`, con el ticket en el entorno:

```bash
# Serie por publicación, retroactiva: 14 días en 28 peticiones
MERCADO_PUBLICO_API_KEY=... python -m scripts.volumetria_api \
    --dias-atras 14 --sin-relativas > ../../spikes/spike-2/poc/muestras-publicacion.jsonl

# Corrida diaria completa: agrega las series por cambio, que no son retroactivas
MERCADO_PUBLICO_API_KEY=... python -m scripts.volumetria_api --dias-atras 2
```
