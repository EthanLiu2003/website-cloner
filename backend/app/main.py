from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .routers import clone, health
from .services.scraper import scraper_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    await scraper_service.start()
    yield
    await scraper_service.stop()


app = FastAPI(title="Website Cloner API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(clone.router, prefix="/api")
