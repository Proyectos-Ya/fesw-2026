"""
Script de Spike para extracción de Órdenes de Compra (Compra Ágil) desde Mercado Público,
búsqueda y descarga de la ficha técnica de cada Compra Ágil, y perfilamiento semántico
de proveedores vía LLM (Gemini con Structured Outputs) para alimentar el pipeline de matching.

Parámetros clave:
    --suppliers: Número de empresas/proveedores a evaluar en el dataset.
    --min-oc-per-supplier: Número mínimo de OCs que debe tener cada proveedor en el test
                           (define además cuántas OCs se fetchean y analizan por proveedor).

Uso:
    python spikes/dataset_compra_agil/generar_dataset_compra_agil.py --mock --suppliers 3 --min-oc-per-supplier 2
    python spikes/dataset_compra_agil/generar_dataset_compra_agil.py --suppliers 10 --min-oc-per-supplier 3 --fecha 20092026
"""

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Asegurar codificación utf-8 y line_buffering en Windows para stdout y stderr
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)

import httpx
from pydantic import BaseModel, Field

# Intentar cargar variables desde .env si python-dotenv está disponible
try:
    from dotenv import load_dotenv

    env_paths = [
        Path(__file__).resolve().parents[2] / ".env",
        Path(__file__).resolve().parents[2] / "monorepo" / ".env",
        Path(__file__).resolve().parents[2] / "monorepo" / "backend" / ".env",
    ]
    for ep in env_paths:
        if ep.exists():
            load_dotenv(ep)
            break
except ImportError:
    pass


# =====================================================================
# Modelos de Dominio para el Dataset
# =====================================================================

class ItemOrdenCompra(BaseModel):
    correlativo: int
    codigo_producto: Optional[str] = None
    nombre_producto: str
    especificacion_comprador: Optional[str] = None
    cantidad: float
    unidad_medida: Optional[str] = None
    precio_neto: Optional[float] = None
    total_neto: Optional[float] = None


class OrdenCompraAgil(BaseModel):
    codigo_oc: str
    nombre_oc: str
    codigo_licitacion_agil: Optional[str] = None
    organismo_comprador: str
    rut_comprador: Optional[str] = None
    region_comprador: Optional[str] = None
    comuna_comprador: Optional[str] = None
    fecha_envio: Optional[str] = None
    rut_proveedor: str
    nombre_proveedor: str
    monto_total: float
    moneda: str = "CLP"
    items: List[ItemOrdenCompra] = []


class ItemCompraAgilTender(BaseModel):
    correlativo: int
    codigo_producto: Optional[str] = None
    nombre: str
    descripcion: Optional[str] = None
    cantidad: float = 1.0
    unidad_medida: Optional[str] = None


class CompraAgilTender(BaseModel):
    """
    Representa la ficha del proceso de Compra Ágil obtenido de Mercado Público.
    Compatible con la entidad Tender de ProyectosYA para que pueda ingresar
    directamente al pipeline de matching (rank_tenders.py).
    """
    code: str = Field(description="Código único de cotización o licitación (ej: 757-45-COT26)")
    name: str = Field(description="Título o nombre del requerimiento de compra pública")
    description: Optional[str] = Field(default=None, description="Bases técnicas o descripción del requerimiento")
    status_code: str = Field(default="adjudicada", description="Estado de la compra")
    buyer_rut: Optional[str] = None
    buyer_name: Optional[str] = None
    region: Optional[str] = None
    commune: Optional[str] = None
    available_amount_clp: Optional[float] = None
    closing_at: Optional[str] = None
    items: List[ItemCompraAgilTender] = []


class SupplierProfileSynthesis(BaseModel):
    """
    Síntesis de perfil que contiene EXACTAMENTE los campos originales del modelo Supplier /
    CreateSupplierSchema de ProyectosYA.
    Al utilizar Structured Outputs nativos del LLM (Pydantic schema), el resultado
    del subagente puede instanciar directamente un Supplier sin mapeos ni parsing intermedio.
    """
    rut: str = Field(description="RUT chileno canónico del proveedor (ej: 76.123.456-7)")
    legal_name: str = Field(description="Razón social oficial de la empresa")
    trade_name: Optional[str] = Field(default=None, description="Nombre de fantasía o comercial si aplica")
    description: str = Field(
        min_length=30,
        max_length=1000,
        description="Descripción densa (30 a 1000 caracteres) de capacidades técnicas, oferta de valor y productos/servicios para matching semántico",
    )
    regions: List[str] = Field(
        min_length=1,
        description="Lista de regiones de Chile donde opera comercial o logísticamente",
    )
    sectors: List[str] = Field(
        min_length=1,
        description="Lista de rubros o sectores principales de la empresa según el catálogo de compras públicas",
    )
    certifications: Optional[List[str]] = Field(
        default_factory=list,
        description="Certificaciones técnicas o de calidad relevantes detectadas o declaradas",
    )
    keywords: Optional[List[str]] = Field(
        default_factory=list,
        description="Lista de 15 a 25 palabras clave, terminología técnica y sinónimos para el buscador",
    )
    years_experience: int = Field(
        default=3,
        ge=0,
        le=100,
        description="Años estimados de experiencia o actividad en el mercado",
    )
    num_employees: int = Field(
        default=5,
        ge=1,
        le=100000,
        description="Estimación del número de colaboradores o tamaño de la empresa",
    )


class RegistroProveedorDataset(BaseModel):
    rut: str
    nombre: str
    perfil: SupplierProfileSynthesis  # Directamente el modelo de Dominio Supplier
    ordenes_compra_adjudicadas: List[OrdenCompraAgil]
    compras_agiles_adjudicadas: List[CompraAgilTender] = Field(
        default_factory=list,
        description="Fichas completas de las Compras Ágiles asociadas para pasar por el pipeline de matching",
    )
    ids_procesos_positivos: List[str] = Field(
        description="IDs de Compra Ágil / OC donde el proveedor fue adjudicado (Ground Truth Positivo)"
    )


# =====================================================================
# Cliente de la API de Mercado Público (Órdenes de Compra y Compras Ágiles)
# =====================================================================

