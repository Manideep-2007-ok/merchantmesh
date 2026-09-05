import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { ShieldCheck, Activity, Users, Settings2, Zap } from 'lucide-react';
import { getProducts, streamNegotiateDeal, confirmSalesOrder } from '../lib/api';
import { useAgentLogs } from '../context/AgentActivityContext';
import { playTensionPing, playGuardrailThud, playDealChime } from '../lib/sound';
import { WhatsAppUI } from '../components/WhatsAppUI';
import { NegotiationArena } from '../components/NegotiationArena';

export const SalesBot = () => {
  const [products, setProducts] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState(null);
  
  // Negotiation State
  const [messages, setMessages] = useState([]);
  const [turns, setTurns] = useState([]);
  const [status, setStatus] = useState('IDLE'); // IDLE, NEGOTIATING, ACCEPTED, REJECTED
  const [loading, setLoading] = useState(false);
  const [dealPrice, setDealPrice] = useState(null);
  const [pendingOrderId, setPendingOrderId] = useState(null);
  const [merchantConfirmed, setMerchantConfirmed] = useState(false);
  const { addLog } = useAgentLogs();

  useEffect(() => {
    getProducts('m1').then(prods => {
      setProducts(prods);
      if (prods.length > 0) setSelectedProduct(prods[0]);
    });
  }, []);

  const startNegotiation = async (buyerTarget, buyerMax) => {
    if (!selectedProduct || status === 'NEGOTIATING') return;
    setMessages([]);
    setTurns([]);
    setStatus('NEGOTIATING');
    setLoading(true);
    setDealPrice(null);
    setPendingOrderId(null);
    setMerchantConfirmed(false);
    
    playTensionPing();
    addLog('SYSTEM', `Starting streaming negotiation for ${selectedProduct.name}`);

    streamNegotiateDeal(selectedProduct.id, buyerTarget, buyerMax, 1, {
      onInit: (data) => {
        addLog('SYSTEM', `Negotiation Initialized: Target=₹${data.buyer_target}, Max=₹${data.buyer_max}`);
      },
      onTurn: (data) => {
        setTurns(prev => [...prev, data]);
        setMessages(prev => [
          ...prev, 
          { 
            role: data.speaker === 'BUYER' ? 'user' : 'assistant', 
            content: data.message 
          }
        ]);
        if (data.guardrail_status === 'FAILED') {
          playGuardrailThud();
          addLog('ERROR', `Guardrail Blocked: Agent attempted below floor price.`);
        } else {
          addLog(data.speaker, data.message);
        }
      },
      onComplete: (data) => {
        setStatus(data.status);
        if (data.status === 'ACCEPTED') {
          playDealChime();
          setDealPrice(data.final_price);
          setPendingOrderId(data.order_id);
          addLog('SYSTEM', `Deal Struck at ₹${data.final_price}. Order ${data.order_id} pending merchant confirmation.`);
        } else {
          addLog('SYSTEM', `Negotiation Ended: ${data.status}`);
        }
        setLoading(false);
      },
      onError: (err) => {
        addLog('ERROR', `Stream error: ${err}`);
        setLoading(false);
        setStatus('ERROR');
      }
    });
  };

  const handleManualHitl = async (confirm) => {
    if (!pendingOrderId) return;
    setLoading(true);
    try {
      await confirmSalesOrder({ order_id: pendingOrderId, confirmation: confirm, merchant_id: 'm1' });
      setMerchantConfirmed(true);
      addLog('SYSTEM', `HITL: Merchant manually ${confirm ? 'confirmed' : 'rejected'} stock for ${pendingOrderId}`);
    } catch (e) {
      alert("Error: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-6xl mx-auto flex flex-col lg:flex-row gap-6 h-[calc(100vh-8rem)]">
      {/* Viewport: Consumer WhatsApp View */}
      <div className="shrink-0 flex justify-center items-center">
         <WhatsAppUI 
            title={selectedProduct?.merchant_name || "Merchant"} 
            subtitle="Autonomous Sales Bot"
            messages={messages}
            loading={loading}
            onSend={(msg) => {
              const numMatch = msg.match(/\d+(?:k|,\d{3}|\d*)/i);
              let target = (selectedProduct?.listed_price || 0) * 0.8;
              let max = (selectedProduct?.listed_price || 0) * 0.9;
              
              if (numMatch) {
                let parsed = numMatch[0].replace(/k/i, '000').replace(/,/g, '');
                target = Number(parsed);
                max = target * 1.1;
              }
              
              setMessages([{ role: 'user', content: msg }]);
              startNegotiation(target, max);
            }}
         />
      </div>

      {/* Stagecraft: Merchant Backstage & Arena */}
      <div className="flex-1 flex flex-col gap-6 overflow-y-auto hide-scrollbar">
        {/* Product Selector Context */}
        <div className="glass-panel p-5 rounded-2xl border border-white/5 shadow-glass-edge">
          <div className="flex items-center justify-between mb-4 pb-4 border-b border-white/[0.04]">
             <h3 className="text-white font-bold flex items-center gap-2"><Settings2 size={16} className="text-slate-400" /> Active Context</h3>
          </div>
          <select 
            className="w-full bg-obsidian-950 border border-white/10 rounded-xl px-4 py-3 text-sm text-white outline-none"
            value={selectedProduct?.id || ''}
            onChange={(e) => setSelectedProduct(products.find(p => p.id === e.target.value))}
            disabled={loading}
          >
            {products.map(p => (
              <option key={p.id} value={p.id}>{p.name} - ₹{(p.listed_price || 0).toLocaleString()}</option>
            ))}
          </select>

          {selectedProduct && (
            <div className="grid grid-cols-2 gap-4 mt-4 text-[11px] font-mono">
              <div className="bg-obsidian-950/50 p-3 rounded-lg border border-white/5">
                <div className="text-slate-500 mb-1">Listed Ask</div>
                <div className="text-white text-sm">₹{(selectedProduct.listed_price || 0).toLocaleString()}</div>
              </div>
              <div className="bg-rose-500/10 p-3 rounded-lg border border-rose-500/20 relative overflow-hidden">
                <div className="absolute top-0 right-0 p-1"><ShieldCheck size={14} className="text-rose-400 opacity-50" /></div>
                <div className="text-rose-400 mb-1">Hard Floor (Secret)</div>
                <div className="text-rose-300 text-sm">₹{Math.floor((selectedProduct.listed_price || 0) * 0.8).toLocaleString()}</div>
              </div>
            </div>
          )}
        </div>

        {/* Live Negotiation Arena */}
        {(turns.length > 0 || status !== 'IDLE') && (
          <NegotiationArena 
            turns={turns}
            status={status}
            finalPrice={dealPrice}
            listedPrice={selectedProduct?.listed_price || 0}
            floorPrice={Math.floor((selectedProduct?.listed_price || 0) * 0.8)}
            buyerTarget={turns[0]?.proposed_price || ((selectedProduct?.listed_price || 0) * 0.85)}
          />
        )}

        {/* HITL Confirmation View */}
        {status === 'ACCEPTED' && pendingOrderId && !merchantConfirmed && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-panel p-6 rounded-2xl border-2 border-emerald-500/40 bg-emerald-500/5">
            <h3 className="font-bold text-emerald-400 flex items-center gap-2 mb-2"><Zap size={18} /> Human-in-the-Loop Override</h3>
            <p className="text-sm text-slate-300 mb-4">Deal locked at ₹{dealPrice?.toLocaleString()}. Before Razorpay collects payment, confirm physical stock availability. (In prod, this is a 1-click WhatsApp notification to the merchant).</p>
            <div className="flex gap-3">
              <button 
                onClick={() => handleManualHitl(true)} disabled={loading}
                className="flex-1 bg-emerald-500 hover:bg-emerald-600 text-white font-bold py-3 rounded-xl disabled:opacity-50 transition-colors shadow-lg shadow-emerald-500/20"
              >
                Yes, Stock Available
              </button>
              <button 
                onClick={() => handleManualHitl(false)} disabled={loading}
                className="flex-1 bg-obsidian-800 hover:bg-rose-500/20 border border-white/10 hover:border-rose-500/50 hover:text-rose-400 text-slate-300 font-bold py-3 rounded-xl disabled:opacity-50 transition-colors"
              >
                No, Out of Stock
              </button>
            </div>
          </motion.div>
        )}

        {merchantConfirmed && (
          <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="glass-panel p-4 rounded-xl border border-emerald-500/30 text-emerald-400 text-sm font-bold flex items-center gap-2 justify-center">
            <ShieldCheck size={18} /> Stock Confirmed. Awaiting Buyer Payment.
          </motion.div>
        )}
      </div>
    </div>
  );
};

