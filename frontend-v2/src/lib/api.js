export function fetchWithTimeout(url, options = {}, timeoutMs = 30000) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  return fetch(url, { ...options, signal: controller.signal })
    .finally(() => clearTimeout(id));
}

export function getSessionId() {
  if (typeof window !== 'undefined' && window.location) {
    const urlParams = new URLSearchParams(window.location.search);
    const urlSession = urlParams.get('session');
    if (urlSession && urlSession.trim()) {
      const cleanSession = `sess_${urlSession.trim().replace(/^sess_/, '')}`;
      sessionStorage.setItem('mm_session_id', cleanSession);
      return cleanSession;
    }
  }

  let sess = sessionStorage.getItem('mm_session_id');
  if (!sess) {
    sess = `sess_${Math.random().toString(36).substring(2, 10)}`;
    sessionStorage.setItem('mm_session_id', sess);
  }
  return sess;
}

export function getBuyerId() {
  return `b_${getSessionId().replace('sess_', '')}`;
}

export async function fetchProducts() {
  const res = await fetch('/api/catalog/products', {
    headers: { 'X-Session-Id': getSessionId() }
  });
  if (!res.ok) throw new Error('Failed to fetch products');
  return res.json();
}

export async function fetchStats(merchantId = null) {
  const url = merchantId ? `/api/stats?merchant_id=${merchantId}` : '/api/stats';
  const res = await fetch(url, {
    headers: { 'X-Session-Id': getSessionId() }
  });
  if (!res.ok) throw new Error('Failed to fetch stats');
  return res.json();
}

export const FALLBACK_DEMO_MERCHANTS = [
  {
    "id": "m1",
    "name": "Sneaker Bhai",
    "key": "merchant_key_m1"
  },
  {
    "id": "m4",
    "name": "Kicks Delhi",
    "key": "merchant_key_m4"
  },
  {
    "id": "m5",
    "name": "Sole Mates",
    "key": "merchant_key_m5"
  },
  {
    "id": "m6",
    "name": "Urban Kicks",
    "key": "merchant_key_m6"
  },
  {
    "id": "m7",
    "name": "The Sneaker Shop",
    "key": "merchant_key_m7"
  },
  {
    "id": "m2",
    "name": "Saree Palace",
    "key": "merchant_key_m2"
  },
  {
    "id": "m8",
    "name": "Ethnic Vogue",
    "key": "merchant_key_m8"
  },
  {
    "id": "m9",
    "name": "Desi Threads",
    "key": "merchant_key_m9"
  },
  {
    "id": "m10",
    "name": "Saree Symphony",
    "key": "merchant_key_m10"
  },
  {
    "id": "m11",
    "name": "Ethnic Elegance",
    "key": "merchant_key_m11"
  },
  {
    "id": "m3",
    "name": "Streetwear Hub",
    "key": "merchant_key_m3"
  },
  {
    "id": "m12",
    "name": "Hypebeast India",
    "key": "merchant_key_m12"
  },
  {
    "id": "m13",
    "name": "Street Style Co",
    "key": "merchant_key_m13"
  },
  {
    "id": "m14",
    "name": "Metro Menswear",
    "key": "merchant_key_m14"
  },
  {
    "id": "m15",
    "name": "The Hype Store",
    "key": "merchant_key_m15"
  },
  {
    "id": "m16",
    "name": "Sneaker Central",
    "key": "merchant_key_m16"
  },
  {
    "id": "m17",
    "name": "Kicksville",
    "key": "merchant_key_m17"
  },
  {
    "id": "m18",
    "name": "Lace Up",
    "key": "merchant_key_m18"
  },
  {
    "id": "m19",
    "name": "Sole Search",
    "key": "merchant_key_m19"
  },
  {
    "id": "m20",
    "name": "Sneaker Society",
    "key": "merchant_key_m20"
  },
  {
    "id": "m21",
    "name": "Saree Mandir",
    "key": "merchant_key_m21"
  },
  {
    "id": "m22",
    "name": "Vastra",
    "key": "merchant_key_m22"
  },
  {
    "id": "m23",
    "name": "Ethnic Charm",
    "key": "merchant_key_m23"
  },
  {
    "id": "m24",
    "name": "Indian Weaves",
    "key": "merchant_key_m24"
  },
  {
    "id": "m25",
    "name": "Silk Story",
    "key": "merchant_key_m25"
  },
  {
    "id": "m26",
    "name": "Street Pulse",
    "key": "merchant_key_m26"
  },
  {
    "id": "m27",
    "name": "Urban Drops",
    "key": "merchant_key_m27"
  },
  {
    "id": "m28",
    "name": "Hype Central",
    "key": "merchant_key_m28"
  },
  {
    "id": "m29",
    "name": "The Street Code",
    "key": "merchant_key_m29"
  },
  {
    "id": "m30",
    "name": "City Fits",
    "key": "merchant_key_m30"
  }
];

