from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.message = message


def not_found() -> AppError:
    # Also used for another caterer's resources, so their existence isn't revealed.
    return AppError(404, "not_found", "הפריט לא נמצא")


def unauthenticated() -> AppError:
    return AppError(401, "unauthenticated", "נדרשת התחברות")


def forbidden() -> AppError:
    return AppError(403, "forbidden", "אין הרשאה לפעולה זו")


def conflict(message: str) -> AppError:
    return AppError(409, "conflict", message)


def _body(code: str, message: str, details: object = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(_body(exc.code, exc.message), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Only loc and type: the raw input may hold personal data.
        fields = [{"loc": list(e["loc"]), "type": e["type"]} for e in exc.errors()]
        body = _body("validation_error", "הנתונים שנשלחו אינם תקינים", {"fields": fields})
        return JSONResponse(body, status_code=422)
