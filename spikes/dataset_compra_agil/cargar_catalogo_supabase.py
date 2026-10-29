"""
Carga el catálogo del benchmark temporal (1.176 Compras Ágiles) en una base de PRUEBA.

No se conecta a Postgres: genera SQL que se aplica por el MCP de Supabase, y por separado
indexa los vectores en el Qdrant local. Replica lo que hace `TenderIngestionUseCase` para
que las filas y los puntos sean indistinguibles de una ingesta real:
  * mismas tablas (buyer_institution, tender, tender_item) y mismos campos,
  * mismo texto de embedding (TextBuilder.build_from_tender) y mismo modelo (BGE-M3 local),
  * mismo payload en Qdrant (status_code, region_id, provincia_id, comuna_id, monto, fechas).

Diferencias deliberadas, solo aceptables en una base de prueba:
  * El id de cada licitación es uuid5(código) y no uuid4, para que el SQL (aplicado por MCP)
    y el punto de Qdrant (escrito desde esta máquina) coincidan sin leer la base.
  * Las OCs ya están adjudicadas; para que el matching las muestre se guardan como
    "publicada" (status_id=2) con cierre en el futuro (hoy + 7..30 días).

Uso:
  python cargar_catalogo_supabase.py sql        -> data/temporal/supabase_sql/*.sql (seed + datos en lotes)
  python cargar_catalogo_supabase.py rest       -> inserta por la API REST (SUPABASE_URL + SUPABASE_PUBLISHABLE_KEY)
  python cargar_catalogo_supabase.py qdrant     -> upsert de los 1.176 vectores en el Qdrant de settings
"""

import asyncio
import json
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "monorepo" / "backend"
sys.path.insert(0, str(BACKEND))

from app.application.services.text_builder import TextBuilder  # noqa: E402
from app.shared.comunas import CHILE_COMUNAS, CHILE_PROVINCIAS, resolve_comuna  # noqa: E402
from app.shared.constants import TENDER_STATUS_CODE_BY_ID  # noqa: E402
from app.shared.datetime_utils import to_utc_epoch  # noqa: E402
from app.shared.regions import (  # noqa: E402
    CHILE_REGIONS,
    UNKNOWN_REGION_ID,
    UNKNOWN_REGION_NAME,
    normalize_region_name,
    region_id_by_name,
)

TEMP = ROOT / "spikes" / "dataset_compra_agil" / "data" / "temporal"
OUT = TEMP / "supabase_sql"
NS = uuid.UUID("6f1c2a3e-8d4b-4c5a-9e7f-0a1b2c3d4e5f")  # namespace fijo para ids reproducibles
STATUS_PUBLICADA = 2
LOTE = 150  # licitaciones por archivo SQL


def q(v: Optional[str]) -> str:
    if v is None:
        return "NULL"
    return "'" + str(v).replace("'", "''") + "'"


def num(v: Optional[float]) -> str:
    return "NULL" if v is None else repr(float(v))


def ts(d: datetime) -> str:
    return "'" + d.strftime("%Y-%m-%d %H:%M:%S") + "'"


def leer_ocs() -> Dict[str, Dict[str, Any]]:
    ocs = {}
    for nombre in ("ocs_detalle.jsonl", "ocs_proveedores_detalle.jsonl"):
        p = TEMP / nombre
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                ocs[r["codigo"]] = r["oc"]
    return ocs


