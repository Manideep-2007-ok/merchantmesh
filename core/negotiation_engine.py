"""
MerchantMesh - Negotiation Engine & Guardrail Verification Core
Handles:
1. Dynamic Seller Negotiation Profile inference from Merchant DNA
2. Historical deal adaptation from past negotiation records
3. Bundle & bulk quantity pricing calculations
4. Code-level hard floor price & buyer budget guardrails
5. LLM-powered multi-turn conversational agents with authentic Indian social commerce personas
"""

import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Literal

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from core.config import DB_PATH

load_dotenv()


# ==========================================
# 1. DATA SCHEMAS
# ==========================================

class NegotiationTurn(BaseModel):
    turn_number: int
    speaker: Literal["BUYER", "SELLER", "SYSTEM"]
    action: Literal["OFFER", "COUNTER", "ACCEPT", "REJECT", "WALK_AWAY"]
    proposed_price: int
    message: str = Field(description="Authentic conversational Hinglish/English message.")
    internal_reasoning: str = Field(description="Private strategic reasoning behind the offer.")
    guardrail_status: str = Field(default="PASSED", description="Code-level guardrail validation flag.")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class SellerNegotiationProfile(BaseModel):
    merchant_id: str
    merchant_name: str
    product_id: str
    product_name: str
    listed_price: int
    floor_price: int
    quantity: int = 1
    total_listed_price: int
    total_floor_price: int
    flexibility: Literal["Firm", "Flexible", "Generous"] = "Flexible"
    max_discount_pct: float = 20.0
    bundle_discount_rate: float = 0.05
    seller_rating: float = 5.0
    past_deal_acceptance_rate: float = 0.75
    allow_upi_instant_discount: bool = True


class BuyerNegotiationConstraints(BaseModel):
    buyer_id: str = "b1"
    target_price: int
    max_budget: int
    quantity: int = 1
    total_target_price: int
    total_max_budget: int
    urgency: Literal["low", "medium", "urgent"] = "medium"
    preferred_payment: Literal["UPI", "COD", "CARD"] = "UPI"


class SellerTurnOutput(BaseModel):
    action: Literal["ACCEPT", "COUNTER", "REJECT"] = Field(
        description="ACCEPT if buyer's offer is profitable (>= floor) and fair. COUNTER with a new price if negotiable. REJECT if insultingly low or below floor."
    )
    counter_price: int = Field(
        description="The total price in INR for the total quantity. MUST be >= total_floor_price."
    )
    message: str = Field(
        description="Authentic WhatsApp seller reply in Hinglish/English (e.g., 'Bhaiya ₹950 final kar lo, premium fabric hai' or 'Deal done! Packing your order now.')."
    )
    internal_reasoning: str = Field(
        description="Strategic explanation of why this counter/acceptance was chosen based on margin and merchant DNA."
    )


class BuyerTurnOutput(BaseModel):
    action: Literal["OFFER", "COUNTER", "ACCEPT", "WALK_AWAY"] = Field(
        description="COUNTER if seller's price is above budget but negotiable. ACCEPT if seller met our target/budget. WALK_AWAY if seller is too firm."
    )
    offer_price: int = Field(
        description="The offered total price in INR for the total quantity. MUST NOT exceed buyer's max budget."
    )
    message: str = Field(
        description="Authentic WhatsApp buyer reply in Hinglish/English (e.g., 'Bhaiya ₹900 me de do, UPI turant kar dunga' or 'Done deal! Send payment link.')."
    )
    internal_reasoning: str = Field(
        description="Strategic reasoning behind the offer increment and price anchoring."
    )


# ==========================================
# 2. SELLER PROFILE INFERENCE & ADAPTATION
# ==========================================

