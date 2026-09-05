import React, { useState, useEffect, useRef } from 'react';
import { Activity, ChevronUp, ChevronDown } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { useAgentLogs, logColors } from '../context/AgentActivityContext';

export const AgentDock = () => {
  const { entries } = useAgentLogs();
  const [expanded, setExpanded] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    if (expanded) bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [entries, expanded]);

  return (
    <motion.div 
      initial={false}
      animate={{ height: expanded ? 280 : 40 }}
      transition={{ type: 'spring', damping: 28, stiffness: 300 }}
      className="fixed bottom-0 md:left-64 left-0 right-0 z-40 glass-panel border-b-0 border-x-0 overflow-hidden rounded-t-2xl md:rounded-t-none md:border-l"
    >
      <button 
        onClick={() => setExpanded(!expanded)}
        className="absolute top-0 left-0 right-0 h-10 flex items-center px-5 gap-3 cursor-pointer hover:bg-white/5 transition-colors z-10"
      >
        <Activity size={14} className="text-emerald-400 animate-pulse" />
        <span className="text-[10px] font-mono text-slate-300 tracking-widest uppercase">System Activity Telemetry</span>
        <span className="text-[10px] font-mono text-slate-500 ml-1">[{entries.length}]</span>
        <div className="ml-auto flex items-center justify-center w-6 h-6 rounded-md bg-white/5 text-slate-400">
          {expanded ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
        </div>
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="h-full mt-10 overflow-y-auto px-5 py-3 font-mono text-[11px] leading-relaxed border-t border-white/[0.04] bg-obsidian-950/40"
          >
            {entries.map((e, i) => (
              <div key={e.ts + '-' + i} className={`mb-1.5 ${logColors[e.type] || logColors.default}`}>
                <span className="text-slate-600 mr-3 select-none">{(i + 1).toString().padStart(3, '0')}</span>
                {e.text}
              </div>
            ))}
            <div ref={bottomRef} className="h-4" />
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};