def construir() -> List[Dict[str, Any]]:
    """Registros listos para SQL y Qdrant, uno por licitación del catálogo."""
    catalogo = json.loads((TEMP / "catalogo_temporal.json").read_text(encoding="utf-8"))
    ocs = leer_ocs()
    comuna_id_by_name = {name: cid for cid, (name, _p) in CHILE_COMUNAS.items()}
    provincia_id_by_name = {name: pid for pid, (name, _r) in CHILE_PROVINCIAS.items()}
    tb = TextBuilder()
    # La fecha base se fija en la primera corrida y se reutiliza: el cierre guardado en Postgres
    # (modo rest) y el del payload de Qdrant (modo qdrant, quizás otro día) tienen que coincidir.
    base_path = TEMP / "supabase_fecha_base.txt"
    if base_path.exists():
        ahora = datetime.fromisoformat(base_path.read_text(encoding="utf-8").strip())
    else:
        ahora = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
        base_path.write_text(ahora.isoformat(), encoding="utf-8")
    registros = []
    for n, d in enumerate(catalogo):
        oc = ocs[d["code"]]
        comprador = oc.get("Comprador") or {}
        items_raw = (oc.get("Items") or {}).get("Listado") or []
        if isinstance(items_raw, dict):
            items_raw = [items_raw]

        tender_id = uuid.uuid5(NS, d["code"])
        buyer_rut = (comprador.get("RutUnidad") or "").strip() or f"GENERIC-{d['code']}"
        buyer_name = (comprador.get("NombreOrganismo") or "Desconocido").strip()
        region_id = normalize_region_name(comprador.get("RegionUnidad")) or UNKNOWN_REGION_ID
        comuna_name, comuna_source = resolve_comuna(buyer_name, use_generic_fallback=False)
        comuna_id = comuna_id_by_name.get(comuna_name) if comuna_name else None
        provincia_id = provincia_id_by_name.get(CHILE_COMUNAS[comuna_id][1]) if comuna_id else None

        items = []
        for it in items_raw:
            items.append({
                "id": uuid.uuid5(NS, f"{d['code']}#{it.get('Correlativo')}#{len(items)}"),
                "product_code": str(it.get("CodigoProducto") or "0"),
                "name": (it.get("Producto") or "Sin nombre").strip(),
                "description": (it.get("EspecificacionComprador") or None),
                "quantity": float(it.get("Cantidad") or 1.0),
                "unit": (it.get("Unidad") or "UN") or "UN",
            })

        fechas = oc.get("Fechas") or {}
        publicada = datetime.fromisoformat((fechas.get("FechaEnvio") or fechas.get("FechaCreacion"))[:19])
        cierre = ahora + timedelta(days=7 + (n % 24))  # repartido entre 7 y 30 días

        class _T:  # lo mínimo que usa TextBuilder
            name = d["name"] or oc.get("Nombre") or d["code"]
            description = d["description"] or None

        class _I:
            def __init__(self, name, description):
                self.name, self.description = name, description

        texto = tb.build_from_tender(_T, [_I(i["name"], i["description"]) for i in items])
        registros.append({
            "tender_id": tender_id, "code": d["code"], "name": _T.name, "description": _T.description,
            "published_at": publicada, "closing_at": cierre, "now": ahora,
            "buyer_rut": buyer_rut, "buyer_name": buyer_name, "buyer_unit": (comprador.get("NombreUnidad") or "Sin Unidad").strip(),
            "region_id": region_id, "comuna_id": comuna_id, "provincia_id": provincia_id,
            "comuna_source": comuna_source if comuna_id else None,
            "amount": oc.get("TotalNeto"), "items": items, "texto": texto,
            "es_distractor": d.get("es_distractor", True),
        })
    return registros


def sql_seed() -> str:
    """Lo mismo que siembra `seed_database_metadata` al arrancar la API."""
    out = []
    regiones = {UNKNOWN_REGION_ID: UNKNOWN_REGION_NAME, **CHILE_REGIONS}
    out.append("INSERT INTO region (id, name) VALUES " + ", ".join(f"({i}, {q(n)})" for i, n in regiones.items())
               + " ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name;")
    out.append("INSERT INTO tender_status (id, code, name) VALUES "
               + ", ".join(f"({i}, {q(c)}, {q(c.replace('_', ' ').capitalize())})" for i, c in TENDER_STATUS_CODE_BY_ID.items())
               + " ON CONFLICT (id) DO UPDATE SET code = EXCLUDED.code, name = EXCLUDED.name;")
    out.append("INSERT INTO provincia (id, name, region_id) VALUES "
               + ", ".join(f"({pid}, {q(n)}, {region_id_by_name(r)})" for pid, (n, r) in CHILE_PROVINCIAS.items())
               + " ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, region_id = EXCLUDED.region_id;")
    prov_by_name = {n: pid for pid, (n, _r) in CHILE_PROVINCIAS.items()}
    out.append("INSERT INTO comuna (id, name, provincia_id) VALUES "
               + ", ".join(f"({cid}, {q(n)}, {prov_by_name[p]})" for cid, (n, p) in CHILE_COMUNAS.items())
               + " ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, provincia_id = EXCLUDED.provincia_id;")
    # Las secuencias SERIAL deben quedar por delante de los ids insertados a mano.
    for t in ("region", "tender_status", "provincia", "comuna"):
        out.append(f"SELECT setval(pg_get_serial_sequence('{t}', 'id'), (SELECT MAX(id) FROM {t}));")
    return "\n".join(out) + "\n"


