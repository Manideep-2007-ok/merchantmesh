"""
MerchantMesh - Market & Demand Intelligence Engine
Provides search trend logging, merchant demand insights, and dynamic
pricing recommendations backed by internal catalog averages and AI market benchmarks.
"""

import os
import re
import sqlite3
from typing import Any

from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

from core.config import DB_PATH, DEFAULT_LLM_MODEL


def init_market_db() -> None:
    """Ensures search trends table exists in the database."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_trends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            category_intent TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        conn.commit()
    finally:
        conn.close()


def log_buyer_search(query: str, category_intent: str | None = None) -> bool:
    """Logs incoming buyer search queries for merchant demand intelligence."""
    if not query or not query.strip():
        return False
    init_market_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO search_trends (query, category_intent) VALUES (?, ?)",
            (query.strip().lower(), category_intent)
        )
        conn.commit()
        return True
    finally:
        conn.close()


def get_trending_insights(limit: int = 3) -> list[str]:
    """Aggregates search demand volume to provide actionable product suggestions to merchants."""
    init_market_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT query, category_intent, COUNT(*) as volume 
            FROM search_trends 
            GROUP BY query 
            ORDER BY volume DESC 
            LIMIT ?
        """, (limit,))
        trends = cursor.fetchall()
        
        insights = []
        for t in trends:
            insights.append(f"🔥 {t['volume']} buyers recently searched for '{t['query']}'. Consider adding this to your catalog!")
        return insights
    finally:
        conn.close()


def suggest_price(category: str, sizes: list[str] | None = None, product_name: str | None = None) -> dict[str, Any]:
    """
    Recommends fair listing and floor prices by combining platform catalog historical data
    with Groq real-world market valuation, preventing deceptive price inflation.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        broad_cat = (category.split(">")[0].strip() + "%") if category else "%"
        cursor.execute(
            "SELECT AVG(listed_price) as avg_price, AVG(floor_price) as avg_floor FROM products WHERE category LIKE ?",
            (broad_cat,)
        )
        result = cursor.fetchone()
    finally:
        conn.close()

    market_benchmark: int | None = None
    
    # Query Groq for market estimate if API key is available
    if os.getenv("GROQ_API_KEY"):
        try:
            llm = ChatGroq(model=DEFAULT_LLM_MODEL, max_retries=3)
            target = product_name or category
            prompt = (
                f"What is the fair median retail price in Indian Rupees (INR) for a standard unbranded '{target}' in India? "
                "Output only the estimated numerical integer amount (e.g. 1200). No explanation or currency symbol."
            )
            response = llm.invoke(prompt)
            match = re.search(r'\d[\d,]*', str(response.content))
            if match:
                market_benchmark = int(match.group().replace(",", ""))
        except Exception:
            market_benchmark = None

    if result and result["avg_price"]:
        suggested_list = int(result["avg_price"])
        suggested_floor = int(result["avg_floor"]) if result["avg_floor"] else int(suggested_list * 0.8)
        
        category_name = category.split(">")[0].strip() if category else "similar"
        msg = f"💡 Platform average for {category_name} items: ₹{suggested_list} (Floor: ₹{suggested_floor})."
        if market_benchmark:
            msg += f"\n🌐 Real-world market benchmark: ~₹{market_benchmark}."
            if suggested_list > (market_benchmark * 1.5):
                msg += "\n⚠️ Notice: Platform average is significantly higher than broader market baseline."
                
        return {
            "message": msg,
            "suggested_listed_price": suggested_list,
            "suggested_floor_price": suggested_floor,
            "market_benchmark": market_benchmark
        }
    
    # Fallback if no catalog data
    default_price = market_benchmark or 1000
    return {
        "message": f"💡 Suggested price baseline: ₹{default_price} (Floor: ₹{int(default_price * 0.8)}).",
        "suggested_listed_price": default_price,
        "suggested_floor_price": int(default_price * 0.8),
        "market_benchmark": market_benchmark
    }



