import asyncio
import json
import os
import sys
import time
from typing import Any
from uuid import UUID, uuid4

# Asegurar que el directorio raíz de backend esté en sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Forzar UTF-8 en Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import asyncpg
from qdrant_client import AsyncQdrantClient
from sentence_transformers import SentenceTransformer

from app.application.services.text_builder import TextBuilder
from app.domain.entities.supplier import Supplier
from app.domain.entities.tender import Tender, TenderItem
from app.infrastructure.services.bge_reranker_service import BgeRerankerService
from app.infrastructure.services.field_weighting_service import FieldWeightingService
from app.shared.regions import are_regions_matching

# ==========================================================
# 1. CONFIGURACIÓN
# ==========================================================
PG_HOST = os.getenv("POSTGRES_HOST", "172.29.211.10")
PG_PORT = int(os.getenv("POSTGRES_PORT", 5432))
PG_USER = os.getenv("POSTGRES_USER", "proyectosya")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "proyectosya_secret")
PG_DB = os.getenv("POSTGRES_DB", "proyectosya_db")

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
COLLECTION_NAME = "tenders"

MODEL_NAME = "BAAI/bge-m3"

# ==========================================================
# 2. DEFINICIÓN DE LOS 10 PERFILES DE PROVEEDORES
# ==========================================================
PROFILES: list[dict[str, Any]] = [
    {
        "rut": "78.333.444-5",
        "legal_name": "Constructora e Ingeniería Alianza Ltda.",
        "trade_name": "Alianza Obras Civiles",
        "description": "Ejecución de obras menores de construcción, pintura de edificios públicos, mantención de techumbres, reparaciones eléctricas, gasfitería y mejoramiento de espacios comunitarios.",
        "regions": [
            "Región del Biobío",
            "Región de La Araucanía",
            "Región de Los Ríos",
            "Región de Valparaíso",
            "Región Metropolitana de Santiago",
        ],
        "sectors": ["Construcción", "Obras Menores", "Mantención de Infraestructura"],
        "keywords": [
            "construcción",
            "pintura",
            "techumbre",
            "reparación",
            "gasfitería",
            "obras civiles",
            "pavimentación",
        ],
        "certificaciones": ["Registro MOP Contratistas Menores"],
    },
    {
        "rut": "76.111.222-8",
        "legal_name": "TecnoCloud SpA",
        "trade_name": "TecnoCloud Soluciones Digitales",
        "description": "Empresa especializada en desarrollo de software a medida, aplicaciones web, soluciones cloud en AWS/Azure, ciberseguridad y soporte de infraestructura TI.",
        "regions": [
            "Región Metropolitana de Santiago",
            "Región de Valparaíso",
            "Región de Los Ríos",
        ],
        "sectors": ["Desarrollo de Software", "Informática", "Telecomunicaciones"],
        "keywords": [
            "software",
            "cloud",
            "desarrollo web",
            "licencias",
            "servidor",
            "soporte ti",
            "ciberseguridad",
        ],
        "certificaciones": ["AWS Certified Solutions Architect", "ISO 27001"],
    },
    {
        "rut": "77.222.333-1",
        "legal_name": "Distribuidora Médica del Sur SpA",
        "trade_name": "MediSur Insumos Clínicos",
        "description": "Importación y comercialización de insumos médicos descartables, material de curación, jeringas, guantes quirúrgicos y equipamiento de diagnóstico menor para hospitales y CESFAM.",
        "regions": [
            "Región de Valparaíso",
            "Región Metropolitana de Santiago",
            "Región de Los Ríos",
        ],
        "sectors": ["Insumos Médicos", "Salud", "Farmacia y Hospitalario"],
        "keywords": [
            "insumos médicos",
            "guantes",
            "jeringas",
            "gasas",
            "mascarillas",
            "catéter",
            "oxímetro",
            "clínico",
        ],
        "certificaciones": ["Registro ISP Chile", "ISO 13485"],
    },
    {
        "rut": "79.444.555-9",
        "legal_name": "Química y Limpieza Total S.A.",
        "trade_name": "LimpiezaTotal Chile",
        "description": "Fabricación y distribución mayorista de productos químicos de aseo institucional, detergentes industriales, desinfectantes, papel higiénico, toallas de papel y útiles de aseo.",
        "regions": [
            "Región Metropolitana de Santiago",
            "Región de Los Lagos",
            "Región de Los Ríos",
        ],
        "sectors": ["Aseo e Higiene", "Productos Químicos", "Artículos de Limpieza"],
        "keywords": [
            "aseo",
            "limpieza",
            "detergente",
            "cloro",
            "papel higiénico",
            "desinfectante",
            "bolsas de basura",
            "mopas",
        ],
        "certificaciones": ["Resolución Sanitaria SEREMI de Salud"],
    },
    {
        "rut": "80.555.666-8",
        "legal_name": "Alimentos y Raciones del Sur SpA",
        "trade_name": "NutriSur Catering",
        "description": "Provisión de raciones alimenticias preparadas, servicios de catering para eventos públicos, suministro de abarrotes mayoristas, carnes y verduras para comedores institucionales y colegios.",
        "regions": ["Región de Los Lagos", "Región de Los Ríos", "Región de Aysén"],
        "sectors": ["Alimentación", "Catering", "Abarrotes", "Gastronomía"],
        "keywords": [
            "alimentos",
            "catering",
            "colaciones",
            "raciones",
            "abarrotes",
            "carnes",
            "desayunos",
            "frutas",
        ],
        "certificaciones": ["HACCP", "Resolución Sanitaria Alimentos"],
    },
    {
        "rut": "81.666.777-1",
        "legal_name": "Seguridad Integral y Vigilancia SpA",
        "trade_name": "SecuritasPro Chile",
        "description": "Servicios de guardias de seguridad privada acreditados OS-10, monitoreo de alarmas 24/7, instalación y mantención de sistemas de cámaras de televigilancia CCTV y control de acceso.",
        "regions": [
            "Región Metropolitana de Santiago",
            "Región de Valparaíso",
            "Región de Los Ríos",
        ],
        "sectors": ["Seguridad Privada", "Vigilancia", "Telecomunicaciones y CCTV"],
        "keywords": [
            "seguridad",
            "guardias",
            "cctv",
            "vigilancia",
            "alarmas",
            "cámaras",
            "control de acceso",
            "os-10",
        ],
        "certificaciones": ["Acreditación OS-10 Carabineros de Chile"],
    },
    {
        "rut": "82.777.888-5",
        "legal_name": "Comercial Papelería e Impresos Maule Ltda.",
        "trade_name": "MaulePapel & Oficina",
        "description": "Distribución de resmas de papel, cartuchos de tóner, útiles de oficina, archivadores, insumos para imprenta, mobiliario de oficina y equipamiento escolar.",
        "regions": [
            "Región del Maule",
            "Región Metropolitana de Santiago",
            "Región de Los Ríos",
        ],
        "sectors": [
            "Librería y Papelería",
            "Mobiliario y Oficina",
            "Insumos de Impresión",
        ],
        "keywords": [
            "papel",
            "resmas",
            "tóner",
            "librería",
            "oficina",
            "archivadores",
            "lápices",
            "cartuchos",
            "muebles",
        ],
        "certificaciones": [],
    },
    {
        "rut": "83.888.999-9",
        "legal_name": "ElectroNorte Suministros Eléctricos SpA",
        "trade_name": "ElectroNorte Ferretería Industrial",
        "description": "Venta mayorista de conductores eléctricos, cables de cobre, luminarias LED de alumbrado público, tableros eléctricos, herramientas manuales y materiales de ferretería pesada.",
        "regions": [
            "Región de Antofagasta",
            "Región de Tarapacá",
            "Región de Los Ríos",
        ],
        "sectors": ["Electricidad", "Ferretería", "Iluminación Pública"],
        "keywords": [
            "cables",
            "luminarias led",
            "tableros eléctricos",
            "ferretería",
            "conductores",
            "herramientas",
            "electricidad",
        ],
        "certificaciones": [
            "Certificación SEC (Superintendencia de Electricidad y Combustibles)"
        ],
    },
    {
        "rut": "84.999.000-4",
        "legal_name": "Transportes y Logística Ruta Chile SpA",
        "trade_name": "RutaChile Transportes",
        "description": "Servicios de transporte terrestre de pasajeros, traslado de funcionarios públicos y escolares en minibuses/buses, fletes de carga y arriendo de camionetas 4x4 con conductor.",
        "regions": ["Región de Coquimbo", "Región de Valparaíso", "Región de Los Ríos"],
        "sectors": ["Transporte y Logística", "Arriendo de Vehículos", "Fletes"],
        "keywords": [
            "transporte de pasajeros",
            "flete",
            "traslado",
            "arriendo de vehículos",
            "camionetas",
            "buses",
            "minibus",
        ],
        "certificaciones": ["Registro Nacional de Transporte Escolar y Turístico MTT"],
    },
    {
        "rut": "85.000.111-1",
        "legal_name": "Consultoría y Capacitaciones Talento Austral Ltda.",
        "trade_name": "TalentoAustral Consultores",
        "description": "Asesorías en gestión estratégica, diseño de proyectos públicos, auditorías contables y tributarias, capacitaciones laborales presenciales y e-learning bajo código SENCE.",
        "regions": [
            "Región de Los Lagos",
            "Región de Magallanes",
            "Región de Los Ríos",
        ],
        "sectors": ["Consultoría", "Capacitación", "Asesoría Legal y Financiera"],
        "keywords": [
            "capacitación",
            "consultoría",
            "asesoría",
            "cursos sence",
            "auditoría",
            "estudio",
            "taller",
        ],
        "certificaciones": [
            "Organismo Técnico de Capacitación (OTEC) acreditado SENCE",
            "NCh 2728",
        ],
    },
]