def sql_lote(regs: List[Dict[str, Any]]) -> str:
    buyers: Dict[str, Dict[str, Any]] = {}
    for r in regs:
        buyers.setdefault(r["buyer_rut"], r)
    out = []
    out.append(
        "INSERT INTO buyer_institution (rut, name, region_id, comuna_id, comuna_resolution_source, created_at, updated_at) VALUES "
        + ", ".join(
            f"({q(b)}, {q(r['buyer_name'])}, {r['region_id']}, {r['comuna_id'] if r['comuna_id'] else 'NULL'}, "
            f"{q(r['comuna_source'])}, {ts(r['now'])}, {ts(r['now'])})"
            for b, r in buyers.items()
        )
        + " ON CONFLICT (rut) DO NOTHING;"
    )
    out.append(
        "INSERT INTO tender (id, code, name, description, status_id, published_at, closing_at, last_change_at, buyer_rut, buyer_unit, available_amount_clp, created_at, updated_at) VALUES "
        + ", ".join(
            f"('{r['tender_id']}', {q(r['code'])}, {q(r['name'])}, {q(r['description'])}, {STATUS_PUBLICADA}, "
            f"{ts(r['published_at'])}, {ts(r['closing_at'])}, {ts(r['now'])}, {q(r['buyer_rut'])}, {q(r['buyer_unit'])}, "
            f"{num(r['amount'])}, {ts(r['now'])}, {ts(r['now'])})"
            for r in regs
        )
        + " ON CONFLICT (code) DO NOTHING;"
    )
    filas_items = [
        f"('{i['id']}', '{r['tender_id']}', {q(i['product_code'])}, {q(i['name'])}, {q(i['description'])}, {num(i['quantity'])}, {q(i['unit'])})"
        for r in regs for i in r["items"]
    ]
    if filas_items:
        out.append("INSERT INTO tender_item (id, tender_id, product_code, name, description, quantity, unit_of_measure) VALUES "
                   + ", ".join(filas_items) + " ON CONFLICT (id) DO NOTHING;")
    return "\n".join(out) + "\n"


def generar_sql():
    regs = construir()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "00_seed.sql").write_text(sql_seed(), encoding="utf-8")
    n = 0
    for i in range(0, len(regs), LOTE):
        n += 1
        (OUT / f"{n:02d}_datos.sql").write_text(sql_lote(regs[i:i + LOTE]), encoding="utf-8")
    tam = sum(p.stat().st_size for p in OUT.glob("*.sql"))
    print(f"{len(regs)} licitaciones, {sum(len(r['items']) for r in regs)} partidas, "
          f"{len({r['buyer_rut'] for r in regs})} compradores -> {n} lotes ({tam / 1024:.0f} KB) en {OUT}")


def cargar_rest():
    """Inserta por la API REST (PostgREST) con la publishable key.

    Las tablas tienen RLS: requiere políticas INSERT temporales para `anon` en
    buyer_institution, tender y tender_item mientras dura la carga (y quitarlas al final).
    Lee SUPABASE_URL y SUPABASE_PUBLISHABLE_KEY del entorno; no las guarda en disco.
    """
    import os

    import httpx

    base = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1"
    headers = {
        "apikey": os.environ["SUPABASE_PUBLISHABLE_KEY"],
        "Content-Type": "application/json",
        # Sin resolution=ignore-duplicates: con RLS, el ON CONFLICT de PostgREST exige además
        # una política SELECT. Por eso la carga asume tablas vacías (no es reentrante).
        "Prefer": "return=minimal",
    }
    regs = construir()
    iso = lambda d: d.strftime("%Y-%m-%dT%H:%M:%S")  # noqa: E731

    buyers: Dict[str, Dict[str, Any]] = {}
    for r in regs:
        buyers.setdefault(r["buyer_rut"], {
            "rut": r["buyer_rut"], "name": r["buyer_name"], "region_id": r["region_id"],
            "comuna_id": r["comuna_id"], "comuna_resolution_source": r["comuna_source"],
            "created_at": iso(r["now"]), "updated_at": iso(r["now"]),
        })
    tenders = [{
        "id": str(r["tender_id"]), "code": r["code"], "name": r["name"], "description": r["description"],
        "status_id": STATUS_PUBLICADA, "published_at": iso(r["published_at"]), "closing_at": iso(r["closing_at"]),
        "last_change_at": iso(r["now"]), "buyer_rut": r["buyer_rut"], "buyer_unit": r["buyer_unit"],
        "available_amount_clp": r["amount"], "created_at": iso(r["now"]), "updated_at": iso(r["now"]),
    } for r in regs]
    items = [{
        "id": str(i["id"]), "tender_id": str(r["tender_id"]), "product_code": i["product_code"], "name": i["name"],
        "description": i["description"], "quantity": i["quantity"], "unit_of_measure": i["unit"],
    } for r in regs for i in r["items"]]

    with httpx.Client(timeout=120.0) as c:
        for tabla, filas in (("buyer_institution", list(buyers.values())), ("tender", tenders), ("tender_item", items)):
            for i in range(0, len(filas), 300):
                resp = c.post(f"{base}/{tabla}", headers=headers, json=filas[i:i + 300])
                if resp.status_code >= 300:
                    raise SystemExit(f"{tabla} lote {i}: HTTP {resp.status_code} {resp.text[:300]}")
            print(f"  {tabla}: {len(filas)} filas enviadas")


