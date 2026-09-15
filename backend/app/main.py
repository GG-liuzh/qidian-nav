from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import (
    administration,
    auth,
    bookmarks,
    catalog,
    credentials,
    maintenance,
    personal,
    public,
    resources,
    transfer,
    workspaces,
)
from .config import Settings
from .db import make_engine, make_sessions
from .security import Vault


def create_app(settings: Settings | None = None):
    settings = settings or Settings()
    engine = make_engine(settings.resolved_database_url)

    @asynccontextmanager
    async def lifespan(app):
        if not settings.key_file.is_file():
            raise RuntimeError("请先运行 python -m app.cli init 创建密钥和数据库。")
        app.state.vault = Vault(settings.key_file.read_bytes())
        yield
        engine.dispose()

    app = FastAPI(
        title="栖点 API", version="0.1.0", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessions = make_sessions(engine)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=[host.strip() for host in settings.allowed_hosts.split(",")]
    )

    def secure_response(request, response):
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        if settings.secure_cookies:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    @app.middleware("http")
    async def boundaries(request: Request, call_next):
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if request.headers.get("origin", "").rstrip("/") not in settings.origin_list:
                return secure_response(
                    request, JSONResponse({"detail": "请求来源不受信任。"}, status_code=403)
                )
            size = 0
            chunks = []
            async for chunk in request.stream():
                size += len(chunk)
                if size > settings.request_limit:
                    return secure_response(
                        request, JSONResponse({"detail": "请求内容过大。"}, status_code=413)
                    )
                chunks.append(chunk)
            request._body = b"".join(chunks)
        return secure_response(request, await call_next(request))

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        # The server logs the exception; the client never receives internal details.
        return secure_response(
            request, JSONResponse({"detail": "服务暂时不可用，请稍后重试。"}, status_code=500)
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # FastAPI's default error includes input values, including passwords.
        labels = {
            "username": "用户名",
            "password": "密码",
            "display_name": "姓名",
            "token": "安装或邀请令牌",
            "workspace_name": "空间名称",
            "recovery_code": "账户恢复码",
            "name": "名称",
            "url": "链接地址",
            "passphrase": "迁移口令",
        }
        errors = []
        for error in exc.errors():
            field = labels.get(str(error["loc"][-1]), "该项内容")
            kind = error["type"]
            if kind == "missing":
                message = f"请填写{field}。"
            elif kind == "extra_forbidden":
                message = "页面与服务的字段不一致，请刷新页面后重试。"
            elif kind == "string_too_short":
                message = f"{field}至少需要 {error['ctx']['min_length']} 个字符。"
            elif kind == "string_too_long":
                message = f"{field}最多允许 {error['ctx']['max_length']} 个字符。"
            elif kind == "value_error":
                message = error["msg"].removeprefix("Value error, ")
            else:
                message = f"{field}格式不正确，请检查。"
            errors.append({"loc": error["loc"], "msg": message, "type": kind})
        return JSONResponse({"detail": "请检查填写内容。", "errors": errors}, status_code=422)

    @app.exception_handler(IntegrityError)
    async def integrity_error(request, exc):
        return JSONResponse({"detail": "数据有冲突或关联内容已改变，请刷新后再试。"}, status_code=409)

    @app.get("/api/v1/health")
    def health():
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok", "version": "0.1.0"}

    for router in (
        auth.router,
        catalog.router,
        resources.router,
        credentials.router,
        personal.router,
        maintenance.router,
        public.router,
        transfer.router,
        workspaces.router,
        administration.router,
        bookmarks.router,
    ):
        app.include_router(router)
    if settings.frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=settings.frontend_dist, html=True), name="frontend")
    return app
