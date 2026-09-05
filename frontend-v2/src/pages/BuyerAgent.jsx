import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Search, ShoppingBag, ArrowRight, ShieldCheck, CreditCard, ChevronRight, CheckCheck, Sparkles } from 'lucide-react';
import { searchBuyerChat, runParallelReverseAuction, checkoutTrustOrder, simulatePayment, getProducts } from '../lib/api';
import { useAgentLogs } from '../context/AgentActivityContext';
import { playTensionPing, playDealChime, playPaymentSuccess } from '../lib/sound';
import { ReverseAuctionArena } from '../components/ReverseAuctionArena';

export const BuyerAgent = () => {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState([]);
  const [discoveredProducts, setDiscoveredProducts] = useState([]);
  const [auctionResult, setAuctionResult] = useState(null);
  const [checkoutState, setCheckoutState] = useState(null); // 'idle', 'pending_stock', 'ready', 'paid'
  const [orderId, setOrderId] = useState(null);
  const { addLog } = useAgentLogs();
  
  const isLocal = typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim() || loading) return;

    setLoading(true);
    setAuctionResult(null);
    setCheckoutState(null);
    setOrderId(null);
    const userMsg = query;
    setQuery('');
    setChatHistory(prev => [...prev, { role: 'user', content: userMsg }]);
    addLog('BUYER', `Processing buyer intent: "${userMsg}"`);

    try {
      const res = await searchBuyerChat(userMsg, chatHistory);
      setChatHistory(prev => [...prev, { role: 'assistant', content: res.reply }]);
      
      if (res.status === 'SUCCESS' && res.products?.length > 0) {
        const pIds = res.products.map(p => p.id);
        addLog('SYSTEM', `Found ${pIds.length} matching SKUs in network.`);
        setDiscoveredProducts(res.products);
        
        // Trigger Parallel RFQ
        addLog('SYSTEM', `Initiating parallel Reverse Auction...`);
        playTensionPing();
        
        const auction = await runParallelReverseAuction({
          product_ids: pIds,
          target_price: res.parsed_query?.target_price,
          max_budget: res.parsed_query?.max_budget
        });
        
        setAuctionResult(auction);
        addLog('BUYER', `Auction concluded. Winner: ${auction.winner ? auction.cheapest_dealer : 'None'}`);
        
        if (auction.winner) {
          playDealChime();
        }
      }
    } catch (err) {
      addLog('ERROR', `Search failed: ${err.message}`);
      setChatHistory(prev => [...prev, { role: 'assistant', content: `Sorry, I encountered an error: ${err.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  const handleCheckout = async () => {
    if (!auctionResult?.winner) return;
    setLoading(true);
    addLog('BUYER', `Initiating trust checkout for deal with ${auctionResult.cheapest_dealer}`);
    
    try {
      const winnerDeal = auctionResult.deals.find(d => d.is_winner);
      const res = await checkoutTrustOrder({
        product_id: winnerDeal.product_id,
        merchant_id: winnerDeal.merchant_id,
        agreed_price: winnerDeal.final_price,
        negotiation_id: winnerDeal.session_id,
        quantity: 1
      });
      
      setOrderId(res.order_id);
      setCheckoutState('pending_stock');
      addLog('SYSTEM', `Order ${res.order_id} created. Awaiting human merchant stock confirmation...`);
      // Start polling for stock confirmation
      pollOrderReady(res.order_id);
    } catch (err) {
      addLog('ERROR', `Checkout failed: ${err.message}`);
      setChatHistory(prev => [...prev, { role: 'assistant', content: `⚠️ Checkout failed: ${err.message}. Please try again.` }]);
    } finally {
      setLoading(false);
    }
  };

  const pollOrderReady = (oid) => {
    // In a real app, use WebSockets. Here we poll.
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/trust/order-status/${oid}?session_id=${sessionStorage.getItem('mm_session_id') || ''}`);
        const data = await res.json();
        if (data.status === 'READY_FOR_PAYMENT') {
          clearInterval(interval);
          setCheckoutState('ready');
          addLog('SYSTEM', `Merchant confirmed stock. Order ${oid} ready for payment.`);
        } else if (data.status === 'CANCELLED' || data.status === 'REJECTED') {
          clearInterval(interval);
          setCheckoutState('rejected');
          addLog('SYSTEM', `Order ${oid} rejected by merchant (out of stock).`);
        }
      } catch (e) {
        console.error("Polling error", e);
      }
    }, 2000);
  };

  const handlePayment = async () => {
    setLoading(true);
    addLog('SYSTEM', `Initiating payment for ${orderId}`);
    try {
      if (isLocal) {
        await simulatePayment(orderId);
        setCheckoutState('paid');
        playPaymentSuccess();
        addLog('SYSTEM', `Payment simulated & verified via HMAC webhook. Order paid.`);
      } else {
        // Razorpay Checkout Integration
        addLog('SYSTEM', `Opening Razorpay Standard Checkout...`);
        const options = {
          key: 'rzp_test_YourTestKeyHere', // Replace with real test key
          amount: auctionResult.deals.find(d => d.is_winner).final_price * 100,
          currency: 'INR',
          name: 'MerchantMesh',
          description: 'A2A Commerce Purchase',
          order_id: '', // Would come from backend Razorpay order creation
          handler: function(response) {
            simulatePayment(orderId).then(() => {
              setCheckoutState('paid');
              playPaymentSuccess();
              addLog('SYSTEM', `Razorpay payment successful. Webhook simulated.`);
            });
          },
          theme: { color: '#0D5FFF' }
        };
        const rzp = new window.Razorpay(options);
        rzp.open();
      }
    } catch (err) {
      addLog('ERROR', `Payment failed: ${err.message}`);
      setChatHistory(prev => [...prev, { role: 'assistant', content: `⚠️ Payment failed: ${err.message}. Please try again.` }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-5xl mx-auto flex flex-col lg:flex-row gap-6 h-[calc(100vh-8rem)]">
      {/* Chat / Search Interface */}
      <div className="flex-1 glass-panel rounded-3xl flex flex-col overflow-hidden relative border border-white/5 shadow-glass-edge">
        <div className="p-6 border-b border-white/[0.04] bg-obsidian-950/50 flex items-center justify-between z-10">
          <div>
            <h2 className="text-lg font-display font-bold text-white flex items-center gap-2">
              <Sparkles size={18} className="text-blue-400" /> Buyer Agent
            </h2>
            <p className="text-[11px] text-slate-400 font-mono mt-1">Natural Language Intent → Protocol RFQ</p>
          </div>
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_10px_rgba(16,185,129,0.5)]" />
        </div>

        <div className="flex-1 p-6 overflow-y-auto space-y-4 font-sans bg-obsidian-900/50">
          {chatHistory.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-center opacity-60">
              <Search size={48} className="mb-4 text-blue-500/50" />
              <p className="text-sm font-medium text-slate-300">"I need an iPhone 15 under ₹60k"</p>
              <p className="text-xs text-slate-500 mt-2 max-w-xs">The agent will query the mesh and negotiate in parallel on your behalf.</p>
            </div>
          )}
          {chatHistory.map((msg, i) => (
            <motion.div 
              initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
              key={i} 
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div className={`max-w-[80%] p-4 rounded-2xl text-[14px] leading-relaxed shadow-sm border ${
                msg.role === 'user' 
                  ? 'bg-razorpay-blue text-white border-blue-400/50 rounded-br-sm' 
                  : 'bg-obsidian-800 text-slate-200 border-white/10 rounded-bl-sm'
              }`}>
                {msg.content}
              </div>
            </motion.div>
          ))}
          {loading && !auctionResult && (
             <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex justify-start">
               <div className="bg-obsidian-800 p-4 rounded-2xl rounded-bl-sm border border-white/10 flex items-center gap-2">
                 <div className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                 <div className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                 <div className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
               </div>
             </motion.div>
          )}
        </div>

        <div className="p-4 bg-obsidian-950/80 border-t border-white/[0.04]">
          <form onSubmit={handleSearch} className="relative">
            <input 
              type="text" 
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="What are you looking to buy?"
              disabled={loading}
              className="w-full bg-obsidian-800 border border-white/10 rounded-full py-3.5 pl-5 pr-14 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 transition-all"
            />
            <button 
              type="submit" 
              disabled={loading || !query.trim()}
              className="absolute right-2 top-1/2 -translate-y-1/2 w-10 h-10 bg-razorpay-blue text-white rounded-full flex items-center justify-center hover:bg-blue-600 transition-colors disabled:opacity-50"
            >
              <ArrowRight size={18} />
            </button>
          </form>
        </div>
      </div>

      {/* Auction & Checkout Sidebar */}
      <AnimatePresence>
        {auctionResult && (
          <motion.div 
            initial={{ opacity: 0, x: 20, width: 0 }} animate={{ opacity: 1, x: 0, width: '100%' }}
            className="lg:max-w-md w-full flex flex-col gap-4 overflow-y-auto hide-scrollbar"
          >
            <ReverseAuctionArena auctionResult={auctionResult} discoveredProducts={discoveredProducts} />

            {auctionResult.winner && !checkoutState && (
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="glass-panel p-5 rounded-2xl border border-emerald-500/30">
                <h4 className="font-bold text-white mb-2 flex items-center gap-2"><ShoppingBag size={16} className="text-emerald-400" /> Deal Ready</h4>
                <p className="text-xs text-slate-400 mb-4">You got the best price across the mesh. Proceed to secure the deal with the merchant.</p>
                <button 
                  onClick={handleCheckout} 
                  disabled={loading}
                  className="w-full bg-emerald-500 hover:bg-emerald-600 text-white font-bold py-3 rounded-xl flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
                >
                  <ShieldCheck size={18} /> Lock Deal & Await Confirmation
                </button>
              </motion.div>
            )}

            {checkoutState === 'pending_stock' && (
              <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="glass-panel p-5 rounded-2xl border border-amber-500/30 bg-amber-500/5">
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-8 h-8 rounded-full border-2 border-amber-500 border-t-transparent animate-spin shrink-0" />
                  <div>
                    <h4 className="font-bold text-amber-400">Awaiting Merchant (HITL)</h4>
                    <p className="text-xs text-slate-400">Merchant is confirming physical stock in 1-2s...</p>
                  </div>
                </div>
              </motion.div>
            )}

            {checkoutState === 'ready' && (
              <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="glass-panel p-5 rounded-2xl border border-razorpay-blue/30 bg-razorpay-blue/5">
                <h4 className="font-bold text-white mb-2 flex items-center gap-2"><ShieldCheck size={16} className="text-emerald-400" /> Stock Confirmed!</h4>
                <p className="text-xs text-slate-400 mb-4">Merchant has confirmed stock availability. Complete payment securely.</p>
                <button 
                  onClick={handlePayment} 
                  disabled={loading}
                  className="w-full bg-razorpay-blue hover:bg-blue-600 text-white font-bold py-3 rounded-xl flex items-center justify-center gap-2 transition-colors shadow-lg shadow-blue-500/20"
                >
                  <CreditCard size={18} /> {isLocal ? 'Simulate UPI Payment' : 'Pay via Razorpay'}
                </button>
              </motion.div>
            )}

            {checkoutState === 'paid' && (
              <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="glass-panel p-6 rounded-2xl border border-emerald-500/50 bg-emerald-500/10 text-center">
                <div className="w-16 h-16 bg-emerald-500 rounded-full flex items-center justify-center mx-auto mb-4">
                  <CheckCheck size={32} className="text-white" />
                </div>
                <h4 className="font-bold text-emerald-400 text-lg mb-1">Payment Successful</h4>
                <p className="text-xs text-slate-300">Funds secured via Razorpay Escrow. Order #{orderId} placed.</p>
              </motion.div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

