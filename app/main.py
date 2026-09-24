from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database import Base, engine
from app.routes.mandates import router as mandate_router
from app.routes.payments import router as payment_router
from app.scheduler import start_scheduler, stop_scheduler

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(
    title="Recurring Payment Mandate Management Platform",
    version="1.0.0",
    lifespan=lifespan,
    description=(
        "Hackathon simulation for recurring payment mandates, scheduled execution, "
        "transaction tracking, retries, idempotency, audit logging and analytics."
    ),
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@app.get("/", include_in_schema=False)
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"request": request},
    )


@app.get("/health", tags=["System"])
def health():
    return {"status": "ok"}


app.include_router(mandate_router)
app.include_router(payment_router)
