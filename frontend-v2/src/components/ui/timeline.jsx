import React from "react";
import { motion } from "framer-motion";

export const Timeline = ({ data }) => {
  return (
    <div className="w-full bg-transparent font-sans">
      <div className="py-6 px-6 md:px-8">
        <h2 className="text-xl font-bold text-white tracking-tight mb-1">
          Live Negotiation Logs
        </h2>
        <p className="text-zinc-400 text-xs">
          Real-time trace of the Sales Bot AI haggle engine.
        </p>
      </div>

      <div className="px-6 md:px-8 pb-12">
        <div className="relative border-l-2 border-zinc-800/80 ml-3">
          {data.map((item, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.2 }}
              className="mb-8 ml-8 relative"
            >
              {/* Timeline Dot */}
              <div className="absolute -left-[41px] top-0 w-5 h-5 bg-black rounded-full border border-zinc-700 flex items-center justify-center shadow-[0_0_10px_rgba(168,85,247,0.2)]">
                <div className="w-1.5 h-1.5 bg-purple-500 rounded-full animate-pulse" />
              </div>
              
              {/* Timestamp Title */}
              <div className="font-mono text-[11px] font-semibold text-purple-400/80 mb-3 uppercase tracking-wider bg-purple-500/10 w-fit px-2 py-0.5 rounded border border-purple-500/20">
                {item.title}
              </div>
              
              {/* Content */}
              <div className="w-full">
                {item.content}
              </div>
            </motion.div>
          ))}
          
          {/* Fading line at the bottom */}
          <div className="absolute -bottom-10 left-[-2px] w-[2px] h-20 bg-gradient-to-b from-zinc-800/80 to-transparent" />
        </div>
      </div>
    </div>
  );
};
