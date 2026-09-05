import React, { createContext, useContext, useState } from 'react';

const AgentActivityContext = createContext();

export const getLogType = (log) => {
  if (!log) return 'default';
  if (log.includes('[ERROR]') || log.includes('VIOLATION') || log.includes('')) return 'error';
  if (log.includes('[LangGraph]') || log.includes('[Agent]')) return 'agent';
  if (log.includes('[Groq]') || log.includes('[TrustAgent]')) return 'trust';
  if (log.includes('[SQLite]')) return 'db';
  if (log.includes('[Razorpay]')) return 'razorpay';
  if (log.includes('[HITL]')) return 'hitl';
  if (log.includes('[Turn')) return 'negotiation';
  if (log.includes('') || log.includes('SUCCESS') || log.includes('')) return 'success';
  if (log.includes('⚠️') || log.includes('FALLBACK')) return 'warning';
  return 'default';
};

export const logColors = {
  error: 'text-rose-400',
  agent: 'text-fuchsia-400',
  trust: 'text-sky-400',
  db: 'text-amber-300',
  razorpay: 'text-emerald-400',
  hitl: 'text-orange-400',
  negotiation: 'text-cyan-300',
  success: 'text-emerald-400',
  warning: 'text-yellow-400',
  default: 'text-emerald-400/80',
  system: 'text-slate-500',
};

export const AgentActivityProvider = ({ children }) => {
  const [entries, setEntries] = useState([
    { ts: Date.now(), text: '> MerchantMesh Activity Monitor active. Live agent events will stream here.', type: 'system' },
  ]);

  const pushLogs = (logs) => {
    if (!Array.isArray(logs)) return;
    const newEntries = logs.map((l, i) => ({ ts: Date.now() + i, text: l, type: getLogType(l) }));
    setEntries(prev => [...prev, ...newEntries]);
  };

  return (
    <AgentActivityContext.Provider value={{ entries, pushLogs }}>
      {children}
    </AgentActivityContext.Provider>
  );
};

export const useAgentLogs = () => useContext(AgentActivityContext);
