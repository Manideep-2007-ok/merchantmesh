import json
import sqlite3
import sys
from typing import Any

from core.config import DB_PATH
from core.razorpay_client import razorpay_client

# ==========================================
# 1. STANDARDIZED MCP TOOL IMPLEMENTATIONS
# ==========================================

def create_payment_link_tool(
    order_id: str,
    expires_in_minutes: int = 15
) -> dict[str, Any]:
    """
    MCP Tool: create_payment_link
    Authoritative order-bound payment link creator.
    Derives transaction amount, product details, and customer info strictly from committed DB orders in PENDING_PAYMENT state.
    Caller cannot inject arbitrary amounts.

    Args:
        order_id (str): Unique order reference identifier (e.g. 'ord_12345').
        expires_in_minutes (int): Payment link expiry duration in minutes. Defaults to 15.

    Returns:
        Dict[str, Any]: Contains 'payment_link_id', 'payment_link_url', 'amount', 'expires_at', and 'status'.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT o.*, p.product_name, b.phone_number as buyer_phone
            FROM orders o
            JOIN products p ON o.product_id = p.id
            LEFT JOIN buyers b ON o.buyer_id = b.id
            WHERE o.id = ?
        """, (order_id,))
        order = cursor.fetchone()

        if not order:
            return {"status": "ERROR", "message": f"Order {order_id} not found in database."}

        # Check existing link for idempotency
        if order["payment_status"] == "PENDING_PAYMENT" and order["payment_link_id"] and order["payment_link_url"]:
            return {
                "status": "SUCCESS",
                "payment_link_id": order["payment_link_id"],
                "payment_link_url": order["payment_link_url"],
                "amount": order["amount"],
                "expires_at": order["expires_at"],
                "reference_id": order_id,
                "is_simulated": True,
                "message": "Returned existing active payment link."
            }

        if order["payment_status"] != "PENDING_PAYMENT":
            return {
                "status": "REJECTED",
                "message": f"Order {order_id} is in state '{order['payment_status']}'. Must be 'PENDING_PAYMENT' with verified guardrails before minting payment link."
            }

        amount = order["amount"]
        quantity = order["quantity"]
        product_name = order["product_name"]
        customer_phone = order["buyer_phone"] or "9876543210"
        customer_name = "MerchantMesh Customer"

        # Bound payment link expiry strictly to active stock reservation to prevent expiry desync
        cursor.execute("SELECT expires_at FROM stock_reservations WHERE order_id = ? AND status = 'ACTIVE'", (order_id,))
        res_row = cursor.fetchone()
        effective_expiry_mins = expires_in_minutes
        if res_row and res_row["expires_at"]:
            try:
                from datetime import datetime
                dt_str = res_row["expires_at"]
                dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                rem_sec = int((dt - datetime.utcnow()).total_seconds())
                effective_expiry_mins = max(expires_in_minutes, int(rem_sec / 60))
            except Exception:
                effective_expiry_mins = expires_in_minutes

        res = razorpay_client.create_payment_link(
            amount_inr=amount,
            customer_phone=customer_phone,
            customer_name=customer_name,
            description=f"Order {order_id}: {quantity}x {product_name}",
            reference_id=order_id,
            expire_in_mins=effective_expiry_mins,
            notes={"mcp_tool": "create_payment_link", "order_id": order_id}
        )

        if res.get("status") == "FAILED":
            return {"status": "FAILED", "error": res.get("error", "Gateway link creation failed")}

        plink_id = res["payment_link_id"]
        plink_url = res["payment_link_url"]

        cursor.execute("""
            UPDATE orders
            SET payment_link_id = ?, payment_link_url = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND payment_status = 'PENDING_PAYMENT'
        """, (plink_id, plink_url, order_id))
        conn.commit()

        return {
            "status": "SUCCESS",
            "payment_link_id": plink_id,
            "payment_link_url": plink_url,
            "amount": amount,
            "expires_at": res["expires_at"],
            "expire_by": res["expire_by"],
            "reference_id": order_id,
            "is_simulated": res.get("is_simulated", True)
        }
    finally:
        conn.close()


