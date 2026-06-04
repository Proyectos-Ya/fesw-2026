from __future__ import annotations
from typing import Dict
from app.application.tenders.interfaces.tenders_repository import ITendersRepository
from app.application.tenders.dtos.tender_ingestion_dto import TenderIngestaDTO

class MockTendersRepository(ITendersRepository):
    def __init__(self):
        self.storage: Dict[str, TenderIngestaDTO] = {}# Simula la base de datos

    async def save(self, tender: TenderIngestaDTO) -> None:
        self.storage[tender.codigo_externo] = tender
        print(f"[Mock DB] Licitación guardada: {tender.nombre} ({tender.codigo_externo})")

    async def exists(self, codigo_externo: str) -> bool:
        return codigo_externo in self.storage