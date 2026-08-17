import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db import init_db
from app.pseudogram_client import PseudogramClient
from app.reconciler import Reconciler
from app.routes.rules import router as rules_router
from app.routes.stats import router as stats_router
from app.routes.webhook import router as webhook_router
from app.worker import SlidingWindowRateLimiter, Worker

worker_instance: Worker | None = None
reconciler_instance: Reconciler | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global worker_instance, reconciler_instance

    init_db()

    client = PseudogramClient()
    rate_limiter = SlidingWindowRateLimiter(max_requests=10, window_seconds=60.0)

    worker_instance = Worker(client=client, rate_limiter=rate_limiter, max_attempts=5)
    reconciler_instance = Reconciler(client=client, poll_interval=10.0, age_threshold=30.0, max_attempts=5)

    worker_task = asyncio.create_task(worker_instance.run())
    reconciler_task = asyncio.create_task(reconciler_instance.run())

    yield

    if worker_instance:
        worker_instance.stop()
    if reconciler_instance:
        reconciler_instance.stop()

    worker_task.cancel()
    reconciler_task.cancel()
    await asyncio.gather(worker_task, reconciler_task, return_exceptions=True)


app = FastAPI(title="Instagram Automation Backend", lifespan=lifespan)

app.include_router(rules_router)
app.include_router(webhook_router)
app.include_router(stats_router)


@app.get("/")
async def root():
    return {"service": "Instagram Automation Backend", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "ok"}
