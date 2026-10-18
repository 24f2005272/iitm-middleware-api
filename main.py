import os
import time
import uuid
import math
from collections import defaultdict, deque
from threading import Lock

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI()

EMAIL = "24f2005272@ds.study.iitm.ac.in"
ALLOWED_ORIGIN = "https://app-b26uca.example.com"

RATE_LIMIT = 10
WINDOW = 10.0

buckets = defaultdict(deque)
lock = Lock()


# Middleware 1: Request context
@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID")
    if not request_id:
        request_id = str(uuid.uuid4())

    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# Middleware 2: Per-client rate limiting
@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)

    client_id = request.headers.get(
        "X-Client-Id", "anonymous"
    )
    now = time.monotonic()

    with lock:
        bucket = buckets[client_id]

        while bucket and now - bucket[0] >= WINDOW:
            bucket.popleft()

        if len(bucket) >= RATE_LIMIT:
            wait = max(
                1,
                math.ceil(WINDOW - (now - bucket[0]))
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": str(wait)},
            )

        bucket.append(now)

    return await call_next(request)


# Middleware 3: Scoped CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        ALLOWED_ORIGIN,
        *[
            origin.strip()
            for origin in os.getenv(
                "EXAM_ORIGIN", ""
            ).split(",")
            if origin.strip()
        ],
    ],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=[
        "X-Client-Id",
        "X-Request-ID",
        "Content-Type",
    ],
    expose_headers=["X-Request-ID", "Retry-After"],
    allow_credentials=False,
)


@app.get("/ping")
async def ping(request: Request):
    return {
        "email": EMAIL,
        "request_id": request.state.request_id,
    }


@app.get("/")
async def home():
    return {"status": "ok"}