def get_merchant_historical_deal_stats(merchant_id: str) -> dict[str, Any]:
    """
    Queries past closed negotiations for this merchant to adapt negotiation concession speed.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT n.outcome, n.final_price, p.listed_price, p.floor_price
            FROM negotiations n
            JOIN products p ON n.product_id = p.id
            WHERE p.merchant_id = ?
            """,
            (merchant_id,)
        )
        rows = cursor.fetchall()
        if not rows:
            return {"total_deals": 0, "acceptance_rate": 0.75, "avg_discount_given": 0.15}

        total = len(rows)
        accepted = sum(1 for r in rows if r["outcome"] in ["ACCEPTED", "AGREED", "SUCCESS"])
        discounts = []
        for r in rows:
            if r["final_price"] and r["listed_price"] and r["listed_price"] > 0:
                disc = (r["listed_price"] - r["final_price"]) / r["listed_price"]
                discounts.append(max(0.0, disc))

        avg_disc = sum(discounts) / len(discounts) if discounts else 0.15
        return {
            "total_deals": total,
            "acceptance_rate": round(accepted / total, 2),
            "avg_discount_given": round(avg_disc, 2)
        }
    finally:
        conn.close()


def calculate_bundle_financials(unit_listed: int, unit_floor: int, quantity: int = 1) -> tuple[int, int, float]:
    """
    Calculates bulk/bundle total listed and total floor prices.
    Volume deals allow aggressive concessions from listed price, but
    STRICTLY enforce the merchant's unit floor limit (total_floor = unit_floor * quantity).
    """
    if quantity <= 1:
        return unit_listed, unit_floor, 0.0

    bundle_discount_rate = 0.05 if quantity == 2 else 0.10
    total_listed = unit_listed * quantity
    total_floor = unit_floor * quantity
    
    return total_listed, total_floor, bundle_discount_rate


def build_seller_profile(
    product: dict[str, Any], 
    merchant: dict[str, Any], 
    quantity: int = 1
) -> SellerNegotiationProfile:
    """
    Builds the seller negotiation profile dynamically from Merchant DNA,
    product pricing attributes, bundle volume settings, and historical deal stats.
    """
    unit_listed = product["listed_price"]
    unit_floor = product["floor_price"] if product.get("floor_price") is not None else unit_listed
    
    total_listed, total_floor, bundle_rate = calculate_bundle_financials(unit_listed, unit_floor, quantity)
    
    # Parse Merchant DNA
    dna = {}
    if merchant.get("merchant_dna_json"):
        try:
            dna = json.loads(merchant["merchant_dna_json"])
        except Exception:
            dna = {}
            
    flexibility = dna.get("flexibility", "Flexible")
    if flexibility not in ["Firm", "Flexible", "Generous"]:
        flexibility = "Flexible"

    # Inferred max discount percentage
    max_discount_pct = ((total_listed - total_floor) / total_listed) * 100.0 if total_listed > 0 else 0.0

    # Historical stats
    hist_stats = get_merchant_historical_deal_stats(merchant.get("id", ""))

    return SellerNegotiationProfile(
        merchant_id=merchant.get("id", "m1"),
        merchant_name=merchant.get("name", "Merchant"),
        product_id=product.get("id", "p1"),
        product_name=product.get("product_name", "Product"),
        listed_price=unit_listed,
        floor_price=unit_floor,
        quantity=quantity,
        total_listed_price=total_listed,
        total_floor_price=total_floor,
        flexibility=flexibility,
        max_discount_pct=round(max_discount_pct, 1),
        bundle_discount_rate=bundle_rate,
        seller_rating=merchant.get("reliability_score", 5.0),
        past_deal_acceptance_rate=hist_stats.get("acceptance_rate", 0.75),
        allow_upi_instant_discount=True
    )


# ==========================================
# 3. HARD CODE-LEVEL GUARDRAILS
# ==========================================

def validate_seller_offer(
    offered_price: int, 
    total_floor_price: int, 
    total_listed_price: int
) -> tuple[bool, str]:
    """
    STRICT CODE-LEVEL GUARDRAIL:
    Ensures no prompt injection, hallucination, or algorithmic glitch can sell below the floor price.
    """
    if offered_price < total_floor_price:
        return False, f"GUARDRAIL_VIOLATION: Offered price ₹{offered_price:,} is strictly below the minimum floor price of ₹{total_floor_price:,}."
    if offered_price > total_listed_price * 1.5:
        return False, f"GUARDRAIL_VIOLATION: Price ₹{offered_price:,} exceeds reasonable upper bounds."
    return True, "PASSED"


