"""Optional CPU sentence encoders. Never silently substitute hash vectors."""

import logging
import math
from functools import lru_cache
from threading import Lock

from .config import get_settings
from .providers import ProviderError

logger = logging.getLogger("filinglens.models")
_lock = Lock()


@lru_cache(maxsize=2)
def load_encoder(name):
    try:
        from sentence_transformers import SentenceTransformer, models

        logger.info("model_loading model=%s (first use downloads weights; later uses the local cache)", name)
        if name == "ProsusAI/finbert":
            # FinBERT is a sentiment classifier, not a trained sentence encoder.
            # Explicit mean pooling makes this an experimental retrieval baseline.
            transformer = models.Transformer(name, max_seq_length=512)
            encoder = SentenceTransformer(
                modules=[transformer, models.Pooling(transformer.get_word_embedding_dimension())],
                device="cpu",
            )
        else:
            encoder = SentenceTransformer(name, device="cpu", trust_remote_code=False)
        logger.info("model_ready model=%s dimensions=%s", name, encoder.get_sentence_embedding_dimension())
        return encoder
    except ImportError:
        raise ProviderError(
            "Semantic search needs the optional ML packages. Install FilingLens with [ml]. Keyword search remains available."
        ) from None
    except Exception:
        raise ProviderError(
            "Could not load the embedding model. Check the model name, internet connection and model cache."
        ) from None


def semantic_embed(texts):
    settings = get_settings()
    name = settings.embedding_model
    if name == "hash-v1":
        name = "sentence-transformers/all-MiniLM-L6-v2"
    with _lock:
        encoder = load_encoder(name)
        native = encoder.get_sentence_embedding_dimension()
        if settings.embedding_dimensions > native:
            raise ProviderError(
                f"This model has {native} dimensions. Configure at most {native}; do not pad embeddings."
            )
        try:
            vectors = encoder.encode(texts, batch_size=32, show_progress_bar=False, convert_to_numpy=True)
            result = []
            for row in vectors:
                values = [float(x) for x in row[: settings.embedding_dimensions]]
                norm = math.sqrt(sum(x * x for x in values))
                if not norm or not all(math.isfinite(x) for x in values):
                    raise ValueError()
                result.append([x / norm for x in values])
            return result
        except Exception:
            raise ProviderError("The local embedding model could not encode this text.") from None
