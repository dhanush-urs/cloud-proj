from google import genai
try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

from app.core.config import get_settings
from app.embeddings.embedding_engine import LocalEmbeddingEngine


class EmbeddingProvider:
    def embed_text(self, text: str) -> list[float]:
        raise NotImplementedError

    @property
    def model_name(self) -> str:
        raise NotImplementedError


class LocalEmbeddingProvider(EmbeddingProvider):
    """Hashing-based lightweight vectorizer (fallback of fallbacks)"""
    def __init__(self):
        self.engine = LocalEmbeddingEngine()

    def embed_text(self, text: str) -> list[float]:
        return self.engine.embed_text(text)

    @property
    def model_name(self) -> str:
        return self.engine.model_name


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """Real local embedding provider using sentence-transformers"""
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        if SentenceTransformer is None:
            raise ImportError("sentence-transformers is not installed")
        self._model_name = model_name
        self.model = SentenceTransformer(model_name)

    def embed_text(self, text: str) -> list[float]:
        # Perform embedding and ensure it's a list of floats
        vector = self.model.encode(text)
        return vector.tolist()

    @property
    def model_name(self) -> str:
        return f"local-{self._model_name}"


class GeminiEmbeddingProvider(EmbeddingProvider):
    def __init__(self):
        settings = get_settings()

        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is required for Gemini embeddings")

        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        # Standardize: remove 'models/' prefix if user provided it, or keep it if SDK wants it.
        # But we will use what's in the config.
        self._model_name = settings.GEMINI_EMBEDDING_MODEL

    def embed_text(self, text: str) -> list[float]:
        # Resilient call
        try:
            response = self.client.models.embed_content(
                model=self._model_name,
                contents=text,
            )
            # Some versions of the SDK might return a list directly or a nested response
            if hasattr(response, "embeddings") and len(response.embeddings) > 0:
                values = response.embeddings[0].values
                return [float(x) for x in values]
            
            # Fallback for different SDK response shapes
            if hasattr(response, "values"):
                return [float(x) for x in response.values]
                
            raise ValueError(f"Unexpected Gemini embedding response shape: {type(response)}")
        except Exception as e:
            print(f"[ERROR] Gemini embedding failed: {e}")
            raise e

    @property
    def model_name(self) -> str:
        return self._model_name


class ChatProvider:
    def answer(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError

    @property
    def model_name(self) -> str:
        raise NotImplementedError


class GeminiChatProvider(ChatProvider):
    def __init__(self):
        settings = get_settings()

        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is required for Gemini chat")

        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self._model_name = settings.GEMINI_CHAT_MODEL

    def answer(self, system_prompt: str, user_prompt: str) -> str:
        combined_prompt = (
            f"System Instructions:\n{system_prompt}\n\n"
            f"User Request:\n{user_prompt}"
        )

        response = self.client.models.generate_content(
            model=self._model_name,
            contents=combined_prompt,
        )

        text = getattr(response, "text", None)
        if text:
            return text.strip()

        # Fallback extraction for SDK variations
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if not content:
                continue
            parts = getattr(content, "parts", None) or []
            for part in parts:
                part_text = getattr(part, "text", None)
                if part_text:
                    return part_text.strip()

        return ""

    @property
    def model_name(self) -> str:
        return self._model_name


def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    provider_type = settings.EMBEDDING_PROVIDER.lower().strip()

    # Priority 1: Gemini (if enabled and key present)
    if provider_type == "gemini" and settings.ENABLE_GEMINI:
        try:
            return GeminiEmbeddingProvider()
        except Exception as e:
            print(f"[WARN] Failed to init GeminiEmbeddingProvider, falling back to Local SentenceTransformer: {e}")

    # Priority 2: SentenceTransformer (Local High-Quality)
    try:
        return SentenceTransformerEmbeddingProvider()
    except Exception as e:
        print(f"[WARN] Failed to init SentenceTransformerEmbeddingProvider, falling back to Hashing: {e}")

    # Priority 3: Hashing (Fallback of fallbacks)
    return LocalEmbeddingProvider()


def get_chat_provider() -> ChatProvider | None:
    settings = get_settings()

    provider = settings.LLM_PROVIDER.lower().strip()

    print(f"[ASK_REPO] LLM_PROVIDER={provider!r}")

    if provider == "gemini":
        # Respect the ENABLE_GEMINI flag
        if not settings.ENABLE_GEMINI:
            print("[ASK_REPO] Gemini DISABLED — ENABLE_GEMINI=false. Using deterministic fallback.")
            return None

        # Reject placeholder/compromised keys
        api_key = settings.GEMINI_API_KEY or ""
        key_preview = api_key[:8] + "..." if len(api_key) >= 8 else "(empty)"
        print(f"[ASK_REPO] GEMINI_API_KEY present: {'yes' if api_key else 'no'} — preview: {key_preview}")

        if not api_key or api_key.startswith("AIzaSyC...") or len(api_key) < 20:
            print("[ASK_REPO] GEMINI_API_KEY is missing or placeholder. Using deterministic fallback.")
            return None

        print(f"[ASK_REPO] Initializing GeminiChatProvider with model={settings.GEMINI_CHAT_MODEL!r}")
        try:
            provider_obj = GeminiChatProvider()
            print(f"[ASK_REPO] GeminiChatProvider initialized OK — model={provider_obj.model_name!r}")
            return provider_obj
        except Exception as e:
            print(f"[ASK_REPO][ERROR] Failed to init GeminiChatProvider: {e}")
            return None

    print(f"[ASK_REPO] No chat provider matched for LLM_PROVIDER={provider!r}. Using deterministic fallback.")
    return None