async def indexar_qdrant(solo_faltantes: bool = False):
    from qdrant_client import AsyncQdrantClient

    from app.bootstrap import MockEmbeddingService, build_embedding_service
    from app.config import settings
    from app.infrastructure.repositories.qdrant_tender_repository import QdrantTenderRepository

    regs = construir()
    client = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    repo = QdrantTenderRepository(client=client, vector_size=settings.embedding_vector_size)
    # Igual que el arranque de la API (main.py): colección e índices de payload antes de escribir.
    await repo.ensure_collection()
    # El mismo constructor que usa la API. En IS_DEV cae a MockEmbeddingService (vectores en cero)
    # si el modelo no carga: indexar eso dejaría Qdrant inservible, así que se aborta.
    svc = build_embedding_service()
    if isinstance(svc, MockEmbeddingService):
        raise SystemExit("build_embedding_service devolvió el mock: el modelo no cargó. No se indexa nada.")
    print(f"Embeddings: {type(svc).__name__} ({settings.embedding_provider}, {settings.embedding_model}) | Qdrant: {settings.qdrant_url}")
    # Lotes chicos y ordenados por largo: BGE-M3 rellena cada lote hasta el texto más largo
    # (hay partidas de >10.000 caracteres) y con lotes de 32 el proceso se cayó por memoria.
    # El upsert es idempotente (ids fijos), así que reintentar no duplica puntos.
    regs = sorted(regs, key=lambda r: len(r["texto"]))
    tam = 8
    if solo_faltantes:
        # Reanudar: se piden a Qdrant los ids ya indexados y se embebe de a uno lo que falta
        # (igual que la ingesta, que llama embed([texto]) por licitación).
        existentes = set()
        ids =[str(r["tender_id"]) for r in regs]
        for i in range(0, len(ids), 256):
            for p in await client.retrieve(collection_name="tenders", ids=ids[i:i + 256], with_payload=False, with_vectors=False):
                existentes.add(str(p.id))
        regs = [r for r in regs if str(r["tender_id"]) not in existentes]
        tam = 1
        print(f"Ya indexadas: {len(existentes)} | faltan: {len(regs)}")
    for i in range(0, len(regs), tam):
        lote = regs[i:i + tam]
        vecs = await svc.embed([r["texto"] for r in lote])
        for r, v in zip(lote, vecs):
            await repo.upsert(
                tender_id=r["tender_id"],
                embedding=v,
                payload={
                    "status_code": TENDER_STATUS_CODE_BY_ID[STATUS_PUBLICADA],
                    "region_id": r["region_id"],
                    "provincia_id": r["provincia_id"],
                    "comuna_id": r["comuna_id"],
                    "available_amount_clp": r["amount"],
                    "closing_at": to_utc_epoch(r["closing_at"]),
                    "published_at": to_utc_epoch(r["published_at"]),
                },
            )
        if (i // tam) % 10 == 0 or i + tam >= len(regs):
            print(f"  indexadas {min(i + tam, len(regs))}/{len(regs)}")
    print("Listo.")


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else "sql"
    if modo == "sql":
        generar_sql()
    elif modo == "rest":
        cargar_rest()
    elif modo == "qdrant":
        asyncio.run(indexar_qdrant(solo_faltantes="--faltantes" in sys.argv))
    else:
        print(__doc__)