# ==========================================================
# 3. CONSULTA DE LICITACIONES
# ==========================================================
async def load_all_tenders_from_db() -> dict[UUID, Tender]:
    """Carga todas las licitaciones e ítems desde PostgreSQL (proyectosya_db)."""
    conn = await asyncpg.connect(
        database=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        host=PG_HOST,
        port=PG_PORT,
    )

    tenders_dict: dict[UUID, Tender] = {}

    try:
        select_sql = """
            SELECT 
                t.id AS tender_id,
                t.code AS tender_code,
                t.name AS tender_name,
                t.description AS tender_description,
                t.status_id,
                t.published_at,
                t.closing_at,
                t.last_change_at,
                t.buyer_rut,
                t.buyer_unit,
                t.available_amount_clp,
                t.created_at,
                t.updated_at,
                b.name AS buyer_name,
                r.name AS region_name,
                ti.id AS item_id,
                ti.product_code AS item_product_code,
                ti.name AS item_name,
                ti.description AS item_description,
                ti.quantity AS item_quantity,
                ti.unit_of_measure AS item_unit_of_measure
            FROM tender t
            LEFT JOIN buyer_institution b ON t.buyer_rut = b.rut
            LEFT JOIN region r ON b.region_id = r.id
            LEFT JOIN tender_item ti ON t.id = ti.tender_id
            ORDER BY t.created_at DESC;
        """
        rows = await conn.fetch(select_sql)

        for row in rows:
            t_id = row["tender_id"]
            if t_id not in tenders_dict:
                tenders_dict[t_id] = Tender(
                    id=t_id,
                    code=row["tender_code"] or str(t_id),
                    name=row["tender_name"] or "",
                    description=row["tender_description"],
                    status_id=row["status_id"] or 1,
                    status_code="publicada",
                    published_at=row["published_at"] or row["created_at"],
                    closing_at=row["closing_at"] or row["created_at"],
                    last_change_at=row["last_change_at"] or row["created_at"],
                    buyer_rut=row["buyer_rut"] or "60.000.000-1",
                    buyer_name=row["buyer_name"],
                    buyer_unit=row["buyer_unit"] or "",
                    region=row["region_name"],
                    available_amount_clp=float(row["available_amount_clp"])
                    if row["available_amount_clp"] is not None
                    else None,
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    items=[],
                )

            if row["item_id"] is not None:
                tenders_dict[t_id].items.append(
                    TenderItem(
                        id=row["item_id"],
                        tender_id=t_id,
                        product_code=row["item_product_code"] or "",
                        name=row["item_name"] or "",
                        description=row["item_description"],
                        quantity=float(row["item_quantity"])
                        if row["item_quantity"] is not None
                        else 1.0,
                        unit_of_measure=row["item_unit_of_measure"] or "UN",
                    )
                )

    finally:
        await conn.close()

    return tenders_dict


