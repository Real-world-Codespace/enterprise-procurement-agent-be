from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, SessionLocal, engine
from .config import CORS_ORIGINS
from .routers import auth, dashboard, requests
from .seed import seed

Base.metadata.create_all(bind=engine)
with SessionLocal() as session:
    seed(session)

app = FastAPI(title="Enterprise Procurement Agent API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router, prefix="/api")
app.include_router(requests.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}
