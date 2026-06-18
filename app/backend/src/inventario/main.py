from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_app() -> FastAPI:
    app = FastAPI(title="Inventário")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    from .api.produtos import router as produtos_router
    from .api.movimentacoes import router as movimentacoes_router
    from .api.operacao import router as operacao_router

    app.include_router(produtos_router)
    app.include_router(movimentacoes_router)
    app.include_router(operacao_router)

    return app


app = create_app()
