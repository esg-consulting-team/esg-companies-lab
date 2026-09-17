from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import comparison, companies, dashboard, documents, domains, items, reports, roadmap

settings = get_settings()

app = FastAPI(title="ESG 진단 콘솔 API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(companies.router)
app.include_router(dashboard.router)
app.include_router(domains.router)
app.include_router(items.router)
app.include_router(comparison.router)
app.include_router(roadmap.router)
app.include_router(documents.router)
app.include_router(reports.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
