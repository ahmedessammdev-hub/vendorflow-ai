from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, settings
from app.core.config import Settings


def create_app(config: Settings | None = None) -> FastAPI:
    application = FastAPI(title="VendorFlow AI", version="0.1.0")
    application.state.settings = config if config is not None else Settings()
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:4200"],
        allow_methods=["GET"],
        allow_headers=["Content-Type"],
    )
    application.include_router(health.router, prefix="/api")
    application.include_router(settings.router, prefix="/api")
    return application


app = create_app()
