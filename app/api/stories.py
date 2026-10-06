"""Read-only web API for approved local stories."""

from dataclasses import asdict
from fastapi import APIRouter, HTTPException, Query
from app.config import get_settings
from app.stories.library import StoryLibrary, StoryNotAvailableError
from app.stories.embeddings import LocalEmbeddingClient

router = APIRouter(prefix="/api/stories", tags=["stories"])
settings = get_settings()
story_library = StoryLibrary(settings.story_library_root, LocalEmbeddingClient(settings.story_embedding_base_url, settings.story_embedding_model, settings.story_embedding_timeout_seconds))


@router.get("/status")
def status() -> dict[str, object]:
    return {"enabled": settings.story_library_enabled, "cloud_enabled": settings.story_cloud_enabled,
            "local_llm_provider": settings.story_local_llm_provider, "languages": ["en", "pt", "es"],
            **story_library.report()}


@router.get("")
def listing(language: str | None = None, age: int | None = Query(None, ge=0, le=120)):
    try: return {"stories": story_library.list_stories(language=language, age=age)}
    except ValueError as exc: raise HTTPException(400, str(exc)) from exc


@router.get("/search")
def search(q: str = Query(min_length=1, max_length=300), language: str | None = None, age: int | None = Query(None, ge=0, le=120)):
    try: return {"results": [asdict(item) for item in story_library.search(q, language=language, age=age)]}
    except ValueError as exc: raise HTTPException(400, str(exc)) from exc


@router.get("/{story_id}")
def detail(story_id: str):
    try: return story_library.get_story(story_id, include_text=False)
    except StoryNotAvailableError as exc: raise HTTPException(404, "Story not found") from exc
