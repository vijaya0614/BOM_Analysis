"""Hybrid substitute retrieval: mechanical filter → embeddings → Pinecone → cross-encoder."""

from __future__ import annotations

import hashlib
import math
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple

from src.component_catalog import find_component, load_component_catalog
from src.models import ComponentSpec
from src.substitute_engine import DROP_IN, evaluate_candidate

EXACT_DROP_IN = "exact drop-in"
REQUIRES_REDESIGN = "requires redesign"
TOP_K = 10

PACKAGE_PIN_COUNTS = {
    "sot-23": 3,
    "sot-223": 4,
    "to-92": 3,
    "to-220": 3,
    "to-220ab": 3,
    "to-263": 3,
    "d2pak": 3,
    "dpak": 3,
    "0402": 2,
    "0603": 2,
    "0805": 2,
    "1206": 2,
    "1210": 2,
}

LEADED_PACKAGE = re.compile(
    r"^(lqfp|tqfp|qfp|qfn|dfn|soic|sop|ssop|tssop|dip|pdip|bga|lga|so)-(\d+)$",
    re.I,
)
PIN_IN_TEXT = re.compile(r"(\d+)\s*-?pins?\b", re.I)


class Embedder(Protocol):
    def encode(self, texts: Sequence[str]) -> List[List[float]]:
        ...


class CrossEncoderReranker(Protocol):
    def predict(self, pairs: Sequence[Tuple[str, str]]) -> List[float]:
        ...


def _norm(vector: Sequence[float]) -> List[float]:
    mag = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / mag for x in vector]


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


class HashingEmbedder:
    """Deterministic bag-of-tokens embedding used when sentence-transformers is unavailable."""

    def __init__(self, dim: int = 64):
        self.dim = dim

    def encode(self, texts: Sequence[str]) -> List[List[float]]:
        vectors = []
        for text in texts:
            vec = [0.0] * self.dim
            for token in re.findall(r"[a-z0-9]+", (text or "").lower()):
                digest = hashlib.md5(token.encode("utf-8")).hexdigest()
                vec[int(digest, 16) % self.dim] += 1.0
            vectors.append(_norm(vec))
        return vectors


class CosineReranker:
    def __init__(self, embedder: Embedder):
        self.embedder = embedder

    def predict(self, pairs: Sequence[Tuple[str, str]]) -> List[float]:
        if not pairs:
            return []
        left = self.embedder.encode([pair[0] for pair in pairs])
        right = self.embedder.encode([pair[1] for pair in pairs])
        return [cosine(a, b) for a, b in zip(left, right)]


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)

    def encode(self, texts: Sequence[str]) -> List[List[float]]:
        matrix = self.model.encode(list(texts), normalize_embeddings=True, convert_to_numpy=True)
        return [row.tolist() for row in matrix]


class SentenceTransformerCrossEncoder:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        from sentence_transformers import CrossEncoder

        self.model = CrossEncoder(model_name)

    def predict(self, pairs: Sequence[Tuple[str, str]]) -> List[float]:
        scores = self.model.predict(list(pairs))
        return [float(score) for score in scores]


def pin_count(component: ComponentSpec) -> Optional[int]:
    specs = component.specs or {}
    for key in ("pin_count", "pins", "pin_number"):
        raw = specs.get(key)
        if raw not in (None, ""):
            try:
                return int(float(raw))
            except (TypeError, ValueError):
                pass

    package = (component.package or "").strip()
    keyed = PACKAGE_PIN_COUNTS.get(package.lower())
    if keyed:
        return keyed
    leaded = LEADED_PACKAGE.match(package.replace(" ", ""))
    if leaded:
        return int(leaded.group(2))

    pinout = str(specs.get("pinout") or "")
    named = PIN_IN_TEXT.search(pinout.replace("_", " "))
    if named:
        return int(named.group(1))
    return None


def datasheet_summary(component: ComponentSpec) -> str:
    specs = ", ".join(f"{key}={value}" for key, value in sorted((component.specs or {}).items()))
    pins = pin_count(component)
    return (
        f"{component.part_number} is a {component.category} in package {component.package or 'unknown'} "
        f"with pin_count={pins if pins is not None else 'unknown'}. "
        f"Manufacturer: {component.manufacturer or 'unknown'}. "
        f"Lifecycle {component.lifecycle_status or 'unknown'}. "
        f"Datasheet highlights: {specs or 'none'}."
    )


