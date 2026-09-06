from __future__ import annotations
from fastapi import FastAPI
from linkground import __version__
from linkground.api.routes import router

def create_app() -> FastAPI:
    app = FastAPI(title='LinkGround API', description='APIs for measuring LLM outputs using linked sources: continuous groundedness against crawled evidence, weighted by Open PageRank authority.', version=__version__)
    app.include_router(router)
    return app
app = create_app()