def validate_buyer_offer(
    offered_price: int, 
    total_max_budget: int
) -> tuple[bool, str]:
    """
    STRICT CODE-LEVEL GUARDRAIL:
    Ensures buyer agent never commits or offers more than the buyer's allocated budget.
    """
    if offered_price > total_max_budget:
        return False, f"GUARDRAIL_VIOLATION: Buyer offer ₹{offered_price:,} exceeds buyer's maximum budget of ₹{total_max_budget:,}."
    if offered_price <= 0:
        return False, f"GUARDRAIL_VIOLATION: Invalid non-positive offer price ₹{offered_price}."
    return True, "PASSED"


# ==========================================
# 4. DETERMINISTIC HEURISTIC FALLBACKS
# ==========================================

def heuristic_seller_response(
    buyer_offer: int,
    profile: SellerNegotiationProfile,
    turn_number: int
) -> SellerTurnOutput:
    """
    Deterministic rule-based seller agent fallback ensuring zero-failure execution
    even without API keys or during LLM downtime.
    """
    floor = profile.total_floor_price
    listed = profile.total_listed_price
    flex = profile.flexibility

    # 1. Hard Floor Violation Rejection
    if buyer_offer < floor:
        # Calculate a safe counter offer at or above floor without disclosing confidential bottom line
        safe_counter = min(listed, max(floor, int(floor * 1.05)))
        # If lowball is extreme (< 85% of floor), politely decline
        if buyer_offer < floor * 0.85:
            return SellerTurnOutput(
                action="REJECT",
                counter_price=safe_counter,
                message=f"Bhaiya ₹{buyer_offer:,} me toh bilkul possible nahi hai. Best quality original maal ke liye ₹{safe_counter:,} final price ho sakta hai.",
                internal_reasoning=f"Buyer offer ₹{buyer_offer} is below margin threshold. Rejected offer and safe counter anchored at ₹{safe_counter}."
            )
        else:
            # Offer is slightly below floor, counter with safe target without revealing floor
            return SellerTurnOutput(
                action="COUNTER",
                counter_price=safe_counter,
                message=f"Bhaiya ₹{buyer_offer:,} thoda kam hai. Aapke liye ₹{safe_counter:,} final kar lete hain, best deal hai!",
                internal_reasoning=f"Buyer offer ₹{buyer_offer} is below floor threshold. Countered with safe target price ₹{safe_counter}."
            )

    # 2. Offer >= Floor: evaluate acceptability based on merchant flexibility
    spread = listed - floor
    if flex == "Generous":
        # Generous seller accepts any offer in bottom 40% of spread or counters very closely
        acceptable_threshold = floor + int(spread * 0.20)
        step_counter = max(floor, listed - int(spread * 0.70 * (turn_number / 2.0)))
    elif flex == "Flexible":
        acceptable_threshold = floor + int(spread * 0.40)
        step_counter = max(floor, listed - int(spread * 0.50 * (turn_number / 2.5)))
    else:  # Firm
        acceptable_threshold = floor + int(spread * 0.75)
        step_counter = max(floor, listed - int(spread * 0.25 * (turn_number / 3.0)))

    if buyer_offer >= acceptable_threshold or turn_number >= 3:
        if buyer_offer >= floor:
            return SellerTurnOutput(
                action="ACCEPT",
                counter_price=buyer_offer,
                message=f"Chalo deal done at ₹{buyer_offer:,}! UPI pe payment kardo, aaj hi parcel nikaal dunga. 🚀",
                internal_reasoning=f"Buyer offer ₹{buyer_offer} meets acceptable threshold ₹{acceptable_threshold} (Floor: ₹{floor}, Style: {flex}). Deal accepted."
            )

    # Otherwise counter
    counter_target = max(floor, min(listed, int(step_counter)))
    # If bundle, mention volume advantage
    bundle_text = f" ({profile.quantity} pieces ke liye)" if profile.quantity > 1 else ""
    return SellerTurnOutput(
        action="COUNTER",
        counter_price=counter_target,
        message=f"Bhaiya ₹{buyer_offer:,} thoda kam hai. ₹{counter_target:,}{bundle_text} final price kar lete hain, best deal hai.",
        internal_reasoning=f"Buyer offer ₹{buyer_offer} was below threshold ₹{acceptable_threshold}. Conceded towards ₹{counter_target} maintaining margin."
    )


