import hashlib
import json
import math
import re


TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_./:-]*")


class LocalEmbeddingEngine:
    def __init__(self, dimension: int = 128):
        self.dimension = dimension
        self.model_name = f"local-hash-{dimension}d"

    def embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension

        tokens = TOKEN_RE.findall(text.lower())
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
            bucket = int(digest[:8], 16) % self.dimension
            sign = 1.0 if int(digest[8:10], 16) % 2 == 0 else -1.0
            weight = 1.0 + min(len(token) / 20.0, 1.5)
            vector[bucket] += sign * weight

        return self._normalize(vector)

    def serialize(self, vector: list[float]) -> str:
        return json.dumps(vector)

    def deserialize(self, payload: str | None) -> list[float]:
        if not payload:
            return [0.0] * self.dimension

        try:
            data = json.loads(payload)
            if isinstance(data, list):
                return [float(x) for x in data]
        except Exception:
            pass

        return [0.0] * self.dimension

    def cosine_similarity(self, a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0

        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))

        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0

        return dot / (norm_a * norm_b)

    def _normalize(self, vector: list[float]) -> list[float]:
        norm = math.sqrt(sum(x * x for x in vector))
        if norm == 0.0:
            return vector
        return [x / norm for x in vector]
