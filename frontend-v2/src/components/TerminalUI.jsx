import React, { useEffect, useRef } from 'react';
import { getLogType, logColors } from '../context/AgentActivityContext';
import { motion, AnimatePresence } from 'motion/react';

export const TerminalUI = ({ logs, title }) => {
  const bottomRef = useRef(null);
  
  useEffect(() => { 
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); 
  }, [logs]);

  return (
    <div className="w-full h-[580px] bg-obsidian-950/80 backdrop-blur-md rounded-2xl overflow-hidden flex flex-col shadow-glass-edge border border-white/[0.08]">
      <div className="bg-obsidian-800/50 px-4 py-3 flex items-center gap-2 border-b border-white/[0.04]">
        <div className="flex gap-1.5 shrink-0">
          <div className="w-3 h-3 rounded-full bg-rose-500/80 shadow-[inset_0_1px_1px_rgba(255,255,255,0.4)]" />
          <div className="w-3 h-3 rounded-full bg-amber-500/80 shadow-[inset_0_1px_1px_rgba(255,255,255,0.4)]" />
          <div className="w-3 h-3 rounded-full bg-emerald-500/80 shadow-[inset_0_1px_1px_rgba(255,255,255,0.4)]" />
        </div>
        <div className="flex-1 text-center text-[11px] font-mono text-slate-400 font-medium tracking-widest">{title}</div>
      </div>
      <div className="flex-1 p-5 overflow-y-auto font-mono text-[11px] leading-relaxed hide-scrollbar">
        <AnimatePresence initial={false}>
          {logs.map((log, i) => {
            const type = getLogType(log);
            return (
              <motion.div 
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                key={i} 
                className={`mb-1.5 whitespace-pre-wrap ${logColors[type] || logColors.default}`}
              >
                <span className="text-slate-700 mr-3 select-none">{(i + 1).toString().padStart(3, '0')}</span>
                {log}
              </motion.div>
            );
          })}
        </AnimatePresence>
        <div ref={bottomRef} className="h-4" />
      </div>
    </div>
  );
};
