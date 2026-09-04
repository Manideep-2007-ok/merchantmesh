import React, { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AnimatedBeam } from "@/components/magicui/animated-beam";
import { IconRobot, IconBuildingStore, IconUserSearch, IconCheck, IconTerminal2, IconMapPin, IconStar, IconPackage } from "@tabler/icons-react";
import { cn } from "@/lib/utils";

export const ReverseAuctionVisualizer = ({ phaseOverride, auctionResult, logsOverride }) => {
  const containerRef = useRef(null);
  const buyerRef = useRef(null);
  const seller1Ref = useRef(null);
  const seller2Ref = useRef(null);
  const seller3Ref = useRef(null);
  const seller4Ref = useRef(null);
  const seller5Ref = useRef(null);
  const terminalEndRef = useRef(null);

  // Phases: 0 = Idle, 1 = Broadcast, 2 = Bidding, 3 = Locked
  const [phase, setPhase] = useState(0);
  useEffect(() => {
    if (phaseOverride !== undefined) setPhase(phaseOverride);
  }, [phaseOverride]);
  const [internalLogs, setInternalLogs] = useState(["[SYSTEM] Buyer Agent initialized. Awaiting user intent..."]);
  const logs = logsOverride || internalLogs;

  const addLog = (log) => {
    setInternalLogs(prev => [...prev.slice(-15), `[${new Date().toLocaleTimeString()}] ${log}`]);
  };

  // PRESENTER MODE: Keyboard controlled phases removed to prevent spacebar conflict in chat input.

  // Auto-scroll terminal
  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs]);

  // Node Positions (Local Scope - SafeArea)
  const sellers = auctionResult?.deals?.slice(0, 5).map((d, i) => {
      const refs = [seller1Ref, seller2Ref, seller3Ref, seller4Ref, seller5Ref];
      const positions = [
        { top: "20%", left: "20%", curvature: 40 },
        { top: "20%", left: "80%", curvature: -40 },
        { top: "50%", left: "15%", curvature: 30 },
        { top: "50%", left: "85%", curvature: -30 },
        { top: "80%", left: "50%", curvature: 0 }
      ];
      return {
        id: i+1,
        ref: refs[i],
        label: d.merchant_name,
        price: "₹" + d.final_price,
        isWinner: d.is_winner,
        curvature: positions[i].curvature,
        dist: "Local",
        rating: (d.reliability_score !== undefined && d.reliability_score !== null) ? Number(d.reliability_score).toFixed(1) : "4.5",
        stock: d.stock_quantity || 100,
        ...positions[i]
      };
  }) || [
    { id: 1, ref: seller1Ref, label: "Vendor A", price: "₹250", top: "20%", left: "20%", isWinner: false, curvature: 40, dist: "12km", rating: "4.2", stock: 150 },
    { id: 2, ref: seller2Ref, label: "Vendor B", price: "₹210", top: "20%", left: "80%", isWinner: false, curvature: -40, dist: "8km", rating: "4.5", stock: 400 },
    { id: 3, ref: seller3Ref, label: "Vendor C", price: "₹230", top: "50%", left: "15%", isWinner: false, curvature: 30, dist: "15km", rating: "4.1", stock: 800 },
    { id: 4, ref: seller4Ref, label: "Vendor D", price: "₹200", top: "50%", left: "85%", isWinner: false, curvature: -30, dist: "3km", rating: "4.9", stock: 120 },
    { id: 5, ref: seller5Ref, label: "Vendor E", price: "₹180", top: "80%", left: "50%", isWinner: true, curvature: 0, dist: "1.2km", rating: "4.9", stock: 950 },
  ];

  const getBeamColors = (isWinner) => {
    if (phase === 0) return { start: "#3f3f46", stop: "#3f3f46", reverse: false }; // Idle
    if (phase === 1) return { start: "#3b82f6", stop: "#8b5cf6", reverse: false }; // Broadcast
    if (phase === 2) return { start: "#eab308", stop: "#f59e0b", reverse: true }; // Bidding
    if (phase === 3) {
      if (isWinner) return { start: "#10b981", stop: "#34d399", reverse: true }; // Winner
      return { start: "#ef4444", stop: "#b91c1c", reverse: true }; // Loser
    }
    return { start: "#3f3f46", stop: "#3f3f46", reverse: false };
  };

  return (
    <div className="relative w-full h-full min-h-[600px] flex flex-col bg-white/5 backdrop-blur-xl rounded-3xl border border-white/10 overflow-hidden shadow-[0_8px_32px_0_rgba(0,0,0,0.36)]" ref={containerRef}>
      
      {/* Top 75% - The Visualizer */}
      <div className="relative flex-1 p-6 flex items-center justify-center">
        {/* Title / Status */}
        <div className="absolute top-6 left-0 w-full text-center z-30">
          <h3 className="text-white/80 font-mono text-sm tracking-widest uppercase mb-1">Live Reverse Auction</h3>
          <p className="text-xs font-mono font-bold px-3 py-1 rounded-full border inline-block transition-colors duration-500"
            style={{
              backgroundColor: phase === 0 ? "rgba(255,255,255,0.05)" : phase === 1 ? "rgba(59,130,246,0.2)" : phase === 2 ? "rgba(234,179,8,0.2)" : "rgba(16,185,129,0.2)",
              color: phase === 0 ? "#71717a" : phase === 1 ? "#60a5fa" : phase === 2 ? "#fde047" : "#6ee7b7",
              borderColor: phase === 0 ? "rgba(255,255,255,0.1)" : phase === 1 ? "rgba(59,130,246,0.3)" : phase === 2 ? "rgba(234,179,8,0.3)" : "rgba(16,185,129,0.3)",
            }}
          >
            {phase === 0 ? "SYSTEM IDLE (Press Space)" : phase === 1 ? "BROADCASTING RFQ..." : phase === 2 ? "EVALUATING BIDS..." : "DEAL LOCKED"}
          </p>
        </div>

        {/* Central Buyer Agent Node */}
        <div 
          ref={buyerRef}
          className={cn(
            "absolute z-20 w-20 h-20 rounded-full border-2 flex items-center justify-center transition-all duration-500",
            phase === 0 ? "bg-zinc-800 border-zinc-500 shadow-none" : 
            phase === 1 ? "bg-blue-600 border-blue-300 shadow-[0_0_40px_rgba(37,99,235,0.8)] scale-110" :
            phase === 2 ? "bg-yellow-500 border-yellow-200 shadow-[0_0_40px_rgba(234,179,8,0.8)]" :
            "bg-emerald-500 border-emerald-200 shadow-[0_0_50px_rgba(16,185,129,0.8)] scale-110"
          )}
        >
          <IconUserSearch className={cn("w-10 h-10 transition-colors duration-500", phase === 0 ? "text-zinc-400" : phase === 1 ? "text-white" : phase === 2 ? "text-yellow-950" : "text-emerald-950")} />
          
          <AnimatePresence>
            {phase === 3 && (
              <motion.div 
                initial={{ scale: 0, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0, opacity: 0 }}
                className="absolute -top-3 -right-3 w-8 h-8 bg-emerald-500 rounded-full flex items-center justify-center border-2 border-black"
              >
                <IconCheck className="w-5 h-5 text-black" stroke={3} />
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Seller Nodes */}
        {sellers.map((seller) => (
          <div
            key={seller.id}
            ref={seller.ref}
            className={cn(
              "absolute z-10 w-16 h-16 rounded-full border-2 flex flex-col items-center justify-center transition-all duration-700 group cursor-help",
              phase === 0 ? "bg-zinc-800 border-zinc-600 shadow-none" :
              phase === 1 ? "bg-purple-600 border-purple-300 shadow-[0_0_20px_rgba(147,51,234,0.8)]" :
              phase === 2 ? "bg-yellow-500 border-yellow-200 shadow-[0_0_30px_rgba(234,179,8,0.8)] scale-110" :
              seller.isWinner ? "bg-emerald-500 border-emerald-200 shadow-[0_0_40px_rgba(16,185,129,0.9)] scale-110" : "bg-zinc-800 border-zinc-600 shadow-none scale-95"
            )}
            style={{ top: seller.top, left: seller.left, transform: "translate(-50%, -50%)" }}
          >
            {/* Tooltip (Only visible when negotiation starts) */}
            {phase > 0 && (
              <div className="absolute -top-16 opacity-0 group-hover:opacity-100 transition-opacity duration-300 bg-[#09090b] border border-white/10 p-2.5 rounded-lg text-white text-[10px] whitespace-nowrap shadow-2xl pointer-events-none z-50">
                 <div className="text-zinc-500 mb-1.5 font-mono tracking-widest uppercase border-b border-white/5 pb-1">{seller.label} Metrics</div>
                 <div className="flex gap-4 font-mono text-zinc-300">
                   <span className="flex items-center gap-1"><IconMapPin className="w-3 h-3 text-blue-400"/> {seller.dist}</span>
                   <span className="flex items-center gap-1"><IconStar className="w-3 h-3 text-yellow-400"/> {seller.rating}</span>
                   <span className="flex items-center gap-1"><IconPackage className="w-3 h-3 text-purple-400"/> {seller.stock} qty</span>
                 </div>
              </div>
            )}

            <IconBuildingStore className={cn(
              "w-7 h-7 transition-colors",
              phase === 0 ? "text-zinc-400" : phase === 1 ? "text-white" : phase === 2 ? "text-yellow-950" : seller.isWinner ? "text-emerald-950" : "text-zinc-500"
            )} />
            
            {/* Label placed completely outside the node to prevent squishing */}
            <span className={cn(
              "absolute -bottom-6 w-max text-[10px] font-bold tracking-widest uppercase transition-colors",
              phase === 0 ? "text-zinc-500" : phase === 1 ? "text-purple-400" : phase === 2 ? "text-yellow-500" : seller.isWinner ? "text-emerald-500" : "text-zinc-600"
            )}>
              {seller.label}
            </span>
            
            <AnimatePresence>
              {(phase === 2 || (phase === 3 && seller.isWinner)) && (
                <motion.div 
                  initial={{ opacity: 0, y: 10, scale: 0.8 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                  className={cn(
                    "absolute -top-8 px-3 py-1 rounded-md text-[11px] font-mono font-bold border whitespace-nowrap z-30 shadow-xl",
                    phase === 3 && seller.isWinner ? "bg-emerald-500 text-black border-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.6)]" : "bg-[#09090b] text-yellow-400 border-yellow-500/50"
                  )}
                >
                  {seller.price}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        ))}

        {/* Animated Beams */}
        {sellers.map((seller) => {
          const colors = getBeamColors(seller.isWinner);
          return (
            <AnimatedBeam
              key={`beam-${seller.id}`}
              containerRef={containerRef}
              fromRef={buyerRef}
              toRef={seller.ref}
              curvature={seller.curvature}
              gradientStartColor={colors.start}
              gradientStopColor={colors.stop}
              reverse={colors.reverse}
              duration={phase === 0 ? 0 : phase === 1 ? 4 : phase === 2 ? 5 : 2}
              pathColor={phase === 0 ? "rgba(255,255,255,0.05)" : "rgba(255,255,255,0.15)"}
              pathWidth={3}
              pathOpacity={phase === 0 ? 0.3 : 1}
              delay={seller.id * 0.1}
            />
          );
        })}
      </div>

      {/* Bottom 25% - Backend Console Logger */}
      <div className="h-40 w-full bg-black/60 border-t border-white/10 p-4 flex flex-col relative z-30 font-mono text-[11px] leading-relaxed">
        <div className="flex items-center gap-2 mb-2 pb-2 border-b border-white/10 text-zinc-500">
          <IconTerminal2 className="w-4 h-4" />
          <span>Backend Execution Logs (LangGraph Engine)</span>
        </div>
        <div className="flex-1 overflow-y-auto space-y-1 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
          {logs.map((log, index) => (
            <div 
              key={index} 
              className={cn(
                "animate-in slide-in-from-bottom-2 opacity-100",
                log.includes("SUPERVISOR_NODE") ? "text-emerald-400" :
                log.includes("WORKER_NODE") ? "text-yellow-400" :
                log.includes("LANGGRAPH") || log.includes("BROADCAST") ? "text-blue-400" : "text-zinc-400"
              )}
            >
              {log}
            </div>
          ))}
          <div ref={terminalEndRef} />
        </div>
      </div>
      
    </div>
  );
};