class MercadoPublicoOCClient:
    """Cliente para interactuar con los endpoints de Mercado Público (Órdenes de Compra y Compras Ágiles)."""

    BASE_URL_OC = "https://api.mercadopublico.cl/servicios/v1/publico/ordenesdecompra.json"
    BASE_URL_LICITACIONES_V1 = "https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json"
    BASE_URL_COMPRA_AGIL_V2 = "https://api2.mercadopublico.cl/v2/compra-agil"

    def __init__(self, ticket: str):
        self.ticket = ticket

    async def obtener_listado_fecha(
        self, client: httpx.AsyncClient, fecha_ddmmaaaa: str
    ) -> List[Dict[str, Any]]:
        """Obtiene el listado de órdenes de compra para una fecha dada (formato DDMMAAAA) con reintentos."""
        url = f"{self.BASE_URL_OC}?fecha={fecha_ddmmaaaa}&ticket={self.ticket}"
        for intento in range(1, 4):
            try:
                resp = await client.get(url, timeout=35.0)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("Listado", [])
                elif resp.status_code == 429:
                    espera = 3.5 * intento
                    print(f"[API MP] 429 Rate limit en listado {fecha_ddmmaaaa}... esperando {espera:.1f}s (intento {intento}/3)")
                    await asyncio.sleep(espera)
                elif resp.status_code >= 500:
                    await asyncio.sleep(2.0 * intento)
                else:
                    print(f"[API Error] Status {resp.status_code} al listar fecha {fecha_ddmmaaaa}: {resp.text[:200]}")
                    return []
            except Exception as e:
                print(f"[API Exception] Error conectando a Mercado Público ({fecha_ddmmaaaa}): {e}")
                await asyncio.sleep(2.0)
        return []

    async def obtener_detalle_oc(
        self, client: httpx.AsyncClient, codigo_oc: str
    ) -> Optional[Dict[str, Any]]:
        """Obtiene la ficha técnica detallada de una orden de compra con reintentos ante 429."""
        url = f"{self.BASE_URL_OC}?codigo={codigo_oc}&ticket={self.ticket}"
        for intento in range(1, 4):
            try:
                resp = await client.get(url, timeout=25.0)
                if resp.status_code == 200:
                    data = resp.json()
                    listado = data.get("Listado", [])
                    if listado:
                        return listado[0]
                    return None
                elif resp.status_code == 429:
                    espera = 2.0 * intento
                    await asyncio.sleep(espera)
                elif resp.status_code >= 500:
                    await asyncio.sleep(1.5 * intento)
                else:
                    return None
            except Exception:
                await asyncio.sleep(1.0)
        return None

    async def obtener_detalle_compra_agil(
        self, client: httpx.AsyncClient, codigo_o_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Obtiene la ficha técnica de un proceso de Compra Ágil / Cotización.
        Intenta primero la API v2 especializada de Compra Ágil y como respaldo la API v1 de Licitaciones.
        """
        # 1. Endpoint V2 Compra Ágil
        url_v2 = f"{self.BASE_URL_COMPRA_AGIL_V2}/{codigo_o_id}"
        headers = {"ticket": self.ticket}
        try:
            resp = await client.get(url_v2, headers=headers, timeout=20.0)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict):
                    payload = data.get("payload")
                    if payload and isinstance(payload, dict):
                        return payload
                    return data
        except Exception as e:
            print(f"[API Exception] Fallo al consultar V2 Compra Ágil ({codigo_o_id}): {e}")

        # 2. Respaldo: Endpoint V1 Licitaciones Públicas
        url_v1 = f"{self.BASE_URL_LICITACIONES_V1}?codigo={codigo_o_id}&ticket={self.ticket}"
        try:
            resp = await client.get(url_v1, timeout=20.0)
            if resp.status_code == 200:
                data = resp.json()
                listado = data.get("Listado", [])
                if listado:
                    return listado[0]
        except Exception as e:
            print(f"[API Exception] Fallo al consultar V1 Licitaciones ({codigo_o_id}): {e}")

        return None

    async def obtener_ordenes_proveedor(
        self, client: httpx.AsyncClient, rut: str
    ) -> List[Dict[str, Any]]:
        """
        Obtiene el historial completo de órdenes de compra de un proveedor por su RUT (parámetro rutProveedor).
        Permite verificar rápidamente si el proveedor tiene >= min_oc_per_supplier compras ágiles.
        """
        rut_clean = rut.strip()
        url = f"{self.BASE_URL_OC}?rutProveedor={rut_clean}&ticket={self.ticket}"
        for intento in range(1, 4):
            try:
                resp = await client.get(url, timeout=35.0)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("Listado", [])
                elif resp.status_code == 429:
                    espera = 2.5 * intento
                    await asyncio.sleep(espera)
                elif resp.status_code >= 500:
                    await asyncio.sleep(1.5 * intento)
                else:
                    return []
            except Exception:
                await asyncio.sleep(1.0)
        return []


def _extraer_ocs_desde_logs_previos() -> List[str]:
    """Recupera códigos de OCs Compra Ágil identificados en ejecuciones anteriores para arrancar rápido."""
    ocs_encontradas = []
    # Buscar en carpetas de tareas de gemini/antigravity
    rutas_log = list(Path(__file__).resolve().parents[2].glob(".gemini/antigravity/brain/**/tasks/*.log"))
    app_data = os.getenv("USERPROFILE") or os.getenv("HOME")
    if app_data:
        rutas_log.extend(Path(app_data).glob(".gemini/antigravity/brain/**/tasks/*.log"))

    for lp in rutas_log:
        try:
            with open(lp, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    m = re.search(r"Compra.+?OC\s+([0-9\-AGCOT]+)", line)
                    if m:
                        ocs_encontradas.append(m.group(1).strip())
        except Exception:
            pass

    vistos = set()
    unicos = []
    for cod in ocs_encontradas:
        if cod not in vistos:
            vistos.add(cod)
            unicos.append(cod)
    return unicos


def es_resumen_compra_agil(it: Dict[str, Any]) -> bool:
    """
    Detecta si un ítem de resumen (listado diario o historial de proveedor)
    corresponde a Compra Ágil por código o nombre.
    """
    cod = str(it.get("Codigo") or "").strip().upper()
    nom = str(it.get("Nombre") or "").strip().upper()
    return (
        "-AG" in cod
        or "-COT" in cod
        or "-AG" in nom
        or "-COT" in nom
        or "COMPRA AGIL" in nom
        or "COMPRA ÁGIL" in nom
    )


def es_compra_agil(oc_raw: Dict[str, Any]) -> bool:
    """
    Verifica si una orden de compra proviene de un proceso de Compra Ágil.
    """
    codigo_licitacion = str(oc_raw.get("CodigoLicitacion") or "")
    if "-AG" in codigo_licitacion.upper() or "-COT" in codigo_licitacion.upper():
        return True

    tipo = str(oc_raw.get("Tipo") or "").upper()
    if tipo in ("AG", "COMPRA ÁGIL", "COMPRA AGIL"):
        return True

    tipo_licitacion = str(oc_raw.get("TipoLicitacion") or "").upper()
    if tipo_licitacion in ("AG", "COMPRA AGIL", "COMPRA ÁGIL"):
        return True

    nombre = str(oc_raw.get("Nombre") or "").upper()
    if "COMPRA AGIL" in nombre or "COMPRA ÁGIL" in nombre:
        return True

    return False


def parsear_oc_agil(oc_raw: Dict[str, Any]) -> Optional[OrdenCompraAgil]:
    """Parsea el JSON crudo de Mercado Público a nuestro modelo estructurado."""
    try:
        proveedor_raw = oc_raw.get("Proveedor", {})
        rut_prov = str(
            proveedor_raw.get("RutProveedor")
            or proveedor_raw.get("RutSucursal")
            or proveedor_raw.get("Rut")
            or proveedor_raw.get("Codigo")
            or ""
        ).strip()
        nombre_prov = str(
            proveedor_raw.get("NombreProveedor")
            or proveedor_raw.get("Nombre")
            or proveedor_raw.get("RazonSocial")
            or proveedor_raw.get("NombreEmpresa")
            or oc_raw.get("NombreProveedor")
            or f"Proveedor {rut_prov}"
        ).strip()

        if not rut_prov:
            return None

        comprador_raw = oc_raw.get("Comprador", {})
        organismo = str(comprador_raw.get("NombreOrganismo") or "Organismo Desconocido")
        rut_comprador = str(comprador_raw.get("RutUnidad") or "")
        region_comprador = str(comprador_raw.get("RegionUnidad") or "")
        comuna_comprador = str(comprador_raw.get("ComunaUnidad") or "")

        codigo_licitacion = str(oc_raw.get("CodigoLicitacion") or "").strip()
        if not codigo_licitacion:
            nombre_completo = f"{oc_raw.get('Nombre', '')} {oc_raw.get('Descripcion', '')}"
            m = re.search(r'(\d+-\d+-COT\d+|\d+-\d+-AG\d+)', nombre_completo)
            if m:
                codigo_licitacion = m.group(1)

        items_parsed: List[ItemOrdenCompra] = []
        items_raw = oc_raw.get("Items", {}).get("Listado", [])
        if isinstance(items_raw, dict):
            items_raw = [items_raw]

        for idx, it in enumerate(items_raw, 1):
            items_parsed.append(
                ItemOrdenCompra(
                    correlativo=int(it.get("Correlativo", idx)),
                    codigo_producto=str(it.get("CodigoProducto") or ""),
                    nombre_producto=str(it.get("Producto") or it.get("Nombre") or ""),
                    especificacion_comprador=it.get("EspecificacionComprador"),
                    cantidad=float(it.get("Cantidad", 1)),
                    unidad_medida=it.get("UnidadMedida"),
                    precio_neto=float(it.get("PrecioNeto", 0)) if it.get("PrecioNeto") is not None else None,
                    total_neto=float(it.get("Total", 0)) if it.get("Total") is not None else None,
                )
            )

        total_monto = float(oc_raw.get("TotalNeto") or oc_raw.get("MontoTotal") or 0.0)

        return OrdenCompraAgil(
            codigo_oc=str(oc_raw.get("Codigo")),
            nombre_oc=str(oc_raw.get("Nombre") or ""),
            codigo_licitacion_agil=oc_raw.get("CodigoLicitacion"),
            organismo_comprador=organismo,
            rut_comprador=rut_comprador,
            region_comprador=region_comprador,
            comuna_comprador=comuna_comprador,
            fecha_envio=oc_raw.get("FechaEnvio"),
            rut_proveedor=rut_prov,
            nombre_proveedor=nombre_prov,
            monto_total=total_monto,
            moneda=str(oc_raw.get("TipoMoneda") or "CLP"),
            items=items_parsed,
        )
    except Exception as e:
        print(f"[Parse Error] Fallo al parsear OC {oc_raw.get('Codigo')}: {e}")
        return None


def parsear_compra_agil_tender(
    codigo: str, raw_tender: Optional[Dict[str, Any]], oc: Optional[OrdenCompraAgil] = None
) -> CompraAgilTender:
    """
    Parsea los datos de la Compra Ágil (desde API o enriquecida desde la OC)
    a la estructura formal CompraAgilTender (compatible con la entidad Tender de ProyectosYA).
    """
    if not raw_tender:
        # Si la API no devolvió la ficha de licitación pero tenemos la OC, construimos el Tender a partir de la OC
        items_tender = []
        if oc:
            for it in oc.items:
                items_tender.append(
                    ItemCompraAgilTender(
                        correlativo=it.correlativo,
                        codigo_producto=it.codigo_producto,
                        nombre=it.nombre_producto,
                        descripcion=it.especificacion_comprador,
                        cantidad=it.cantidad,
                        unidad_medida=it.unidad_medida,
                    )
                )
        return CompraAgilTender(
            code=codigo,
            name=oc.nombre_oc if oc else f"Proceso Compra Ágil {codigo}",
            description=f"Proceso de cotización y adquisición de Compra Ágil correspondiente a {oc.nombre_oc if oc else codigo}.",
            status_code="adjudicada",
            buyer_rut=oc.rut_comprador if oc else None,
            buyer_name=oc.organismo_comprador if oc else None,
            region=oc.region_comprador if oc else None,
            commune=oc.comuna_comprador if oc else None,
            available_amount_clp=oc.monto_total if oc else None,
            closing_at=oc.fecha_envio if oc else None,
            items=items_tender,
        )

    # Si viene desde API V2 o V1 de Mercado Público:
    nombre = raw_tender.get("nombre") or raw_tender.get("Nombre") or (oc.nombre_oc if oc else f"Proceso {codigo}")
    descripcion = raw_tender.get("descripcion") or raw_tender.get("Descripcion") or (oc.nombre_oc if oc else "")

    comprador = raw_tender.get("comprador") or raw_tender.get("Comprador") or {}
    buyer_rut = comprador.get("rut") or comprador.get("RutUnidad") or (oc.rut_comprador if oc else None)
    buyer_name = comprador.get("nombreOrganismo") or comprador.get("NombreOrganismo") or (oc.organismo_comprador if oc else None)
    region = comprador.get("region") or comprador.get("RegionUnidad") or (oc.region_comprador if oc else None)
    commune = comprador.get("comuna") or comprador.get("ComunaUnidad") or (oc.comuna_comprador if oc else None)

    monto = raw_tender.get("montoEstimado") or raw_tender.get("MontoEstimado") or (oc.monto_total if oc else None)

    items_tender = []
    items_raw = raw_tender.get("items") or raw_tender.get("Items", {}).get("Listado", [])
    if isinstance(items_raw, dict):
        items_raw = [items_raw]

    for idx, it in enumerate(items_raw, 1):
        items_tender.append(
            ItemCompraAgilTender(
                correlativo=int(it.get("correlativo") or it.get("Correlativo") or idx),
                codigo_producto=str(it.get("codigoProducto") or it.get("CodigoProducto") or ""),
                nombre=str(it.get("nombre") or it.get("Producto") or it.get("Nombre") or "Item"),
                descripcion=it.get("descripcion") or it.get("EspecificacionComprador"),
                cantidad=float(it.get("cantidad") or it.get("Cantidad") or 1.0),
                unidad_medida=it.get("unidadMedida") or it.get("UnidadMedida"),
            )
        )

    if not items_tender and oc:
        for it in oc.items:
            items_tender.append(
                ItemCompraAgilTender(
                    correlativo=it.correlativo,
                    codigo_producto=it.codigo_producto,
                    nombre=it.nombre_producto,
                    descripcion=it.especificacion_comprador,
                    cantidad=it.cantidad,
                    unidad_medida=it.unidad_medida,
                )
            )

    return CompraAgilTender(
        code=codigo,
        name=str(nombre),
        description=str(descripcion) if descripcion else None,
        status_code="adjudicada",
        buyer_rut=buyer_rut,
        buyer_name=buyer_name,
        region=region,
        commune=commune,
        available_amount_clp=float(monto) if monto else None,
        closing_at=raw_tender.get("fechaCierre") or raw_tender.get("FechaCierre") or (oc.fecha_envio if oc else None),
        items=items_tender,
    )


# =====================================================================
# Subagente Perfilador de Proveedor (LLM con Structured Outputs)
# =====================================================================

class SubagentePerfiladorProveedor:
    """
    Subagente que procesa el catálogo de productos y órdenes de compra ganadas
    por un proveedor para generar su perfil semántico directamente en la entidad Supplier.
    """

    def __init__(self, gemini_api_key: Optional[str] = None):
        self.api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
        self._gemini_client = None

        if self.api_key:
            try:
                from google import genai
                self._gemini_client = genai.Client(api_key=self.api_key)
                self._sdk_type = "genai"
            except ImportError:
                try:
                    import google.generativeai as legacy_genai
                    legacy_genai.configure(api_key=self.api_key)
                    model_name = os.getenv("GEMINI_MODEL") or "gemini-3.8-flash"
                    self._gemini_client = legacy_genai.GenerativeModel(model_name)
                    self._sdk_type = "legacy"
                except ImportError:
                    print("[Aviso] Librerías de Google Gemini no instaladas. Se usará perfilador heurístico.")
                    self._gemini_client = None

    async def perfilar_proveedor(
        self, rut: str, nombre: str, ordenes: List[OrdenCompraAgil]
    ) -> SupplierProfileSynthesis:
        """Sintetiza la información de adjudicaciones y genera el perfil con el modelo Supplier de ProyectosYA."""

        # 1. Compilar evidencia de ventas
        resumen_items = []
        regiones_vistas = set()
        total_acumulado = 0.0

        for oc in ordenes:
            total_acumulado += oc.monto_total
            if oc.region_comprador:
                regiones_vistas.add(oc.region_comprador)
            for it in oc.items:
                desc = it.nombre_producto
                if it.especificacion_comprador:
                    desc += f" ({it.especificacion_comprador})"
                resumen_items.append(desc)

        muestra_items = list(set(resumen_items))[:30]
        regiones_lista = sorted(list(regiones_vistas)) if regiones_vistas else ["Región Metropolitana de Santiago"]

        # 2. Si no hay cliente LLM disponible, usar extracción heurística
        if not self._gemini_client:
            return self._perfilar_heuristicamente(
                rut, nombre, muestra_items, regiones_lista, total_acumulado, len(ordenes)
            )

        # 3. Prompt para el subagente perfilador
        prompt = f"""
Eres un analista experto en compras públicas chilenas (Mercado Público / ChileCompra).
A partir del historial de adjudicaciones en "Compra Ágil" de un proveedor, debes construir directamente la entidad Supplier (perfil de empresa) con los campos exactos del modelo del sistema.

DATOS DEL PROVEEDOR:
- RUT: {rut}
- Razón Social: {nombre}
- Total OCs adjudicadas en muestra: {len(ordenes)}
- Monto total adjudicado en muestra: ${total_acumulado:,.0f} CLP
- Regiones donde ha vendido: {', '.join(regiones_lista)}

MUESTRA DE ÍTEMS / SERVICIOS ADJUDICADOS:
{json.dumps(muestra_items, ensure_ascii=False, indent=2)}

INSTRUCCIONES:
Debes completar los campos del esquema SupplierProfileSynthesis:
- legal_name: Razón social oficial ({nombre})
- trade_name: Nombre de fantasía si es deducible o null
- description: Párrafo de 50 a 800 caracteres denso y persuasivo que resuma la oferta de valor, especialidad y productos/servicios para matching semántico vectorial.
- regions: Lista de regiones de Chile donde tiene cobertura demostrada.
- sectors: Lista de 1 a 4 rubros/sectores oficiales de compras públicas correspondientes.
- certifications: Lista de certificaciones técnicas si aplican (o lista vacía).
- keywords: Lista de 15 a 25 palabras clave y términos técnicos del rubro.
- years_experience: Años estimados de experiencia (entero entre 1 y 50).
- num_employees: Cantidad estimada de colaboradores (entero).
"""

        for intento in range(1, 3):
            try:
                model_target = os.getenv("GEMINI_MODEL") or "gemini-3.8-flash"
                if self._sdk_type == "genai":
                    from google.genai import types

                    config = types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=SupplierProfileSynthesis,
                        temperature=0.2,
                    )
                    response = self._gemini_client.models.generate_content(
                        model=model_target,
                        contents=prompt,
                        config=config,
                    )
                    if hasattr(response, "parsed") and response.parsed:
                        return response.parsed
                    return SupplierProfileSynthesis.model_validate_json(response.text)
                else:
                    response = self._gemini_client.generate_content(
                        prompt,
                        generation_config={
                            "response_mime_type": "application/json",
                            "response_schema": SupplierProfileSynthesis,
                            "temperature": 0.2,
                        },
                    )
                    return SupplierProfileSynthesis.model_validate_json(response.text)
            except Exception as e:
                if intento < 2:
                    await asyncio.sleep(2.5)
                    continue
                print(f"[Subagente LLM Error] Fallo al invocar Gemini con Structured Outputs para {rut} ({e}). Usando heurística.")
                return self._perfilar_heuristicamente(
                    rut, nombre, muestra_items, regiones_lista, total_acumulado, len(ordenes)
                )

    def _perfilar_heuristicamente(
        self,
        rut: str,
        nombre: str,
        items: List[str],
        regiones: List[str],
        monto_total: float,
        cant_oc: int,
    ) -> SupplierProfileSynthesis:
        """Respaldo determinista sin LLM compatible 1:1 con el modelo Supplier."""
        desc = (
            f"Proveedor comercial '{nombre}' con adjudicaciones de Compra Ágil registradas en Mercado Público. "
            f"Especializado en el suministro y entrega de: {', '.join(items[:8])}."
        )
        if len(desc) < 30:
            desc = desc.ljust(35, " ")

        keywords = list({word.lower() for item in items for word in re.findall(r"\b[a-zA-ZáéíóúÁÉÍÓÚñÑ]{4,}\b", item)})[:15]

        return SupplierProfileSynthesis(
            rut=rut,
            legal_name=nombre,
            trade_name=None,
            description=desc[:1000],
            regions=regiones if regiones else ["Región Metropolitana de Santiago"],
            sectors=["Comercialización y Suministros del Estado", "Servicios Generales"],
            certifications=[],
            keywords=keywords,
            years_experience=3,
            num_employees=5,
        )


def guardar_dataset_disco(
    output_dir: Path,
    proveedores: List[RegistroProveedorDataset],
    compras_agiles: List[CompraAgilTender],
):
    """
    Escribe los archivos JSON y JSONL a disco de forma inmediata/incremental.
    Garantiza que interrumpir la ejecución en cualquier momento conserve el progreso.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    archivo_proveedores = output_dir / "dataset_compra_agil_proveedores.json"
    archivo_compras_agiles = output_dir / "compras_agiles_para_matching.json"
    archivo_benchmark = output_dir / "benchmark_matching_ground_truth.jsonl"

    # 1. Dataset de proveedores con su perfil Supplier, OCs y Compras Ágiles
    with open(archivo_proveedores, "w", encoding="utf-8") as f:
        json.dump([r.model_dump() for r in proveedores], f, ensure_ascii=False, indent=2)

    # 2. Catálogo consolidado de Compras Ágiles listas para el pipeline de matching
    with open(archivo_compras_agiles, "w", encoding="utf-8") as f:
        json.dump([t.model_dump() for t in compras_agiles], f, ensure_ascii=False, indent=2)

    # 3. Formato benchmark de ranking (Query / Ground Truth Positives)
    with open(archivo_benchmark, "w", encoding="utf-8") as f:
        for reg in proveedores:
            line = {
                "supplier_id": reg.perfil.rut,
                "supplier_name": reg.perfil.legal_name,
                "trade_name": reg.perfil.trade_name,
                "query_text_rubro": ", ".join(reg.perfil.sectors),
                "query_text_descripcion": reg.perfil.description,
                "query_keywords": reg.perfil.keywords or [],
                "regiones": reg.perfil.regions,
                "sectors": reg.perfil.sectors,
                "years_experience": reg.perfil.years_experience,
                "num_employees": reg.perfil.num_employees,
                "positive_tender_ids": reg.ids_procesos_positivos,
            }
            f.write(json.dumps(line, ensure_ascii=False) + "\n")


async def ejecutar_pipeline(
    ticket: str,
    fechas: List[str],
    target_suppliers: int,
    min_oc_per_supplier: int,
    limite_oc_por_fecha: int,
    output_dir: Path,
    gemini_key: Optional[str] = None,
    usar_mock: bool = False,
    reset: bool = False,
):
    print("=" * 75)
    print("[INICIO] Generación de Dataset de Matching: Proveedores y Compras Ágiles")
    print(f"Directorio de salida: {output_dir}")
    print(f"Proveedores objetivo en esta corrida: {target_suppliers}")
    print(f"Mínimo OCs por proveedor (--min-oc-per-supplier): {min_oc_per_supplier}")
    print(f"Modo Acumulación / Reset: {'RESET (Comenzar desde 0)' if reset else 'ACUMULAR con datos existentes'}")
    print(f"Fechas de búsqueda: {fechas}")
    print(f"Modo Mock: {'ACTIVADO' if usar_mock else 'DESACTIVADO (Conexión Real MP)'}")
    print("=" * 75)

    output_dir.mkdir(parents=True, exist_ok=True)
    archivo_proveedores = output_dir / "dataset_compra_agil_proveedores.json"
    archivo_compras_agiles = output_dir / "compras_agiles_para_matching.json"
    archivo_benchmark = output_dir / "benchmark_matching_ground_truth.jsonl"

    # Diccionarios acumuladores: RUT -> RegistroProveedorDataset, Code -> CompraAgilTender
    existentes_proveedores: Dict[str, RegistroProveedorDataset] = {}
    existentes_compras_agiles: Dict[str, CompraAgilTender] = {}

    if reset:
        print("\n[Reset] Flag --reset activada: Eliminando datasets previos para comenzar desde 0...")
        for arch in [archivo_proveedores, archivo_compras_agiles, archivo_benchmark]:
            if arch.exists():
                try:
                    arch.unlink()
                    print(f"  - Archivo eliminado: {arch.name}")
                except Exception as e:
                    print(f"  [Aviso] No se pudo eliminar {arch.name}: {e}")
    else:
        # Cargar datasets previos si existen
        if archivo_proveedores.exists():
            try:
                with open(archivo_proveedores, "r", encoding="utf-8") as f:
                    raw_p = json.load(f)
                    for item in raw_p:
                        reg_obj = RegistroProveedorDataset.model_validate(item)
                        existentes_proveedores[reg_obj.rut] = reg_obj
                print(f"[Acumulación] Se cargaron {len(existentes_proveedores)} proveedores existentes desde {archivo_proveedores.name}")
            except Exception as e:
                print(f"[Aviso] No se pudo leer {archivo_proveedores.name} para acumular ({e}). Se iniciará vacío.")

        if archivo_compras_agiles.exists():
            try:
                with open(archivo_compras_agiles, "r", encoding="utf-8") as f:
                    raw_c = json.load(f)
                    for item in raw_c:
                        tender_obj = CompraAgilTender.model_validate(item)
                        existentes_compras_agiles[tender_obj.code] = tender_obj
                print(f"[Acumulación] Se cargaron {len(existentes_compras_agiles)} compras ágiles existentes desde {archivo_compras_agiles.name}")
            except Exception as e:
                print(f"[Aviso] No se pudo leer {archivo_compras_agiles.name} para acumular ({e}). Se iniciará vacío.")

    if len(existentes_proveedores) >= target_suppliers:
        print(f"\n✓ Meta de {target_suppliers} proveedores ya alcanzada ({len(existentes_proveedores)} en disco).")
        return

    subagente = SubagentePerfiladorProveedor(gemini_api_key=gemini_key)

    if usar_mock:
        offset_actual = len(existentes_proveedores)
        faltantes = target_suppliers - offset_actual
        print(f"\n[Mock] Generando {faltantes} proveedores simulados (offset={offset_actual})...")
        mock_data = _generar_datos_mock(faltantes, min_oc_per_supplier, offset=offset_actual)

        for rut, ocs in mock_data.items():
            nombre = ocs[0].nombre_proveedor
            print(f"  [Mock] Procesando {nombre} ({rut})...")
            compras_agiles_prov = []
            ids_positivos = []
            for oc in ocs:
                cod_tender = oc.codigo_licitacion_agil or f"{oc.codigo_oc}-COT"
                ids_positivos.append(cod_tender)
                tender_obj = parsear_compra_agil_tender(cod_tender, None, oc)
                existentes_compras_agiles[cod_tender] = tender_obj
                compras_agiles_prov.append(tender_obj)

            perfil = await subagente.perfilar_proveedor(rut=rut, nombre=nombre, ordenes=ocs)
            reg = RegistroProveedorDataset(
                rut=rut,
                nombre=nombre,
                perfil=perfil,
                ordenes_compra_adjudicadas=ocs,
                compras_agiles_adjudicadas=compras_agiles_prov,
                ids_procesos_positivos=sorted(list(set(ids_positivos))),
            )
            existentes_proveedores[rut] = reg
            guardar_dataset_disco(output_dir, list(existentes_proveedores.values()), list(existentes_compras_agiles.values()))
            print(f"  ★ [GUARDADO INCREMENTAL] Proveedor #{len(existentes_proveedores)}/{target_suppliers} guardado en disco: {nombre}")

    else:
        client_mp = MercadoPublicoOCClient(ticket=ticket)
        # Diccionario acumulador en memoria: RUT -> List[OrdenCompraAgil]
        candidatos_proveedores: Dict[str, List[OrdenCompraAgil]] = {}
        candidatos_nombres: Dict[str, str] = {}

        # 1. Precargar OCs verificadas de ejecuciones previas (para arrancar con los proveedores ya avanzados)
        ocs_cola: List[str] = _extraer_ocs_desde_logs_previos()
        if ocs_cola:
            print(f"[Acelerador] Se precargaron {len(ocs_cola)} órdenes de Compra Ágil verificadas para reutilizar.")

        async with httpx.AsyncClient() as http_client:
            print(f"\n[Escaneo y Matching Real] Agrupando OCs legítimas por proveedor con guardado incremental...")
            print(f"Meta actual: {len(existentes_proveedores)} / {target_suppliers} proveedores calificados (mínimo {min_oc_per_supplier} OCs c/u).")

            async def procesar_codigo_oc(cod_oc: str) -> bool:
                """Procesa una OC individual. Retorna True si ya se alcanzó la meta global de proveedores."""
                if len(existentes_proveedores) >= target_suppliers:
                    return True

                detalle_oc = await client_mp.obtener_detalle_oc(http_client, cod_oc)
                if not detalle_oc or not es_compra_agil(detalle_oc):
                    return False

                parsed_oc = parsear_oc_agil(detalle_oc)
                if not parsed_oc:
                    return False

                rut = parsed_oc.rut_proveedor
                nombre = parsed_oc.nombre_proveedor

                # Si el proveedor ya completó su cuota y está guardado en disco, no consumimos más OCs de él
                if not rut or rut in existentes_proveedores:
                    return False

                # Evitar duplicar la misma OC en la lista del proveedor
                ocs_actuales = candidatos_proveedores.setdefault(rut, [])
                if any(o.codigo_oc == parsed_oc.codigo_oc for o in ocs_actuales):
                    return False

                ocs_actuales.append(parsed_oc)
                candidatos_nombres[rut] = nombre
                progreso = len(ocs_actuales)

                print(
                    f"  [+] Compra Ágil: OC {parsed_oc.codigo_oc} | Prov: {nombre[:25]} (Progreso: {progreso}/{min_oc_per_supplier})",
                    flush=True,
                )

                if progreso >= min_oc_per_supplier:
                    print(
                        f"\n  [✓] PROVEEDOR CALIFICADO: {nombre} ({rut}) completó {progreso}/{min_oc_per_supplier} Compras Ágiles.",
                        flush=True,
                    )
                    ocs_prov = ocs_actuales[:min_oc_per_supplier]
                    tenders_prov: List[CompraAgilTender] = []
                    ids_procesos_prov: List[str] = []

                    for oc_obj in ocs_prov:
                        cod_proc = oc_obj.codigo_licitacion_agil or oc_obj.codigo_oc
                        ids_procesos_prov.append(cod_proc)
                        if cod_proc in existentes_compras_agiles:
                            tenders_prov.append(existentes_compras_agiles[cod_proc])
                        else:
                            await asyncio.sleep(0.2)
                            raw_tender = await client_mp.obtener_detalle_compra_agil(http_client, cod_proc)
                            tender_obj = parsear_compra_agil_tender(cod_proc, raw_tender, oc_obj)
                            existentes_compras_agiles[cod_proc] = tender_obj
                            tenders_prov.append(tender_obj)

                    print(f"  [AI] Generando perfil Supplier con Structured Outputs para {nombre}...", flush=True)
                    perfil = await subagente.perfilar_proveedor(rut=rut, nombre=nombre, ordenes=ocs_prov)

                    reg = RegistroProveedorDataset(
                        rut=rut,
                        nombre=nombre,
                        perfil=perfil,
                        ordenes_compra_adjudicadas=ocs_prov,
                        compras_agiles_adjudicadas=tenders_prov,
                        ids_procesos_positivos=sorted(list(set(ids_procesos_prov))),
                    )
                    existentes_proveedores[rut] = reg
                    del candidatos_proveedores[rut]

                    guardar_dataset_disco(
                        output_dir=output_dir,
                        proveedores=list(existentes_proveedores.values()),
                        compras_agiles=list(existentes_compras_agiles.values()),
                    )
                    print(
                        f"  ★ [GUARDADO INCREMENTAL] Proveedor #{len(existentes_proveedores)}/{target_suppliers} guardado en disco: {nombre} ({rut})\n",
                        flush=True,
                    )

                await asyncio.sleep(0.2)
                return len(existentes_proveedores) >= target_suppliers

            # 1. Procesar primero la cola de OCs verificadas previas
            if ocs_cola:
                for cod in ocs_cola:
                    meta_alcanzada = await procesar_codigo_oc(cod)
                    if meta_alcanzada:
                        break

            # 2. Si aún no alcanzamos la meta de proveedores calificados, continuar escaneando fechas
            if len(existentes_proveedores) < target_suppliers:
                for fecha in fechas:
                    if len(existentes_proveedores) >= target_suppliers:
                        print(f"\n✓ Se alcanzó la meta total de {target_suppliers} proveedores calificados.", flush=True)
                        break

                    print(f"\n--- Consultando fecha {fecha} en Mercado Público ---", flush=True)
                    listado = await client_mp.obtener_listado_fecha(http_client, fecha)
                    candidatos_fecha = [
                        it.get("Codigo")
                        for it in listado
                        if es_resumen_compra_agil(it) and it.get("Codigo")
                    ]
                    print(
                        f"  -> {len(candidatos_fecha)} órdenes con patrón Compra Ágil identificadas en fecha {fecha}.",
                        flush=True,
                    )

                    for cod in candidatos_fecha[:limite_oc_por_fecha]:
                        meta_alcanzada = await procesar_codigo_oc(cod)
                        if meta_alcanzada:
                            break

    lista_proveedores_final = list(existentes_proveedores.values())
    lista_compras_agiles_final = list(existentes_compras_agiles.values())

    print("\n" + "=" * 75)
    print("[FINALIZADO] DATASET Y COMPRAS ÁGILES EN DISCO")
    print(f"1. Dataset Proveedores (Supplier): {archivo_proveedores.resolve()}")
    print(f"2. Compras Ágiles para Matching:    {archivo_compras_agiles.resolve()}")
    print(f"3. Benchmark Ground Truth (JSONL):   {archivo_benchmark.resolve()}")
    print(f"Estadísticas Acumuladas: {len(lista_proveedores_final)}/{target_suppliers} proveedores, {len(lista_compras_agiles_final)} compras ágiles.")
    print("=" * 75)


def _generar_datos_mock(target_suppliers: int, min_oc: int, offset: int = 0) -> Dict[str, List[OrdenCompraAgil]]:
    """Genera datos de prueba simulados con soporte de offset para acumulación sin duplicados."""
    rubros_mock = [
        {
            "rut": "76.123.456-7",
            "nombre": "Distribuidora Médica y Quirúrgica del Sur SpA",
            "org": "Hospital Regional de Rancagua",
            "region": "Región del Libertador General Bernardo O'Higgins",
            "comuna": "Rancagua",
            "producto": "Guantes Quirúrgicos Estériles Talla M",
        },
        {
            "rut": "77.987.654-3",
            "nombre": "CloudTech Consultores SpA",
            "org": "Municipalidad de Providencia",
            "region": "Región Metropolitana de Santiago",
            "comuna": "Providencia",
            "producto": "Consultoría e Infraestructura Cloud DevOps",
        },
        {
            "rut": "76.555.444-1",
            "nombre": "Constructora e Ingeniería Maipo Ltda",
            "org": "Servicio de Salud Metropolitano",
            "region": "Región Metropolitana de Santiago",
            "comuna": "Santiago",
            "producto": "Mantención de Redes Sanitarias y Obras Menores",
        },
        {
            "rut": "78.222.333-5",
            "nombre": "Insumos y Papelería Austral Limitada",
            "org": "Dirección de Vialidad Aysén",
            "region": "Región de Aysén del General Carlos Ibáñez del Campo",
            "comuna": "Coyhaique",
            "producto": "Resmas Papel Carta y Toners Impresión",
        },
        {
            "rut": "79.111.999-8",
            "nombre": "Seguridad y Monitoreo Integral Chile SpA",
            "org": "Municipalidad de Viña del Mar",
            "region": "Región de Valparaíso",
            "comuna": "Viña del Mar",
            "producto": "Servicio de Vigilancia y Cámaras de Seguridad",
        },
        {
            "rut": "76.888.777-2",
            "nombre": "Biotecnología y Reactivos Clínicos del Norte SpA",
            "org": "Hospital Regional de Antofagasta",
            "region": "Región de Antofagasta",
            "comuna": "Antofagasta",
            "producto": "Reactivos de Laboratorio Clínico",
        },
        {
            "rut": "77.333.222-9",
            "nombre": "Transporte y Logística Patagonia Express Ltda",
            "org": "Gobernación Regional de Magallanes",
            "region": "Región de Magallanes y de la Antártica Chilena",
            "comuna": "Punta Arenas",
            "producto": "Servicio de Fletes y Carga Aérea/Marítima",
        },
        {
            "rut": "78.444.666-4",
            "nombre": "EcoEnergía y Paneles Solares Chile SpA",
            "org": "Municipalidad de La Serena",
            "region": "Región de Coquimbo",
            "comuna": "La Serena",
            "producto": "Suministro e Instalación de Paneles Fotovoltaicos",
        },
    ]

    resultado: Dict[str, List[OrdenCompraAgil]] = {}
    for i in range(target_suppliers):
        idx = (offset + i) % len(rubros_mock)
        base = rubros_mock[idx].copy()
        
        # Si se da la vuelta a la lista, añadir sufijo para unicidad
        vuelta = (offset + i) // len(rubros_mock)
        if vuelta > 0:
            base["rut"] = f"{base['rut'][:-2]}-{vuelta}{base['rut'][-1]}"
            base["nombre"] = f"{base['nombre']} (Sucursal {vuelta + 1})"

        lista_ocs = []
        for j in range(min_oc):
            oc_id = f"OC-{base['rut'][:4]}-{offset+i+1}{j+1}"
            cot_id = f"{base['rut'][:4]}-{offset+i+1}{j+1}-COT26"
            lista_ocs.append(
                OrdenCompraAgil(
                    codigo_oc=oc_id,
                    nombre_oc=f"Adquisición de {base['producto']} - Lote {j+1}",
                    codigo_licitacion_agil=cot_id,
                    organismo_comprador=base["org"],
                    rut_comprador="60.000.000-1",
                    region_comprador=base["region"],
                    comuna_comprador=base["comuna"],
                    fecha_envio="2026-09-20T10:00:00Z",
                    rut_proveedor=base["rut"],
                    nombre_proveedor=base["nombre"],
                    monto_total=1200000.0 * (j + 1),
                    items=[
                        ItemOrdenCompra(
                            correlativo=1,
                            nombre_producto=base["producto"],
                            especificacion_comprador="Entrega inmediata con despacho",
                            cantidad=10 * (j + 1),
                            unidad_medida="Unidad",
                            precio_neto=100000,
                            total_neto=1000000 * (j + 1),
                        )
                    ],
                )
            )
        resultado[base["rut"]] = lista_ocs

    return resultado


# =====================================================================
# CLI Entrypoint
# =====================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Spike: Extracción de Compra Ágil de Mercado Público y perfilamiento con IA para dataset de matching."
    )
    parser.add_argument(
        "--suppliers",
        type=int,
        default=5,
        help="Número de empresas/proveedores a evaluar en esta corrida (por defecto: 5).",
    )
    parser.add_argument(
        "--min-oc-per-supplier",
        type=int,
        default=2,
        help="Número mínimo de órdenes de compra por proveedor; define además cuántas OCs se fetchean y analizan por cada uno (por defecto: 2).",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Borra los archivos previamente generados y empieza desde 0. Si no se pasa esta flag, los nuevos datos se acumulan con los existentes.",
    )
    parser.add_argument(
        "--ticket",
        type=str,
        default=os.getenv("MERCADO_PUBLICO_API_KEY") or os.getenv("MP_TICKET") or "",
        help="Ticket de acceso API Mercado Público (por defecto lee MERCADO_PUBLICO_API_KEY del .env).",
    )
    parser.add_argument(
        "--gemini-key",
        type=str,
        default=os.getenv("GEMINI_API_KEY") or "",
        help="API Key de Google Gemini para el subagente perfilador.",
    )
    parser.add_argument(
        "--fecha",
        type=str,
        default="",
        help="Fecha a consultar en formato DDMMAAAA (o varias separadas por coma). Si no se pasa, usa --dias.",
    )
    parser.add_argument(
        "--dias",
        type=int,
        default=5,
        help="Número de días hacia atrás a consultar si no se pasa --fecha explícita (por defecto: 5 días).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Límite máximo de órdenes de compra a inspeccionar por cada fecha (por defecto: 500).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="spikes/dataset_compra_agil/data",
        help="Carpeta donde se guardará el dataset generado.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Usa datos simulados para probar el pipeline sin consumir llamadas a la API de Mercado Público.",
    )

    args = parser.parse_args()

    ticket_clean = (args.ticket or "").strip('\'"').strip()
    gemini_clean = (args.gemini_key or "").strip('\'"').strip()

    if not args.mock and not ticket_clean:
        print("\n❌ Error: No se proporcionó el ticket de Mercado Público.")
        print("Puedes pasarlo con --ticket <MI_TICKET>, definir MERCADO_PUBLICO_API_KEY en tu .env, o correr con --mock para prueba rápida.")
        sys.exit(1)

    if args.fecha:
        fechas = [f.strip() for f in args.fecha.split(",") if f.strip()]
    else:
        # Generar lista de fechas hacia atrás empezando desde hace 2 días (para asegurar días hábiles consolidados)
        fechas = [(datetime.now() - timedelta(days=i + 2)).strftime("%d%m%Y") for i in range(max(1, args.dias))]

    out_dir = Path(args.output_dir)

    asyncio.run(
        ejecutar_pipeline(
            ticket=ticket_clean,
            fechas=fechas,
            target_suppliers=args.suppliers,
            min_oc_per_supplier=args.min_oc_per_supplier,
            limite_oc_por_fecha=args.limit,
            output_dir=out_dir,
            gemini_key=gemini_clean,
            usar_mock=args.mock,
            reset=args.reset,
        )
    )


if __name__ == "__main__":
    main()