# ==========================================================
# 4. MOTOR DE EVALUACIÓN
# ==========================================================
async def evaluate_profile(
    supplier: Supplier,
    tenders_dict: dict[UUID, Tender],
    qdrant_client: AsyncQdrantClient,
    embed_model: SentenceTransformer,
    reranker: BgeRerankerService,
    weighter: FieldWeightingService,
    text_builder: TextBuilder,
    limit_candidates: int = 12,
    top_results: int = 3,
) -> dict[str, Any]:
    """Ejecuta el pipeline completo de matching híbrido optimizado para un perfil."""
    start_time = time.perf_counter()

    # 1. Construir query textual del proveedor
    supplier_full_text = text_builder.build_from_supplier(supplier)

    # 2. Generar embedding
    loop = asyncio.get_running_loop()
    query_vector = (
        await loop.run_in_executor(
            None,
            lambda: embed_model.encode([supplier_full_text], normalize_embeddings=True),
        )
    )[0].tolist()

    # 3. Búsqueda Vectorial en Qdrant
    res = await qdrant_client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        using="tender",
        limit=50,
    )

    valid_candidates = []
    hydrated_tenders: dict[UUID, Tender] = {}

    for p in res.points:
        uid = UUID(str(p.id))
        tender = tenders_dict.get(uid)
        if tender:
            # Filtro estricto por región canónica
            if supplier.regions and not are_regions_matching(
                tender.region, supplier.regions
            ):
                continue
            hydrated_tenders[uid] = tender
            valid_candidates.append((uid, float(p.score)))

    # Ordenar y acotar candidatos para el Reranker (Top 12)
    valid_candidates.sort(key=lambda x: x[1], reverse=True)
    top_candidates = valid_candidates[:limit_candidates]

    # 4. Preparar candidatos para Re-ranking
    rerank_pairs: list[tuple[UUID, str]] = []
    for uid, _ in top_candidates:
        tender = hydrated_tenders[uid]
        tender_text = text_builder.build_from_tender(tender=tender, items=tender.items)
        rerank_pairs.append((uid, tender_text))

    # 5. Ejecutar Re-ranking
    rerank_start = time.perf_counter()
    reranked = await reranker.rerank(
        query_text=supplier_full_text,
        candidates=rerank_pairs,
        limit=limit_candidates,
    )
    rerank_duration = time.perf_counter() - rerank_start
    rerank_map = {uid: score for uid, score in reranked}

    # 6. Ponderación Híbrida con Reglas de Negocio
    candidates_for_weighting = [
        (hydrated_tenders[uid], rerank_map.get(uid, 0.0))
        for uid, _ in top_candidates
        if uid in rerank_map
    ]

    final_weighted = weighter.calculate_scores(candidates_for_weighting, supplier)

    # 7. Formatear Top Resultados
    results_list = []
    for rank, (tid, final_score) in enumerate(final_weighted[:top_results], 1):
        t = hydrated_tenders[tid]
        rr_score = rerank_map.get(tid, 0.0)
        percentage = round(final_score * 100)

        region_match = are_regions_matching(t.region, supplier.regions)
        tender_full_text = f"{t.name} {t.description or ''}"
        sector_match = any(
            s.lower() in tender_full_text.lower() for s in (supplier.sectors or [])
        )
        kw_match = any(
            kw.lower() in " ".join([i.name.lower() for i in t.items])
            for kw in (supplier.keywords or [])
        )

        results_list.append(
            {
                "rank": rank,
                "tender_id": str(t.id),
                "code": t.code,
                "name": t.name,
                "buyer": t.buyer_name,
                "region": t.region,
                "items_count": len(t.items),
                "amount_clp": t.available_amount_clp,
                "reranker_score": round(rr_score, 4),
                "final_score": round(final_score, 4),
                "compatibility_percentage": f"{percentage}%",
                "region_match": region_match,
                "sector_match": sector_match,
                "keyword_match": kw_match,
            }
        )

    total_duration = time.perf_counter() - start_time

    return {
        "supplier_name": supplier.legal_name,
        "sectors": supplier.sectors,
        "top_results": results_list,
        "total_duration_sec": round(total_duration, 3),
        "rerank_duration_sec": round(rerank_duration, 3),
    }


