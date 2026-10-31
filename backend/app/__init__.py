"""Weather station backend package."""

# Import models so alembic can discover them
import app.models  # noqa: F401
from app.main import app  # type: ignore[no-redef]

__all__ = ["app"]