def mechanical_match(original: ComponentSpec, candidate: ComponentSpec) -> bool:
    orig_pkg = (original.package or "").strip().lower()
    cand_pkg = (candidate.package or "").strip().lower()
    if not orig_pkg or orig_pkg != cand_pkg:
        return False
    orig_pins = pin_count(original)
    cand_pins = pin_count(candidate)
    if orig_pins is None or cand_pins is None:
        return orig_pins == cand_pins
    return orig_pins == cand_pins


def map_classification(engine_label: str) -> str:
    if engine_label == DROP_IN:
        return EXACT_DROP_IN
    return REQUIRES_REDESIGN


@dataclass
class VectorMatch:
    id: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class VectorIndex(Protocol):
    def upsert(self, items: Sequence[Tuple[str, Sequence[float], Dict[str, Any]]]) -> None:
        ...

    def query(
        self,
        vector: Sequence[float],
        top_k: int,
        metadata_filter: Dict[str, Any],
    ) -> List[VectorMatch]:
        ...


class LocalVectorIndex:
    """In-process cosine index used when Pinecone is not configured."""

    def __init__(self) -> None:
        self._items: Dict[str, Tuple[List[float], Dict[str, Any]]] = {}

    def upsert(self, items: Sequence[Tuple[str, Sequence[float], Dict[str, Any]]]) -> None:
        for item_id, vector, metadata in items:
            self._items[item_id] = (_norm(vector), dict(metadata))

    def query(self, vector: Sequence[float], top_k: int, metadata_filter: Dict[str, Any]) -> List[VectorMatch]:
        query_vec = _norm(vector)
        scored: List[VectorMatch] = []
        for item_id, (stored, metadata) in self._items.items():
            if any(str(metadata.get(key)) != str(value) for key, value in metadata_filter.items()):
                continue
            scored.append(VectorMatch(id=item_id, score=cosine(query_vec, stored), metadata=metadata))
        scored.sort(key=lambda match: match.score, reverse=True)
        return scored[:top_k]


class PineconeVectorIndex:
    def __init__(self, api_key: str, index_name: str):
        from pinecone import Pinecone

        self._index = Pinecone(api_key=api_key).Index(index_name)

    def upsert(self, items: Sequence[Tuple[str, Sequence[float], Dict[str, Any]]]) -> None:
        self._index.upsert(
            vectors=[
                {"id": item_id, "values": list(vector), "metadata": metadata}
                for item_id, vector, metadata in items
            ]
        )

    def query(self, vector: Sequence[float], top_k: int, metadata_filter: Dict[str, Any]) -> List[VectorMatch]:
        pinecone_filter = {key: {"$eq": value} for key, value in metadata_filter.items()}
        response = self._index.query(
            vector=list(vector),
            top_k=top_k,
            filter=pinecone_filter or None,
            include_metadata=True,
        )
        matches = []
        for match in response.get("matches") or response.matches:
            metadata = dict(getattr(match, "metadata", None) or match.get("metadata") or {})
            match_id = getattr(match, "id", None) or match.get("id")
            score = float(getattr(match, "score", None) or match.get("score") or 0.0)
            matches.append(VectorMatch(id=str(match_id), score=score, metadata=metadata))
        return matches


def default_embedder() -> Embedder:
    try:
        return SentenceTransformerEmbedder()
    except Exception:
        return HashingEmbedder()


def default_reranker(embedder: Embedder) -> CrossEncoderReranker:
    try:
        return SentenceTransformerCrossEncoder()
    except Exception:
        return CosineReranker(embedder)


def default_index() -> VectorIndex:
    api_key = os.environ.get("PINECONE_API_KEY", "").strip()
    index_name = os.environ.get("PINECONE_INDEX", "bom-substitutes")
    if api_key:
        return PineconeVectorIndex(api_key, index_name)
    return LocalVectorIndex()