def heuristic_buyer_response(
    seller_counter: int,
    constraints: BuyerNegotiationConstraints,
    turn_number: int,
    seller_flexibility: str = "Flexible",
    api_key: str = None
) -> BuyerTurnOutput:
    """
    Deterministic rule-based buyer agent fallback.
    """
    target = constraints.total_target_price
    budget = constraints.total_max_budget

    # If seller counter is within target or budget on final turn, accept
    if seller_counter <= target:
        return BuyerTurnOutput(
            action="ACCEPT",
            offer_price=seller_counter,
            message=f"Great! ₹{seller_counter:,} works perfectly for me. Please share payment details.",
            internal_reasoning=f"Seller counter ₹{seller_counter} is at or below target ₹{target}. Accepted immediately."
        )

    if seller_counter <= target or (seller_counter <= budget and turn_number >= 2):
        return BuyerTurnOutput(
            action="ACCEPT",
            offer_price=seller_counter,
            message=f"Theek hai bhaiya, ₹{seller_counter:,} done karte hain. Sending payment via UPI.",
            internal_reasoning=f"Turn {turn_number}: Seller counter ₹{seller_counter} is within max budget ₹{budget}. Accepted."
        )

    # Increment offer towards seller's counter
    remaining_headroom = budget - target
    step_inc = int(remaining_headroom * (turn_number / 3.0))
    next_offer = min(budget, target + step_inc)

    # If already at max budget and seller is still above it
    if next_offer >= budget and seller_counter > budget:
        if turn_number >= 3:
            return BuyerTurnOutput(
                action="WALK_AWAY",
                offer_price=budget,
                message=f"Sorry bhaiya, mera maximum budget ₹{budget:,} hi hai. Isse zyada nahi ho payega. Agar consider kar sako toh batana.",
                internal_reasoning=f"Seller price ₹{seller_counter} exceeds max budget ₹{budget}. Walked away politely."
            )
        else:
            return BuyerTurnOutput(
                action="COUNTER",
                offer_price=budget,
                message=f"Bhaiya last ₹{budget:,} de paunga. Please consider kar lo, turant payment kar dunga.",
                internal_reasoning=f"Offered max budget ₹{budget} as final bid."
            )

    return BuyerTurnOutput(
        action="COUNTER",
        offer_price=next_offer,
        message=f"Bhaiya thoda sa adjust karo na. How about ₹{next_offer:,}? Mai abhi UPI se transfer karta hu.",
        internal_reasoning=f"Incremented offer from ₹{target} to ₹{next_offer} towards seller ask ₹{seller_counter}, staying within budget ₹{budget}."
    )


# ==========================================
# 5. LLM-POWERED AGENTS WITH GUARDRAIL BINDINGS
# ==========================================

