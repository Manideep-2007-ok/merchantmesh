import React, { useState, useEffect, useRef } from 'react';
import { parseCatalogMessage, getProducts , getSessionId } from '@/lib/api';
import { motion } from 'framer-motion';
import { 
  IconCheck, 
  IconChecks, 
  IconPhone, 
  IconList,
  IconX,
  IconVideo, 
  IconSearch, 
  IconDotsVertical,
  IconPaperclip,
  IconMoodSmile,
  IconMicrophone,
  IconDatabase,
  IconFileInvoice,
  IconMessage,
  IconHeartHandshake,
  IconRobot,
  IconTable,
  IconTerminal2,
  IconWifi,
  IconAntennaBars5,
  IconBatteryFilled,
  IconTriangle,
  IconCircle,
  IconSquare
} from '@tabler/icons-react';
import { AnimatedList } from './ui/animated-list';
import { playSound } from '@/lib/sounds';
import { 
  ChatContainer, 
  ChatHeader, 
  ChatMessageList, 
  ChatBubble, 
  ChatInputContainer 
} from './ui/chat';

const Notification = ({ icon, title, description, color, time }) => (
  <figure className="relative mx-auto min-h-fit w-full cursor-pointer overflow-hidden rounded-xl p-3 transition-all duration-200 ease-in-out hover:scale-[102%] bg-black/40 border border-white/10 backdrop-blur-md shadow-lg mb-2">
    <div className="flex flex-row items-center gap-3">
      <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl ${color}`}>
        {icon}
      </div>
      <div className="flex flex-col overflow-hidden">
        <figcaption className="flex flex-row items-center text-sm font-medium text-white">
          <span className="text-[13px]">{title}</span>
          <span className="mx-1 text-zinc-600">·</span>
          <span className="text-[10px] text-zinc-500">{time}</span>
        </figcaption>
        <p className="text-[11px] font-normal text-zinc-400 leading-snug truncate">{description}</p>
      </div>
    </div>
  </figure>
);

export function CatalogBotTab({ activeMerchantId, merchantsList, onMerchantChange, onUpdateMerchantName }) {
  const [messages, setMessages] = useState([]);
  const [showMenuSheet, setShowMenuSheet] = useState(false);
  const [showInventorySheet, setShowInventorySheet] = useState(false);
  const [inventorySearch, setInventorySearch] = useState('');
  const [stockEdits, setStockEdits] = useState({});
  const [pendingStockUpdate, setPendingStockUpdate] = useState(null);

  const [inputValue, setInputValue] = useState('');
  const [selectedImage, setSelectedImage] = useState(null);
  const [logs, setLogs] = useState([{ id: "init", title: "System Initialized", description: "Waiting for incoming webhook events...", color: "bg-emerald-500/20 text-emerald-400" }]);
  const [products, setProducts] = useState([]);
  const [isUploading, setIsUploading] = useState(false);

  // Onboarding State
  const [onboardingStep, setOnboardingStep] = useState(0); 
  const [merchantName, setMerchantName] = useState(null);
  const [merchantLocation, setMerchantLocation] = useState(null);
  const [loadedForMerchant, setLoadedForMerchant] = useState(null);
  const [language, setLanguage] = useState(() => sessionStorage.getItem('global_catalog_language_v2') || null);

  useEffect(() => {
    // 1. Load correct history for the newly selected merchant
    let loadedMessages = [];
    try {
      const saved = sessionStorage.getItem(`catalog_chat_v12_${activeMerchantId}`);
      if (saved) loadedMessages = JSON.parse(saved);
    } catch {}

    const hasHistory = loadedMessages.length > 0;
    
    // 2. Determine Onboarding State
    const globalLang = sessionStorage.getItem('global_catalog_language_v2');
    
    // If they HAVE history, we should trust the history and make sure onboarding is 0 (or at least not ask them again).
    // Specifically, if onboarding step was already 0 and they have history, don't reset it to 100 just because of language.
    // Wait, the logic for 'm_custom' is separate from standard merchants.
    
    if (activeMerchantId?.startsWith('m_custom')) {
      if (globalLang) {
        // Only set onboarding to 2 if they don't already have a name!
        if (hasHistory) {
            // Assume if they have history on a custom merchant, they've finished onboarding.
            setOnboardingStep(0);
        } else {
            setOnboardingStep(2); // Ask for store name
            loadedMessages = [{ id: Date.now(), role: 'ai', text: `Welcome to MerchantMesh! Language is set to ${globalLang}. What is your store's name?` }];
        }
      } else {
        if (hasHistory) {
             setOnboardingStep(0);
        } else {
            setOnboardingStep(2);
            loadedMessages = [{ id: Date.now(), role: 'ai', text: "Welcome to MerchantMesh! What is your store's name?" }];
        }
      }
    } else {
      // STANDARD MERCHANTS (m1, m4, etc.)
      if (!globalLang) {
        setOnboardingStep(100); // Ask language
          if (loadedMessages.length === 0) {
            const globalLang = sessionStorage.getItem('global_catalog_language_v2')?.toLowerCase() || '';
            let defaultMsg = "Welcome to your Catalog Bot! Please upload a photo of your product to add it to your inventory.";
            if (globalLang.includes('hindi')) defaultMsg = "कैटलॉग बॉट में आपका स्वागत है! कृपया अपनी इन्वेंट्री में जोड़ने के लिए अपने उत्पाद की एक तस्वीर अपलोड करें।";
            else if (globalLang.includes('hinglish')) defaultMsg = "Catalog Bot mein aapka swagat hai! Apni inventory mein add karne ke liye product ki photo upload karein.";
            loadedMessages = [{ id: Date.now(), role: 'ai', text: defaultMsg }];
          }
      } else {
        setOnboardingStep(0); // Fully onboarded
        setMerchantName(null);
        setMerchantLocation(null);
        
        const currentM = merchantsList.find(m => m.id === activeMerchantId);
        const mName = currentM ? currentM.name : "";
        const lang = globalLang.toLowerCase();
        let msg = mName 
           ? `Welcome back, ${mName}! To add a new product or to update the stock please check the menu options.` 
           : `Welcome back! To add a new product or to update the stock please check the menu options.`;
        if (lang.includes('hindi')) msg = mName 
           ? `वापसी पर स्वागत है, ${mName}! नया उत्पाद जोड़ने या स्टॉक अपडेट करने के लिए कृपया मेनू विकल्प देखें।` 
           : `वापसी पर स्वागत है! नया उत्पाद जोड़ने या स्टॉक अपडेट करने के लिए कृपया मेनू विकल्प देखें।`;
        else if (lang.includes('hinglish')) msg = mName 
           ? `Welcome back, ${mName}! Naya product add karne ya stock update karne ke liye please menu options check karein.` 
           : `Welcome back! Naya product add karne ya stock update karne ke liye please menu options check karein.`;
        
        if (!hasHistory) {
          loadedMessages = [{ id: Date.now(), role: 'ai', text: msg, isMenu: true }];
        }

      }
    }
    
    // Apply final merged state
    setMessages(loadedMessages);
    setLoadedForMerchant(activeMerchantId);
  }, [activeMerchantId]);

  const handleMenuSelection = (option) => {
    setShowMenuSheet(false);
    playSound('sent');
    setMessages(prev => [...prev, { id: Date.now(), role: 'user', text: option }]);
    
    if (option.toLowerCase().includes('check inventory') || option.includes('स्टॉक देखें') || option.toLowerCase().includes('stock check karein')) {
       setShowInventorySheet(true);
       return;
    }

    if (option.toLowerCase().includes('add new product') || option.includes('नया उत्पाद जोड़ें') || option.toLowerCase().includes('naya product add karein')) {
       setTimeout(() => {
         playSound('received');
         const lang = sessionStorage.getItem('global_catalog_language_v2')?.toLowerCase() || '';
         let msg = `Got it! Please upload a photo of the product first (this is mandatory). Also include the product name, selling price, your lowest acceptable price (last price), stock quantity, and available sizes (if applicable).`;
         if (lang.includes('hindi')) msg = `ठीक है! कृपया सबसे पहले उत्पाद की एक फोटो अपलोड करें (यह अनिवार्य है)। इसके साथ उत्पाद का नाम, बिक्री मूल्य, आपका अंतिम मूल्य, स्टॉक मात्रा और उपलब्ध आकार (यदि लागू हो) भी शामिल करें।`;
         else if (lang.includes('hinglish')) msg = `Samajh gaya! Sabse pehle product ki ek photo bhejein (yeh zaroori hai). Saath mein product ka naam, selling price, last price, stock quantity, aur sizes (agar applicable ho) bhi batayein.`;
         setMessages(prev => [...prev, { id: Date.now()+1, role: 'ai', text: msg }]);
       }, 500);
       return;
    }
  };

  // Safely save messages only if they belong to the active merchant
  useEffect(() => {
    if (loadedForMerchant === activeMerchantId) {
      sessionStorage.setItem(`catalog_chat_v12_${activeMerchantId}`, JSON.stringify(messages));
    }
    
    // Inactivity Timeout: If the last message is AI asking for clarification (no menu), start a timer
    if (messages.length > 0) {
      const lastMsg = messages[messages.length - 1];
      if (lastMsg.role === 'ai' && !lastMsg.isMenu) {
        const timer = setTimeout(() => {
          setMessages(prev => {
            // Only append if the user hasn't sent a new message in the meantime
            if (prev.length === messages.length) {
               playSound('received');
               const lang = sessionStorage.getItem('global_catalog_language_v2')?.toLowerCase() || '';
               let timeoutMsg = "Product draft discarded due to inactivity. Please select an option to continue.";
               if (lang.includes('hindi')) timeoutMsg = "निष्क्रियता के कारण उत्पाद ड्राफ्ट रद्द कर दिया गया है। कृपया जारी रखने के लिए एक विकल्प चुनें।";
               else if (lang.includes('hinglish')) timeoutMsg = "Inactivity ki wajah se product draft discard kar diya gaya hai. Continue karne ke liye option select karein.";
               return [...prev, { id: Date.now(), role: 'ai', text: timeoutMsg, isMenu: true }];
            }
            return prev;
          });
        }, 120000); // 2 minutes for demo purposes (can be 5-10 mins in prod)
        return () => clearTimeout(timer);
      }
    }
  }, [messages, loadedForMerchant, activeMerchantId]);

  const handleSend = async () => {
    if(!inputValue.trim() && !selectedImage) return;
    playSound('sent');
    const userText = inputValue.trim() || (selectedImage ? 'Uploaded product image' : '');
    const imgToSend = selectedImage;
    
    setMessages(prev => [...prev, { id: Date.now(), role: 'user', text: userText, isImage: !!imgToSend, imageBase64: imgToSend }]);
    setInputValue('');
    setSelectedImage(null);

    if (pendingStockUpdate) {
        const units = parseInt(userText.replace(/[^0-9]/g, ''), 10);
        if (!isNaN(units) && units > 0) {
            try {
                const res = await fetch(`/api/catalog/products/${pendingStockUpdate.id}/reduce_stock`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-Merchant-Id': activeMerchantId },
                    body: JSON.stringify({ units_sold: units })
                });
                const data = await res.json();
                playSound('received');
                setMessages(prev => [...prev, { id: Date.now()+1, role: 'ai', text: ` Stock reduced! ${pendingStockUpdate.name} now has ${data.new_stock} units remaining.` }]);
                fetchProducts();
            } catch (e) {
                playSound('received');
                setMessages(prev => [...prev, { id: Date.now()+1, role: 'ai', text: `Failed to update stock: ${e.message}` }]);
            }
        } else {
            playSound('received');
            setMessages(prev => [...prev, { id: Date.now()+1, role: 'ai', text: "Invalid quantity. Please enter a valid number." }]);
        }
        setPendingStockUpdate(null);
        return;
    }

    if (onboardingStep > 0 && onboardingStep < 4) {
      handleOnboarding(userText);
      return;
    }

    try {
        if (imgToSend) setIsUploading(true);
        const res = await parseCatalogMessage(userText, activeMerchantId, imgToSend, merchantName, merchantLocation, language);
        playSound('received');
        const shouldShowMenu = !(res.parsed?.clarification_needed);
        setMessages(prev => [...prev, {
          id: Date.now()+1,
          role: 'ai',
          text: res.reply || 'Added to catalog!',
          isMenu: shouldShowMenu
        }]);
        setLogs(prev => [...prev, {
           id: Date.now()+2,
           title: "Processing Message",
           description: `Parsed: ${res.parsed?.product_name || 'Item'} at ₹${res.parsed?.listed_price || '—'}`,
           color: "bg-blue-500/20 text-blue-400"
        }]);
        fetchProducts();
    } catch (err) {
        playSound('received');
        setMessages(prev => [...prev, {
          id: Date.now()+1,
          role: 'ai',
          text: `Failed to process: ${err.message}`,
          isMenu: true
        }]);
    } finally {
        setIsUploading(false);
    }
  };

  const fetchProducts = async () => {
    try {
      const p = await getProducts(activeMerchantId);
      setProducts(p);
    } catch(e) {}
  };

  useEffect(() => {
    fetchProducts();
  }, [activeMerchantId]);

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if ((onboardingStep > 0 && onboardingStep < 4) || onboardingStep === 100) {
      alert("Please finish setting up your profile first!");
      return;
    }

    const reader = new FileReader();
    reader.onload = (ev) => {
      setSelectedImage(ev.target.result);
    };
    reader.readAsDataURL(file);
    // Reset file input so they can select the same file again if they cancel
    e.target.value = null;
  };

  const handleSaveStock = async () => {
    const edits = Object.entries(stockEdits);
    if (edits.length === 0) return;
    
    setShowInventorySheet(false);
    playSound('sent');
    setMessages(prev => [...prev, { id: Date.now(), role: 'user', text: `Submitted WhatsApp Flow: Update Stock for ${edits.length} items.` }]);

    let successCount = 0;
    for (const [id, newStock] of edits) {
        try {
            await fetch(`http://localhost:8000/api/catalog/products/${id}/set_stock`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ new_stock: parseInt(newStock, 10) })
            });
            successCount++;
        } catch (e) {
            console.error(e);
        }
    }
    
    setStockEdits({});
    fetchProducts();
    
    setTimeout(() => {
        playSound('received');
        const lang = sessionStorage.getItem('global_catalog_language_v2')?.toLowerCase() || '';
        let msg = ` Successfully updated stock for ${successCount} items via Flow.`;
        if (lang.includes('hindi')) msg = ` फ्लो के माध्यम से ${successCount} उत्पादों का स्टॉक सफलतापूर्वक अपडेट किया गया।`;
        else if (lang.includes('hinglish')) msg = ` Flow ke through ${successCount} items ka stock successfully update ho gaya.`;
        setMessages(prev => [...prev, { id: Date.now()+1, role: 'ai', text: msg, isMenu: true }]);
    }, 1000);
  };

  // Dynamic Live Timestamps
  const now = new Date();
  const timeNow = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }).toLowerCase();
  const timeMinus1 = new Date(now.getTime() - 60000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }).toLowerCase();
  const timeMinus5 = new Date(now.getTime() - 300000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }).toLowerCase();
  const timeMinus10 = new Date(now.getTime() - 600000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }).toLowerCase();

  const currentLang = sessionStorage.getItem('global_catalog_language_v2')?.toLowerCase() || 'english';
  const isHindi = currentLang.includes('hindi');
  const isHinglish = currentLang.includes('hinglish');

  const txtViewOptions = isHindi ? "विकल्प देखें" : (isHinglish ? "Options Dekhein" : "View Options");
  const txtMenuTitle = isHindi ? "कैटलॉग मेनू" : "Catalog Menu";
  const txtInvTitle = isHindi ? "स्टॉक देखें" : (isHinglish ? "Stock Check Karein" : "Check Inventory");
  const txtInvDesc = isHindi ? "मौजूदा स्टॉक देखें" : (isHinglish ? "Current stock dekhein" : "View current product stock");
  const txtAddTitle = isHindi ? "नया उत्पाद जोड़ें" : (isHinglish ? "Naya Product Add Karein" : "Add New Product");
  const txtAddDesc = isHindi ? "फोटो या टेक्स्ट अपलोड करें" : (isHinglish ? "Photo ya text bhejein" : "Upload a photo or text");


  return (
    <motion.div 
      initial={{ opacity: 0, y: 30 }} 
      animate={{ opacity: 1, y: 0 }} 
      transition={{ duration: 0.8, delay: 0.4, ease: "easeOut" }} 
      className="w-full flex flex-col lg:flex-row gap-6 min-h-[600px] relative z-10"
    >
      
      {/* LEFT: Android WhatsApp Mobile Mockup */}
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
                        <option value="new" className="font-semibold text-emerald-600 bg-white">[ + Add New Merchant ]</option>
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
               <span className="text-[11px] font-medium text-zinc-300">{timeMinus10.replace(" am", "").replace(" pm", "")}</span>
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

              <ChatMessageList className="p-3 gap-1 pb-4 rounded-none">
              {messages.map(m => (
                <ChatBubble 
                  key={m.id} 
                  variant={m.role === 'user' ? 'sent' : 'received'}
                >
                  {m.imageBase64 && (
                     <div className="mb-2 max-w-full overflow-hidden rounded-xl border border-white/10">
                        <img src={m.imageBase64} alt="uploaded" className="w-full h-auto object-cover max-h-[200px]" />
                     </div>
                  )}
                  <div className="whitespace-pre-wrap break-words">{m.text}</div>
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
                         onClick={() => handleMenuSelection(txtInvTitle)}
                         className="flex items-center justify-between px-5 py-4 cursor-pointer hover:bg-[#202c33] border-b border-[#2a3942]"
                       >
                         <div className="flex flex-col">
                            <span className="text-[#00a884] font-medium text-[16px]">{txtInvTitle}</span>
                            <span className="text-[#8696a0] text-sm">{txtInvDesc}</span>
                         </div>
                         <div className="w-5 h-5 rounded-full border-2 border-[#8696a0] flex items-center justify-center"></div>
                       </div>
                       
                       <div 
                         onClick={() => handleMenuSelection(txtAddTitle)}
                         className="flex items-center justify-between px-5 py-4 cursor-pointer hover:bg-[#202c33]"
                       >
                         <div className="flex flex-col">
                            <span className="text-[#00a884] font-medium text-[16px]">{txtAddTitle}</span>
                            <span className="text-[#8696a0] text-sm">{txtAddDesc}</span>
                         </div>
                         <div className="w-5 h-5 rounded-full border-2 border-[#8696a0] flex items-center justify-center"></div>
                       </div>
                    </div>
                  </motion.div>
                </div>
              )}

              {/* WhatsApp Flows: Native Inventory Management Screen */}
              {showInventorySheet && (
                <div className="absolute inset-0 bg-black/60 z-[70] flex items-end justify-center pb-[62px]">
                  <motion.div 
                    initial={{ y: "100%" }}
                    animate={{ y: 0 }}
                    exit={{ y: "100%" }}
                    transition={{ type: "spring", bounce: 0, duration: 0.3 }}
                    className="w-full h-[90%] bg-[#111b21] rounded-t-2xl shadow-2xl flex flex-col overflow-hidden border border-[#2a3942]"
                  >
                    {/* Flow Header */}
                    <div className="flex items-center justify-between px-4 py-3 bg-[#202c33] border-b border-[#2a3942] shrink-0">
                       <span className="text-[#e9edef] font-medium text-lg">Manage Stock (WhatsApp Flow)</span>
                       <IconX className="w-6 h-6 text-[#8696a0] cursor-pointer hover:text-white" onClick={() => setShowInventorySheet(false)} />
                    </div>
                    
                    {/* Search Bar */}
                    <div className="p-3 bg-[#111b21] shrink-0 border-b border-[#2a3942]">
                      <div className="bg-[#202c33] rounded-lg h-10 flex items-center px-3 gap-2">
                        <IconSearch className="w-5 h-5 text-[#8696a0]" />
                        <input 
                          type="text" 
                          placeholder="Search products..."
                          value={inventorySearch}
                          onChange={(e) => setInventorySearch(e.target.value)}
                          className="flex-1 bg-transparent border-none outline-none text-[#d1d7db] placeholder:text-[#8696a0] text-sm"
                        />
                      </div>
                    </div>

                    {/* Product List */}
                    <div className="flex flex-col py-2 overflow-y-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none] flex-1 pb-20">
                       {products.filter(p => (p.name || "").toLowerCase().includes((inventorySearch || "").toLowerCase())).map(p => {
                         const currentVal = stockEdits[p.id] !== undefined ? stockEdits[p.id] : p.stock;
                         return (
                         <div 
                           key={p.id}
                           className="flex items-center gap-3 px-4 py-3 border-b border-[#2a3942] hover:bg-[#202c33]"
                         >
                           <img src={p.image_url} alt="" className="w-12 h-12 rounded-md object-cover bg-zinc-800 shrink-0 border border-zinc-700" />
                           <div className="flex flex-col flex-1 overflow-hidden pr-2">
                              <span className="text-[#e9edef] font-medium text-[15px] truncate leading-snug">{p.name}</span>
                              <span className="text-[#8696a0] text-[13px] truncate">₹{p.listed_price}</span>
                           </div>
                           
                           {/* Editable Stock Input */}
                           <div className="flex items-center gap-2 shrink-0 bg-[#202c33] px-2 py-1.5 rounded-lg border border-[#2a3942]">
                              <span className="text-[#8696a0] text-xs font-medium">Stock:</span>
                              <input 
                                type="number" 
                                value={currentVal}
                                onChange={(e) => setStockEdits({...stockEdits, [p.id]: e.target.value})}
                                className="w-14 bg-transparent border-none outline-none text-emerald-500 font-bold text-center text-sm"
                                min="0"
                              />
                           </div>
                         </div>
                       )})}
                    </div>
                    
                    {/* Save Button Footer */}
                    {Object.keys(stockEdits).length > 0 && (
                      <div className="absolute bottom-0 left-0 right-0 p-4 bg-[#202c33] border-t border-[#2a3942] flex justify-center">
                        <button 
                          onClick={handleSaveStock}
                          className="w-full bg-[#00a884] hover:bg-[#008f6f] text-[#111b21] font-bold py-3 rounded-full transition-colors shadow-lg"
                        >
                          Submit Updates ({Object.keys(stockEdits).length} changed)
                        </button>
                      </div>
                    )}
                  </motion.div>
                </div>
              )}

              {/* Selected Image Preview Box */}
              {selectedImage && (
                <div className="w-full bg-[#111b21] p-3 border-t border-[#2a3942] flex items-end gap-3 shrink-0 relative">
                   <div className="relative inline-block border-2 border-emerald-500/50 rounded-lg overflow-hidden shrink-0">
                      <img src={selectedImage} alt="preview" className="h-20 w-20 object-cover" />
                      <div 
                         onClick={() => setSelectedImage(null)}
                         className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 rounded-full flex items-center justify-center cursor-pointer hover:scale-110 transition-transform shadow-lg"
                      >
                         <IconX className="w-3 h-3 text-white" />
                      </div>
                   </div>
                   <div className="text-xs text-zinc-400 pb-1">Image ready to send. Type a caption below.</div>
                </div>
              )}

              {/* Standard WhatsApp Web Input */}
              <div className="h-[62px] bg-[#202c33] flex items-center gap-2 px-4 shrink-0 w-full">
                 <IconMoodSmile className="w-[26px] h-[26px] text-[#8696a0] cursor-pointer hover:text-[#d1d7db] transition-colors shrink-0" />
                 <label className="cursor-pointer flex items-center justify-center">
                    <IconPaperclip className="w-[26px] h-[26px] text-[#8696a0] hover:text-[#d1d7db] transition-colors shrink-0 mx-1" />
                    <input type="file" className="hidden" accept="image/*" onChange={handleFileUpload} disabled={isUploading} />
                 </label>
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
                 {inputValue.trim() || selectedImage ? (
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

      {/* RIGHT: Backend Brain */}
      <div className="flex-[2] flex flex-col p-2 sm:p-4 gap-4 z-20 justify-center">
        {/* Alignment Spacer (Matches Merchant Selector) */}
        <div className="hidden lg:block h-[42px] shrink-0 pointer-events-none opacity-0" />
        
        {/* Magic UI Animated Logs */}
        <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-3xl p-4 shadow-2xl relative overflow-hidden w-full sm:h-[720px] h-[650px] flex flex-col shrink-0">
           <div className="flex items-center gap-2 mb-3 px-2 border-b border-white/10 pb-4 pt-2">
             <div className="flex gap-1.5 mr-4">
               <div className="w-3 h-3 rounded-full bg-red-500/80"></div>
               <div className="w-3 h-3 rounded-full bg-yellow-500/80"></div>
               <div className="w-3 h-3 rounded-full bg-green-500/80"></div>
             </div>
             <IconTerminal2 className="w-4 h-4 text-zinc-400" />
             <h3 className="font-mono text-white text-xs opacity-70">catalog_bot_brain.exe</h3>
           </div>
           <div className="w-full flex-1 overflow-hidden mt-2 relative">
             <div className="absolute inset-0 overflow-y-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none] px-2">
                <AnimatedList delay={1500} className="min-h-full justify-end">
                {logs.map(log => (
                  <Notification key={log.id} icon={<IconSearch className="w-5 h-5" />} title={log.title} description={log.description} color={log.color} time={timeMinus1} />
                ))}
              </AnimatedList>
           </div>
        </div>
        </div>
      </div>
      
    </motion.div>
  );
}

