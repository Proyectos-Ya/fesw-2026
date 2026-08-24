import asyncio
import sys
from datetime import UTC, datetime, timedelta
from uuid import UUID

import asyncpg
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

EXCEL_PATH = "d:/ProyectosYA/project-data/chiripa_tenders.xlsx"
DST_DB = "proyectosya_db"
DST_USER = "proyectosya"
DST_PASSWORD = "proyectosya_secret"
DST_HOST = "172.29.211.10"
DST_PORT = 5432

def clean_val(val):
    if pd.isna(val) or val is None:
        return None
    if isinstance(val, (np.integer, int)):
        return int(val)
    if isinstance(val, (np.floating, float)):
        return float(val)
    if isinstance(val, (pd.Timestamp, np.datetime64)):
        return pd.to_datetime(val).to_pydatetime()
    return val

async def main():
    print(f"[RELOAD] Leyendo {EXCEL_PATH}...")
    excel = pd.ExcelFile(EXCEL_PATH)
    conn = await asyncpg.connect(database=DST_DB, user=DST_USER, password=DST_PASSWORD, host=DST_HOST, port=DST_PORT)

    future_date = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=30)
    now_naive = datetime.now(UTC).replace(tzinfo=None)

    # 1. region
    df_reg = excel.parse("region")
    for _, row in df_reg.iterrows():
        await conn.execute("INSERT INTO region (id, name) VALUES ($1, $2) ON CONFLICT (id) DO NOTHING;", int(row["id"]), str(row["name"]))
    print("✓ Region cargada")

    # 2. tender_status
    df_st = excel.parse("tender_status")
    for _, row in df_st.iterrows():
        await conn.execute("INSERT INTO tender_status (id, code, name) VALUES ($1, $2, $3) ON CONFLICT (id) DO NOTHING;", int(row["id"]), str(row["code"]), str(row["name"]))
    print("✓ Status cargado")

    # 3. buyer_institution
    df_b = excel.parse("buyer_institution")
    for _, row in df_b.iterrows():
        b_rut = str(row["rut"])
        b_name = str(row["name"])
        b_reg = int(row["region_id"]) if "region_id" in row and not pd.isna(row["region_id"]) else None
        b_created = clean_val(row.get("created_at")) or now_naive
        b_updated = clean_val(row.get("updated_at")) or now_naive
        await conn.execute("INSERT INTO buyer_institution (rut, name, region_id, created_at, updated_at) VALUES ($1, $2, $3, $4, $5) ON CONFLICT (rut) DO NOTHING;", b_rut, b_name, b_reg, b_created, b_updated)
    print("✓ Buyer cargado")

    # 4. tender
    df_t = excel.parse("tender")
    t_count = 0
    for _, row in df_t.iterrows():
        t_id = UUID(str(row["id"]))
        t_code = str(row["code"]) if not pd.isna(row["code"]) else str(t_id)
        t_name = str(row["name"]) if not pd.isna(row["name"]) else ""
        t_desc = str(row["description"]) if not pd.isna(row["description"]) else None
        t_status = int(row["status_id"]) if not pd.isna(row["status_id"]) else 1
        t_pub = clean_val(row["published_at"])
        t_last = clean_val(row["last_change_at"])
        t_close = future_date # Activamos todas las licitaciones por 30 días
        t_buyer_rut = str(row["buyer_rut"]) if not pd.isna(row["buyer_rut"]) else None
        t_buyer_unit = str(row["buyer_unit"]) if not pd.isna(row["buyer_unit"]) else None
        t_prov = str(row["province"]) if not pd.isna(row["province"]) else None
        t_amount = float(row["available_amount_clp"]) if not pd.isna(row["available_amount_clp"]) else None
        t_created = clean_val(row.get("created_at")) or now_naive
        t_updated = clean_val(row.get("updated_at")) or now_naive

        await conn.execute("""
            INSERT INTO tender (
                id, code, name, description, status_id, published_at, closing_at,
                last_change_at, buyer_rut, buyer_unit, province, available_amount_clp, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            ON CONFLICT (id) DO UPDATE SET closing_at = EXCLUDED.closing_at;
        """, t_id, t_code, t_name, t_desc, t_status, t_pub, t_close, t_last, t_buyer_rut, t_buyer_unit, t_prov, t_amount, t_created, t_updated)
        t_count += 1
    print(f"✓ {t_count} Licitaciones cargadas en tender")

    # 5. tender_item
    df_ti = excel.parse("tender_item")
    ti_count = 0
    for _, row in df_ti.iterrows():
        ti_id = UUID(str(row["id"]))
        ti_tender_id = UUID(str(row["tender_id"]))
        ti_prod_code = str(row["product_code"]) if not pd.isna(row["product_code"]) else ""
        ti_name = str(row["name"]) if not pd.isna(row["name"]) else ""
        ti_desc = str(row["description"]) if not pd.isna(row["description"]) else None
        ti_qty = float(row["quantity"]) if not pd.isna(row["quantity"]) else 1.0
        ti_unit = str(row["unit_of_measure"]) if not pd.isna(row["unit_of_measure"]) else "UN"

        await conn.execute("""
            INSERT INTO tender_item (
                id, tender_id, product_code, name, description, quantity, unit_of_measure
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (id) DO NOTHING;
        """, ti_id, ti_tender_id, ti_prod_code, ti_name, ti_desc, ti_qty, ti_unit)
        ti_count += 1
    print(f"✓ {ti_count} Items cargados en tender_item")

    final_t = await conn.fetchval("SELECT COUNT(*) FROM tender;")
    final_ti = await conn.fetchval("SELECT COUNT(*) FROM tender_item;")
    print(f"\n[SUCCESS] PostgreSQL listo con {final_t} licitaciones y {final_ti} items!")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
