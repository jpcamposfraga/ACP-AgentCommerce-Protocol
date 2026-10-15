from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import init_db
from app.routers import wallets, search, merchants, webhooks, checkout, trackers

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB tables if they don't exist
    await init_db()
    yield
    # Shutdown

app = FastAPI(
    title="AgentCommerce Protocol (ACP) API",
    description="The commerce, execution, and wallet layer for autonomous AI agents",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(wallets.router)
app.include_router(search.router)
app.include_router(merchants.router)
app.include_router(webhooks.router)
app.include_router(checkout.router)
app.include_router(trackers.router)

@app.get("/")
async def root():
    return {
        "name": "AgentCommerce Protocol (ACP) API",
        "version": "0.1.0",
        "status": "online",
        "docs": "/docs"
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}
