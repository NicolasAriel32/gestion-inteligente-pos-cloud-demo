"""Servidor de desarrollo en loopback; mismo bloqueo que mantenimiento/launcher."""
from uuid import uuid4

import uvicorn

from app.infrastructure.database import get_db_path
from app.main import create_app
from app.runtime import InstanceLock

if __name__ == '__main__':
    path = get_db_path()
    lock = InstanceLock(path.parent.parent / 'config' / 'instance.lock')
    if not lock.acquire():
        raise SystemExit('La aplicación ya está iniciada; no se abrió otra instancia')
    try:
        application = create_app(path)
        instance = str(uuid4())
        lock.publish(instance)
        application.state.instance_id = instance
        uvicorn.run(application, host='127.0.0.1', port=8765)
    finally:
        lock.release()
