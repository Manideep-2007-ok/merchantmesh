"""
MerchantMesh - Central Configuration & Dynamic Taxonomy
Defines configurable thresholds, ranking weights, and database-backed dynamic taxonomy helpers.
"""

import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "merchantmesh.db")

# Supported GroqCloud Production Models with Rate-Limit & Token Resiliency:
GROQ_MODEL = os.getenv("DEFAULT_LLM_MODEL", os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"))
DEFAULT_LLM_MODEL = GROQ_MODEL
GROQ_FAST_MODEL = os.getenv("GROQ_FAST_MODEL", "openai/gpt-oss-20b")
GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.8-27b")

GROQ_CASCADE_MODELS = [
    GROQ_MODEL,
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
    "qwen/qwen3.6-27b"
]

def invoke_structured_llm(
    messages: list[Any],
    schema: Any,
    temperature: float = 0.1,
    api_key: str | None = None
) -> Any | None:
    """
    Invokes Groq with resilient multi-model cascading.
    Detects multimodal image content and routes directly to Groq Vision models.
    If the primary high-TPM model encounters 429, timeout, or tool-choice limits,
    it automatically rotates to subsequent cascade models before falling back.
    """
    from langchain_groq import ChatGroq
    active_key = api_key or os.getenv("GROQ_API_KEY")
    if not active_key or active_key.startswith("your_"):
        return None

    # Detect if multimodal image content is present in messages
    has_image = False
    for msg in messages:
        content = getattr(msg, "content", msg)
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    has_image = True
                    break

    if has_image:
        models_to_try = [
            "qwen/qwen3.8-27b",
            "qwen/qwen3.6-27b",
            GROQ_VISION_MODEL,
            "qwen/qwen3.8-27b",
            "qwen/qwen3.6-27b"
        ]
    else:
        # De-duplicate while preserving priority order
        seen = set()
        models_to_try = [m for m in GROQ_CASCADE_MODELS if not (m in seen or seen.add(m))]

    for model_name in models_to_try:
        try:
            llm = ChatGroq(
                model=model_name,
                api_key=active_key,
                temperature=temperature,
                max_retries=2,
                max_tokens=150 if has_image else None
            )
            structured_llm = llm.with_structured_output(schema)
            res = structured_llm.invoke(messages)
            if res is not None:
                return res
        except Exception as e:
            print(f"⚠️ Model '{model_name}' cascade notice: {e}. Trying next available model...")
            continue

    return None


def generate_execution_provenance(
    llm_provider: str = "groq",
    llm_model: str | None = None,
    llm_mode: str = "live",
    payment_mode: str = "test",
    fallback_reason: str | None = None
) -> dict[str, Any]:
    """
    Generates immutable runtime execution provenance for audit correlation.
    """
    return {
        "execution_id": f"exec_{uuid.uuid4().hex[:12]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "provenance": {
            "llm": {
                "provider": llm_provider,
                "model": llm_model or GROQ_MODEL,
                "mode": llm_mode,
                "fallback_reason": fallback_reason
            },
            "payment": {
                "provider": "razorpay",
                "mode": payment_mode
            },
            "inventory": {
                "source": "sqlite",
                "reservation": "atomic_begin_immediate"
            }
        }
    }


class RankingWeights(BaseModel):
    relevance: float = 0.50
    deal_feasibility: float = 0.20
    seller_trust: float = 0.15
    stock_freshness: float = 0.15


class RankingConfig(BaseModel):
    default_weights: RankingWeights = Field(default_factory=RankingWeights)
    budget_conscious_weights: RankingWeights = Field(
        default_factory=lambda: RankingWeights(relevance=0.40, deal_feasibility=0.35, seller_trust=0.15, stock_freshness=0.10)
    )
    quality_first_weights: RankingWeights = Field(
        default_factory=lambda: RankingWeights(relevance=0.45, deal_feasibility=0.10, seller_trust=0.30, stock_freshness=0.15)
    )
    urgent_weights: RankingWeights = Field(
        default_factory=lambda: RankingWeights(relevance=0.40, deal_feasibility=0.15, seller_trust=0.15, stock_freshness=0.30)
    )
    
    # Semantic & Match Thresholds
    min_semantic_similarity_threshold: float = 0.65
    min_relevance_threshold: float = 0.15
    
    # Availability Confidence Thresholds
    high_confidence_threshold: float = 80.0
    medium_confidence_threshold: float = 40.0
    
    # Negotiation Flexibility Factors
    generous_flexibility_multiplier: float = 1.00
    flexible_flexibility_multiplier: float = 0.85
    firm_flexibility_multiplier: float = 0.60


CONFIG = RankingConfig()


def get_active_catalog_categories() -> list[str]:
    """
    Dynamically introspects the active database to retrieve all product categories in the catalog.
    No hardcoded taxonomy - adapts automatically as merchants add new inventory.
    """
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND is_prohibited = 0")
        rows = cursor.fetchall()
        return [r[0] for r in rows if r[0]]
    except Exception:
        return []
    finally:
        conn.close()


def match_best_catalog_category(query_tokens: list[str]) -> str | None:
    """
    Dynamically finds the best matching category from the live database based on token overlap.
    """
    active_categories = get_active_catalog_categories()
    if not active_categories:
        return None

    best_cat = None
    best_overlap = 0

    for cat in active_categories:
        cat_tokens = set(t.strip().lower() for t in cat.replace(">", " ").split())
        overlap = sum(1 for q in query_tokens if q.lower() in cat_tokens)
        if overlap > best_overlap:
            best_overlap = overlap
            best_cat = cat

    return best_cat if best_overlap > 0 else None
