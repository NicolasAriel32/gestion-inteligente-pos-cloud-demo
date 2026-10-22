import asyncio

import pytest

from app.domain.identity import IdentityError
from app.infrastructure.maintenance_gate import MaintenanceGate


def test_gate_drains_requests_rejects_new_and_releases_after_failure():
    async def scenario():
        gate = MaintenanceGate()
        release = asyncio.Event()
        started = asyncio.Event()
        order = []
        async def reader():
            async with gate.access():
                started.set(); await release.wait(); order.append('request_finished')
        async def restore():
            async with gate.access(exclusive=True):
                order.append('restore_started')
                raise OSError('restore failed')
        pending = asyncio.create_task(reader()); await started.wait()
        maintenance = asyncio.create_task(restore())
        await asyncio.sleep(0)
        assert gate.exclusive and gate.active == 1
        with pytest.raises(IdentityError, match='Mantenimiento'):
            async with gate.access():
                pytest.fail('No debe entrar una solicitud nueva')
        release.set()
        await pending
        with pytest.raises(OSError):
            await maintenance
        assert order == ['request_finished', 'restore_started']
        async with gate.access():
            assert gate.active == 1 and not gate.exclusive
    asyncio.run(scenario())