class HybridSubstitutePipeline:
    def __init__(
        self,
        embedder: Embedder,
        reranker: CrossEncoderReranker,
        index: VectorIndex,
        catalog_path: str = "data/component_specs.csv",
        data_dir: str = "data",
        auto_index: bool = True,
    ) -> None:
        self.embedder = embedder
        self.reranker = reranker
        self.index = index
        self.catalog_path = catalog_path
        self.data_dir = data_dir
        self._indexed = False
        if auto_index:
            self.index_catalog()

    @classmethod
    def from_env(cls, **kwargs) -> "HybridSubstitutePipeline":
        embedder = default_embedder()
        return cls(embedder, default_reranker(embedder), default_index(), **kwargs)

    def index_catalog(self) -> None:
        catalog = load_component_catalog(self.catalog_path)
        items = []
        summaries = [datasheet_summary(component) for component in catalog.values()]
        vectors = self.embedder.encode(summaries) if summaries else []
        for component, vector in zip(catalog.values(), vectors):
            items.append(
                (
                    component.component_id,
                    vector,
                    {
                        "part_number": component.part_number,
                        "package": (component.package or "").strip(),
                        "pin_count": pin_count(component),
                        "category": component.category,
                        "summary": datasheet_summary(component),
                    },
                )
            )
        if items:
            self.index.upsert(items)
        self._indexed = True

    def find_substitutes(self, part_number: str, top_k: int = TOP_K) -> Dict[str, Any]:
        original = find_component(part_number, self.catalog_path)
        if original is None:
            return {
                "error": "COMPONENT_NOT_FOUND",
                "message": f"No component found for part number '{part_number}'.",
            }

        package = (original.package or "").strip()
        pins = pin_count(original)
        catalog = load_component_catalog(self.catalog_path)
        mechanical = [
            component
            for component in catalog.values()
            if component.component_id != original.component_id and mechanical_match(original, component)
        ]
        allowed_ids = {component.component_id for component in mechanical}

        query_summary = datasheet_summary(original)
        query_vector = self.embedder.encode([query_summary])[0]
        metadata_filter: Dict[str, Any] = {"package": package}
        if pins is not None:
            metadata_filter["pin_count"] = pins

        retrieved = [
            match
            for match in self.index.query(query_vector, top_k=max(top_k, TOP_K), metadata_filter=metadata_filter)
            if match.id in allowed_ids or match.metadata.get("part_number") in {c.part_number for c in mechanical}
        ][:TOP_K]

        if not retrieved and mechanical:
            summaries = [datasheet_summary(component) for component in mechanical]
            vectors = self.embedder.encode(summaries)
            ranked_local = sorted(
                zip(mechanical, vectors),
                key=lambda item: cosine(query_vector, item[1]),
                reverse=True,
            )[:TOP_K]
            retrieved = [
                VectorMatch(
                    id=component.component_id,
                    score=cosine(query_vector, vector),
                    metadata={"part_number": component.part_number, "summary": datasheet_summary(component)},
                )
                for component, vector in ranked_local
            ]

        by_id = {component.component_id: component for component in mechanical}
        by_pn = {component.part_number: component for component in mechanical}
        candidates: List[ComponentSpec] = []
        pinecone_scores: Dict[str, float] = {}
        for match in retrieved:
            component = by_id.get(match.id) or by_pn.get(str(match.metadata.get("part_number") or ""))
            if component is None:
                continue
            candidates.append(component)
            pinecone_scores[component.component_id] = match.score

        pairs = [(query_summary, datasheet_summary(component)) for component in candidates]
        rerank_scores = self.reranker.predict(pairs) if pairs else []
        ordered = sorted(
            zip(candidates, rerank_scores),
            key=lambda item: item[1],
            reverse=True,
        )

        substitutes = []
        for component, rerank_score in ordered[:top_k]:
            evaluated = evaluate_candidate(original, component, self.data_dir)
            substitutes.append(
                {
                    "part_number": component.part_number,
                    "component_id": component.component_id,
                    "package": component.package,
                    "pin_count": pin_count(component),
                    "classification": map_classification(evaluated["classification"]),
                    "engine_classification": evaluated["classification"],
                    "semantic_score": round(pinecone_scores.get(component.component_id, 0.0), 4),
                    "rerank_score": round(float(rerank_score), 4),
                    "datasheet_summary": datasheet_summary(component),
                    "matched_parameters": evaluated["matched_parameters"],
                    "mismatched_parameters": evaluated["mismatched_parameters"],
                    "explanation": evaluated["explanation"],
                }
            )

        return {
            "part_number": original.part_number,
            "component_id": original.component_id,
            "package": package,
            "pin_count": pins,
            "hard_filter": {
                "package": package,
                "pin_count": pins,
                "candidates_after_filter": len(mechanical),
            },
            "pipeline": [
                "exact_pin_count_and_package_filter",
                "sentence_transformers_embed_datasheet_summaries",
                "pinecone_top_10",
                "cross_encoder_rerank",
                "drop_in_or_redesign_classification",
            ],
            "substitutes": substitutes,
        }
