from __future__ import annotations
from fastapi import FastAPI
from linkground import __version__
from linkground.api.routes import router

def create_app() -> FastAPI:
    app = FastAPI(
        title="LinkGround API",
        description="Score a statement against crawled URLs. Support and prestige stay separate.",
        version=__version__,
    )
    app.include_router(router)
    return app
app = create_app()