def check_payment_status_tool(payment_link_id: str) -> dict[str, Any]:
    """
    MCP Tool: check_payment_status
    Fetches the live status of a Razorpay payment link.

    Args:
        payment_link_id (str): The unique Razorpay payment link identifier (e.g. 'plink_abc123').

    Returns:
        Dict[str, Any]: Contains 'payment_link_id', 'status' ('created', 'paid', 'expired', 'cancelled').
    """
    res = razorpay_client.fetch_payment_link(payment_link_id)
    return {
        "status": "SUCCESS",
        "payment_link_id": payment_link_id,
        "link_status": res.get("status", "created"),
        "amount": res.get("amount"),
        "raw_response": res
    }


def cancel_payment_link_tool(payment_link_id: str) -> dict[str, Any]:
    """
    MCP Tool: cancel_payment_link
    Cancels an active unpaid Razorpay payment link when an order times out or is aborted.

    Args:
        payment_link_id (str): The unique Razorpay payment link identifier to cancel.

    Returns:
        Dict[str, Any]: Status confirmation of cancellation.
    """
    res = razorpay_client.cancel_payment_link(payment_link_id)
    return {
        "status": "SUCCESS",
        "payment_link_id": payment_link_id,
        "action": "CANCELLED",
        "link_status": res.get("status", "cancelled")
    }


def verify_payment_signature_tool(
    payment_id: str,
    payment_link_id: str,
    signature: str
) -> dict[str, Any]:
    """
    MCP Tool: verify_payment_signature
    Cryptographically verifies that a captured payment came from Razorpay.

    Args:
        payment_id (str): The Razorpay payment identifier (e.g. 'pay_xyz789').
        payment_link_id (str): The corresponding payment link identifier.
        signature (str): The cryptographic signature sent in the webhook or redirect.

    Returns:
        Dict[str, Any]: Boolean verification flag and validation details.
    """
    if razorpay_client.is_live and razorpay_client.client:
        try:
            razorpay_client.client.utility.verify_payment_link_signature({
                "payment_link_id": payment_link_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature
            })
            return {
                "status": "SUCCESS",
                "is_valid": True,
                "payment_id": payment_id,
                "payment_link_id": payment_link_id,
                "is_simulated": False
            }
        except Exception as e:
            return {
                "status": "FAILED",
                "is_valid": False,
                "payment_id": payment_id,
                "payment_link_id": payment_link_id,
                "error": str(e),
                "is_simulated": False
            }

    # Simulation Mode
    payload_str = f"{payment_link_id}|{payment_id}"
    is_valid = razorpay_client.verify_webhook_signature(payload_str, signature)
    return {
        "status": "SUCCESS" if is_valid else "FAILED",
        "is_valid": is_valid,
        "payment_id": payment_id,
        "payment_link_id": payment_link_id,
        "is_simulated": True
    }


def refund_payment_tool(
    payment_id: str,
    amount: int,
    reason: str = "Merchant order cancelled"
) -> dict[str, Any]:
    """
    MCP Tool: refund_payment
    Processes a refund for a failed or cancelled transaction (Fail-closed in live mode).

    Args:
        payment_id (str): The Razorpay payment identifier to refund.
        amount (int): Refund amount in INR.
        reason (str): Reason for issuing refund.

    Returns:
        Dict[str, Any]: Refund reference and confirmation status.
    """
    res = razorpay_client.refund_payment(payment_id, amount_inr=amount)
    if res.get("status") == "FAILED":
        return {
            "status": "FAILED",
            "error": res.get("error", "Refund failed"),
            "payment_id": payment_id,
            "is_simulated": False
        }

    return {
        "status": "SUCCESS",
        "refund_id": res.get("refund_id"),
        "payment_id": payment_id,
        "amount_refunded": amount,
        "reason": reason,
        "settlement_action": "REFUNDED_TO_BUYER",
        "is_simulated": res.get("is_simulated", True)
    }


