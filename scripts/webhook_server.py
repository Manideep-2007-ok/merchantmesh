"""
MerchantMesh - Standalone Local Webhook Debug Server (Testing Utility)
Used for local debugging & ngrok tunnel forwarding during development.
NOTE: In the main application, the production webhook receiver is hosted directly
at POST /api/webhook/razorpay inside main.py.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.trust_engine import process_payment_webhook


class RazorpayWebhookHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        if self.path in ["/webhook/razorpay", "/webhook", "/api/razorpay-webhook"]:
            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length)
            signature = self.headers.get("X-Razorpay-Signature")

            try:
                payload = json.loads(body_bytes.decode("utf-8"))
                print("\n" + "=" * 60)
                print(f"📥 LIVE WEBHOOK RECEIVED: {payload.get('event')}")
                print("=" * 60)

                # Process payment and auto-deduct stock
                result = process_payment_webhook(raw_body=body_bytes, signature=signature)
                print(f"✅ Processing Result: {result}")

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "result": result}).encode("utf-8"))
            except Exception as e:
                print(f"❌ Error processing webhook: {e}")
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"MerchantMesh Razorpay Webhook Server is LIVE on port 5000!")


def run_server(port: int = 5000):
    server = HTTPServer(("0.0.0.0", port), RazorpayWebhookHandler)
    print("=" * 60)
    print(f"🚀 MerchantMesh Webhook Server listening on http://localhost:{port}/webhook/razorpay")
    print("   Ready to receive live Razorpay webhook callbacks!")
    print("=" * 60)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Webhook server stopped.")
        server.server_close()


if __name__ == "__main__":
    run_server()
