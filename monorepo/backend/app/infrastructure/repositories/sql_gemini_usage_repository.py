"""Implementación SQL del registro de cuota diaria de Gemini (plan 233, decisión 4)."""

from datetime import date

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.gemini_usage_repository import (
    IGeminiUsageRepository,
)
from app.infrastructure.repositories.attachment_processing_model import (
    AttachmentGeminiDailyUsageModel,
)


class SqlGeminiUsageRepository(IGeminiUsageRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def try_reserve_call(self, *, day: date, limit: int) -> bool:
        tabla = AttachmentGeminiDailyUsageModel.__table__
        stmt = (
            pg_insert(AttachmentGeminiDailyUsageModel)
            .values(day=day, calls=1, prompt_tokens=0, output_tokens=0)
            .on_conflict_do_update(
                index_elements=["day"],
                set_={"calls": tabla.c.calls + 1},
                where=tabla.c.calls < limit,
            )
            .returning(tabla.c.calls)
        )
        filas = (await self.session.exec(stmt)).all()  # type: ignore[call-overload]
        if not filas:
            await self.session.rollback()
            return False
        await self.session.commit()
        return True

    async def add_tokens(
        self, *, day: date, prompt_tokens: int, output_tokens: int
    ) -> None:
        tabla = AttachmentGeminiDailyUsageModel.__table__
        stmt = (
            pg_insert(AttachmentGeminiDailyUsageModel)
            .values(
                day=day,
                calls=0,
                prompt_tokens=prompt_tokens,
                output_tokens=output_tokens,
            )
            .on_conflict_do_update(
                index_elements=["day"],
                set_={
                    "prompt_tokens": tabla.c.prompt_tokens + prompt_tokens,
                    "output_tokens": tabla.c.output_tokens + output_tokens,
                },
            )
        )
        await self.session.exec(stmt)
        await self.session.commit()

    async def calls_on(self, day: date) -> int:
        modelo = await self.session.get(AttachmentGeminiDailyUsageModel, day)
        return modelo.calls if modelo is not None else 0