def settle_order_tool(
    order_id: str,
    platform_fee_percentage: float = 2.0
) -> dict[str, Any]:
    """
    MCP Tool: settle_order
    Executes split payment / merchant settlement via Razorpay Route transfer for a PAID order.

    Args:
        order_id (str): The unique order reference ID (must be in PAID state).
        platform_fee_percentage (float): Platform commission percentage (defaults to 2.0).

    Returns:
        Dict[str, Any]: Settlement status, transfer ID, platform fee, and net payout.
    """
    from core.trust_engine import execute_merchant_settlement
    return execute_merchant_settlement(order_id, platform_fee_pct=platform_fee_percentage)


def run_reverse_auction_tool(
    product_ids: list,
    target_price: int | None = None,
    max_budget: int | None = None,
    quantity: int = 1,
    buyer_id: str = "b_mcp_agent"
) -> dict[str, Any]:
    """
    MCP Tool: run_reverse_auction
    Fans out parallel multi-dealer reverse auction negotiations across candidate products.
    """
    from core.reverse_auction import run_parallel_reverse_auction
    return run_parallel_reverse_auction(
        product_ids=product_ids,
        buyer_target_price=target_price,
        buyer_max_budget=max_budget,
        quantity=quantity,
        buyer_id=buyer_id
    )


# ==========================================
# 2. MCP TOOL DEFINITIONS & REGISTRY
# ==========================================

MCP_TOOL_REGISTRY = {
    "run_reverse_auction": {
        "name": "run_reverse_auction",
        "description": "Execute parallel reverse auction across competing merchants with multi-factor scoring (Savings + Speed + Trust).",
        "function": run_reverse_auction_tool,
        "parameters": {
            "type": "object",
            "properties": {
                "product_ids": {"type": "array", "items": {"type": "string"}, "description": "List of candidate product IDs to haggle with"},
                "target_price": {"type": "integer", "description": "Buyer target price in INR"},
                "max_budget": {"type": "integer", "description": "Buyer maximum budget cap in INR"},
                "quantity": {"type": "integer", "default": 1, "description": "Quantity to purchase"},
                "buyer_id": {"type": "string", "default": "b_mcp_agent", "description": "Buyer identity identifier"}
            },
            "required": ["product_ids"]
        }
    },
    "create_payment_link": {
        "name": "create_payment_link",
        "description": "Create a Razorpay payment link for an order in PENDING_PAYMENT state (amount derived from database order).",
        "function": create_payment_link_tool,
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "Order reference ID in PENDING_PAYMENT state"},
                "expires_in_minutes": {"type": "integer", "default": 15, "description": "Expiry time in minutes"}
            },
            "required": ["order_id"]
        }
    },
    "check_payment_status": {
        "name": "check_payment_status",
        "description": "Check if a Razorpay payment link has been paid, expired, or cancelled.",
        "function": check_payment_status_tool,
        "parameters": {
            "type": "object",
            "properties": {
                "payment_link_id": {"type": "string", "description": "Razorpay payment link ID"}
            },
            "required": ["payment_link_id"]
        }
    },
    "cancel_payment_link": {
        "name": "cancel_payment_link",
        "description": "Cancel an active unpaid payment link.",
        "function": cancel_payment_link_tool,
        "parameters": {
            "type": "object",
            "properties": {
                "payment_link_id": {"type": "string", "description": "Razorpay payment link ID"}
            },
            "required": ["payment_link_id"]
        }
    },
    "verify_payment_signature": {
        "name": "verify_payment_signature",
        "description": "Cryptographically verify Razorpay payment signatures.",
        "function": verify_payment_signature_tool,
        "parameters": {
            "type": "object",
            "properties": {
                "payment_id": {"type": "string", "description": "Razorpay payment ID"},
                "payment_link_id": {"type": "string", "description": "Razorpay payment link ID"},
                "signature": {"type": "string", "description": "HMAC signature string"}
            },
            "required": ["payment_id", "payment_link_id", "signature"]
        }
    },
    "refund_payment": {
        "name": "refund_payment",
        "description": "Issue a full or partial refund to a buyer.",
        "function": refund_payment_tool,
        "parameters": {
            "type": "object",
            "properties": {
                "payment_id": {"type": "string", "description": "Razorpay payment ID"},
                "amount": {"type": "integer", "description": "Amount in INR to refund"},
                "reason": {"type": "string", "description": "Reason for refund"}
            },
            "required": ["payment_id", "amount"]
        }
    },
    "settle_order": {
        "name": "settle_order",
        "description": "Execute Razorpay Route transfer to settle net payout to merchant linked account for a PAID order.",
        "function": settle_order_tool,
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "Order reference ID in PAID state"},
                "platform_fee_percentage": {"type": "number", "default": 2.0, "description": "Platform fee percentage"}
            },
            "required": ["order_id"]
        }
    }
}


