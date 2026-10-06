"""Deterministic multilingual story intent and session engine."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.stories.library import StoryLibrary
from app.stories.types import StoryTurn


@dataclass(slots=True)
class _Session:
    story_id: str | None = None
    next_section: int = 1
    language: str = "pt"
    pending_section: int | None = None


class StoryEngine:
    def __init__(self, library: StoryLibrary) -> None:
        self.library = library
        self._sessions: dict[str, _Session] = {}

    @staticmethod
    def _language(text: str) -> str:
        lowered = text.casefold()
        if any(word in lowered for word in (" cuento", "historia", "lee ", "inventa")): return "es"
        if any(word in lowered for word in (" story", "read ", "tell ", "create ")): return "en"
        return "pt"

    @staticmethod
    def _query(text: str) -> str:
        cleaned = re.sub(r"(?i)\b(por favor|please|por favor|uma|um|a|the|la|el)\b", " ", text)
        cleaned = re.sub(r"(?i)\b(leia|ler|conte|contar|reconte|read|tell|retell|lee|cuenta|história|historia|story|cuento)\b", " ", cleaned)
        return re.sub(r"\s+", " ", cleaned).strip(" .?!,:\"")

    def forget(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def confirm_playback(self, session_id: str) -> None:
        state = self._sessions.get(session_id)
        if state is not None and state.pending_section is not None:
            state.next_section = state.pending_section + 1
            state.pending_section = None
            if state.story_id:
                self.library.save_progress(session_id, state.story_id, state.next_section, state.language)

    def _state(self, session_id: str) -> _Session:
        if session_id not in self._sessions:
            saved = self.library.load_progress(session_id)
            self._sessions[session_id] = _Session(
                story_id=str(saved["story_id"]) if saved else None,
                next_section=int(saved["next_section"]) if saved else 1,
                language=str(saved["language"]) if saved else "pt",
            )
        return self._sessions[session_id]

    def handle(self, session_id: str, text: str) -> StoryTurn | None:
        lowered = f" {text.casefold()} "
        state = self._state(session_id)
        language = self._language(lowered)
        list_words = ("liste histórias", "listar histórias", "quais histórias", "que histórias", "list stories", "what stories", "which stories", "lista cuentos", "qué cuentos", "que cuentos")
        if any(word in lowered for word in list_words):
            items = self.library.list_stories(language=language, limit=8)
            names = ", ".join(str(item["title"]) for item in items)
            intro = {"pt": "Histórias disponíveis: ", "en": "Available stories: ", "es": "Cuentos disponibles: "}[language]
            return StoryTurn("READ_EXACT", language, (intro + (names or "—"),))

        if any(word in lowered for word in (" continue", "continue ", " continuar", "continua ", " sigue", "next section")) and state.story_id:
            story = self.library.get_story(state.story_id)
            sections = story["sections"]
            requested_section = state.pending_section or state.next_section
            section = next((item for item in sections if item["section_order"] == requested_section), None)
            if section is None:
                end = {"pt": "Fim da história.", "en": "The story is finished.", "es": "Fin del cuento."}[state.language]
                return StoryTurn("READ_EXACT", state.language, (end,), story_id=state.story_id)
            state.pending_section = requested_section
            return StoryTurn("READ_EXACT", state.language, (section["text"],), story_id=state.story_id)

        create_words = (" crie uma história", " invente uma história", " história curta sobre", " create a story", " story about", " inventa un cuento", " cuento sobre")
        if any(word in lowered for word in create_words):
            prompt = f"Create a short, age-appropriate story in language '{language}'. User request: {text}. Do not claim it comes from the catalog."
            return StoryTurn("CREATE", language, llm_prompt=prompt)

        if any(word in lowered for word in (" interativa", " interativo", " interactive", " interactivo", " interactiva")):
            prompt = f"Begin or continue a short interactive children's story in '{language}'. Offer exactly two safe choices, preserve prior choices from conversation history, and identify it as original fiction. User request: {text}"
            return StoryTurn("INTERACTIVE", language, llm_prompt=prompt, story_id=state.story_id)

        read_words = (" leia", " conte", " read", " tell", " lee", " cuenta")
        read_words += (" cuéntame", " léeme")
        retell = any(word in lowered for word in ("reconte", "retell", "resume", "resuma"))
        if any(word in lowered for word in read_words) or retell:
            query = self._query(text)
            refers_to_active = state.story_id and any(word in lowered for word in (" essa história", " esta história", " that story", " this story", " ese cuento", " este cuento", " para uma criança", " for a child", " para un niño"))
            results = []
            if refers_to_active:
                active = self.library.get_story(state.story_id)
                story = active
            else:
                results = self.library.search(query, language=language, limit=3) if query else []
            if not results:
                if refers_to_active:
                    pass
                else:
                    message = {"pt": "Não encontrei uma história aprovada com esse nome. Posso listar as histórias locais disponíveis.", "en": "I could not find an approved story with that name. I can list the available local stories.", "es": "No encontré un cuento aprobado con ese nombre. Puedo listar los cuentos locales disponibles."}[language]
                    return StoryTurn("READ_EXACT", language, (message,))
            if not refers_to_active:
                story = self.library.get_story(results[0].story_id)
                state.story_id = results[0].story_id
            else:
                state.story_id = str(story["story_id"])
            state.language = story["language"]
            if retell:
                source = "\n\n".join(item["text"] for item in story["sections"])
                return StoryTurn("RETELL", story["language"], llm_prompt=f"Retell this approved story briefly in {story['language']}. Preserve its meaning and say that this is an adaptation.\n\n{source}", story_id=state.story_id)
            state.next_section = 1
            state.pending_section = 1
            return StoryTurn("READ_EXACT", story["language"], (story["sections"][0]["text"],), story_id=state.story_id)

        if state.story_id and text.rstrip().endswith("?"):
            evidence = self.library.chunks_for_question(state.story_id, text, through_section=max(1, state.next_section - 1))
            context = "\n\n".join(item["text"] for item in evidence)
            prompt = f"Answer in {state.language} using only the story excerpts below. Avoid spoilers beyond them. If unknown, say so.\nQuestion: {text}\nExcerpts:\n{context}"
            return StoryTurn("ASK_ABOUT_STORY", state.language, llm_prompt=prompt, story_id=state.story_id)
        if any(word in lowered for word in (" história", " story", " cuento")):
            message = {"pt": "Não entendi qual modo de história você quer. Posso listar, ler, recontar ou criar uma história local.", "en": "I did not understand the story mode. I can list, read, retell, or create a local story.", "es": "No entendí el modo de cuento. Puedo listar, leer, volver a contar o crear un cuento local."}[language]
            return StoryTurn("READ_EXACT", language, (message,))
        return None
