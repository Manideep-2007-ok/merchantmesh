import React, { useState, useEffect } from 'react';
import { motion } from 'motion/react';
import { ShieldCheck, Zap, User, Store } from 'lucide-react';
import { cn } from '../lib/utils';

export const NegotiationArena = ({ 
  turns, 
  status, 
  finalPrice, 
  listedPrice, 
  floorPrice, 
  buyerTarget, 
  buyerMax, 
  merchantName 
}) => {
  const [displayedTurns, setDisplayedTurns] = useState([]);
  const [currentBuyerBid, setCurrentBuyerBid] = useState(buyerTarget || 0);
  const [currentSellerAsk, setCurrentSellerAsk] = useState(listedPrice || 0);
  const [animating, setAnimating] = useState(false);

  // Playback logic for pacing the negotiation visualization
  useEffect(() => {
    if (!turns || turns.length === 0) return;
    setAnimating(true);
    let delay = 0;
    
    // Reset
    setDisplayedTurns([]);
    
    const timers = turns.map((turn, idx) => {
      delay += 800; // 0.8s per turn pacing
      return setTimeout(() => {
        setDisplayedTurns(prev => [...prev, turn]);
        if (turn.speaker === 'BUYER') {
          setCurrentBuyerBid(turn.proposed_price || currentBuyerBid);
        } else if (turn.speaker === 'SELLER') {
          setCurrentSellerAsk(turn.proposed_price || currentSellerAsk);
        }
        if (idx === turns.length - 1) setAnimating(false);
      }, delay);
    });
    
    return () => timers.forEach(clearTimeout);
  }, [turns, buyerTarget, listedPrice]);

  // Calculate percentages for the tug-of-war slider
  // Range: Min = floorPrice * 0.5, Max = listedPrice
  const minVal = Math.min(buyerTarget * 0.8, floorPrice * 0.8, 1);
  const maxVal = listedPrice * 1.1;
  const range = maxVal - minVal;
  
  const getPct = (val) => Math.max(0, Math.min(100, ((val - minVal) / range) * 100));
  
  const buyerPct = getPct(currentBuyerBid);
  const sellerPct = getPct(currentSellerAsk);
  const floorPct = getPct(floorPrice);

  return (
    <div className="w-full bg-obsidian-900 border border-white/[0.08] rounded-2xl p-6 shadow-glass-edge overflow-hidden relative">
      <div className="flex items-center justify-between mb-8">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <Zap size={16} className="text-amber-400 fill-amber-400" /> Live Negotiation Arena
        </h3>
        {animating && <span className="text-[10px] font-mono bg-blue-500/20 text-blue-300 px-2 py-0.5 rounded-full animate-pulse border border-blue-500/30">STREAMING</span>}
        {!animating && status === 'ACCEPTED' && <span className="text-[10px] font-mono bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded-full border border-emerald-500/30">DEAL STRUCK</span>}
      </div>

      {/* Tug of War Track */}
      <div className="relative h-12 bg-obsidian-800 rounded-xl mb-10 border border-white/5 overflow-hidden">
        {/* Floor Shield Line */}
        <div 
          className="absolute top-0 bottom-0 w-0.5 bg-rose-500/50 z-10"
          style={{ left: `${floorPct}%` }}
        >
          <div className="absolute top-full mt-2 -translate-x-1/2 flex flex-col items-center">
            <ShieldCheck size={12} className="text-rose-400 mb-0.5" />
            <span className="text-[9px] font-mono text-rose-300 whitespace-nowrap">Protected Floor: ₹{floorPrice?.toLocaleString()}</span>
          </div>
        </div>

        {/* The connecting active bar */}
        <motion.div 
          className="absolute top-2 bottom-2 bg-gradient-to-r from-blue-500/20 to-amber-500/20 rounded-md"
          animate={{ left: `${buyerPct}%`, width: `${Math.max(0, sellerPct - buyerPct)}%` }}
          transition={{ type: 'spring', damping: 20, stiffness: 100 }}
        />

        {/* Buyer Marker */}
        <motion.div 
          className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 z-20 flex flex-col items-center"
          animate={{ left: `${buyerPct}%` }}
          transition={{ type: 'spring', damping: 25, stiffness: 200 }}
        >
          <div className="w-8 h-8 rounded-full bg-blue-600 border-2 border-obsidian-900 shadow-lg flex items-center justify-center">
            <User size={14} className="text-white" />
          </div>
          <div className="absolute bottom-full mb-1 bg-blue-900/80 backdrop-blur text-blue-100 text-[10px] font-mono font-bold px-2 py-0.5 rounded border border-blue-500/30 whitespace-nowrap">
            Bid: ₹{currentBuyerBid?.toLocaleString()}
          </div>
        </motion.div>

        {/* Seller Marker */}
        <motion.div 
          className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 z-20 flex flex-col items-center"
          animate={{ left: `${sellerPct}%` }}
          transition={{ type: 'spring', damping: 25, stiffness: 200 }}
        >
          <div className="w-8 h-8 rounded-full bg-amber-500 border-2 border-obsidian-900 shadow-lg flex items-center justify-center">
            <Store size={14} className="text-obsidian-950" />
          </div>
          <div className="absolute top-full mt-1 bg-amber-900/80 backdrop-blur text-amber-200 text-[10px] font-mono font-bold px-2 py-0.5 rounded border border-amber-500/30 whitespace-nowrap">
            Ask: ₹{currentSellerAsk?.toLocaleString()}
          </div>
        </motion.div>
      </div>

      {/* Turn Dialogue */}
      <div className="space-y-4 pt-6 mt-4 border-t border-white/[0.04]">
        {displayedTurns.map((t, i) => (
          <motion.div 
            key={i}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className={`flex ${t.speaker === 'BUYER' ? 'justify-start' : 'justify-end'}`}
          >
            <div className={cn(
              "max-w-[75%] p-3 rounded-2xl text-[13px] leading-relaxed relative",
              t.speaker === 'BUYER' 
                ? "bg-obsidian-800 border border-blue-500/20 text-blue-50 rounded-tl-sm"
                : "bg-amber-950/30 border border-amber-500/20 text-amber-50 rounded-tr-sm"
            )}>
              <div className="flex items-center gap-2 mb-1.5">
                <span className={cn(
                  "text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-sm",
                  t.action === 'ACCEPT' ? "bg-emerald-500/20 text-emerald-400" :
                  t.speaker === 'BUYER' ? "bg-blue-500/20 text-blue-400" : "bg-amber-500/20 text-amber-400"
                )}>{t.action}</span>
                <span className="font-mono text-xs font-bold opacity-80">₹{t.proposed_price?.toLocaleString()}</span>
              </div>
              <p className="italic opacity-90">"{t.message}"</p>
              <div className="mt-2 text-[9px] font-mono text-white/30 flex items-center gap-1">
                Guardrail: <span className={t.guardrail_status === 'PASSED' ? 'text-emerald-500/80' : 'text-rose-400/80'}>{t.guardrail_status}</span>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
};