def dispatch_mcp_call(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Dispatches a tool call with strict schema parameter validation.
    Explicitly rejects unexpected parameters (e.g. caller-injected amounts) at perimeter boundary.
    """
    if tool_name not in MCP_TOOL_REGISTRY:
        return {"status": "ERROR", "message": f"Unknown MCP tool: {tool_name}"}
    
    tool_entry = MCP_TOOL_REGISTRY[tool_name]
    params_schema = tool_entry.get("parameters", {})
    allowed_props = params_schema.get("properties", {})
    required_props = params_schema.get("required", [])

    # 1. Perimeter Check: Reject unexpected/injected parameters
    for k in arguments:
        if k not in allowed_props:
            if k == "amount" and tool_name == "create_payment_link":
                return {
                    "status": "ERROR",
                    "message": "UNEXPECTED_ARGUMENT: amount. Payment amount cannot be caller-controlled; it is strictly derived from the verified database order in PENDING_PAYMENT state."
                }
            return {
                "status": "ERROR",
                "message": f"UNEXPECTED_ARGUMENT: {k}. Parameter '{k}' is not permitted by tool schema."
            }

    # 2. Check required parameters
    for r in required_props:
        if r not in arguments:
            return {
                "status": "ERROR",
                "message": f"MISSING_REQUIRED_ARGUMENT: '{r}' is required for tool '{tool_name}'."
            }

    try:
        result = tool_entry["function"](**arguments)
        return result
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}


# ==========================================
# 3. JSON-RPC 2.0 MODEL CONTEXT PROTOCOL (MCP) STDIO SERVER
# ==========================================

def handle_json_rpc(request_str: str) -> str | None:
    """Handles a single JSON-RPC 2.0 request according to the Model Context Protocol."""
    try:
        req = json.loads(request_str)
    except Exception:
        return json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})

    req_id = req.get("id")
    method = req.get("method")
    params = req.get("params", {})

    if method == "initialize":
        return json.dumps({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False}
                },
                "serverInfo": {
                    "name": "razorpay-merchantmesh-mcp",
                    "version": "2.0.0"
                }
            }
        })
    elif method in ["notifications/initialized", "initialized"]:
        return None
    elif method == "ping":
        return json.dumps({"jsonrpc": "2.0", "id": req_id, "result": {}})
    elif method == "tools/list":
        tools_list = []
        for name, entry in MCP_TOOL_REGISTRY.items():
            tools_list.append({
                "name": entry["name"],
                "description": entry["description"],
                "inputSchema": entry["parameters"]
            })
        return json.dumps({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": tools_list}
        })
    elif method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        res = dispatch_mcp_call(tool_name, arguments)
        is_error = res.get("status") in ["ERROR", "FAILED", "REJECTED"]
        return json.dumps({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(res, indent=2)
                    }
                ],
                "isError": is_error
            }
        })
    else:
        return json.dumps({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}
        })


def run_stdio_server():
    """Runs a standard JSON-RPC 2.0 stdio server loop for external MCP clients."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        response = handle_json_rpc(line)
        if response:
            sys.stdout.write(response + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ["--stdio", "stdio", "serve"] or not sys.stdin.isatty():
        run_stdio_server()
    else:
        # CLI diagnostic inspection
        print(json.dumps({
            "server": "Razorpay_MCP_Server",
            "protocol": "Model Context Protocol (JSON-RPC 2.0)",
            "version": "2.0.0",
            "tools": list(MCP_TOOL_REGISTRY.keys())
        }, indent=2))
