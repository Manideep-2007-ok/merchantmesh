import React, { useState, useEffect, useRef } from 'react';
import { Send, CheckCheck, Paperclip, X, Mic, Play, MoreVertical, Phone, Video } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { Icon } from '@iconify/react';

export const WhatsAppUI = ({ messages, title, onSend, loading, subtitle, showImageUpload = false }) => {
  const [input, setInput] = useState('');
  const [selectedImage, setSelectedImage] = useState(null);
  const fileInputRef = useRef(null);
  const bottomRef = useRef(null);

  useEffect(() => { 
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); 
  }, [messages, loading]);

  const handleImageChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setSelectedImage(reader.result);
    reader.readAsDataURL(file);
  };

  const handleSend = () => { 
    if ((input.trim() || selectedImage) && !loading) { 
      playSound('sent');
      onSend(input.trim(), selectedImage); 
      setInput(''); 
      setSelectedImage(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    } 
  };

  return (
    <div className="relative w-full max-w-[360px] h-[640px] bg-obsidian-950 rounded-[40px] border-[8px] border-obsidian-800 shadow-2xl overflow-hidden flex flex-col shrink-0 ring-1 ring-white/10">
      {/* iOS Notch */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-32 h-6 bg-obsidian-800 rounded-b-3xl z-50 flex items-center justify-end px-3">
        <div className="w-1.5 h-1.5 rounded-full bg-emerald-500/20 mr-1" />
      </div>

      {/* Header */}
      <div className="bg-[#0B141A] text-white pt-10 pb-3 px-4 flex items-center gap-3 z-10 shadow-sm border-b border-white/5">
        <div className="w-9 h-9 rounded-full bg-slate-700 overflow-hidden flex items-center justify-center shrink-0">
          <Icon icon="mdi:store" className="text-white/70" width="20" />
        </div>
        <div className="flex flex-col flex-1 min-w-0">
          <span className="font-semibold text-sm leading-tight truncate">{title}</span>
          <span className="text-[11px] text-white/60 truncate">{subtitle || 'online'}</span>
        </div>
        <div className="flex items-center gap-4 text-white/70 shrink-0">
          <Video size={18} />
          <Phone size={18} />
          <MoreVertical size={18} />
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 bg-[#0B141A] p-3 overflow-y-auto flex flex-col gap-2 relative" 
           style={{ backgroundImage: 'radial-gradient(rgba(255,255,255,0.03) 1px, transparent 1px)', backgroundSize: '16px 16px' }}>
        <AnimatePresence initial={false}>
          {messages.map((m, i) => (
            <motion.div 
              initial={{ opacity: 0, y: 10, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ type: 'spring', damping: 25, stiffness: 300 }}
              key={i} 
              className={`flex w-full ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div className={`max-w-[85%] p-2 px-3 text-[13px] shadow-sm relative ${
                m.role === 'user' 
                  ? 'bg-[#005C4B] text-[#E9EDEF] rounded-2xl rounded-tr-sm' 
                  : 'bg-[#202C33] text-[#E9EDEF] rounded-2xl rounded-tl-sm'
              }`}>
                {m.role === 'assistant' && <div className="text-[10px] font-bold text-emerald-400 mb-1">{title}</div>}
                {m.image && (
                  <div className="mb-2 rounded-lg overflow-hidden border border-white/10">
                    <img src={m.image} alt="Upload" className="w-full h-32 object-cover" />
                  </div>
                )}
                <div className="whitespace-pre-wrap leading-relaxed break-words">{m.content}</div>
                <div className="text-[9px] text-right mt-1 text-white/50 flex justify-end items-center gap-1">
                  {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  {m.role === 'user' && <CheckCheck size={12} className="text-[#53BDEB]" />}
                </div>
              </div>
            </motion.div>
          ))}
          {loading && (
            <motion.div 
              initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, scale: 0.9 }}
              className="flex justify-start"
            >
              <div className="bg-[#202C33] p-3 px-4 rounded-2xl rounded-tl-sm shadow-sm">
                <div className="flex gap-1.5">
                  <motion.span animate={{ y: [0, -4, 0] }} transition={{ repeat: Infinity, duration: 0.6, delay: 0 }} className="w-1.5 h-1.5 bg-emerald-400/60 rounded-full" />
                  <motion.span animate={{ y: [0, -4, 0] }} transition={{ repeat: Infinity, duration: 0.6, delay: 0.2 }} className="w-1.5 h-1.5 bg-emerald-400/60 rounded-full" />
                  <motion.span animate={{ y: [0, -4, 0] }} transition={{ repeat: Infinity, duration: 0.6, delay: 0.4 }} className="w-1.5 h-1.5 bg-emerald-400/60 rounded-full" />
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        <div ref={bottomRef} className="h-2" />
      </div>

      {/* Image Preview Tray */}
      <AnimatePresence>
        {selectedImage && (
          <motion.div initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }} className="bg-[#202C33] px-3 py-2 flex items-center justify-between border-t border-white/5 overflow-hidden">
            <div className="flex items-center gap-2">
              <img src={selectedImage} alt="Attachment" className="w-10 h-10 rounded object-cover border border-white/10" />
              <span className="text-xs text-white/80 font-medium">Photo Attached</span>
            </div>
            <button onClick={() => { setSelectedImage(null); if (fileInputRef.current) fileInputRef.current.value = ''; }} className="text-white/50 hover:text-rose-400 p-1">
              <X size={16} />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Input Area */}
      <div className="bg-[#0B141A] p-2 flex items-center gap-2 z-10 pb-6">
        {showImageUpload && (
          <>
            <input type="file" accept="image/*" ref={fileInputRef} onChange={handleImageChange} className="hidden" />
            <button onClick={() => fileInputRef.current?.click()} disabled={loading} className="w-10 h-10 rounded-full text-white/60 hover:bg-[#2a3942]/5 flex items-center justify-center shrink-0 transition-colors disabled:opacity-50">
              <Paperclip size={20} />
            </button>
          </>
        )}
        <div className="flex-1 bg-[#2A3942] rounded-full flex items-center px-4 py-2 min-h-[40px]">
          <input 
            type="text" 
            value={input} 
            onChange={(e) => setInput(e.target.value)} 
            onKeyDown={(e) => { if (e.key === 'Enter') handleSend(); }}
            placeholder={selectedImage ? "Add caption..." : "Message"} 
            disabled={loading}
            className="flex-1 bg-transparent border-none outline-none text-sm text-[#E9EDEF] placeholder-white/40 disabled:opacity-50" 
          />
        </div>
        {(input.trim() || selectedImage) ? (
          <motion.button 
            initial={{ scale: 0.5, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
            whileTap={{ scale: 0.9 }}
            onClick={handleSend} disabled={loading}
            className="w-10 h-10 rounded-full bg-[#00A884] text-white flex items-center justify-center shrink-0 disabled:opacity-50"
          >
            <Send size={18} className="ml-1" />
          </motion.button>
        ) : (
          <button disabled className="w-10 h-10 rounded-full text-white/60 flex items-center justify-center shrink-0">
            <Mic size={20} />
          </button>
        )}
      </div>
    </div>
  );
};
