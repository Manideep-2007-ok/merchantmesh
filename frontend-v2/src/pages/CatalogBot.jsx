import React, { useState } from 'react';
import { PackageSearch, ArrowRight, ShieldCheck, Camera, Sparkles } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { parseCatalogMessage } from '../lib/api';
import { useAgentLogs } from '../context/AgentActivityContext';
import { WhatsAppUI } from '../components/WhatsAppUI';

export const CatalogBot = () => {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [parsedEntity, setParsedEntity] = useState(null);
  const { addLog } = useAgentLogs();

  const handleSend = async (text, imageBase64) => {
    if ((!text && !imageBase64) || loading) return;
    
    setMessages(prev => [...prev, { role: 'user', content: text, image: imageBase64 }]);
    setLoading(true);
    setParsedEntity(null);
    addLog('BUYER', `Sent catalog listing: "${text}" ${imageBase64 ? '[+Image]' : ''}`);

    try {
      addLog('SYSTEM', 'Processing multimodal catalog extraction...');
      const res = await parseCatalogMessage(text, 'm1', imageBase64);
      
      setMessages(prev => [...prev, { role: 'assistant', content: res.reply }]);
      
      if (res.action === 'ADD_PRODUCT' && res.product) {
        setParsedEntity(res.product);
        addLog('SYSTEM', `Extracted SKU: ${res.product.name} (Floor: ₹${res.product.floor_price}, Ask: ₹${res.product.price})`);
      }
    } catch (err) {
      addLog('ERROR', `Catalog parse failed: ${err.message}`);
      setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${err.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-6xl mx-auto flex flex-col lg:flex-row gap-6 h-[calc(100vh-8rem)]">
      {/* WhatsApp Viewport for Merchant */}
      <div className="shrink-0 flex justify-center items-center">
        <WhatsAppUI 
          title="Mesh Catalog Assistant" 
          subtitle="Snap a photo to list"
          messages={messages}
          loading={loading}
          onSend={handleSend}
          showImageUpload={true}
        />
      </div>

      {/* Stagecraft: Extraction Visualizer */}
      <div className="flex-1 flex flex-col justify-center max-w-md mx-auto">
        {chatHistoryEmpty(messages) && !loading && !parsedEntity && (
           <div className="text-center opacity-60">
              <Camera size={48} className="mx-auto mb-4 text-emerald-500/50" />
              <p className="text-sm text-slate-300">"Got 5 units of iPhone 14 Pro Max 256GB. Need at least 95k each, try to sell for 105k."</p>
           </div>
        )}

        <AnimatePresence mode="wait">
          {loading && (
            <motion.div 
              key="loading"
              initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.9 }}
              className="glass-panel p-6 rounded-3xl text-center border border-emerald-500/30"
            >
              <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-emerald-500/10 flex items-center justify-center">
                <Sparkles className="text-emerald-400 animate-spin" />
              </div>
              <h3 className="font-display font-bold text-white mb-2">Multimodal Extraction</h3>
              <p className="text-xs text-slate-400 font-mono">Running Gemini Flash to structure inventory...</p>
            </motion.div>
          )}

          {parsedEntity && !loading && (
            <motion.div 
              key="result"
              initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
              className="glass-panel p-6 rounded-3xl border border-white/10 shadow-glass-edge"
            >
              <div className="flex items-center justify-between mb-6 pb-4 border-b border-white/[0.04]">
                <h3 className="font-bold text-white flex items-center gap-2"><PackageSearch className="text-blue-400" /> Extracted SKU</h3>
                <span className="text-[10px] font-mono bg-emerald-500/20 text-emerald-400 px-2 py-1 rounded-md border border-emerald-500/30">Indexed to Mesh</span>
              </div>
              
              <div className="space-y-4">
                <div className="bg-obsidian-950/50 p-3 rounded-xl border border-white/5">
                  <div className="text-[10px] uppercase font-mono text-slate-500 mb-1">Standardized Name</div>
                  <div className="font-bold text-white text-sm">{parsedEntity.name}</div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-obsidian-950/50 p-3 rounded-xl border border-white/5">
                    <div className="text-[10px] uppercase font-mono text-slate-500 mb-1">Listed Ask</div>
                    <div className="font-bold text-blue-400 font-mono">₹{parsedEntity.price.toLocaleString()}</div>
                  </div>
                  <div className="bg-rose-500/10 p-3 rounded-xl border border-rose-500/20">
                    <div className="text-[10px] uppercase font-mono text-rose-400 mb-1 flex items-center gap-1">
                      <ShieldCheck size={12} /> Guardrail Floor
                    </div>
                    <div className="font-bold text-rose-300 font-mono">₹{parsedEntity.floor_price.toLocaleString()}</div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-obsidian-950/50 p-3 rounded-xl border border-white/5">
                    <div className="text-[10px] uppercase font-mono text-slate-500 mb-1">Category</div>
                    <div className="text-slate-300 text-xs">{parsedEntity.category}</div>
                  </div>
                  <div className="bg-obsidian-950/50 p-3 rounded-xl border border-white/5">
                    <div className="text-[10px] uppercase font-mono text-slate-500 mb-1">Initial Stock</div>
                    <div className="text-slate-300 text-xs">{parsedEntity.stock} Units</div>
                  </div>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};

const chatHistoryEmpty = (arr) => !arr || arr.length === 0;

