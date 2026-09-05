import React, { useState, useEffect } from 'react';
import { LayoutDashboard, MessageSquare, ShoppingCart, Search, Sparkles, RotateCcw, Loader2, Menu, X, Share2, Check, Volume2, VolumeX } from 'lucide-react';
import { getSessionId, resetDemoDatabase } from '../lib/api';
import { isSoundEnabled, toggleSound } from '../lib/sound';

export const Sidebar = ({ activeTab, setActiveTab }) => {
  const [resetting, setResetting] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [soundOn, setSoundOn] = useState(true);
  const sessionId = getSessionId();

  useEffect(() => {
    setSoundOn(isSoundEnabled());
  }, []);

  const handleReset = async () => {
    if (window.confirm("Reset Demo Sandbox to clean baseline? (Wipes test transactions and restores pristine 18 products)")) {
      setResetting(true);
      try {
        await resetDemoDatabase();
        window.location.reload();
      } catch (e) {
        alert("Reset failed: " + e.message);
      }
      setResetting(false);
    }
  };

  const handleShareSession = () => {
    if (typeof window !== 'undefined') {
      const shareUrl = `${window.location.origin}${window.location.pathname}?session=${sessionId.replace('sess_', '')}`;
      navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    }
  };

  const handleToggleSound = () => {
    const newState = toggleSound();
    setSoundOn(newState);
  };

  const navItems = [
    { id: 'overview', label: 'Command Center', icon: LayoutDashboard },
    { id: 'buyer-agent', label: 'Buyer Agent', icon: Search },
    { id: 'catalog-bot', label: 'Catalog Bot', icon: MessageSquare },
    { id: 'sales-engine', label: 'Sales Bot', icon: ShoppingCart },
  ];

  return (
    <>
      <div className="md:hidden fixed top-0 left-0 right-0 h-14 bg-obsidian-850/80 backdrop-blur-xl border-b border-white/10 z-40 flex items-center justify-between px-4 shadow-glass-edge">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-razorpay-blue flex items-center justify-center shadow-inner">
            <Sparkles size={14} className="text-white" />
          </div>
          <span className="font-display font-bold text-slate-100 text-sm tracking-tight">MerchantMesh</span>
        </div>
        <button onClick={() => setMobileOpen(!mobileOpen)} className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors">
          {mobileOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {mobileOpen && (
        <div className="md:hidden fixed inset-0 bg-obsidian-950/60 backdrop-blur-sm z-45" onClick={() => setMobileOpen(false)} />
      )}

      <div className={`w-64 glass-panel border-r-0 border-y-0 h-screen fixed top-0 left-0 z-50 flex flex-col transition-transform duration-300 ease-out md:translate-x-0 ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="p-6 pb-6 hidden md:block border-b border-white/[0.04]">
          <h1 className="text-xl font-display font-bold flex items-center gap-2.5 text-slate-100 tracking-tight text-glow">
            <div className="w-8 h-8 rounded-lg bg-razorpay-blue flex items-center justify-center shadow-[inset_0_1px_0_0_rgba(255,255,255,0.4)]">
              <Sparkles size={15} className="text-white" />
            </div>
            MerchantMesh
          </h1>
          <p className="text-[10px] text-slate-500 font-mono mt-2 tracking-widest uppercase">A2A Commerce Protocol</p>
        </div>

        <div className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button 
                key={item.id} 
                onClick={() => { setActiveTab(item.id); setMobileOpen(false); }}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl font-medium text-sm transition-all duration-200 ${isActive ? 'bg-razorpay-blue/10 text-razorpay-light border border-razorpay-blue/20 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.05)]' : 'text-slate-400 hover:bg-white/5 hover:text-slate-200 border border-transparent'}`}
              >
                <Icon size={18} className={isActive ? 'text-razorpay-light' : 'text-slate-500'} />
                {item.label}
              </button>
            );
          })}
        </div>

        <div className="p-4 border-t border-white/[0.04] mx-3 mb-2 space-y-3">
          <div className="flex items-center justify-between mb-2 px-1">
            <div>
              <div className="text-[9px] font-bold text-slate-500 uppercase tracking-widest mb-0.5 font-mono">Isolated Demo Sandbox</div>
              <div className="text-[10px] text-emerald-400 font-medium flex items-center gap-1.5 font-mono">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)] animate-pulse" />
                Active Session
              </div>
            </div>
            <button onClick={handleToggleSound} className={`p-2 rounded-lg transition-colors ${soundOn ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-white/5 text-slate-500 border border-white/10'}`} title="Toggle Audio Feedback">
              {soundOn ? <Volume2 size={14} /> : <VolumeX size={14} />}
            </button>
          </div>

          <button
            onClick={handleShareSession}
            className="w-full bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300 text-[11px] font-semibold py-2 px-3 rounded-xl flex items-center justify-center gap-2 transition-colors shadow-glass-edge-subtle"
          >
            {copied ? <Check size={13} className="text-emerald-400" /> : <Share2 size={13} />}
            {copied ? "Link Copied!" : "Sync Multi-Device Demo"}
          </button>

          <button 
            onClick={handleReset} 
            disabled={resetting}
            className="w-full bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 text-rose-400 text-[11px] font-semibold py-2 px-3 rounded-xl flex items-center justify-center gap-2 transition-colors disabled:opacity-50 shadow-glass-edge-subtle"
          >
            {resetting ? <Loader2 size={12} className="animate-spin" /> : <RotateCcw size={12} />}
            {resetting ? "Resetting..." : "Wipe & Seed Sandbox"}
          </button>
        </div>
      </div>
    </>
  );
};
