"""Safe application exceptions and a single public error envelope."""

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class AppError(Exception):
    """An exception whose public message is deliberately safe to expose."""

    status_code = 500
    code = "internal_error"
    public_message = "An internal error occurred."

    def __init__(self, *, operation: str | None = None, upstream_status: int | None = None) -> None:
        self.operation = operation
        self.upstream_status = upstream_status
        super().__init__(self.public_message)


class DatabaseUnavailable(AppError):
    status_code = 503
    code = "database_unavailable"
    public_message = "The database is unavailable."


class OllamaError(AppError):
    status_code = 502
    code = "ollama_error"
    public_message = "The Ollama request failed."


class OllamaUnreachable(OllamaError):
    status_code = 503
    code = "ollama_unreachable"
    public_message = "Ollama is unavailable."


class ModelNotFound(OllamaError):
    status_code = 404
    code = "model_not_found"
    public_message = "The requested Ollama model was not found."


class OllamaInvalidResponse(OllamaError):
    status_code = 502
    code = "ollama_invalid_response"
    public_message = "Ollama returned an invalid response."
