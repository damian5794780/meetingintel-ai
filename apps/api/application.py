import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.config import Settings
from apps.api.routes.research import router
from apps.api.schemas.jobs import HealthResponse
from apps.api.services.jobs import ResearchJobs
from apps.api.store import Store


def create_app(settings: Settings | None = None, research_factory=None, llm_factory=None) -> FastAPI:
    config = settings if settings is not None else Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store = await asyncio.to_thread(Store, config.database_path)
        jobs = ResearchJobs(config, store, research_factory, llm_factory)
        await jobs.start()
        app.state.jobs = jobs
        try:
            yield
        finally:
            await jobs.stop()

    app = FastAPI(title='MeetingIntel AI', version='0.1.0', lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=[config.web_origin],
                       allow_methods=['GET', 'POST'], allow_headers=['Authorization', 'Content-Type', 'Idempotency-Key'])
    app.include_router(router)

    @app.get('/health')
    def health() -> HealthResponse:
        return HealthResponse(status='ok', live_ready=config.live_ready, demo_available=True)

    return app
