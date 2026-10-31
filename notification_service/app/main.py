import asyncio
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app import rabbitmq
from app.endpoints.notification_router import router
from app.errors import DomainError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Notification Service", version="1.0")


@app.on_event("startup")
async def startup():
    loop = asyncio.get_event_loop()
    asyncio.ensure_future(rabbitmq.consume(loop))


@app.exception_handler(DomainError)
async def domain_error_handler(_: Request, exc: DomainError):
    return JSONResponse(status_code=exc.status, content={"code": exc.code, "message": exc.message})


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    err = exc.errors()[0]
    return JSONResponse(status_code=400, content={"code": "validation_error",
                                                  "message": f"{err['msg']} ({'.'.join(str(x) for x in err['loc'])})"})


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}


app.include_router(router, prefix="/api")
