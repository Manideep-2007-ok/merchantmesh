import React from 'react';
import { motion } from 'motion/react';
import { Trophy, Clock, TrendingDown, Store } from 'lucide-react';
import { cn } from "../lib/utils";
import confetti from "canvas-confetti";
import { BorderBeam } from "./magicui/border-beam";

export const ReverseAuctionArena = ({ auctionResult, discoveredProducts }) => {
  if (!auctionResult || !auctionResult.deals) return null;

  const triggerConfetti = () => {
    confetti({
      particleCount: 100,
      spread: 70,
      origin: { y: 0.6 },
      colors: ['#0D5FFF', '#10B981', '#F59E0B']
    });
  };

  React.useEffect(() => {
    if (auctionResult.winner) {
      triggerConfetti();
    }
  }, [auctionResult.winner]);

  return (
    <div className="w-full bg-obsidian-900 border border-white/[0.08] rounded-2xl p-6 shadow-glass-edge">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-6 pb-4 border-b border-white/[0.04]">
        <div className="flex items-center gap-2">
          <Trophy size={18} className="text-amber-400" />
          <h3 className="font-display font-extrabold text-white text-sm tracking-wide">Parallel Reverse Auction Results</h3>
          <span className="bg-razorpay-blue/20 text-blue-300 text-[10px] px-2 py-0.5 rounded-full font-bold border border-razorpay-blue/30">
            {auctionResult.total_dealers} Concurrent Workers
          </span>
        </div>
        <div className="flex items-center gap-4 text-[11px] text-slate-400">
          {auctionResult.fastest_dealer && (
            <span className="flex items-center gap-1.5 text-blue-400">
              <Clock size={13} /> Fastest: <b className="text-white">{auctionResult.fastest_dealer}</b> ({auctionResult.fastest_latency_ms}ms)
            </span>
          )}
          {auctionResult.cheapest_dealer && (
            <span className="flex items-center gap-1.5 text-emerald-400">
              <TrendingDown size={13} /> Best Price: <b className="text-white">{auctionResult.cheapest_dealer}</b> (₹{auctionResult.cheapest_price?.toLocaleString()})
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {auctionResult.deals.map((deal, idx) => {
          const isWinner = deal.is_winner;
          const prod = discoveredProducts?.find(p => p.id === deal.product_id);

          return (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.1, type: 'spring', damping: 25 }}
              key={idx}
              className={cn(
                "rounded-xl p-5 relative flex flex-col justify-between overflow-hidden",
                isWinner 
                  ? "bg-obsidian-800 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.1),0_0_20px_rgba(245,158,11,0.15)]" 
                  : "bg-obsidian-950/50 border border-white/[0.04]"
              )}
            >
              {isWinner && <BorderBeam size={150} duration={8} delay={0.5} />}

              {isWinner && (
                <div className="absolute top-0 right-0 bg-gradient-to-l from-amber-500/20 to-transparent w-32 h-full z-0" />
              )}
              
              {isWinner && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-amber-500 text-obsidian-950 font-black text-[9px] uppercase tracking-widest px-3 py-1 rounded-b-md shadow-md z-10 flex items-center gap-1">
                  <Trophy size={10} className="text-obsidian-900" /> Crowned Deal
                </div>
              )}

              <div className="relative z-10">
                <div className="flex gap-3 mb-4 pb-4 border-b border-white/[0.04]">
                  <div className="w-10 h-10 rounded-lg bg-obsidian-800 border border-white/5 flex items-center justify-center shrink-0">
                    <Store size={18} className="text-slate-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-bold text-slate-200 text-sm truncate">{deal.merchant_name}</div>
                    <div className="text-[10px] text-slate-500 flex items-center gap-1.5 mt-1">
                      <span>{deal.reliability_score}⭐ Trust</span>
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className={cn("font-black text-lg font-mono", deal.status === 'ACCEPTED' ? 'text-emerald-400' : 'text-rose-400/80')}>
                      {deal.final_price ? `₹${deal.final_price.toLocaleString()}` : 'No Deal'}
                    </div>
                  </div>
                </div>

                <div className="bg-obsidian-950/80 rounded-lg p-3 space-y-2 text-[11px] font-mono border border-white/[0.02]">
                  <div className="flex justify-between text-slate-400">
                    <span>Turn Latency:</span>
                    <span className="text-blue-400 font-bold tabular-nums">{deal.latency_ms.toFixed(0)}ms</span>
                  </div>
                  <div className="flex justify-between text-slate-400">
                    <span>Turns:</span>
                    <span className="text-slate-300 tabular-nums">{deal.turns_count} turns</span>
                  </div>
                  <div className="flex justify-between text-slate-400 pt-2 border-t border-white/[0.02]">
                    <span>Merit Score:</span>
                    <span className={cn("font-bold tabular-nums text-sm", isWinner ? 'text-amber-400' : 'text-slate-300')}>
                      {deal.deal_score.toFixed(1)}
                    </span>
                  </div>
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
};