export async function fetchMerchants() {
  try {
    const res = await fetch('/api/merchants', {
      headers: { 'X-Session-Id': getSessionId() }
    });
    if (!res.ok) throw new Error('Failed to fetch dynamic merchants');
    const data = await res.json();
    if (data.merchants && data.merchants.length > 0) {
      return data.merchants;
    }
    return FALLBACK_DEMO_MERCHANTS;
  } catch (e) {
    console.warn('Using fallback merchants:', e);
    return FALLBACK_DEMO_MERCHANTS;
  }
}

export function getMerchantKey(merchantId, merchantList = FALLBACK_DEMO_MERCHANTS) {
  const m = merchantList.find(item => item.id === merchantId);
  return m ? (m.api_key || m.key || `merchant_key_${merchantId}`) : `merchant_key_${merchantId}`;
}

export async function parseCatalogMessage(message, merchantId = 'm1', imageBase64 = null, merchantName = null, merchantLocation = null, language = null) {
  const res = await fetchWithTimeout('/api/catalog/parse', {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'X-Session-Id': getSessionId()
    },
    body: JSON.stringify({ 
      message, 
      merchant_id: merchantId,
      image_base64: imageBase64,
      merchant_name: merchantName,
      merchant_location: merchantLocation,
      language: language,
      session_id: getSessionId()
    })
  });
  if (!res.ok) throw new Error('Catalog parse failed');
  return res.json();
}

export async function fetchPendingSalesOrders(merchantId = 'm1', merchantKey = null) {
  const keyToUse = merchantKey || `merchant_key_${merchantId}`;
  const headers = {
    'X-Merchant-Id': merchantId,
    'X-Merchant-Key': keyToUse,
    'X-Session-Id': getSessionId()
  };
  const res = await fetch('/api/sales/pending', { headers });
  if (!res.ok) throw new Error('Failed to fetch pending orders');
  return res.json();
}

export async function confirmSalesOrder(payload) {
  if (!payload || typeof payload !== 'object' || !payload.order_id) {
    throw new Error('Valid order_id is required for merchant stock confirmation.');
  }
  const merchantId = payload.merchant_id || 'm1';
  const keyToUse = payload.merchant_key || `merchant_key_${merchantId}`;
  const headers = { 
    'Content-Type': 'application/json',
    'X-Merchant-Id': merchantId,
    'X-Merchant-Key': keyToUse,
    'X-Session-Id': getSessionId()
  };
  const res = await fetch('/api/sales/confirm', {
    method: 'POST',
    headers,
    body: JSON.stringify({
      order_id: payload.order_id,
      confirmation: payload.confirmation,
      merchant_id: merchantId
    })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Sales confirmation failed');
  }
  return res.json();
}

export async function searchBuyerChat(query, history = null) {
  const res = await fetchWithTimeout('/api/buyer/chat', {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'X-Session-Id': getSessionId()
    },
    body: JSON.stringify({ 
      query, 
      history, 
      buyer_id: getBuyerId(),
      session_id: getSessionId() 
    })
  });
  if (!res.ok) throw new Error('Buyer search failed');
  return res.json();
}

export async function negotiateDeal(productId, targetPrice, maxBudget, quantity = 1, buyerId = null) {
  const activeBuyerId = buyerId || getBuyerId();
  const res = await fetchWithTimeout('/api/negotiate', {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'X-Session-Id': getSessionId()
    },
    body: JSON.stringify({
      product_id: productId,
      buyer_target_price: targetPrice ? Number(targetPrice) : null,
      buyer_max_budget: maxBudget ? Number(maxBudget) : null,
      quantity: Number(quantity) || 1,
      buyer_id: activeBuyerId,
      session_id: getSessionId()
    })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Negotiation failed');
  }
  return res.json();
}

