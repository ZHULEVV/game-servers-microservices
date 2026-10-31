import asyncio
import logging
from uuid import UUID

from app.dependencies import get_service
from app.settings import settings

log = logging.getLogger("deploy.runner")


async def run_deployment(deployment_id: UUID) -> None:
    """Имитация долгого развёртывания: ждём deploy_seconds, затем завершаем операцию."""
    await asyncio.sleep(settings.deploy_seconds)
    dep = await asyncio.to_thread(get_service().complete, deployment_id)
    log.info("deployment %s -> %s", deployment_id, dep.status.value)