def generate_seller_turn_llm(
    history: list[NegotiationTurn],
    profile: SellerNegotiationProfile,
    buyer_last_offer: int,
    api_key: str | None = None
) -> SellerTurnOutput:
    """
    Executes Seller Agent turn with Groq + Pydantic validation + Code Guardrail enforcement.
    """
    active_key = api_key or os.getenv("GROQ_API_KEY")
    turn_num = len([t for t in history if t.speaker == "SELLER"]) + 1

    if not active_key:
        return heuristic_seller_response(buyer_last_offer, profile, turn_num)

    system_prompt = f"""
You are the AI Sales Assistant representing '{profile.merchant_name}', an Indian informal merchant on WhatsApp/Instagram.
You are negotiating with a prospective buyer.

MERCHANT PROFILE & CONSTRAINTS:
- Product: {profile.product_name} (Quantity: {profile.quantity})
- Total Listed Price: ₹{profile.total_listed_price:,}
- Total Floor Price (ABSOLUTE BOTTOM LINE): ₹{profile.total_floor_price:,}
- Merchant Negotiation Style: {profile.flexibility}
- Rating: {profile.seller_rating} ⭐
- Max Discount Room: {profile.max_discount_pct}%

CRITICAL RULES:
1. HARD FLOOR CONSTRAINT: You MUST NEVER accept or offer any price below ₹{profile.total_floor_price:,}. 
   If buyer asks below floor, counter with at least ₹{profile.total_floor_price:,} or politely decline.
2. TONE & PERSONA (UNIVERSAL LANGUAGE MIRRORING):
   - You MUST detect the language, script, dialect, and tone used by the buyer and reply in the EXACT SAME language.
   - If the buyer messages in Indian English (e.g. "Bro, this is too expensive, make it 900" or "Sir, can you give discount?"), respond in warm, conversational Indian English (e.g. "Sir/Bro, this is premium quality, best I can do is ₹X for instant UPI dispatch").
   - If the buyer messages in Hinglish (e.g. "Bhaiya thoda kam karo"), respond in natural Hinglish (e.g. "Bhaiya ₹X final price kar lete hain").
   - If the buyer messages in a regional language (Tamil, Telugu, Kannada, Malayalam, Marathi, Bengali, Gujarati, etc.), respond in that exact language and script.
   - Behave like an authentic, friendly local shopkeeper in their language.
   - Keep messages short (1-2 sentences), ready for WhatsApp chat.
3. NEGOTIATION STRATEGY ({profile.flexibility}):
   - If 'Firm': Hold close to listed price, emphasize quality and free/fast delivery. Concede very slowly.
   - If 'Flexible': Meet buyer halfway, offer small step-down discounts.
   - If 'Generous': Be open to good deals, especially if buyer promises instant UPI or buys bulk.
4. ACTION SELECTION:
   - 'ACCEPT': If buyer offer is >= floor price and provides a satisfactory margin.
   - 'COUNTER': If offer is below your target but >= floor price, or if offer is slightly below floor and you want to anchor at floor.
   - 'REJECT': If buyer offers a ridiculous lowball (< 70% of floor).
"""

    history_text = "\n".join([f"{t.speaker}: ₹{t.proposed_price} — \"{t.message}\"" for t in history])
    user_prompt = f"""
PREVIOUS CONVERSATION:
{history_text if history_text else "No prior turns. Buyer just made opening offer."}

CURRENT INCOMING BUYER OFFER: ₹{buyer_last_offer:,}

Determine your response (action, counter_price, message, internal_reasoning).
Remember: counter_price MUST be >= ₹{profile.total_floor_price:,}.
"""

    from core.config import invoke_structured_llm
    res = invoke_structured_llm(
        [HumanMessage(content=f"{system_prompt}\n\n{user_prompt}")],
        SellerTurnOutput,
        temperature=0.2,
        api_key=active_key
    )

    if res is not None and isinstance(res, SellerTurnOutput):
        # STRICT POST-LLM CODE GUARDRAIL
        is_valid, reason = validate_seller_offer(res.counter_price, profile.total_floor_price, profile.total_listed_price)
        if not is_valid:
            print(f"⚠️ Seller LLM generated floor violation: {reason}. Enforcing code guardrail override.")
            # Code override: calculate a safe counter strictly >= floor without revealing confidential floor price
            spread = profile.total_listed_price - profile.total_floor_price
            if spread > 0:
                safe_counter = min(profile.total_listed_price, profile.total_floor_price + max(50, int(spread * 0.10)))
            else:
                safe_counter = profile.total_floor_price
            
            last_buyer_msg = history[-1].message.lower() if history else ""
            is_hindi = any(word in last_buyer_msg for word in ['bhaiya', 'kam', 'karo', 'thoda', 'sahi', 'bhai', 'chahiye', 'kardo', 'dena'])
            if is_hindi:
                fallback_msg = f"Bhaiya is price pe possible nahi hai. Best price ₹{safe_counter:,} final kar sakte hain."
            else:
                fallback_msg = f"Sir/Ma'am, I cannot accept that offer. The best price I can offer is ₹{safe_counter:,}."

            return SellerTurnOutput(
                action="COUNTER" if res.action != "REJECT" else "REJECT",
                counter_price=safe_counter,
                message=fallback_msg,
                internal_reasoning=f"Code Guardrail Override: LLM attempted ₹{res.counter_price} (below floor ₹{profile.total_floor_price}). Clamped to safe counter ₹{safe_counter}."
            )

        return res

    return heuristic_seller_response(buyer_last_offer, profile, turn_num)


