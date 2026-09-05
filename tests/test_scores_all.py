from core.discovery_engine import retrieve_candidates, score_candidate_heuristics
from core.query_parser import _heuristic_fallback_parser


def main():
    parsed = _heuristic_fallback_parser("can you fine me a blue tshirt for 500")
    print("Parsed search keywords:", parsed.search_keywords)
    
    candidates = retrieve_candidates(parsed, include_all_for_fallback=True)
    
    for c in candidates:
        score = score_candidate_heuristics(c, parsed)
        print(f"Product: {c['product_name']} | Score: {score} | Relevance: {c.get('relevance')}")

main()