export async function streamNegotiateDeal(
  productId, 
  targetPrice, 
  maxBudget, 
  quantity = 1,
  { onInit, onTurn, onComplete, onError } = {}
) {
  try {
    const res = await fetch('/api/negotiate/stream', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'X-Session-Id': getSessionId()
      },
      body: JSON.stringify({
        product_id: productId,
        buyer_target_price: targetPrice ? Number(targetPrice) : null,
        buyer_max_budget: maxBudget ? Number(maxBudget) : null,
        quantity: Number(quantity) || 1,
        buyer_id: getBuyerId(),
        session_id: getSessionId()
      })
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Streaming negotiation failed to initialize');
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split('\n\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('data: ')) {
          try {
            const data = JSON.parse(trimmed.slice(6));
            if (data.event === 'init' && onInit) {
              onInit(data);
            } else if (data.event === 'turn' && onTurn) {
              onTurn(data);
            } else if (data.event === 'complete' && onComplete) {
              onComplete(data);
            } else if (data.event === 'error' && onError) {
              onError(data.error);
            }
          } catch (e) {
            console.error('SSE parse error:', e, trimmed);
          }
        }
      }
    }
  } catch (err) {
    if (onError) onError(err.message);
    else throw err;
  }
}

export async function runParallelReverseAuction({
  product_ids,
  target_price,
  max_budget,
  quantity = 1,
  buyer_id = null
}) {
  const res = await fetchWithTimeout('/api/negotiate/parallel', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Session-Id': getSessionId()
    },
    body: JSON.stringify({
      product_ids,
      buyer_target_price: target_price ? Number(target_price) : null,
      buyer_max_budget: max_budget ? Number(max_budget) : null,
      quantity: Number(quantity) || 1,
      buyer_id: buyer_id || getBuyerId(),
      session_id: getSessionId()
    })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Parallel reverse auction failed');
  }
  return res.json();
}

export async function checkoutTrustOrder(payload) {
  const res = await fetchWithTimeout('/api/trust/checkout', {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'X-Session-Id': getSessionId()
    },
    body: JSON.stringify({
      ...payload,
      buyer_id: payload.buyer_id || getBuyerId(),
      session_id: getSessionId()
    })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Checkout failed');
  }
  return res.json();
}

export function getAdminKey() {
  return sessionStorage.getItem('merchantmesh_admin_key') || import.meta.env.VITE_ADMIN_KEY || 'merchantmesh_admin_secret_key_2026';
}

export function setAdminKey(key) {
  sessionStorage.setItem('merchantmesh_admin_key', key);
}

export async function fetchAuditLogs(adminKey = null) {
  const keyToUse = adminKey || getAdminKey();
  const headers = {
    'X-Admin-Key': keyToUse,
    'X-Session-Id': getSessionId()
  };
  const res = await fetch('/api/audit/logs', { headers });
  if (!res.ok) throw new Error('Failed to fetch audit logs');
  const data = await res.json();
  return data.logs || [];
}

export async function simulatePayment(orderId, adminKey = null) {
  const keyToUse = adminKey || getAdminKey();
  const res = await fetchWithTimeout('/api/payment/simulate-webhook', {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'X-Admin-Key': keyToUse,
      'X-Session-Id': getSessionId()
    },
    body: JSON.stringify({ order_id: orderId })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Payment simulation failed');
  }
  return res.json();
}

export async function resetDemoDatabase() {
  const adminKey = getAdminKey();
  const res = await fetch('/api/catalog/seed', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Admin-Key': adminKey
    },
    body: JSON.stringify({ force: true })
  });
  if (!res.ok) throw new Error('Database reset failed');
  sessionStorage.removeItem('mm_session_id');
  localStorage.clear();
  return res.json();
}


export async function getProducts(merchantId = null) {
  const url = merchantId ? `/api/catalog/products?merchant_id=${merchantId}&_t=${Date.now()}` : `/api/catalog/products?_t=${Date.now()}`;
  const res = await fetch(url, {
    headers: {
      'X-Session-Id': getSessionId()
    }
  });
  if (!res.ok) throw new Error('Failed to fetch products');
  const data = await res.json();
  return data.products || [];
}

export async function checkOrderStatus(orderId) {
  const res = await fetch(`/api/trust/order-status/${orderId}`);
  if (!res.ok) throw new Error('Failed to fetch order status');
  return res.json();
}

export async function fetchSessionHistory() {
  const res = await fetch(`/api/session/history?session_id=${getSessionId()}`);
  if (!res.ok) throw new Error('Failed to fetch session history');
  return res.json();
}

export async function saveSessionHistory(chatData) {
  const res = await fetch('/api/session/history', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: getSessionId(), chat_data: JSON.stringify(chatData) })
  });
  if (!res.ok) throw new Error('Failed to save session history');
  return res.json();
}


export async function sendSalesChat(message, merchantId = 'm1') {
  const res = await fetch('/api/sales/chat', {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'X-Merchant-Id': merchantId,
      'X-Merchant-Key': `merchant_key_${merchantId}`
    },
    body: JSON.stringify({ message })
  });
  if (!res.ok) throw new Error('Failed to send sales chat');
  return res.json();
}
