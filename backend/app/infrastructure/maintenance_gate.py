"""Puerta asíncrona compartida: solicitudes concurrentes o restauración exclusiva."""
import asyncio
from contextlib import asynccontextmanager

from app.domain.identity import IdentityError


class MaintenanceGate:
    def __init__(self):
        self.condition = asyncio.Condition()
        self.active = 0
        self.exclusive = False

    @asynccontextmanager
    async def access(self, exclusive: bool = False):
        async with self.condition:
            if self.exclusive:
                raise IdentityError(503, "Mantenimiento en curso; esperá y volvé a ingresar")
            if exclusive:
                self.exclusive = True
                try:
                    await self.condition.wait_for(lambda: self.active == 0)
                except BaseException:
                    self.exclusive = False
                    self.condition.notify_all()
                    raise
            else:
                self.active += 1
        try:
            yield
        finally:
            async with self.condition:
                if exclusive:
                    self.exclusive = False
                else:
                    self.active -= 1
                self.condition.notify_all()
