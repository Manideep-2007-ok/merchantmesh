import json
import sqlite3

from core.discovery_engine import score_candidate_heuristics
from core.query_parser import parse_buyer_query


def main():
    conn = sqlite3.connect("data/merchantmesh.db")
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM products WHERE product_name LIKE '%Smartwatch%'").fetchone()
    candidate = dict(row)
    candidate["search_tags"] = json.loads(candidate["search_tags_json"])
    candidate["sizes"] = json.loads(candidate["sizes_json"])
    candidate["merchant_dna"] = {}
    candidate["seller_rating"] = 4.5
    
    parsed = parse_buyer_query("can you fine me a blue tshirt for 500")
    print("Parsed search keywords:", parsed.search_keywords)
    
    score = score_candidate_heuristics(candidate, parsed)
    print("Pre-score:", score)
    print("Relevance:", candidate.get("relevance"))

main()
