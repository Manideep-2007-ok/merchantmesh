import React, { useState, useEffect, useRef } from 'react';
import { fetchPendingSalesOrders, confirmSalesOrder, fetchAuditLogs, getSessionId, fetchStats, sendSalesChat } from '@/lib/api';
import { playSound } from '@/lib/sounds';
import { motion } from 'framer-motion';
import { 
  IconChecks, 
  IconPhone, 
  IconVideo, 
  IconDotsVertical,
  IconPaperclip,
  IconMoodSmile,
  IconList,
  IconChevronRight,
  IconX,
  IconMicrophone,
  IconRobot,
  IconWifi,
  IconAntennaBars5,
  IconBatteryFilled,
  IconTriangle,
  IconCircle,
  IconSquare,
  IconUserSearch,
  IconCheck
} from '@tabler/icons-react';
import { 
  ChatContainer, 
  ChatHeader, 
  ChatMessageList, 
  ChatBubble,
} from './ui/chat';
import { Timeline } from './ui/timeline';
import { BorderBeam } from './ui/border-beam';

export function SalesBotEngineTab({ activeMerchantId, merchantsList, onMerchantChange }) {
  const [pendingOrders, setPendingOrders] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [loadedForMerchant, setLoadedForMerchant] = useState(null);
  const [messages, setMessages] = useState([]);

  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(`sales_chat_v5_${activeMerchantId}`);
      if (saved) {
        let loaded = JSON.parse(saved);
        const lang = sessionStorage.getItem('global_catalog_language_v2')?.toLowerCase() || '';
        let msg = `*Sales Bot Dashboard*\n\nWelcome! Select an option below to view earnings or pending orders.`;
        if (lang.includes('hindi')) msg = `*सेल्स बॉट डैशबोर्ड*\n\nनमस्ते! कमाई या लंबित ऑर्डर देखने के लिए नीचे दिए गए विकल्प का चयन करें।`;
        else if (lang.includes('hinglish')) msg = `*Sales Bot Dashboard*\n\nNamaste! Earnings ya pending orders dekhne ke liye niche diye gaye option ko select karein.`;
        
        if (loaded.length === 0) {
           loaded = [{ id: Date.now(), role: 'ai', text: msg, isMenu: true }];
        }
        setMessages(loaded);
      } else {
        const lang = sessionStorage.getItem('global_catalog_language_v2')?.toLowerCase() || '';
        let msg = `*Sales Bot Dashboard*\n\nWelcome! Select an option below to view earnings or pending orders.`;
        if (lang.includes('hindi')) msg = `*सेल्स बॉट डैशबोर्ड*\n\nनमस्ते! कमाई या लंबित ऑर्डर देखने के लिए नीचे दिए गए विकल्प का चयन करें।`;
        else if (lang.includes('hinglish')) msg = `*Sales Bot Dashboard*\n\nNamaste! Earnings ya pending orders dekhne ke liye niche diye gaye option ko select karein.`;
        setMessages([{ id: Date.now(), role: 'ai', text: msg, isMenu: true }]);
      }
    } catch {
      setMessages([]);
    }
    setLoadedForMerchant(activeMerchantId);
  }, [activeMerchantId]);

  useEffect(() => {
    if (loadedForMerchant === activeMerchantId) {
      sessionStorage.setItem(`sales_chat_v5_${activeMerchantId}`, JSON.stringify(messages));
    }
  }, [messages, loadedForMerchant, activeMerchantId]);

  




  const [inputValue, setInputValue] = useState('');
  const [showMenuSheet, setShowMenuSheet] = useState(false);
  
  const currentLang = sessionStorage.getItem('global_catalog_language_v2')?.toLowerCase() || 'english';
  const isHindi = currentLang.includes('hindi');
  const isHinglish = currentLang.includes('hinglish');

  const txtViewOptions = isHindi ? "विकल्प देखें" : (isHinglish ? "Options Dekhein" : "View Options");
  const txtMenuTitle = isHindi ? "सेल्स मेनू" : "Sales Menu";
  const txtEarnTitle = isHindi ? "कमाई देखें" : (isHinglish ? "Earnings Dekhein" : "Check Earnings");
  const txtEarnDesc = isHindi ? "आज, सप्ताह और महीने की बिक्री देखें" : (isHinglish ? "Aaj, week aur month ki sales dekhein" : "View sales (Today, Week, Month)");
  const txtOrdTitle = isHindi ? "लंबित ऑर्डर देखें" : (isHinglish ? "Pending Orders Dekhein" : "Check Pending Orders");
  const txtOrdDesc = isHindi ? "स्टॉक पुष्टि की प्रतीक्षा कर रहे ऑर्डर देखें" : (isHinglish ? "Stock confirmation ke liye pending orders" : "View orders awaiting stock confirmation");

  const handleSend = () => {
    if(!inputValue.trim()) return;
    const val = inputValue.trim().toLowerCase();
    const lang = sessionStorage.getItem('global_catalog_language_v2')?.toLowerCase() || '';
    playSound('sent');
    
    // Find last action BEFORE updating state
    const lastActionMsg = [...messages].reverse().find(m => m.isAction);
    
    setMessages(prev => {
      const updated = prev.map(m => m.id === lastActionMsg?.id ? { ...m, isAction: false } : m);
      return [...updated, { id: Date.now(), role: 'user', text: inputValue }];
    });
    
    if (lastActionMsg && (val === 'yes' || val === 'no' || val === 'y' || val === 'n')) {
       const actionCode = (val === 'yes' || val === 'y') ? 'Y' : 'N';
       setTimeout(() => handleAction(lastActionMsg.orderId, actionCode), 500);
    } else if (!lastActionMsg && (val === '1' || val.includes('earning') || val.includes('stats') || val.includes('money') || val.includes('kamaya'))) {
       setTimeout(async () => {
          try {
             const stats = await fetchStats(activeMerchantId);
             playSound('received');
             const total = stats.captured_earnings || 0;
             const today = stats.today_earnings || 0;
             const week = stats.week_earnings || 0;
             const isHindi = lang.includes('hindi');
             const isHinglish = lang.includes('hinglish');
             setMessages(m => [...m, { 
                id: Date.now()+1, 
                role: 'ai', 
                text: isHindi ? `*कमाई रिपोर्ट*\n\n*आज*: ₹${today.toLocaleString()}\n*इस सप्ताह*: ₹${week.toLocaleString()}\n*कुल कमाई*: ₹${total.toLocaleString()}\n\nसफल ऑर्डर्स: ${stats.settled_count || 0}` : (isHinglish ? `*Earnings Report*\n\n*Aaj*: ₹${today.toLocaleString()}\n*Is Week*: ₹${week.toLocaleString()}\n*Total (All-Time)*: ₹${total.toLocaleString()}\n\nTotal Orders Settled: ${stats.settled_count || 0}` : `*Earnings Report*\n\n*Today*: ₹${today.toLocaleString()}\n*This Week*: ₹${week.toLocaleString()}\n*Total (All-Time)*: ₹${total.toLocaleString()}\n\nTotal Orders Settled: ${stats.settled_count || 0}`),
                isMenu: true
             }]);
          } catch(e) {
             playSound('received');
             setMessages(m => [...m, { id: Date.now()+1, role: 'ai', text: "Failed to fetch stats." }]);
          }
       }, 1000);
    } else if (!lastActionMsg && (val === '2' || val.includes('stock') || val.includes('inventory'))) {
       setTimeout(() => {
          playSound('received');
          setMessages(m => [...m, { 
             id: Date.now()+1, 
             role: 'ai', 
             text: `*Inventory Updates*\n\nTo update your stock or prices effortlessly, please switch to the *Inventory Tab* at the top of your screen. \n\nIt provides a complete visual dashboard for managing your products!\n\n_Type 'menu' to see options again._` 
          }]);
       }, 1000);
    } else {
       setTimeout(() => {
          playSound('received');
          if (lastActionMsg) {
              setMessages(m => [...m, { id: Date.now()+1, role: 'ai', text: "I can only process 'yes' or 'no' for the pending order." }]);
          } else {
              setMessages(m => [...m, { 
                 id: Date.now()+1, 
                 role: 'ai', 
                 text: `*Sales Bot Menu*\n\nSelect an option below to manage your store.\n\n_(Note: Any pending orders will appear here automatically)_`,
                 isMenu: true
              }]);
          }
       }, 1000);
    }
    
    setInputValue('');
  };

  
  const handleCardClick = (card) => {
    playSound('sent');
    setMessages(prev => [...prev, { id: Date.now(), role: 'user', text: `Review order ${card.order_id.split('-')[0]}` }]);
    
    setTimeout(() => {
       playSound('received');
       setMessages(prev => [...prev, {
          id: card.order_id,
          role: 'ai',
          text: `*Order Review: ${card.order_id.split('-')[0]}*

Buyer wants: *${card.product_name}* (Qty: ${card.quantity})
Negotiated Price: *₹${card.amount}*

Do you have this in stock? (Reply Yes or No)`,
          isAction: true,
          orderId: card.order_id
       }]);
    }, 800);
  };

  const handleMenuSelection = (option) => {
    setShowMenuSheet(false);
    setInputValue(option);
    setTimeout(() => {
        // We need a synthetic event or we can just bypass and call handleSend logic
        const fakeInput = option.toLowerCase();
        playSound('sent');
        setMessages(prev => [...prev, { id: Date.now(), role: 'user', text: option }]);
        
        if (fakeInput.includes('earning') || fakeInput.includes('कमाई') || fakeInput.includes('earnings dekhein')) {
           setTimeout(async () => {
              try {
                 const stats = await fetchStats(activeMerchantId);
                 playSound('received');
                 const total = stats.captured_earnings || 0;
                 const today = stats.today_earnings || 0;
                 const week = stats.week_earnings || 0;
                 setMessages(m => [...m, { 
                    id: Date.now()+1, 
                    role: 'ai', 
                    text: isHindi ? `*कमाई रिपोर्ट*\n\n*आज*: ₹${today.toLocaleString()}\n*इस सप्ताह*: ₹${week.toLocaleString()}\n*कुल कमाई*: ₹${total.toLocaleString()}\n\nसफल ऑर्डर्स: ${stats.settled_count || 0}` : (isHinglish ? `*Earnings Report*\n\n*Aaj*: ₹${today.toLocaleString()}\n*Is Week*: ₹${week.toLocaleString()}\n*Total (All-Time)*: ₹${total.toLocaleString()}\n\nTotal Orders Settled: ${stats.settled_count || 0}` : `*Earnings Report*\n\n*Today*: ₹${today.toLocaleString()}\n*This Week*: ₹${week.toLocaleString()}\n*Total (All-Time)*: ₹${total.toLocaleString()}\n\nTotal Orders Settled: ${stats.settled_count || 0}`),
                    isMenu: true
                 }]);
              } catch(e) {
                 playSound('received');
                 setMessages(m => [...m, { id: Date.now()+1, role: 'ai', text: "Failed to fetch stats.", isMenu: true }]);
              }
           }, 1000);
        } else if (fakeInput.includes('order') || fakeInput.includes('लंबित') || fakeInput.includes('pending orders dekhein')) {
           setTimeout(() => {
              playSound('received');
              const pendingCount = pendingOrders.length;
              let reply = pendingCount === 0 
                ? `You currently have 0 pending orders! Great job keeping up.`
                : `You have ${pendingCount} pending order(s) waiting for your confirmation! Please tap on an order card below to review and process it.`;
              if (isHindi) {
                 reply = pendingCount === 0 ? `वर्तमान में आपके पास 0 लंबित ऑर्डर हैं! बहुत बढ़िया।` : `आपके पास ${pendingCount} लंबित ऑर्डर हैं! कृपया समीक्षा करने और प्रक्रिया करने के लिए नीचे दिए गए ऑर्डर कार्ड पर टैप करें।`;
              } else if (isHinglish) {
                 reply = pendingCount === 0 ? `Abhi aapke paas 0 pending orders hain! Great job.` : `Aapke paas ${pendingCount} pending orders hain! Please review karne ke liye neeche order card par tap karein.`;
              }
              setMessages(m => [...m, { 
                 id: Date.now()+1, 
                 role: 'ai', 
                 text: reply,
                 isMenu: pendingCount === 0,
                 orderCards: pendingCount > 0 ? pendingOrders : undefined
              }]);
           }, 1000);
        }
    }, 100);
  };

  const loadLogs = async () => {
    try {
      const logs = await fetchAuditLogs();
      setAuditLogs(logs);
    } catch(e) {}
  };
  
  const loadPending = async () => {
    try {
      const data = await fetchPendingSalesOrders(activeMerchantId);
      const pendingIds = new Set((data.pending_orders || []).map(o => o.order_id));
      
      setPendingOrders(data.pending_orders || []);
      
      setMessages(prev => {
         // Clear isAction from any old message whose order is no longer pending (e.g. from sessionStorage)
         const swept = prev.map(m => {
            if (m.isAction && !pendingIds.has(m.orderId)) {
               return { ...m, isAction: false };
            }
            return m;
         });
         
         const existingIds = new Set(swept.map(m => m.id));
         const newMsgs = (data.pending_orders || []).map(o => ({
            id: o.order_id,
            role: 'ai',
            text: `*New Order via MerchantMesh*\n\nBuyer wants: *${o.product_name}* (Qty: ${o.quantity})\nFinal Negotiated Price: *₹${o.amount}*\nCurrent Stock: ${o.stock_quantity}\n\nPlease confirm stock availability so we can send the payment link.`,
            isAction: true,
            orderId: o.order_id
         })).filter(m => !existingIds.has(m.id));
         
         return [...swept, ...newMsgs];
      });
    } catch(e) {}
  };

  useEffect(() => {
    const interval = setInterval(() => { loadPending(); loadLogs(); }, 3000);
    loadLogs();
    loadPending();
    return () => clearInterval(interval);
  }, [activeMerchantId]);

  const handleAction = async (orderId, action) => {
    try {
      await confirmSalesOrder({ order_id: orderId, confirmation: action, merchant_id: activeMerchantId });
      const lang = sessionStorage.getItem('global_catalog_language_v2')?.toLowerCase() || '';
      let msg = action === 'Y' ? ' Stock Confirmed — Payment link sent to buyer.' : '❌ Order Rejected — Stock released.';
      if (lang.includes('hindi')) msg = action === 'Y' ? ' स्टॉक की पुष्टि हो गई — खरीदार को भुगतान लिंक भेज दिया गया है।' : '❌ ऑर्डर अस्वीकृत — स्टॉक मुक्त कर दिया गया।';
      else if (lang.includes('hinglish')) msg = action === 'Y' ? ' Stock confirm ho gaya — buyer ko payment link bhej diya gaya hai.' : '❌ Order reject ho gaya — stock free kar diya gaya.';
      
      setMessages(prev => [...prev, {
         id: Date.now(),
         role: 'ai',
         text: msg,
         isMenu: true
      }]);
      loadPending();
      loadLogs();
    } catch (e) {
      setMessages(prev => [...prev, {
         id: Date.now(),
         role: 'ai',
         text: `⚠️ Action failed: ${e.message}`
      }]);
    }
  };

  // Dynamic Live Timestamps
  const now = new Date();
  const timeNow = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }).toLowerCase();
  const timeMinus1 = new Date(now.getTime() - 60000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }).toLowerCase();
  const timeMinus5 = new Date(now.getTime() - 300000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }).toLowerCase();
  const timeMinus10 = new Date(now.getTime() - 600000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }).toLowerCase();

  
  const timelineData = auditLogs.map(log => ({
    title: log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : 'Recent',
    content: (
        <div className="flex gap-4 items-start">
           <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center border border-purple-500/50 shrink-0 mt-1">
             <IconRobot className="w-4 h-4 text-purple-400" />
           </div>
           <div className="bg-white/5 border border-white/10 rounded-2xl p-4 w-full">
             <p className="text-xs text-zinc-500 font-mono mb-2 bg-black/40 p-2 rounded-lg border border-white/5">
               &gt; Action: {log.action}<br/>
               &gt; Agent: {log.agent}
             </p>
             <p className="text-sm text-zinc-300 font-mono mt-3">
               <span className="text-purple-400">System:</span> {log.reasoning}
             </p>
           </div>
        </div>
    )
  }));

  return (
    <motion.div 
      initial={{ opacity: 0, y: 30 }} 
      animate={{ opacity: 1, y: 0 }} 
      transition={{ duration: 0.8, delay: 0.4, ease: "easeOut" }} 
      className="w-full flex flex-col lg:flex-row gap-6 min-h-[600px] relative z-10"
    >
      
      {/* LEFT: Android WhatsApp Mobile Mockup (Approval Flow) */}
      <div className="flex-[3] flex flex-col items-center justify-center p-2 sm:p-4 relative z-20 min-w-0 gap-4">
        
        {/* Merchant Selector Moved Above Phone */}
        <div className="flex items-center gap-3 bg-zinc-900/80 border border-zinc-800 rounded-full px-5 py-2 shadow-xl backdrop-blur-md z-30 h-[42px] shrink-0">
            <span className="text-zinc-400 text-sm font-medium">Active Merchant:</span>
            <select 
                        value={activeMerchantId} 
                        onChange={(e) => onMerchantChange(e.target.value)}
                        className="bg-zinc-800 outline-none cursor-pointer text-[#e9edef] px-2 py-1 rounded-md text-sm border border-zinc-600 shadow-sm hover:bg-zinc-700 transition-colors"
                      >
                        {merchantsList && merchantsList.map(m => (
                          <option key={m.id} value={m.id} className="text-black bg-white">{m.name}</option>
                        ))}
                      </select>
        </div>
        
        {/* Mobile Device Frame */}
        <div className="w-full max-w-[360px] sm:h-[720px] h-[650px] bg-black flex-shrink rounded-[3rem] p-3 shadow-[0_20px_50px_-12px_rgba(0,0,0,0.8)] border border-zinc-800 relative flex flex-col shrink-0 overflow-hidden ring-1 ring-white/10">
          
          {/* Top Notch / Camera Area */}
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-32 h-6 bg-black rounded-b-2xl z-50 flex items-center justify-center">
             <div className="w-12 h-1.5 rounded-full bg-zinc-800"></div>
          </div>

          {/* Android App Screen */}
          <div className="flex-1 bg-[#0b141a] rounded-[2.25rem] overflow-hidden flex flex-col relative">
            
            {/* Android Status Bar */}
            <div className="h-6 bg-[#1f2c34] w-full px-5 flex items-center justify-between z-20 shrink-0">
               <span className="text-[11px] font-medium text-zinc-300">{timeMinus1.replace(" am", "").replace(" pm", "")}</span>
               <div className="flex items-center gap-1">
                  <IconWifi className="w-3.5 h-3.5 text-zinc-300" />
                  <IconAntennaBars5 className="w-4 h-4 text-zinc-300" />
                  <IconBatteryFilled className="w-4 h-4 text-zinc-300 ml-0.5" />
               </div>
            </div>

            <ChatContainer className="rounded-none h-full bg-transparent">
              <ChatHeader className="h-14 bg-[#1f2c34] px-2 shadow-none border-none">
                <div className="flex items-center gap-1">
                  <div className="p-1 cursor-pointer">
                    <svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" className="text-[#aebac1]"><line x1="19" y1="12" x2="5" y2="12"></line><polyline points="12 19 5 12 12 5"></polyline></svg>
                  </div>
                  <div className="w-9 h-9 rounded-full bg-emerald-600 flex items-center justify-center overflow-hidden mr-1">
                    <IconRobot className="w-5 h-5 text-white" />
                  </div>
                  <div className="flex flex-col">
                    <span className="text-[#e9edef] font-medium text-[16px] leading-5 tracking-wide">
                      MerchantMesh
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-4 text-[#aebac1] pr-2">
                  <IconVideo className="w-5 h-5 cursor-pointer" />
                  <IconPhone className="w-5 h-5 cursor-pointer" />
                  <IconDotsVertical className="w-5 h-5 cursor-pointer" />
                </div>
              </ChatHeader>

              <ChatMessageList className="p-3 gap-1 pb-4 rounded-none [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
              {messages.map(m => (
                <ChatBubble 
                  key={m.id} 
                  variant={m.role === 'user' ? 'sent' : 'received'}
                >
                  <div className="whitespace-pre-wrap break-words">{m.text}</div>
                  {m.orderCards && (
                    <div className="flex flex-col gap-2 mt-3 w-full">
                       {m.orderCards.map((c, i) => (
                          <div 
                             key={`${c.order_id}-${i}`} 
                             onClick={() => handleCardClick(c)}
                             className="bg-[#2a3942] hover:bg-[#32454f] cursor-pointer text-[#e9edef] flex flex-col p-3 rounded-lg border border-emerald-500/30 transition-colors shadow-sm w-full relative overflow-hidden"
                          >
                             <div className="absolute top-0 right-0 w-12 h-12 bg-emerald-500/10 rounded-bl-[100%] pointer-events-none" />
                             <div className="text-[15px] font-bold text-white line-clamp-1 mb-1 pr-4">{c.product_name}</div>
                             <div className="text-sm text-emerald-400 font-medium">₹{c.amount} <span className="text-zinc-400 font-normal text-xs">(Qty: {c.quantity})</span></div>
                             <div className="text-[11px] text-zinc-400 mt-2 font-mono">ID: {c.order_id.split('-')[0]}</div>
                             <div className="mt-3 text-[13px] text-emerald-500 font-semibold border-t border-emerald-500/20 pt-2 text-center w-full uppercase tracking-wider">
                                Review Order
                             </div>
                          </div>
                       ))}
                    </div>
                  )}
                  {m.isMenu && (
                     <div 
                       onClick={() => setShowMenuSheet(true)}
                       className="mt-2 bg-[#2a3942] hover:bg-[#32454f] cursor-pointer text-[#00a884] flex items-center justify-center gap-2 py-2 px-6 rounded-md border border-[#111b21] font-medium transition-colors text-sm shadow-sm"
                     >
                       <IconList className="w-4 h-4" /> {txtViewOptions}
                     </div>
                  )}
                </ChatBubble>
              ))}
            </ChatMessageList>

              {/* WhatsApp Interactive List Bottom Sheet */}
              {showMenuSheet && (
                <div className="absolute inset-0 bg-black/60 z-[60] flex items-end justify-center pb-[62px]">
                  <motion.div 
                    initial={{ y: "100%" }}
                    animate={{ y: 0 }}
                    exit={{ y: "100%" }}
                    transition={{ type: "spring", bounce: 0, duration: 0.3 }}
                    className="w-full max-w-sm bg-[#111b21] rounded-t-2xl shadow-2xl flex flex-col overflow-hidden border border-[#2a3942]"
                  >

                    <div className="flex items-center justify-between px-4 py-3 bg-[#202c33] border-b border-[#2a3942]">
                       <span className="text-[#e9edef] font-medium">{txtMenuTitle}</span>
                       <IconX className="w-6 h-6 text-[#8696a0] cursor-pointer hover:text-white" onClick={() => setShowMenuSheet(false)} />
                    </div>
                    <div className="flex flex-col py-2 max-h-[300px] overflow-y-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
                       <div 
                         onClick={() => handleMenuSelection(" " + txtEarnTitle)}
                         className="flex items-center justify-between px-5 py-4 cursor-pointer hover:bg-[#202c33] border-b border-[#2a3942]"
                       >
                         <div className="flex flex-col">
                            <span className="text-[#00a884] font-medium text-[16px]">{txtEarnTitle}</span>
                            <span className="text-[#8696a0] text-sm">{txtEarnDesc}</span>
                         </div>
                         <div className="w-5 h-5 rounded-full border-2 border-[#8696a0] flex items-center justify-center"></div>
                       </div>
                       
                       <div 
                         onClick={() => handleMenuSelection(" " + txtOrdTitle)}
                         className="flex items-center justify-between px-5 py-4 cursor-pointer hover:bg-[#202c33]"
                       >
                         <div className="flex flex-col">
                            <span className="text-[#00a884] font-medium text-[16px]">{txtOrdTitle}</span>
                            <span className="text-[#8696a0] text-sm">{txtOrdDesc}</span>
                         </div>
                         <div className="w-5 h-5 rounded-full border-2 border-[#8696a0] flex items-center justify-center"></div>
                       </div>
                    </div>
                  </motion.div>
                </div>
              )}
              
              {/* Standard WhatsApp Web Input */}
              <div className="h-[62px] bg-[#202c33] flex items-center gap-2 px-4 shrink-0 w-full">
                 <IconMoodSmile className="w-[26px] h-[26px] text-[#8696a0] cursor-pointer hover:text-[#d1d7db] transition-colors shrink-0" />
                 <IconPaperclip className="w-[26px] h-[26px] text-[#8696a0] cursor-pointer hover:text-[#d1d7db] transition-colors shrink-0 mx-1" />
                 <div className="flex-1 bg-[#2a3942] rounded-lg h-[42px] flex items-center px-3">
                   <input 
                     type="text" 
                     placeholder="Type a message" 
                     value={inputValue} 
                     onChange={(e) => setInputValue(e.target.value)} 
                     onKeyDown={(e) => { if(e.key === 'Enter') handleSend(); }} 
                     className="w-full bg-transparent text-[#d1d7db] placeholder:text-[#8696a0] text-[15px] outline-none" 
                   />
                 </div>
                 {inputValue.trim() ? (
                   <div onClick={handleSend} className="w-[40px] h-[40px] flex items-center justify-center cursor-pointer shrink-0 group">
                     <svg viewBox="0 0 24 24" height="24" width="24" preserveAspectRatio="xMidYMid meet" className="text-[#8696a0] group-hover:text-[#d1d7db] transition-colors fill-current" version="1.1" x="0px" y="0px" enableBackground="new 0 0 24 24">
                       <path d="M1.101,21.757L23.8,12.028L1.101,2.3l0.011,7.912l13.623,1.816L1.112,13.845 L1.101,21.757z"></path>
                     </svg>
                   </div>
                 ) : (
                   <div className="w-[40px] h-[40px] flex items-center justify-center cursor-pointer shrink-0 group">
                     <IconMicrophone className="w-[26px] h-[26px] text-[#8696a0] group-hover:text-[#d1d7db] transition-colors" />
                   </div>
                 )}
              </div>

            </ChatContainer>
            
            {/* Android Navigation Bar */}
            <div className="h-8 bg-black w-full flex items-center justify-center gap-14 shrink-0 pb-1">
               <IconTriangle className="w-3 h-3 text-zinc-500 fill-current rotate-90 cursor-pointer" />
               <IconCircle className="w-3 h-3 text-zinc-500 fill-current cursor-pointer" />
               <IconSquare className="w-3 h-3 text-zinc-500 fill-current cursor-pointer" />
            </div>
          </div>
        </div>
      </div>

      {/* RIGHT: AI Brain & Negotiation Timeline */}
      <div className="flex-[2] flex flex-col p-2 sm:p-4 gap-4 z-20 justify-center">
        {/* Alignment Spacer (Matches Merchant Selector) */}
        <div className="hidden lg:block h-[42px] shrink-0 pointer-events-none opacity-0" />
        
        
        {/* Terminal Wrapper with BorderBeam */}
        <div className="relative w-full sm:h-[720px] h-[650px] bg-black/40 backdrop-blur-xl border border-white/10 rounded-3xl overflow-hidden shadow-2xl flex flex-col shrink-0">
          <BorderBeam size={250} duration={12} delay={0} colorFrom="#a855f7" colorTo="#3b82f6" />
          
          <div className="flex items-center gap-2 p-4 border-b border-white/10 bg-black/60 shrink-0">
             <div className="flex gap-1.5 mr-4">
               <div className="w-3 h-3 rounded-full bg-red-500/80"></div>
               <div className="w-3 h-3 rounded-full bg-yellow-500/80"></div>
               <div className="w-3 h-3 rounded-full bg-green-500/80"></div>
             </div>
             <IconRobot className="w-4 h-4 text-purple-400" />
             <h3 className="font-mono text-white text-xs opacity-70">sales_bot_brain.exe</h3>
          </div>
          
          <div className="flex-1 overflow-y-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
             <Timeline data={timelineData} />
          </div>
        </div>
      </div>
      
    </motion.div>
  );
}