def generate_buyer_turn_llm(
    history: list[NegotiationTurn],
    constraints: BuyerNegotiationConstraints,
    seller_last_counter: int,
    seller_flexibility: str = "Flexible",
    api_key: str = None
) -> BuyerTurnOutput:
    """
    Executes Buyer Agent turn with Groq + Pydantic validation + Code Guardrail enforcement.
    """
    active_key = api_key or os.getenv("GROQ_API_KEY")
    turn_num = len([t for t in history if t.speaker == "BUYER"]) + 1

    if not active_key:
        return heuristic_buyer_response(seller_last_counter, constraints, turn_num, seller_flexibility)

    system_prompt = f"""
You are the AI Buyer Agent negotiating on behalf of an Indian shopper.
Your goal is to get the best possible deal while remaining respectful and realistic.

BUYER PROFILE & CONSTRAINTS:
- Target Price: ₹{constraints.total_target_price:,} (Quantity: {constraints.quantity})
- Absolute Maximum Budget: ₹{constraints.total_max_budget:,} (HARD CAP - NEVER EXCEED)
- Payment Method: {constraints.preferred_payment}
- Urgency: {constraints.urgency}

CRITICAL RULES:
1. BUDGET CAP (HARD CONSTRAINT): You MUST NEVER offer or accept any price above ₹{constraints.total_max_budget:,}.
2. TONE & PERSONA:
   - Natural Indian shopper haggling on WhatsApp.
   - Polite, smart, conversational in Hinglish/English.
   - Phrases like "Bhaiya thoda kam karo", "Deal done", "UPI payment abhi karta hu".
3. HAGGLING TACTICS:
   - Start low (around target price).
   - If seller counters, move up in small increments towards seller ask, but stay <= max budget.
   - Mention immediate payment via UPI as an incentive.
   - If seller price is <= max budget and you've negotiated 2+ turns, close the deal ('ACCEPT').
   - If seller strictly refuses to come down to your max budget, politely walk away ('WALK_AWAY').
"""

    history_text = "\n".join([f"{t.speaker}: ₹{t.proposed_price} — \"{t.message}\"" for t in history])
    user_prompt = f"""
PREVIOUS CONVERSATION:
{history_text if history_text else "Opening turn. Buyer making first bid."}

CURRENT SELLER COUNTER-OFFER: ₹{seller_last_counter:,}

Determine your response (action, offer_price, message, internal_reasoning).
Remember: offer_price MUST NOT exceed ₹{constraints.total_max_budget:,}.
"""

    from core.config import invoke_structured_llm
    res = invoke_structured_llm(
        [HumanMessage(content=f"{system_prompt}\n\n{user_prompt}")],
        BuyerTurnOutput,
        temperature=0.2,
        api_key=active_key
    )

    if res is not None and isinstance(res, BuyerTurnOutput):
        # STRICT POST-LLM CODE GUARDRAIL
        is_valid, reason = validate_buyer_offer(res.offer_price, constraints.total_max_budget)
        if not is_valid:
            print(f"⚠️ Buyer LLM generated budget violation: {reason}. Enforcing code guardrail override.")
            # Clamp strictly between positive lower bound (target price or 1) and total_max_budget
            raw_offer = res.offer_price if res.offer_price > 0 else constraints.total_target_price
            clamped_price = max(1, min(constraints.total_max_budget, raw_offer))
            return BuyerTurnOutput(
                action="COUNTER" if clamped_price < seller_last_counter else "ACCEPT",
                offer_price=clamped_price,
                message=f"Bhaiya last ₹{clamped_price:,} ho payega mere end se.",
                internal_reasoning=f"Code Guardrail Override: Validated price within safe range ₹1–₹{constraints.total_max_budget}."
            )

        return res

    return heuristic_buyer_response(seller_last_counter, constraints, turn_num, seller_flexibility)
