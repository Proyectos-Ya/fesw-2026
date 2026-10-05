"""Tests unitarios para AttachmentProcessingScheduler (plan 233, decisión 4)."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from app.infrastructure.services.attachment_processing_scheduler import (
    AsyncioProcessingSignal,
    AttachmentProcessingScheduler,
)


@pytest.mark.asyncio
async def test_signal_notify_sin_conectar_no_lanza():
    signal = AsyncioProcessingSignal()
    # No lanza aunque no esté conectado
    signal.notify()


@pytest.mark.asyncio
async def test_process_next_vacia_cola_hasta_false():
    respuestas = [True, True, False]
    llamadas_next = 0

    async def fake_process_next() -> bool:
        nonlocal llamadas_next
        if llamadas_next < len(respuestas):
            res = respuestas[llamadas_next]
        else:
            res = False
        llamadas_next += 1
        return res

    sweep_mock = AsyncMock()
    signal = AsyncioProcessingSignal()

    scheduler = AttachmentProcessingScheduler(
        process_next=fake_process_next,
        sweep=sweep_mock,
        signal=signal,
        poll_interval_seconds=3600.0,
        sweep_interval_seconds=3600.0,
        initial_delay_seconds=0.0,
    )

    tarea = asyncio.create_task(scheduler.start_loop())
    for _ in range(5):
        await asyncio.sleep(0.01)
    tarea.cancel()
    try:
        await tarea
    except asyncio.CancelledError:
        pass

    assert llamadas_next == 3
    assert sweep_mock.await_count == 1


@pytest.mark.asyncio
async def test_signal_notify_despierta_el_loop_inmediatamente():
    llamadas_next = 0

    async def fake_process_next() -> bool:
        nonlocal llamadas_next
        llamadas_next += 1
        return False

    sweep_mock = AsyncMock()
    signal = AsyncioProcessingSignal()

    scheduler = AttachmentProcessingScheduler(
        process_next=fake_process_next,
        sweep=sweep_mock,
        signal=signal,
        poll_interval_seconds=3600.0,
        sweep_interval_seconds=3600.0,
        initial_delay_seconds=0.0,
    )

    tarea = asyncio.create_task(scheduler.start_loop())
    await asyncio.sleep(0.01)
    assert llamadas_next == 1

    # Emitir señal
    signal.notify()
    for _ in range(5):
        await asyncio.sleep(0.01)
    tarea.cancel()
    try:
        await tarea
    except asyncio.CancelledError:
        pass

    assert llamadas_next >= 2


@pytest.mark.asyncio
async def test_error_en_primera_llamada_no_detiene_loop():
    llamadas_next = 0

    async def fake_process_next() -> bool:
        nonlocal llamadas_next
        llamadas_next += 1
        if llamadas_next == 1:
            raise RuntimeError("error temporal en bd")
        return False

    sweep_mock = AsyncMock()
    signal = AsyncioProcessingSignal()

    scheduler = AttachmentProcessingScheduler(
        process_next=fake_process_next,
        sweep=sweep_mock,
        signal=signal,
        poll_interval_seconds=0.001,
        sweep_interval_seconds=3600.0,
        initial_delay_seconds=0.0,
    )

    tarea = asyncio.create_task(scheduler.start_loop())
    while llamadas_next < 2:
        await asyncio.sleep(0.005)
    tarea.cancel()
    try:
        await tarea
    except asyncio.CancelledError:
        pass

    assert llamadas_next >= 2


@pytest.mark.asyncio
async def test_barrido_no_corre_de_nuevo_antes_del_intervalo():
    tiempo_actual = 100.0

    def fake_monotonic() -> float:
        return tiempo_actual

    sweep_count = 0

    async def fake_sweep():
        nonlocal sweep_count
        sweep_count += 1

    async def fake_process_next() -> bool:
        return False

    signal = AsyncioProcessingSignal()
    scheduler = AttachmentProcessingScheduler(
        process_next=fake_process_next,
        sweep=fake_sweep,
        signal=signal,
        poll_interval_seconds=0.001,
        sweep_interval_seconds=300.0,
        initial_delay_seconds=0.0,
        monotonic=fake_monotonic,
    )

    tarea = asyncio.create_task(scheduler.start_loop())
    await asyncio.sleep(0.01)
    assert sweep_count == 1

    # Tiempo no avanzó 300s
    tiempo_actual = 200.0
    signal.notify()
    await asyncio.sleep(0.01)
    assert sweep_count == 1

    # Ahora sí avanzó
    tiempo_actual = 450.0
    signal.notify()
    await asyncio.sleep(0.01)
    tarea.cancel()
    try:
        await tarea
    except asyncio.CancelledError:
        pass

    assert sweep_count == 2


@pytest.mark.asyncio
async def test_concurrencia_estricta_1():
    concurrencia_actual = 0
    max_concurrencia = 0
    llamadas = 0

    async def fake_process_next() -> bool:
        nonlocal concurrencia_actual, max_concurrencia, llamadas
        concurrencia_actual += 1
        max_concurrencia = max(max_concurrencia, concurrencia_actual)
        llamadas += 1
        await asyncio.sleep(0.005)
        concurrencia_actual -= 1
        return llamadas < 5

    sweep_mock = AsyncMock()
    signal = AsyncioProcessingSignal()
    scheduler = AttachmentProcessingScheduler(
        process_next=fake_process_next,
        sweep=sweep_mock,
        signal=signal,
        poll_interval_seconds=3600.0,
        sweep_interval_seconds=3600.0,
        initial_delay_seconds=0.0,
    )

    tarea = asyncio.create_task(scheduler.start_loop())

    # Disparar múltiples notify concurrentes
    for _ in range(10):
        signal.notify()

    while llamadas < 5:
        await asyncio.sleep(0.01)

    tarea.cancel()
    try:
        await tarea
    except asyncio.CancelledError:
        pass

    assert max_concurrencia == 1
    assert llamadas >= 5