# ==========================================================
# 5. EJECUCIÓN PRINCIPAL Y REPORTE
# ==========================================================
async def main():
    print("=" * 80, flush=True)
    print(
        "[INIT] BENCHMARK CON PORCENTAJES DE COMPATIBILIDAD (% COMPATIBILIDAD)",
        flush=True,
    )
    print("=" * 80, flush=True)

    # 1. Cargar Licitaciones desde PostgreSQL
    print("[POSTGRES] Cargando catálogo de licitaciones...", flush=True)
    tenders_dict = await load_all_tenders_from_db()
    print(
        f"[POSTGRES] {len(tenders_dict)} licitaciones cargadas en memoria.", flush=True
    )

    # 2. Conectar a Qdrant
    qdrant_client = AsyncQdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    # 3. Cargar Modelos
    print(f"[MODEL] Cargando modelo de embeddings '{MODEL_NAME}'...", flush=True)
    loop = asyncio.get_running_loop()
    embed_model = await loop.run_in_executor(
        None, lambda: SentenceTransformer(MODEL_NAME)
    )

    print("[MODEL] Cargando BgeRerankerService (INT8 ONNX Cuantizado)...", flush=True)
    reranker = BgeRerankerService(temperature=1.5)
    weighter = FieldWeightingService(
        reranker_weight=0.70,
        sector_weight=0.15,
        keyword_weight=0.15,
    )
    text_builder = TextBuilder()

    all_evaluations = []

    print("\n" + "-" * 80, flush=True)
    print("[RUN] EVALUANDO PERFILES Y CALCULANDO % DE COMPATIBILIDAD", flush=True)
    print("-" * 80, flush=True)

    for idx, p_data in enumerate(PROFILES, 1):
        supplier = Supplier(
            id=uuid4(),
            rut=p_data["rut"],
            legal_name=p_data["legal_name"],
            trade_name=p_data.get("trade_name"),
            description=p_data.get("description"),
            regions=p_data.get("regions"),
            sectors=p_data.get("sectors"),
            certifications=p_data.get("certificaciones"),
            keywords=p_data.get("keywords"),
        )

        print(
            f"\n[{idx}/10] {supplier.legal_name} | Rubros: {', '.join(supplier.sectors or [])}",
            flush=True,
        )
        res = await evaluate_profile(
            supplier=supplier,
            tenders_dict=tenders_dict,
            qdrant_client=qdrant_client,
            embed_model=embed_model,
            reranker=reranker,
            weighter=weighter,
            text_builder=text_builder,
            limit_candidates=12,
            top_results=3,
        )
        all_evaluations.append(res)

        print(
            f"  ⏱ Tiempo: {res['total_duration_sec']}s (Reranker: {res['rerank_duration_sec']}s)",
            flush=True,
        )
        for r in res["top_results"]:
            matches_flags = []
            if r["region_match"]:
                matches_flags.append("Región")
            if r["sector_match"]:
                matches_flags.append("Sector")
            if r["keyword_match"]:
                matches_flags.append("Keywords")
            flags_str = (
                f" [Coincidencias: {', '.join(matches_flags)}]" if matches_flags else ""
            )

            print(f"   #{r['rank']} [{r['code']}] {r['name'][:70]}...", flush=True)
            print(
                f"      🎯 Compatibilidad: {r['compatibility_percentage']} (Score: {r['final_score']} | Reranker: {r['reranker_score']}){flags_str}",
                flush=True,
            )

    # Guardar resultados
    output_path = os.path.join(
        os.path.dirname(__file__), "matching_evaluation_results.json"
    )
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_evaluations, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] Benchmark actualizado guardado en: {output_path}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
