import React, { useState, useEffect, useRef } from 'react';
import { CatalogBotTab } from '@/components/CatalogBotTab';
import { SalesBotEngineTab } from '@/components/SalesBotEngineTab';
import { InventoryTab } from '@/components/InventoryTab';
import { ReverseAuctionVisualizer } from '@/components/ReverseAuctionVisualizer';
import { searchBuyerChat, runParallelReverseAuction, checkoutTrustOrder, simulatePayment, getSessionId, fetchWithTimeout, checkOrderStatus, fetchSessionHistory, saveSessionHistory } from '@/lib/api';
import { playSound } from '@/lib/sounds';
import { ShootingStars } from '@/components/ui/shooting-stars';
import { StarsBackground } from '@/components/ui/stars-background';
import { NoiseTexture } from '@/components/ui/noise-texture';
import { BackgroundBeams } from '@/components/ui/background-beams';
import { IconMessage, IconBolt, IconHeartHandshake, IconMicrophone } from '@tabler/icons-react';

import { cn } from "@/lib/utils";
import { DotPattern } from "@/components/magicui/dot-pattern";
import {
  NavigationMenu,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
  navigationMenuTriggerStyle,
} from "@/components/ui/navigation-menu";
import { BentoGrid, BentoGridItem } from "@/components/ui/bento-grid";
import {
  IconArrowWaveRightUp,
  IconBoxAlignTopLeft,
  IconSignature,
  IconTableColumn,
  IconMessages,
  IconTrendingDown,
  IconBrain,
  IconGavel,
  IconChecklist,
  IconBuildingBank,
  IconSearch,
  IconChartBar
} from "@tabler/icons-react";
import { NumberTicker } from "@/components/magicui/number-ticker";
import { Terminal, TypingAnimation, AnimatedSpan } from "@/components/magicui/terminal";
import { ShimmerButton } from "@/components/magicui/shimmer-button";
import { HoverEffect } from "@/components/ui/card-hover-effect";
import { AnimatedBeam } from "@/components/magicui/animated-beam";
import { motion, AnimatePresence } from "framer-motion";

// Shadcn Charts
import { Line, LineChart, Pie, PieChart, Label } from "recharts"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart"

import {
  IconHandClick,
  IconBrandWhatsapp,
  IconUserSearch,
  IconRobot,
  IconShieldCheck,
  IconReceipt2, IconServer
} from "@tabler/icons-react";

// --- Dynamic Chart Components ---

const LiveGMVChart = ({ data }) => {
  const chartConfig = {
    bid: { label: "Lowest Bid", color: "#10b981" },
  }
  return (
    <div className="flex-1 w-full h-full relative overflow-hidden flex flex-col justify-end pt-4">
      <ChartContainer config={chartConfig} className="w-full h-[120px]">
        <LineChart data={data} margin={{ left: -20, right: 10, top: 10, bottom: 0 }}>
          <ChartTooltip cursor={false} content={<ChartTooltipContent indicator="line" />} />
          <Line
            dataKey="bid"
            type="stepAfter"
            stroke="var(--color-bid)"
            strokeWidth={2}
            dot={{ fill: "var(--color-bid)", r: 3 }}
            activeDot={{ r: 5 }}
            isAnimationActive={true}
          />
        </LineChart>
      </ChartContainer>
    </div>
  )
}

const LiveConversionDonut = () => {
  const chartData = [
    { status: "success", count: 94, fill: "#f97316" },
    { status: "deadlock", count: 6, fill: "#431407" },
  ]
  const chartConfig = {
    success: { label: "Successful", color: "#f97316" },
    deadlock: { label: "Deadlocks", color: "#431407" },
  }
  return (
    <div className="flex-1 w-full h-full flex items-center justify-center relative -mt-4">
      <div className="absolute w-[120px] h-[120px] rounded-full border-[2px] border-orange-500/10 border-t-orange-500/30 animate-[spin_4s_linear_infinite]"></div>
      <div className="absolute w-[135px] h-[135px] rounded-full border-[1px] border-orange-900/20 border-b-orange-500/20 animate-[spin_8s_linear_infinite_reverse]"></div>
      
      <ChartContainer config={chartConfig} className="aspect-square h-[140px] relative z-10">
        <PieChart>
          <ChartTooltip cursor={false} content={<ChartTooltipContent hideLabel />} />
          <Pie data={chartData} dataKey="count" nameKey="status" innerRadius={45} outerRadius={55} strokeWidth={0}>
            <Label
              content={({ viewBox }) => {
                if (viewBox && "cx" in viewBox && "cy" in viewBox) {
                  return (
                    <text x={viewBox.cx} y={viewBox.cy} textAnchor="middle" dominantBaseline="middle">
                      <tspan x={viewBox.cx} y={viewBox.cy} className="fill-white text-3xl font-bold">94%</tspan>
                    </text>
                  )
                }
              }}
            />
          </Pie>
        </PieChart>
      </ChartContainer>
    </div>
  )
}


const MultimodalExtractionHeader = () => {
  return (
    <div className="flex-1 w-full h-full flex flex-col items-center justify-center relative p-4 overflow-hidden bg-black/20 rounded-xl">
      <div className="flex w-full items-center justify-center gap-4">
        {/* Mock WhatsApp Bubble */}
        <div className="bg-[#005c4b] text-[#e9edef] text-[10px] p-2 rounded-xl rounded-tr-none shadow-sm w-[40%] text-left">
          <IconMicrophone className="w-3 h-3 inline mr-1 text-emerald-400" />
          "Bhai black hoodie 1200 laga de, 20 piece hain"
        </div>
        
        {/* Animated Arrow/Magic */}
        <div className="flex flex-col items-center shrink-0">
          <IconBolt className="w-5 h-5 text-yellow-500 animate-pulse" />
        </div>
        
        {/* Clean JSON */}
        <div className="bg-zinc-950 border border-zinc-800 text-emerald-400 font-mono text-[9px] p-2 rounded-md shadow-sm w-[50%] text-left whitespace-pre leading-relaxed">
          {`{
  "item": "Black Hoodie",
  "price": 1200,
  "stock": 20
}`}
        </div>
      </div>
    </div>
  )
}

const AgentNegotiationHeader = () => {
  return (
    <div className="flex-1 w-full h-full relative overflow-hidden bg-black/20 rounded-xl flex items-center justify-center p-4">
      <div className="w-full flex justify-between items-center h-24 relative px-4">
        <div className="absolute left-10 right-10 top-1/2 -translate-y-1/2 border-b-2 border-dashed border-zinc-700/50"></div>
        
        {/* Buyer Node */}
        <div className="flex flex-col items-center z-10 bg-[#080B10] p-1 rounded-full">
          <div className="bg-purple-500/10 text-purple-400 text-[10px] px-2 py-0.5 rounded mb-1 border border-purple-500/30">Bid: ₹800</div>
          <IconRobot className="w-6 h-6 text-purple-500" />
        </div>
        
        {/* Sync Icon */}
        <div className="z-10 bg-[#080B10] p-1 rounded-full">
          <IconHeartHandshake className="w-6 h-6 text-emerald-500 animate-pulse" />
        </div>

        {/* Seller Node */}
        <div className="flex flex-col items-center z-10 bg-[#080B10] p-1 rounded-full">
          <div className="bg-blue-500/10 text-blue-400 text-[10px] px-2 py-0.5 rounded mb-1 border border-blue-500/30">Ask: ₹1200</div>
          <IconRobot className="w-6 h-6 text-blue-500" />
        </div>
      </div>
    </div>
  )
}

const PlatformRevenueHeader = ({ revenue }) => {
  return (
    <div className="flex-1 w-full h-full flex items-center justify-center relative">
      <div className="flex items-baseline gap-1">
        <span className="text-3xl font-bold text-white">₹</span>
        <NumberTicker key={revenue} value={revenue} className="text-5xl font-bold text-white tracking-tighter" />
      </div>
    </div>
  )
}

const MarginTerminalHeader = ({ logs }) => {
  return (
    <div className="flex-1 w-full h-full relative overflow-hidden bg-black/40 rounded-xl">
      <Terminal className="bg-transparent border-0" sequence={false}>
        {logs.map((log, i) => (
          <div key={i} className={cn("text-[11px] font-mono", log.color || "text-zinc-400")}>
            {log.text}
          </div>
        ))}
      </Terminal>
    </div>
  )
}

import { HoverCard, HoverCardTrigger, HoverCardContent } from '@/components/ui/hover-card';
import { IconDatabase } from '@tabler/icons-react';
import { TracingBeam } from '@/components/ui/tracing-beam';
import { GlowingEffect } from '@/components/ui/glowing-effect';

import { PlaceholdersAndVanishInput } from '@/components/ui/placeholders-and-vanish-input';
import { ProChatInput } from '@/components/ui/pro-chat-input';
import { AnimatedList } from '@/components/ui/animated-list';
import { IconCheck, IconX, IconLock } from '@tabler/icons-react';

export default function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [hasSalesPing, setHasSalesPing] = useState(false);
  const [showWelcomeModal, setShowWelcomeModal] = useState(() => !sessionStorage.getItem('global_catalog_language_v2'));

  // Merchant State
  const [merchantsList, setMerchantsList] = useState([
    {
        "id": "m1",
        "name": "Sneaker Bhai"
    },
    {
        "id": "m4",
        "name": "Kicks Delhi"
    },
    {
        "id": "m5",
        "name": "Sole Mates"
    },
    {
        "id": "m6",
        "name": "Urban Kicks"
    },
    {
        "id": "m7",
        "name": "The Sneaker Shop"
    },
    {
        "id": "m2",
        "name": "Saree Palace"
    },
    {
        "id": "m8",
        "name": "Ethnic Vogue"
    },
    {
        "id": "m9",
        "name": "Desi Threads"
    },
    {
        "id": "m10",
        "name": "Saree Symphony"
    },
    {
        "id": "m11",
        "name": "Ethnic Elegance"
    },
    {
        "id": "m3",
        "name": "Streetwear Hub"
    },
    {
        "id": "m12",
        "name": "Hypebeast India"
    },
    {
        "id": "m13",
        "name": "Street Style Co"
    },
    {
        "id": "m14",
        "name": "Metro Menswear"
    },
    {
        "id": "m15",
        "name": "The Hype Store"
    },
    {
        "id": "m16",
        "name": "Sneaker Central"
    },
    {
        "id": "m17",
        "name": "Kicksville"
    },
    {
        "id": "m18",
        "name": "Lace Up"
    },
    {
        "id": "m19",
        "name": "Sole Search"
    },
    {
        "id": "m20",
        "name": "Sneaker Society"
    },
    {
        "id": "m21",
        "name": "Saree Mandir"
    },
    {
        "id": "m22",
        "name": "Vastra"
    },
    {
        "id": "m23",
        "name": "Ethnic Charm"
    },
    {
        "id": "m24",
        "name": "Indian Weaves"
    },
    {
        "id": "m25",
        "name": "Silk Story"
    },
    {
        "id": "m26",
        "name": "Street Pulse"
    },
    {
        "id": "m27",
        "name": "Urban Drops"
    },
    {
        "id": "m28",
        "name": "Hype Central"
    },
    {
        "id": "m29",
        "name": "The Street Code"
    },
    {
        "id": "m30",
        "name": "City Fits"
    }
]);
  const [catalogMerchantId, setCatalogMerchantId] = useState('m1');
  const [salesMerchantId, setSalesMerchantId] = useState('m1');

  useEffect(() => {
    import('@/lib/api').then(({ fetchMerchants }) => {
      fetchMerchants().then(list => setMerchantsList(list)).catch(() => {});
    });
  }, []);

  const handleCatalogMerchantChange = (val) => {
    if (val === 'new') {
      const newId = `m_custom_${Math.random().toString(36).substring(2, 8)}`;
      setCatalogMerchantId(newId);
      setMerchantsList(prev => [...prev, { id: newId, name: 'New Store' }]);
    } else {
      setCatalogMerchantId(val);
    }
  };

  const handleSalesMerchantChange = (val) => {
    setSalesMerchantId(val);
  };

  const [chatMessages, setChatMessages] = useState([]);
  const [hasLoadedHistory, setHasLoadedHistory] = useState(false);

  useEffect(() => {
    fetchSessionHistory().then(data => {
      if (data.chat_data && Array.isArray(data.chat_data) && data.chat_data.length > 0) {
        setChatMessages(data.chat_data);
      } else {
        setChatMessages([{ role: 'ai', text: "Hello! I am your MerchantMesh Buyer Agent. Tell me what you're looking for, and I'll spawn parallel threads to haggle with local WhatsApp sellers for you." }]);
      }
      setHasLoadedHistory(true);
    }).catch(() => {
      setChatMessages([{ role: 'ai', text: "Hello! I am your MerchantMesh Buyer Agent. Tell me what you're looking for, and I'll spawn parallel threads to haggle with local WhatsApp sellers for you." }]);
      setHasLoadedHistory(true);
    });
  }, []);

  useEffect(() => {
    if (hasLoadedHistory && chatMessages.length > 0) {
      saveSessionHistory(chatMessages).catch(e => console.error("Failed to save session history:", e));
    }
  }, [chatMessages, hasLoadedHistory]);

  const [chatInputValue, setChatInputValue] = useState("");
  const [isHaggling, setIsHaggling] = useState(false);
  const [selectedDealView, setSelectedDealView] = useState(null);
  const [activeImageIdx, setActiveImageIdx] = useState(0);
  const [visualizerPhase, setVisualizerPhase] = useState(() => { try { return JSON.parse(sessionStorage.getItem('visualizerPhase_v2')) || 0; } catch { return 0; } });
  const [visualizerLogs, setVisualizerLogs] = useState([]);
  const [fullAuctionResult, setFullAuctionResult] = useState(() => { try { return JSON.parse(sessionStorage.getItem('fullAuctionResult_v2')); } catch { return null; } });
  const [showLogs, setShowLogs] = useState(false);
  const [dealOptions, setDealOptions] = useState(() => { try { return JSON.parse(sessionStorage.getItem('dealOptions_v2')) || []; } catch { return []; } });
  const [pendingOrderId, setPendingOrderId] = useState(() => { try { return JSON.parse(sessionStorage.getItem('pendingOrderId_v2')); } catch { return null; } });
  const [auctionResult, setAuctionResult] = useState(() => { try { return JSON.parse(sessionStorage.getItem('auctionResult_v2')); } catch { return null; } });

  useEffect(() => {
    sessionStorage.setItem('visualizerPhase_v2', JSON.stringify(visualizerPhase));
    sessionStorage.setItem('fullAuctionResult_v2', JSON.stringify(fullAuctionResult));
    sessionStorage.setItem('dealOptions_v2', JSON.stringify(dealOptions));
    sessionStorage.setItem('pendingOrderId_v2', JSON.stringify(pendingOrderId));
    sessionStorage.setItem('auctionResult_v2', JSON.stringify(auctionResult));
  }, [visualizerPhase, fullAuctionResult, dealOptions, pendingOrderId, auctionResult]);

  const handleChatSubmit = async (val) => {
    let userQuery = val;
    if (val && typeof val.preventDefault === 'function') {
        val.preventDefault();
        userQuery = chatInputValue;
    }
    
    if (!userQuery || typeof userQuery !== 'string') return;
    setChatInputValue(''); // Clear input eagerly
    playSound('sent');
    
    // Add user message
    setChatMessages(prev => [...prev, { role: 'user', text: userQuery }]);
    setIsHaggling(true);
    setShowLogs(true);
    setDealOptions([]);
    setPendingOrderId(null);
    setAuctionResult(null);
    setFullAuctionResult(null);
    setVisualizerPhase(0);
    setVisualizerLogs(['[SYSTEM] Intent received. Parsing Natural Language...']);
    
    try {
      // 1. Natural Language Search
      setVisualizerPhase(1);
      setVisualizerLogs(prev => [...prev, '[SYSTEM] Broadcasting RFQ to active local nodes...']);
      const historyForBackend = chatMessages
        .filter(m => m.role === 'user' || m.role === 'ai')
        .slice(-6)
        .map(m => ({ role: m.role === 'ai' ? 'assistant' : 'user', content: m.text }));
      const searchRes = await searchBuyerChat(userQuery, historyForBackend);
      playSound('received');
      setChatMessages(prev => [...prev, { role: 'ai', text: searchRes.reply }]);
      
      if (searchRes.status === 'SUCCESS' && searchRes.products?.length > 0) {
         const pIds = searchRes.products.map(p => p.id);
         // 2. Run real Parallel Reverse Auction
         setVisualizerPhase(2);
         setVisualizerLogs(prev => [...prev, '[WORKER] Collecting bids...']);
         const auction = await runParallelReverseAuction({
            product_ids: pIds,
            target_price: searchRes.parsed_query?.target_price,
            max_budget: searchRes.parsed_query?.max_budget,
            quantity: searchRes.parsed_query?.quantity || 1
         });
         
         if (auction.deals && auction.deals.some(r => r.status === 'ACCEPTED')) {
            
            setFullAuctionResult(auction);
            setVisualizerPhase(3);
            setVisualizerLogs(prev => [...prev, '[SUPERVISOR] Auction complete. Presenting options.']);

            const accepted = auction.deals.filter(r => r.status === 'ACCEPTED').sort((a,b) => b.deal_score - a.deal_score);
            setDealOptions(accepted.slice(0, 3));
            setChatMessages(prev => [
              ...prev, 
              { role: 'ai', text: searchRes.parsed_query?.max_budget ? `✅ Good news! ${accepted.length} merchants agreed to your budget. Here are the winning bids:` : `✅ I've secured ${accepted.length} great offers for you! Here are the top deals:` }
            ]);
            setIsHaggling(false);
         } else {
            setFullAuctionResult(auction);
            setVisualizerPhase(3);
            setVisualizerLogs(prev => [...prev, '[SUPERVISOR] Auction complete. All merchants rejected the budget.']);
            setChatMessages(prev => [
              ...prev, 
              { role: 'ai', text: `I negotiated with the merchants, but unfortunately, no one was able to meet your budget constraints. The lowest offer was above your maximum budget.` }
            ]);
            setIsHaggling(false);
         }
      } else {
         setIsHaggling(false);
      }
    } catch (err) {
      console.error(err);
      const msg = err.name === 'AbortError'
        ? 'The AI agents are experiencing high load. Please try again in a moment.'
        : `Oops — something went wrong. ${err.message || 'Please try again.'}`;
      setChatMessages(prev => [...prev, { role: 'ai', text: msg }]);
      setIsHaggling(false);
    }
  };

  const handleSelectDeal = async (w) => {
    setAuctionResult(w);
    // Update the visualizer node glow to jump to the newly selected merchant
    setFullAuctionResult(prev => {
      if (!prev || !prev.deals) return prev;
      return {
        ...prev,
        deals: prev.deals.map(d => ({
          ...d,
          is_winner: d.merchant_id === w.merchant_id
        }))
      };
    });
    setDealOptions(prev => prev.filter(opt => opt.merchant_id !== w.merchant_id));
    setChatMessages(prev => [
      ...prev,
      { role: 'user', text: `I'll go with ${w.merchant_name} for ₹${w.final_price}.` },
      { role: 'ai', text: ' Initiating Checkout...\n\n① Creating order in SQLite\n② Awaiting merchant manual confirmation...' }
    ]);
    
    try {
      const res = await checkoutTrustOrder({
        product_id: w.product_id,
        merchant_id: w.merchant_id,
        agreed_price: w.final_price,
        negotiation_id: w.session_id,
        quantity: w.quantity || 1,
        require_merchant_confirmation: true
      });
      playSound('received');
      setPendingOrderId(res.order_id);
      setChatMessages(prev => [...prev, { 
        role: 'ai', 
        text: ` Order ${res.order_id} created.\n\n Sent to merchant's WhatsApp for final stock verification. Waiting for merchant to Accept or Reject...` 
      }]);
    } catch (err) {
      console.error(err);
      setChatMessages(prev => [...prev, { role: 'ai', text: `⚠️ Checkout failed: ${err.message}.` }]);
    }
  };

  useEffect(() => {
    let intervalId;
    let linkShown = false;
    if (pendingOrderId && auctionResult) {
      intervalId = setInterval(async () => {
        try {
          const res = await checkOrderStatus(pendingOrderId);
          
          if (res.status === 'READY_FOR_PAYMENT') {
            
            // Only show the link message once
            if (!linkShown) {
              setChatMessages(prev => {
                if(prev.some(m => m.paymentLink === res.payment_link_url)) return prev;
                return [...prev, { role: 'ai', text: ` 🟢 Merchant Confirmed Stock!
 Razorpay Payment Link generated.

 Link expires in 15 minutes. Complete payment to lock your deal.`, paymentLink: res.payment_link_url }];
              });
              linkShown = true;
              
              linkShown = true;
              
              if (res.payment_link_url && !res.payment_link_url.includes('sim_')) {
                
                // Keep polling to catch the PAID status
              } else {
                clearInterval(intervalId);
                // SIMULATION MODE: Auto-simulate payment
              setChatMessages(prev => [...prev, { role: 'ai', text: ` Merchant Accepted!\n Payment Link generated.\n\nSimulating UPI payment...` }]);
              
              const payRes = await simulatePayment(pendingOrderId);
              setChatMessages(prev => [...prev, { role: 'ai', text: ` Payment verified via raw-byte HMAC-SHA256!\n\n Razorpay Route Settlement:\n• Total: ₹${auctionResult.final_price}\n• Merchant Payout (100%): ₹${auctionResult.final_price}\n• Platform Fee (0%): ₹0\n\nOrder ${pendingOrderId} is fully settled. ` }]);
              setPendingOrderId(null);
              
              setTimeout(() => {
                setVisualizerPhase(0);
                setFullAuctionResult(null);
              }, 3000);
            }
            } // <--- Added closing brace for the outer if (!chatMessages.some...)
          } else if (res.status === 'REJECTED' || res.status === 'CANCELLED') {
            clearInterval(intervalId);
            setChatMessages(prev => [...prev, { role: 'ai', text: `❌ Merchant Rejected (or Timed Out).\nTheir reliability score has been penalized by 0.3.\n\nPlease select another merchant from the remaining options:` }]);
            setPendingOrderId(null);
            if (dealOptions.length === 0) {
              setChatMessages(prev => [...prev, { role: 'ai', text: `No other merchants are available. Please try a new search.` }]);
            }
          } else if (res.status === 'PAID' || res.status === 'SETTLED') {
            // Real Razorpay webhook confirmed payment
            clearInterval(intervalId);
            
            setChatMessages(prev => [...prev, { role: 'ai', text: ` Payment confirmed via Razorpay!\n\n Razorpay Route Settlement:\n• Total: ₹${auctionResult.final_price}\n• Merchant Payout (100%): ₹${auctionResult.final_price}\n• Platform Fee (0%): ₹0\n\nOrder ${pendingOrderId} is fully settled. ` }]);
            setPendingOrderId(null);
            setTimeout(() => {
              setVisualizerPhase(0);
              setFullAuctionResult(null);
            }, 3000);
          }
        } catch (e) {
          console.error("Polling error:", e);
        }
      }, 2000);
    }
    return () => clearInterval(intervalId);
  }, [pendingOrderId, auctionResult, dealOptions]);

  const Notification = ({ color, icon, title, description, time }) => (
    <div className="relative mx-auto min-h-fit w-full max-w-[400px] overflow-hidden rounded-2xl p-4 transition-all duration-200 ease-in-out hover:scale-[103%] bg-white/5 backdrop-blur-md border border-white/10 shadow-[0_4px_24px_0_rgba(0,0,0,0.2)]">
      <div className="flex flex-row items-center gap-3">
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${color}`}>
          <span className="text-lg">{icon}</span>
        </div>
        <div className="flex flex-col overflow-hidden w-full">
          <div className="flex flex-row items-center justify-between w-full gap-4">
            <span className="text-sm font-bold text-white whitespace-nowrap overflow-hidden text-ellipsis">{title}</span>
            <span className="text-xs text-zinc-500 shrink-0">{time}</span>
          </div>
          <p className="text-xs font-normal text-zinc-400 whitespace-pre-wrap">{description}</p>
        </div>
      </div>
    </div>
  );

  const dummyLogs = [
    <Notification key="1" icon={<IconSearch className="w-5 h-5" />} title="Discovery Agent Active" description="Querying SQLite for matches..." color="bg-blue-500/20 text-blue-400" time="Just now" />,
    <Notification key="2" icon={<IconMessage className="w-5 h-5" />} title="Contacting 4 Sellers" description="Spawning parallel WhatsApp threads." color="bg-purple-500/20 text-purple-400" time="1s ago" />,
    <Notification key="3" icon={<IconBolt className="w-5 h-5" />} title="Acme Corp replied" description="Quoted ₹180/piece. Too high." color="bg-orange-500/20 text-orange-400" time="2s ago" />,
    <Notification key="4" icon={<IconRobot className="w-5 h-5" />} title="Negotiation Node" description="Counter-offering ₹120/piece based on historical data." color="bg-emerald-500/20 text-emerald-400" time="4s ago" />,
    <Notification key="5" icon={<IconTrendingDown className="w-5 h-5" />} title="Price Dropped!" description="GlobalText undercut to ₹150/piece." color="bg-green-500/20 text-green-400" time="5s ago" />,
    <Notification key="6" icon={<IconHeartHandshake className="w-5 h-5" />} title="Deal Locked" description="Acme Corp finalized at ₹140/piece." color="bg-blue-500/20 text-blue-400" time="6s ago" />,
    <Notification key="7" icon={<IconLock className="w-5 h-5" />} title="Inventory Secured" description="SQLite locks applied." color="bg-zinc-500/20 text-zinc-400" time="7s ago" />,
  ];


  const [chartData, setChartData] = useState([]);
  const [revenue, setRevenue] = useState(0);
  const [logs, setLogs] = useState([]);
  
  const turnRef = useRef(0);
  const containerRef = useRef(null);
  const div1Ref = useRef(null);
  const div2Ref = useRef(null);
  const div4Ref = useRef(null);
  const divCatalogRef = useRef(null);
  const divSalesRef = useRef(null);
  const divBuyerRef = useRef(null);
  const div5Ref = useRef(null);
  const div6Ref = useRef(null);
  const div7Ref = useRef(null);
  const divMcpRef = useRef(null);

  useEffect(() => {
    if (activeTab !== 'overview') return;
    
    turnRef.current = 0;
    setChartData([{ time: '0s', bid: 1250000 }]);
    setRevenue(0);
    setLogs([{ text: '> Initiating Reverse Auction RFQ...', color: 'text-zinc-500' }]);

    const interval = setInterval(() => {
      turnRef.current += 1;
      const turn = turnRef.current;
      
      if (turn === 1) {
        setChartData(prev => [...prev, { time: '2s', bid: 1150000 }]);
        setLogs(prev => [...prev, { text: '> TechCorp Bot bid ₹1,150,000. Input: 320 tokens. Cost: ₹0.04', color: 'text-zinc-300' }]);
      } else if (turn === 2) {
        setChartData(prev => [...prev, { time: '4s', bid: 1120000 }]);
        setLogs(prev => [...prev, { text: '> GlobalIT Bot undercut ₹1,120,000. Input: 640 tokens. Cost: ₹0.08', color: 'text-zinc-300' }]);
      } else if (turn === 3) {
        setChartData(prev => [...prev, { time: '6s', bid: 1050000 }]);
        setLogs(prev => [...prev, { text: '> Acme Supplier bid ₹1,050,000. Input: 960 tokens. Cost: ₹0.12', color: 'text-zinc-300' }]);
      } else if (turn === 4) {
        setChartData(prev => [...prev, { time: '8s', bid: 950000 }]);
        setLogs(prev => [...prev, { text: '> TechCorp Bot counter-bid ₹950,000. Input: 1280 tokens. Cost: ₹0.16', color: 'text-zinc-300' }]);
      } else if (turn === 5) {
        setLogs(prev => [
          ...prev, 
          { text: '> DEAL CLOSED at ₹950,000.', color: 'text-emerald-400 font-bold mt-2' },
          { text: '> Total Tokens: 4,500. Exact LLM Cost: ₹0.43', color: 'text-red-400' }
        ]);
        setRevenue(950000 * 0.02);
        clearInterval(interval);
      }
    }, 2000);
    
    return () => clearInterval(interval);
  }, [activeTab]);

  const metrics = [
    {
      title: "Multimodal Catalog Ingestion",
      description: "Messy Hinglish audio & images parsed to structured JSON in ~800ms.",
      header: <MultimodalExtractionHeader />,
      icon: <IconBolt className="h-4 w-4 text-yellow-500" />,
      className: "md:col-span-2",
    },
    {
      title: "Autonomous Negotiation",
      description: "Buyer & Seller AIs haggle to market equilibrium.",
      header: <AgentNegotiationHeader />,
      icon: <IconHeartHandshake className="h-4 w-4 text-purple-500" />,
      className: "md:col-span-1",
    }
  ];

  const navItems = [
    { id: 'overview', label: 'Overview' },
    { id: 'buyer-agent', label: 'Buyer Agent' },
    { id: 'catalog-bot', label: 'Catalog Bot' },
    { id: 'inventory', label: 'Inventory' },
    { id: 'sales-engine', label: 'Sales Bot' },
  ];

  return (
    <div className="relative min-h-screen font-sans text-zinc-200 pb-20 overflow-hidden flex flex-col items-center bg-[#080B10]">
      
      {/* Welcome Modal for Hackathon Judges */}
      <AnimatePresence>
        {(showWelcomeModal && (activeTab === 'catalog-bot' || activeTab === 'sales-bot')) && (
          <motion.div 
            initial={{ opacity: 0 }} 
            animate={{ opacity: 1 }} 
            exit={{ opacity: 0 }} 
            className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
          >
            <motion.div 
              initial={{ scale: 0.95, y: 20 }} 
              animate={{ scale: 1, y: 0 }} 
              exit={{ scale: 0.95, y: -20 }} 
              className="bg-zinc-900 border border-white/10 p-8 rounded-3xl max-w-xl w-full shadow-2xl relative overflow-hidden"
            >
              <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/10 to-transparent pointer-events-none" />
              
              <div className="relative z-10 flex flex-col items-center text-center">
                <div className="w-16 h-16 rounded-full bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center mb-6">
                  <IconRobot className="w-8 h-8 text-emerald-400" />
                </div>
                
                <h2 className="text-3xl font-bold text-white mb-4 tracking-tight">Welcome to MerchantMesh</h2>
                <p className="text-zinc-400 text-lg mb-8 leading-relaxed">
                  You are evaluating a prototype designed for India's 63M invisible social sellers. Our AI dynamically adapts to their literacy level and operates frictionlessly over WhatsApp.
                </p>

                <div className="w-full bg-black/40 border border-white/5 rounded-2xl p-6 mb-8 text-left">
                  <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
                    <IconBolt className="w-5 h-5 text-yellow-500" /> 
                    To begin, pick a language to test the AI in:
                  </h3>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-4">
                    {['English', 'Hindi', 'Hinglish'].map((lang) => (
                      <button
                        key={lang}
                        onClick={() => {
                          sessionStorage.setItem('global_catalog_language_v2', lang.toLowerCase());
                          setShowWelcomeModal(false);
                        }}
                        className="py-3 px-4 rounded-xl bg-white/5 border border-white/10 hover:bg-emerald-500/20 hover:border-emerald-500/50 hover:text-emerald-400 transition-all font-medium"
                      >
                        {lang}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="text-sm text-zinc-500 flex items-center gap-2">
                  <IconHeartHandshake className="w-4 h-4" /> 
                  Thanks for judging! Feel free to upload photos or type in the chat to test it.
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* BACKGROUND 1: Buyer Agent (Premium Dark Glass Image) */}
      <div 
        className="fixed inset-0 z-0 pointer-events-none transition-opacity duration-1000 ease-in-out" 
        style={{ opacity: activeTab === 'buyer-agent' ? 1 : 0 }}
      >
        <div className="absolute inset-0 bg-cover bg-center bg-no-repeat scale-125" style={{ backgroundImage: "url('/images/dark_bg.jpg?v=3')" }}></div>
        <div className="absolute inset-0 bg-gradient-to-t from-[#080B10] via-[#080B10]/40 to-transparent"></div>
      </div>

      {/* BACKGROUND 2: Overview (SaaS Grid) */}
      <div 
        className="fixed inset-0 z-0 pointer-events-none transition-opacity duration-1000 ease-in-out" 
        style={{ opacity: activeTab === 'overview' ? 1 : 0 }}
      >
        <div className="absolute inset-0 bg-[#080B10] bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px]">
          <div className="absolute inset-0 bg-[#080B10] [mask-image:radial-gradient(ellipse_80%_100%_at_50%_-20%,transparent_70%,black)]"></div>
        </div>
      </div>

      {/* BACKGROUND 3: Catalog Bot (Emerald Dynamic Theme) */}
      <div 
        className="fixed inset-0 z-0 pointer-events-none transition-opacity duration-1000 ease-in-out bg-[#080B10]" 
        style={{ opacity: activeTab === 'catalog-bot' ? 1 : 0 }}
      >
        <StarsBackground starDensity={0.0002} allStarsTwinkle={false} twinkleProbability={0.8} minTwinkleSpeed={0.5} maxTwinkleSpeed={1.5} />
        <ShootingStars minSpeed={10} maxSpeed={20} minDelay={2000} maxDelay={5000} starColor="#10b981" trailColor="#047857" />
        <NoiseTexture noiseOpacity={0.25} />
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[50%] bg-emerald-900/10 rounded-full blur-[120px] mix-blend-screen"></div>
      </div>

      {/* BACKGROUND 4: Sales Engine (Purple Dynamic Theme) */}
      <div 
        className="fixed inset-0 z-0 pointer-events-none transition-opacity duration-1000 ease-in-out bg-[#040010]" 
        style={{ opacity: activeTab === 'sales-engine' ? 1 : 0 }}
      >
        <BackgroundBeams />
        <div className="absolute inset-0 bg-gradient-to-t from-[#040010] via-transparent to-[#040010]/50"></div>
      </div>
      
      <header className="sticky top-4 z-50 w-full max-w-4xl px-4 mt-6 mb-10">
        <div className="flex items-center justify-between bg-zinc-900/60 backdrop-blur-xl border border-zinc-800 shadow-sm rounded-full px-4 py-2">
          <div className="flex items-center gap-2 pl-2 group" title="Click to copy Session URL" onClick={() => {
            const url = new URL(window.location.href);
            url.searchParams.set('session', getSessionId().replace('sess_', ''));
            navigator.clipboard.writeText(url.toString());
            alert('Session URL copied to clipboard! Open this exact link on your phone.');
          }}>
            <div className="w-6 h-6 bg-white rounded-full flex items-center justify-center cursor-pointer">
              <svg className="text-zinc-900 w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2L2 22h20L12 2z"/></svg>
            </div>
            <span className="font-semibold text-sm tracking-tight text-white hidden sm:block cursor-pointer">MerchantMesh</span>
            <span className="text-xs text-zinc-500 font-mono ml-2 hidden sm:block bg-zinc-800/50 group-hover:bg-zinc-700/80 transition-colors px-2 py-0.5 rounded-full border border-zinc-700/50 cursor-pointer">
              {getSessionId().slice(0,10)}
            </span>
          </div>

          <NavigationMenu>
            <NavigationMenuList className="gap-1">
              {navItems.map((item) => (
                <NavigationMenuItem key={item.id}>
                  <NavigationMenuLink
                    className={`${navigationMenuTriggerStyle()} h-8 px-4 py-1 text-sm bg-transparent cursor-pointer transition-all ${
                      activeTab === item.id 
                        ? 'bg-zinc-800 shadow-sm text-white font-medium rounded-full' 
                        : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50 rounded-full'
                    }`}
                    onClick={() => setActiveTab(item.id)}
                  >
                    {item.label}
                  </NavigationMenuLink>
                </NavigationMenuItem>
              ))}
            </NavigationMenuList>
          </NavigationMenu>
        </div>
      </header>

      <main className="container max-w-7xl mx-auto px-4 relative z-10 w-full flex-1 flex flex-col items-center justify-start mt-4">
        {activeTab === 'overview' && (
          <div className="w-full animate-in fade-in zoom-in-95 duration-700 pb-20">
            <TracingBeam className="px-0 md:px-6">
            
            {/* 1. HERO SECTION */}
            <motion.section initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: false, margin: "-50px" }} transition={{ duration: 0.8, ease: "easeOut" }} className="flex flex-col items-center justify-center text-center pt-10 pb-20 max-w-4xl mx-auto">
              <div className="inline-flex items-center rounded-full border border-zinc-800 bg-zinc-900/50 px-3 py-1 text-sm text-zinc-300 backdrop-blur-sm mb-6">
                <span className="flex h-2 w-2 rounded-full bg-emerald-500 mr-2 animate-pulse"></span>
                Razorpay AI Buildathon 2026
              </div>
              <h1 className="text-4xl md:text-6xl font-bold tracking-tighter text-white leading-tight mb-6">
                The Agent-to-Agent Commerce Protocol.
              </h1>
              <p className="text-zinc-400 text-lg md:text-xl max-w-2xl mx-auto mb-10 leading-relaxed">
                India is home to 63 million informal micro-merchants. MerchantMesh connects their ephemeral, invisible WhatsApp catalogs to autonomous AI buyers via Razorpay rails.
              </p>
              <div className="flex flex-col sm:flex-row items-center gap-4">
                <ShimmerButton 
                  onClick={() => setActiveTab('buyer-agent')} 
                  className="shadow-2xl"
                  background="#000000" 
                  shimmerColor="#ffffff"
                >
                  <span className="whitespace-pre-wrap text-center text-sm font-medium leading-none tracking-tight text-white lg:text-base">
                    Spawn Buyer Agent
                  </span>
                </ShimmerButton>
                <ShimmerButton 
                  onClick={() => document.getElementById('architecture')?.scrollIntoView({ behavior: 'smooth' })} 
                  className="shadow-2xl"
                  background="#000000" 
                  shimmerColor="#ffffff"
                >
                  <span className="whitespace-pre-wrap text-center text-sm font-medium leading-none tracking-tight text-white lg:text-base">
                    View Architecture
                  </span>
                </ShimmerButton>
              </div>
            </motion.section>

            {/* 2. THE STORY (5 3D CARDS ROW) */}
            <motion.section initial={{ opacity: 0, y: 40 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: false, margin: "-50px" }} transition={{ duration: 0.8, ease: "easeOut" }} className="pt-20 pb-20 w-full">
              <div className="flex flex-col mb-16 text-center items-center">
                <h4 className="text-xs font-bold text-blue-500 tracking-[0.2em] uppercase mb-4">The Journey</h4>
                <h2 className="text-3xl md:text-5xl font-bold tracking-tight text-white">We started with one problem. It kept getting bigger.</h2>
                <p className="text-zinc-400 text-sm md:text-base mt-4 max-w-xl">
                  Informal commerce didn't need a new storefront. It needed an entirely new layer of autonomous infrastructure to secure and verify intent.
                </p>
              </div>
              
              <div className="flex flex-wrap md:flex-nowrap justify-center gap-6 w-full mx-auto">
                {/* Card 1 */}
                <div className="group h-[320px] w-full md:w-[220px] [perspective:1000px]">
                  <div className="relative h-full w-full rounded-2xl transition-all duration-700 [transform-style:preserve-3d] group-hover:[transform:rotateY(180deg)] shadow-sm">
                    {/* Front */}
                    <div className="absolute inset-0 h-full w-full rounded-2xl bg-zinc-900 border border-zinc-800 p-6 [backface-visibility:hidden] flex flex-col items-center justify-between text-center gap-4">
                      <div className="flex justify-between items-center w-full">
                        <span className="text-[10px] font-mono text-emerald-400 font-bold tracking-wider uppercase">01 · Market</span>
                        <IconBrandWhatsapp className="w-4 h-4 text-zinc-600" />
                      </div>
                      <motion.div animate={{ y: [0, -8, 0] }} transition={{ repeat: Infinity, duration: 3, ease: "easeInOut" }}>
                        <IconBrandWhatsapp className="w-12 h-12 text-emerald-400" />
                      </motion.div>
                      <div>
                        <h3 className="text-base font-bold text-white mb-1">Invisible Catalogs</h3>
                        <p className="text-[10px] text-zinc-500 leading-tight">63M merchants rely on fleeting status updates.</p>
                      </div>
                    </div>
                    {/* Back */}
                    <div className="absolute inset-0 h-full w-full rounded-2xl bg-zinc-800 border border-zinc-700 p-6 [transform:rotateY(180deg)] [backface-visibility:hidden] flex flex-col items-center justify-center text-center">
                      <h3 className="text-sm font-bold text-emerald-400 mb-2 uppercase tracking-widest">No Shopify</h3>
                      <p className="text-xs text-zinc-300 leading-relaxed">Micro-merchants don't use SEO or store builders. They drop blurry photos on WhatsApp. It's a massive localized supply with zero discoverability.</p>
                    </div>
                  </div>
                </div>

                {/* Card 2 */}
                <div className="group h-[320px] w-full md:w-[220px] [perspective:1000px]">
                  <div className="relative h-full w-full rounded-2xl transition-all duration-700 [transform-style:preserve-3d] group-hover:[transform:rotateY(180deg)] shadow-sm">
                    {/* Front */}
                    <div className="absolute inset-0 h-full w-full rounded-2xl bg-zinc-900 border border-zinc-800 p-6 [backface-visibility:hidden] flex flex-col items-center justify-between text-center gap-4">
                      <div className="flex justify-between items-center w-full">
                        <span className="text-[10px] font-mono text-orange-400 font-bold tracking-wider uppercase">02 · Friction</span>
                        <IconMessages className="w-4 h-4 text-zinc-600" />
                      </div>
                      <motion.div animate={{ scale: [1, 1.1, 1] }} transition={{ repeat: Infinity, duration: 2.5, ease: "easeInOut" }}>
                        <IconMessages className="w-12 h-12 text-orange-400" />
                      </motion.div>
                      <div>
                        <h3 className="text-base font-bold text-white mb-1">Manual Exhaustion</h3>
                        <p className="text-[10px] text-zinc-500 leading-tight">Buyers must DM dozens of sellers manually.</p>
                      </div>
                    </div>
                    {/* Back */}
                    <div className="absolute inset-0 h-full w-full rounded-2xl bg-zinc-800 border border-zinc-700 p-6 [transform:rotateY(180deg)] [backface-visibility:hidden] flex flex-col items-center justify-center text-center">
                      <h3 className="text-sm font-bold text-orange-400 mb-2 uppercase tracking-widest">Slow Haggling</h3>
                      <p className="text-xs text-zinc-300 leading-relaxed">To find the best price, a buyer has to DM 10 different sellers, negotiate base prices, and wait hours for replies while inventory disappears.</p>
                    </div>
                  </div>
                </div>

                {/* Card 3 */}
                <div className="group h-[320px] w-full md:w-[220px] [perspective:1000px]">
                  <div className="relative h-full w-full rounded-2xl transition-all duration-700 [transform-style:preserve-3d] group-hover:[transform:rotateY(180deg)] shadow-sm">
                    {/* Front */}
                    <div className="absolute inset-0 h-full w-full rounded-2xl bg-zinc-900 border border-zinc-800 p-6 [backface-visibility:hidden] flex flex-col items-center justify-between text-center gap-4">
                      <div className="flex justify-between items-center w-full">
                        <span className="text-[10px] font-mono text-red-400 font-bold tracking-wider uppercase">03 · Risk</span>
                        <IconShieldCheck className="w-4 h-4 text-zinc-600" />
                      </div>
                      <motion.div animate={{ rotate: [0, 5, -5, 0] }} transition={{ repeat: Infinity, duration: 4 }}>
                        <IconShieldCheck className="w-12 h-12 text-red-400" />
                      </motion.div>
                      <div>
                        <h3 className="text-base font-bold text-white mb-1">The Trust Gap</h3>
                        <p className="text-[10px] text-zinc-500 leading-tight">Paying strangers via UPI with no guarantee.</p>
                      </div>
                    </div>
                    {/* Back */}
                    <div className="absolute inset-0 h-full w-full rounded-2xl bg-zinc-800 border border-zinc-700 p-6 [transform:rotateY(180deg)] [backface-visibility:hidden] flex flex-col items-center justify-center text-center">
                      <h3 className="text-sm font-bold text-red-400 mb-2 uppercase tracking-widest">No Buyer Guard</h3>
                      <p className="text-xs text-zinc-300 leading-relaxed">Even if they agree on a price, transferring money directly requires immense trust. Scams and ghosting kill conversions in informal markets.</p>
                    </div>
                  </div>
                </div>

                {/* Card 4 */}
                <div className="group h-[320px] w-full md:w-[220px] [perspective:1000px]">
                  <div className="relative h-full w-full rounded-2xl transition-all duration-700 [transform-style:preserve-3d] group-hover:[transform:rotateY(180deg)] shadow-sm">
                    {/* Front */}
                    <div className="absolute inset-0 h-full w-full rounded-2xl bg-zinc-900 border border-zinc-800 p-6 [backface-visibility:hidden] flex flex-col items-center justify-between text-center gap-4">
                      <div className="flex justify-between items-center w-full">
                        <span className="text-[10px] font-mono text-purple-400 font-bold tracking-wider uppercase">04 · Solution</span>
                        <IconRobot className="w-4 h-4 text-zinc-600" />
                      </div>
                      <motion.div animate={{ y: [0, -5, 0], scale: [1, 1.05, 1] }} transition={{ repeat: Infinity, duration: 3 }}>
                        <IconRobot className="w-12 h-12 text-purple-400" />
                      </motion.div>
                      <div>
                        <h3 className="text-base font-bold text-white mb-1">AI Matchmaking</h3>
                        <p className="text-[10px] text-zinc-500 leading-tight">What if code did the haggling for you?</p>
                      </div>
                    </div>
                    {/* Back */}
                    <div className="absolute inset-0 h-full w-full rounded-2xl bg-zinc-800 border border-zinc-700 p-6 [transform:rotateY(180deg)] [backface-visibility:hidden] flex flex-col items-center justify-center text-center">
                      <h3 className="text-sm font-bold text-purple-400 mb-2 uppercase tracking-widest">Parallel Agents</h3>
                      <p className="text-xs text-zinc-300 leading-relaxed">MerchantMesh spawns parallel AI agents to instantly negotiate with every local seller at once, relentlessly driving prices down to the true market floor.</p>
                    </div>
                  </div>
                </div>

                {/* Card 5 */}
                <div className="group h-[320px] w-full md:w-[220px] [perspective:1000px]">
                  <div className="relative h-full w-full rounded-2xl transition-all duration-700 [transform-style:preserve-3d] group-hover:[transform:rotateY(180deg)] shadow-sm">
                    {/* Front */}
                    <div className="absolute inset-0 h-full w-full rounded-2xl bg-zinc-900 border border-zinc-800 p-6 [backface-visibility:hidden] flex flex-col items-center justify-between text-center gap-4">
                      <div className="flex justify-between items-center w-full">
                        <span className="text-[10px] font-mono text-blue-400 font-bold tracking-wider uppercase">05 · Trust</span>
                        <IconBuildingBank className="w-4 h-4 text-zinc-600" />
                      </div>
                      <motion.div animate={{ rotateY: [0, 180, 360] }} transition={{ repeat: Infinity, duration: 4, ease: "linear" }}>
                        <IconBuildingBank className="w-12 h-12 text-blue-400" />
                      </motion.div>
                      <div>
                        <h3 className="text-base font-bold text-white mb-1">Automated Split Settlement</h3>
                        <p className="text-[10px] text-zinc-500 leading-tight">Code-enforced trust via Razorpay Route.</p>
                      </div>
                    </div>
                    {/* Back */}
                    <div className="absolute inset-0 h-full w-full rounded-2xl bg-zinc-800 border border-zinc-700 p-6 [transform:rotateY(180deg)] [backface-visibility:hidden] flex flex-col items-center justify-center text-center">
                      <h3 className="text-sm font-bold text-blue-400 mb-2 uppercase tracking-widest">Split Settlement</h3>
                      <p className="text-xs text-zinc-300 leading-relaxed">Once the AI locks in the lowest bid, Razorpay routes the funds, taking our 2% cut without human intervention.</p>
                    </div>
                  </div>
                </div>
              </div>
            </motion.section>

            {/* 3. ARCHITECTURE (ACCURATE BACKEND WORKFLOW) */}
            <motion.section initial={{ opacity: 0, scale: 0.95 }} whileInView={{ opacity: 1, scale: 1 }} viewport={{ once: false, margin: "-50px" }} transition={{ duration: 0.8, ease: "easeOut" }} id="architecture" className="pt-20 pb-20 w-full flex flex-col items-center">
              <div className="flex flex-col mb-16 text-center items-center">
                <h4 className="text-xs font-bold text-emerald-500 tracking-[0.2em] uppercase mb-4">Architecture</h4>
                <h2 className="text-3xl md:text-5xl font-bold tracking-tight text-white">One network. Infinite connections.</h2>
                <p className="text-zinc-400 text-sm mt-4 max-w-lg">
                  Hover over the nodes to see exactly how the LangGraph orchestrator secures the AI transaction layer.
                </p>
              </div>
              
              <div className="relative flex w-full max-w-4xl mx-auto h-[400px] items-center justify-between px-2 sm:px-10 scale-[0.6] sm:scale-75 md:scale-90 lg:scale-100 origin-center" ref={containerRef}>
                {/* Left Col (Inputs) */}
                <div className="flex flex-col justify-center gap-16 h-full py-10 relative z-10">
                  
                  <div className="z-10 relative">
                    <HoverCard delay={0} closeDelay={0}>
                      <HoverCardTrigger asChild>
                        <div ref={div1Ref} className="relative h-14 w-14 rounded-2xl border border-zinc-700 p-[1px] shadow-xl cursor-help group">
                          <GlowingEffect blur={0} spread={40} glow={true} disabled={false} proximity={64} inactiveZone={0.01} borderWidth={2} />
                          <div className="relative flex h-full w-full items-center justify-center rounded-[14px] bg-zinc-900 overflow-hidden z-10">
                            <IconBrandWhatsapp className="h-6 w-6 text-green-400" />
                          </div>
                        </div>
                      </HoverCardTrigger>
                      <HoverCardContent side="left" align="center" sideOffset={16} className="w-64 bg-zinc-900 border-zinc-700 shadow-2xl">
                        <h4 className="text-xs font-bold text-green-400 mb-1 uppercase tracking-widest">WhatsApp UI</h4>
                        <p className="text-[11px] text-zinc-300">Merchant's native interface for both inventory ingestion (Catalog Agent) and active negotiation (Sales Agent).</p>
                      </HoverCardContent>
                    </HoverCard>
                    <span className="absolute -left-32 top-1/2 -translate-y-1/2 text-xs font-semibold text-zinc-500 whitespace-nowrap hidden md:block">WhatsApp Seller</span>
                  </div>

                  <div className="z-10 relative">
                    <HoverCard delay={0} closeDelay={0}>
                      <HoverCardTrigger asChild>
                        <div ref={div2Ref} className="relative h-14 w-14 rounded-2xl border border-zinc-700 p-[1px] shadow-xl cursor-help group">
                          <GlowingEffect blur={0} spread={40} glow={true} disabled={false} proximity={64} inactiveZone={0.01} borderWidth={2} />
                          <div className="relative flex h-full w-full items-center justify-center rounded-[14px] bg-zinc-900 overflow-hidden z-10">
                            <IconUserSearch className="h-6 w-6 text-blue-400" />
                          </div>
                        </div>
                      </HoverCardTrigger>
                      <HoverCardContent side="left" align="center" sideOffset={16} className="w-64 bg-zinc-900 border-zinc-700 shadow-2xl">
                        <h4 className="text-xs font-bold text-blue-400 mb-1 uppercase tracking-widest">Buyer RFQ</h4>
                        <p className="text-[11px] text-zinc-300">The buyer's natural language procurement request (e.g. "Find me 500 white tees under ₹200").</p>
                      </HoverCardContent>
                    </HoverCard>
                    <span className="absolute -left-32 top-1/2 -translate-y-1/2 text-xs font-semibold text-zinc-500 whitespace-nowrap hidden md:block">Buyer RFQ</span>
                  </div>
                </div>

                {/* Col 2: The Agents */}
                <div className="flex flex-col justify-between gap-16 h-full py-10 relative z-10">
                  <div className="z-10 relative">
                    <HoverCard delay={0} closeDelay={0}>
                      <HoverCardTrigger asChild>
                        <div ref={divCatalogRef} className="relative h-16 w-16 rounded-2xl border border-green-500/40 p-[1px] shadow-[0_0_30px_-5px_rgba(34,197,94,0.3)] cursor-help group">
                          <GlowingEffect blur={0} spread={40} glow={true} disabled={false} proximity={64} inactiveZone={0.01} borderWidth={2} />
                          <div className="relative flex h-full w-full items-center justify-center rounded-[14px] bg-zinc-900 z-10">
                            <IconRobot className="h-7 w-7 text-green-400" />
                          </div>
                          <span className="absolute -top-8 left-1/2 -translate-x-1/2 text-[10px] font-bold tracking-widest text-green-400 uppercase whitespace-nowrap">Catalog Agent</span>
                        </div>
                      </HoverCardTrigger>
                      <HoverCardContent side="top" align="center" sideOffset={12} className="w-64 bg-zinc-900 border-zinc-700 shadow-2xl">
                        <h4 className="text-xs font-bold text-green-400 mb-1 uppercase tracking-widest">Catalog Agent</h4>
                        <p className="text-[11px] text-zinc-300">Extracts multimodal product data (images/text) from WhatsApp into structured SQLite databases.</p>
                      </HoverCardContent>
                    </HoverCard>
                  </div>

                  <div className="z-10 relative">
                    <HoverCard delay={0} closeDelay={0}>
                      <HoverCardTrigger asChild>
                        <div ref={divSalesRef} className="relative h-16 w-16 rounded-2xl border border-yellow-500/40 p-[1px] shadow-[0_0_30px_-5px_rgba(234,179,8,0.3)] cursor-help group">
                          <GlowingEffect blur={0} spread={40} glow={true} disabled={false} proximity={64} inactiveZone={0.01} borderWidth={2} />
                          <div className="relative flex h-full w-full items-center justify-center rounded-[14px] bg-zinc-900 z-10">
                            <IconRobot className="h-7 w-7 text-yellow-400" />
                          </div>
                          <span className="absolute -left-28 top-1/2 -translate-y-1/2 text-[10px] font-bold tracking-widest text-yellow-400 uppercase whitespace-nowrap hidden md:block">Sales Agent</span>
                        </div>
                      </HoverCardTrigger>
                      <HoverCardContent side="top" align="center" sideOffset={12} className="w-64 bg-zinc-900 border-zinc-700 shadow-2xl">
                        <h4 className="text-xs font-bold text-yellow-400 mb-1 uppercase tracking-widest">Sales Agent</h4>
                        <p className="text-[11px] text-zinc-300">Negotiates on behalf of the seller, balancing profit margins with real-time inventory clearance goals.</p>
                      </HoverCardContent>
                    </HoverCard>
                  </div>

                  <div className="z-10 relative">
                    <HoverCard delay={0} closeDelay={0}>
                      <HoverCardTrigger asChild>
                        <div ref={divBuyerRef} className="relative h-16 w-16 rounded-2xl border border-blue-500/40 p-[1px] shadow-[0_0_30px_-5px_rgba(59,130,246,0.3)] cursor-help group">
                          <GlowingEffect blur={0} spread={40} glow={true} disabled={false} proximity={64} inactiveZone={0.01} borderWidth={2} />
                          <div className="relative flex h-full w-full items-center justify-center rounded-[14px] bg-zinc-900 z-10">
                            <IconRobot className="h-7 w-7 text-blue-400" />
                          </div>
                          <span className="absolute -bottom-8 left-1/2 -translate-x-1/2 text-[10px] font-bold tracking-widest text-blue-400 uppercase whitespace-nowrap">Buyer Agent</span>
                        </div>
                      </HoverCardTrigger>
                      <HoverCardContent side="bottom" align="center" sideOffset={12} className="w-64 bg-zinc-900 border-zinc-700 shadow-2xl">
                        <h4 className="text-xs font-bold text-blue-400 mb-1 uppercase tracking-widest">Buyer Agent</h4>
                        <p className="text-[11px] text-zinc-300">Translates natural language RFQs into deterministic search queries and haggles vendors for the lowest floor price.</p>
                      </HoverCardContent>
                    </HoverCard>
                  </div>
                </div>

                {/* Col 3: Supervisor */}
                <div className="flex flex-col justify-center h-full relative z-10 px-8">
                  <div className="z-10 relative">
                    <HoverCard delay={0} closeDelay={0}>
                      <HoverCardTrigger asChild>
                        <div ref={div4Ref} className="relative h-28 w-28 rounded-[2rem] border border-purple-500/50 p-[1px] shadow-[0_0_50px_-5px_rgba(168,85,247,0.5)] cursor-help">
                          <GlowingEffect blur={0} spread={60} glow={true} disabled={false} proximity={80} inactiveZone={0.01} borderWidth={2} />
                          <div className="relative flex h-full w-full items-center justify-center rounded-[30px] bg-black z-10">
                            <IconRobot className="h-12 w-12 text-purple-400" />
                          </div>
                          <span className="absolute -bottom-10 left-1/2 -translate-x-1/2 text-[11px] font-bold tracking-widest text-purple-400 uppercase whitespace-nowrap">LangGraph Supervisor</span>
                        </div>
                      </HoverCardTrigger>
                      <HoverCardContent side="bottom" align="center" sideOffset={12} className="w-72 bg-zinc-900 border-zinc-700 shadow-2xl">
                        <h4 className="text-[10px] font-bold text-purple-400 mb-2 flex items-center gap-2 uppercase tracking-widest">LangGraph Supervisor</h4>
                        <p className="text-xs text-zinc-300 leading-relaxed">The central orchestrator routing tasks between agents.</p>
                      </HoverCardContent>
                    </HoverCard>
                  </div>
                </div>

                {/* Right Col (Outputs) */}
                <div className="flex flex-col justify-between gap-10 h-full py-0 relative z-10">
                  
                  <div className="z-10 relative">
                    <HoverCard delay={0} closeDelay={0}>
                      <HoverCardTrigger asChild>
                        <div ref={div5Ref} className="relative h-14 w-14 rounded-2xl border border-zinc-700 p-[1px] shadow-xl cursor-help group">
                          <GlowingEffect blur={0} spread={40} glow={true} disabled={false} proximity={64} inactiveZone={0.01} borderWidth={2} />
                          <div className="relative flex h-full w-full items-center justify-center rounded-[14px] bg-zinc-900 overflow-hidden z-10">
                            <IconDatabase className="h-6 w-6 text-zinc-400" />
                          </div>
                        </div>
                      </HoverCardTrigger>
                      <HoverCardContent side="left" align="center" className="w-64 bg-zinc-900 border-zinc-700 shadow-2xl">
                        <h4 className="text-xs font-bold text-zinc-400 mb-1 uppercase tracking-widest">SQLite Locks</h4>
                        <p className="text-[11px] text-zinc-300">Atomic locks prevent double-spending.</p>
                      </HoverCardContent>
                    </HoverCard>
                    <span className="absolute -right-32 top-1/2 -translate-y-1/2 text-[11px] font-semibold text-zinc-500 whitespace-nowrap hidden md:block">SQLite Data</span>
                  </div>
                  
                  <div className="z-10 relative">
                    <HoverCard delay={0} closeDelay={0}>
                      <HoverCardTrigger asChild>
                        <div ref={div6Ref} className="relative h-14 w-14 rounded-2xl border border-zinc-700 p-[1px] shadow-xl cursor-help group">
                          <GlowingEffect blur={0} spread={40} glow={true} disabled={false} proximity={64} inactiveZone={0.01} borderWidth={2} />
                          <div className="relative flex h-full w-full items-center justify-center rounded-[14px] bg-zinc-900 overflow-hidden z-10">
                            <IconShieldCheck className="h-6 w-6 text-red-400" />
                          </div>
                        </div>
                      </HoverCardTrigger>
                      <HoverCardContent side="left" align="center" className="w-64 bg-zinc-900 border-zinc-700 shadow-2xl">
                        <h4 className="text-xs font-bold text-red-400 mb-1 uppercase tracking-widest">Trust Agent</h4>
                        <p className="text-[11px] text-zinc-300">Python guardrails ensuring margin safety.</p>
                      </HoverCardContent>
                    </HoverCard>
                    <span className="absolute -right-32 top-1/2 -translate-y-1/2 text-[11px] font-semibold text-zinc-500 whitespace-nowrap hidden md:block">Python Guardrails</span>
                  </div>

                  {/* MCP SERVER */}
                  <div className="z-10 relative">
                    <HoverCard delay={0} closeDelay={0}>
                      <HoverCardTrigger asChild>
                        <div ref={divMcpRef} className="relative h-14 w-14 rounded-2xl border border-zinc-700 p-[1px] shadow-xl cursor-help group">
                          <GlowingEffect blur={0} spread={40} glow={true} disabled={false} proximity={64} inactiveZone={0.01} borderWidth={2} />
                          <div className="relative flex h-full w-full items-center justify-center rounded-[14px] bg-zinc-900 overflow-hidden z-10">
                            <IconServer className="h-6 w-6 text-cyan-400" />
                          </div>
                        </div>
                      </HoverCardTrigger>
                      <HoverCardContent side="left" align="center" className="w-64 bg-zinc-900 border-zinc-700 shadow-2xl">
                        <h4 className="text-xs font-bold text-cyan-400 mb-1 uppercase tracking-widest">MCP Server</h4>
                        <p className="text-[11px] text-zinc-300">Model Context Protocol server exposing real-time APIs to the LangGraph agents.</p>
                      </HoverCardContent>
                    </HoverCard>
                    <span className="absolute -right-32 top-1/2 -translate-y-1/2 text-[11px] font-semibold text-cyan-500 whitespace-nowrap hidden md:block">MCP Server</span>
                  </div>

                  <div className="z-10 relative">
                    <HoverCard delay={0} closeDelay={0}>
                      <HoverCardTrigger asChild>
                        <div ref={div7Ref} className="relative h-14 w-14 rounded-2xl border border-zinc-700 p-[1px] shadow-xl cursor-help group">
                          <GlowingEffect blur={0} spread={40} glow={true} disabled={false} proximity={64} inactiveZone={0.01} borderWidth={2} />
                          <div className="relative flex h-full w-full items-center justify-center rounded-[14px] bg-zinc-900 overflow-hidden z-10">
                            <IconReceipt2 className="h-6 w-6 text-orange-400" />
                          </div>
                        </div>
                      </HoverCardTrigger>
                      <HoverCardContent side="left" align="center" className="w-64 bg-zinc-900 border-zinc-700 shadow-2xl">
                        <h4 className="text-[10px] font-bold text-orange-400 mb-2 uppercase tracking-widest">Route API</h4>
                        <p className="text-[11px] text-zinc-300">Razorpay Route payment splitting.</p>
                      </HoverCardContent>
                    </HoverCard>
                    <span className="absolute -right-32 top-1/2 -translate-y-1/2 text-[11px] font-bold text-orange-400 whitespace-nowrap hidden md:block">Razorpay Route</span>
                  </div>
                </div>

                {/* Beams */}
                {/* Users -> Agents */}
                <AnimatedBeam containerRef={containerRef} fromRef={div1Ref} toRef={divCatalogRef} curvature={-20} gradientStartColor="#4ade80" gradientStopColor="#4ade80" delay={0} pathWidth={4} pathOpacity={0.6} />
                <AnimatedBeam containerRef={containerRef} fromRef={div1Ref} toRef={divSalesRef} curvature={20} gradientStartColor="#4ade80" gradientStopColor="#facc15" delay={0.5} pathWidth={4} pathOpacity={0.6} />
                <AnimatedBeam containerRef={containerRef} fromRef={div2Ref} toRef={divBuyerRef} curvature={20} gradientStartColor="#60a5fa" gradientStopColor="#60a5fa" delay={1} pathWidth={4} pathOpacity={0.6} />
                
                {/* Agents -> Supervisor */}
                <AnimatedBeam containerRef={containerRef} fromRef={divCatalogRef} toRef={div4Ref} curvature={40} gradientStartColor="#4ade80" gradientStopColor="#c084fc" delay={0.5} pathWidth={4} pathOpacity={0.6} />
                <AnimatedBeam containerRef={containerRef} fromRef={divSalesRef} toRef={div4Ref} curvature={0} gradientStartColor="#facc15" gradientStopColor="#c084fc" delay={1} pathWidth={4} pathOpacity={0.6} />
                <AnimatedBeam containerRef={containerRef} fromRef={divBuyerRef} toRef={div4Ref} curvature={-40} gradientStartColor="#60a5fa" gradientStopColor="#c084fc" delay={1.5} pathWidth={4} pathOpacity={0.6} />

                {/* Supervisor -> Output */}
                <AnimatedBeam containerRef={containerRef} fromRef={div4Ref} toRef={div5Ref} curvature={-40} gradientStartColor="#c084fc" gradientStopColor="#a1a1aa" delay={2} pathWidth={4} pathOpacity={0.6} />
                <AnimatedBeam containerRef={containerRef} fromRef={div4Ref} toRef={div6Ref} curvature={-15} gradientStartColor="#c084fc" gradientStopColor="#f87171" delay={2.3} pathWidth={4} pathOpacity={0.6} />
                <AnimatedBeam containerRef={containerRef} fromRef={div4Ref} toRef={divMcpRef} curvature={15} gradientStartColor="#c084fc" gradientStopColor="#22d3ee" delay={2.6} pathWidth={4} pathOpacity={0.6} />
                <AnimatedBeam containerRef={containerRef} fromRef={div4Ref} toRef={div7Ref} curvature={40} gradientStartColor="#c084fc" gradientStopColor="#fb923c" delay={3} pathWidth={4} pathOpacity={0.6} />
              </div>
            </motion.section>

            {/* 4. BENTO GRID (LIVE ECONOMICS) */}
            <motion.section initial={{ opacity: 0, y: 40 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: false, margin: "-50px" }} transition={{ duration: 0.8, ease: "easeOut", staggerChildren: 0.2 }} className="pt-20 pb-20 max-w-4xl mx-auto">
              <div className="flex flex-col mb-12 text-center items-center">
                <h2 className="text-3xl font-bold tracking-tight text-white">Core Agentic Architecture</h2>
                <p className="text-zinc-400 text-sm mt-2 max-w-lg">
                  Watch our multimodal AI parse chaotic WhatsApp drops while autonomous buyer and seller agents negotiate deals in real-time.
                </p>
              </div>
              <BentoGrid className="mx-auto">
                {metrics.map((item, i) => (
                  <BentoGridItem
                    key={i}
                    title={item.title}
                    description={item.description}
                    header={item.header}
                    icon={item.icon}
                    className={item.className}
                  />
                ))}
              </BentoGrid>
            </motion.section>

            </TracingBeam>
          </div>
        )}
        

        {activeTab === 'buyer-agent' && (
          <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, delay: 0.4, ease: "easeOut" }} className="w-full flex flex-col lg:flex-row gap-6 min-h-[600px] relative">


            {/* LEFT: Main Chat Window */}
            <div className="flex-[2] flex flex-col bg-white/5 backdrop-blur-xl border border-white/10 rounded-3xl overflow-hidden relative shadow-[0_8px_32px_0_rgba(0,0,0,0.36)] h-[80vh]">
              {/* Header */}
              <div className="h-16 border-b border-white/10 bg-white/5 flex items-center px-6 justify-between shrink-0 shadow-sm">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-purple-500/20 border border-purple-500/50 flex items-center justify-center">
                    <IconRobot className="w-4 h-4 text-purple-400" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-white text-sm">Buyer Multi-Agent System</h3>
                    <p className="text-xs text-zinc-400 flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                      Online & Ready
                    </p>
                  </div>
                </div>
                <button 
                  onClick={() => {
                    setChatMessages([{ role: 'ai', text: "Hello! I am your MerchantMesh Buyer Agent. Tell me what you're looking for, and I'll spawn parallel threads to haggle with local WhatsApp sellers for you." }]);
                    setDealOptions([]);
                    setPendingOrderId(null);
                    setAuctionResult(null);
                    setFullAuctionResult(null);
                    setVisualizerPhase(0);
                    setVisualizerLogs([]);
                    setIsHaggling(false);
                  }}
                  className="text-xs text-zinc-500 hover:text-white transition-colors px-3 py-1.5 rounded-full border border-white/10 hover:border-white/20 hover:bg-white/5"
                >
                  New Chat
                </button>
              </div>

              {/* Message Scroll Area */}
              <div className="flex-1 overflow-y-auto p-6 space-y-6 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none] pb-32">
                {chatMessages.map((msg, idx) => (
                  <div key={idx} className={`flex w-full ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`flex gap-3 max-w-[80%] ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                      
                      {/* Avatar */}
                      <div className={`w-8 h-8 rounded-full flex shrink-0 items-center justify-center ${msg.role === 'user' ? 'bg-white/10 border border-white/20' : 'bg-purple-500/20 border border-purple-500/50'}`}>
                        {msg.role === 'user' ? <IconUserSearch className="w-4 h-4 text-white" /> : <IconRobot className="w-4 h-4 text-purple-400" />}
                      </div>

                      {/* Bubble */}
                      <div className={`p-4 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap break-words ${
                        msg.role === 'user' 
                          ? 'bg-white/10 text-white backdrop-blur-md border border-white/10 shadow-sm rounded-tr-sm' 
                          : 'bg-white/5 border border-white/10 text-zinc-200 rounded-tl-sm'
                      }`}>
                        {msg.text}
                        {msg.paymentLink && (
                          <a 
                            href={msg.paymentLink} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="mt-3 w-full py-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-center transition-all shadow-[0_0_15px_rgba(59,130,246,0.4)] flex items-center justify-center gap-2 no-underline"
                          >
                             Pay Now with Razorpay
                          </a>
                        )}
                      </div>

                    </div>
                  </div>
                ))}

                {isHaggling && (
                  <div className="flex w-full justify-start">
                    <div className="flex gap-3 max-w-[80%] flex-row">
                      <div className="w-8 h-8 rounded-full bg-purple-500/20 border border-purple-500/50 flex shrink-0 items-center justify-center">
                        <IconRobot className="w-4 h-4 text-purple-400" />
                      </div>
                      <div className="p-4 rounded-2xl bg-white/5 border border-white/10 text-zinc-400 rounded-tl-sm flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-zinc-500 animate-bounce"></span>
                        <span className="w-2 h-2 rounded-full bg-zinc-500 animate-bounce" style={{ animationDelay: '0.2s' }}></span>
                        <span className="w-2 h-2 rounded-full bg-zinc-500 animate-bounce" style={{ animationDelay: '0.4s' }}></span>
                      </div>
                    </div>
                  </div>
                )}

                {dealOptions.length > 0 && !pendingOrderId && (
                  <div className="flex w-full justify-start pt-2 pb-6">
                    <div className="flex flex-col gap-3 w-full max-w-md">
                      {dealOptions.map((w, i) => {
                        const savings = w.original_price ? w.original_price - w.final_price : 0;
                        const savingsPct = w.original_price ? Math.round((savings / w.original_price) * 100) : 0;
                        return (
                          <div key={i} className="bg-white/5 border border-white/20 p-4 rounded-xl flex items-center justify-between hover:bg-white/10 transition-colors cursor-pointer" onClick={() => { setSelectedDealView(w); setActiveImageIdx(0); }}>
                            <div className="flex items-center gap-4">
                              {w.image_path ? (
                                <img src={w.image_path} alt={w.product_name} className="w-16 h-16 object-cover rounded-lg bg-zinc-800" />
                              ) : (
                                <div className="w-16 h-16 bg-zinc-800 rounded-lg flex items-center justify-center">
                                  <span className="text-zinc-600 text-xs">No Image</span>
                                </div>
                              )}
                              <div>
                                <div className="font-semibold text-white text-sm">{w.merchant_name || 'Local Seller'}</div>
                                <div className="text-[10px] text-zinc-300 line-clamp-1">{w.product_name}</div>
                                <div className="text-[10px] text-zinc-400 mt-1">Score: {w.reliability_score?.toFixed(1) || '5.0'} ⭐ | {w.latency_ms}ms response</div>
                                <div className="text-sm font-bold text-emerald-400 mt-1">₹{w.final_price} <span className="text-xs line-through text-zinc-500 font-normal">₹{w.original_price}</span></div>
                              </div>
                            </div>
                            <button onClick={(e) => { e.stopPropagation(); handleSelectDeal(w); }} className="px-3 py-1.5 bg-purple-500/20 text-purple-300 rounded-lg text-xs font-medium border border-purple-500/30 hover:bg-purple-500/40 ml-4 shrink-0 cursor-pointer">
                              Select
                            </button>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}

                {pendingOrderId && !chatMessages.some(m => m.paymentLink) && (
                  <div className="flex w-full justify-center pt-4 pb-10">
                    <div className="bg-white/10 backdrop-blur-xl border border-white/20 rounded-2xl p-6 w-full max-w-sm shadow-2xl animate-in zoom-in-95 duration-500">
                      <div className="flex items-center gap-3 mb-4">
                        <div className="w-10 h-10 rounded-full bg-orange-500/20 flex items-center justify-center border border-orange-500/30">
                          <IconLock className="w-5 h-5 text-orange-400" />
                        </div>
                        <div>
                          <h4 className="font-bold text-white">Awaiting Merchant</h4>
                          <p className="text-xs text-zinc-400">Order sent to {auctionResult?.merchant_name}</p>
                        </div>
                      </div>
                      <p className="text-sm text-zinc-300 mb-6">
                        The order is locked in SQLite and waiting for the merchant to confirm stock availability via the Sales Bot window.
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {/* Input Area (Pro Prompt-Kit Inspired) */}
              <div className="absolute bottom-0 w-full p-4 bg-gradient-to-t from-[#080B10] via-[#080B10]/90 to-transparent pt-16">
                <ProChatInput 
                  placeholder="I need 500 white cotton t-shirts under ₹150..."
                  onSubmit={handleChatSubmit}
                />
              </div>
            </div>

            {/* RIGHT: Agent Brain (Neural Swarm Visualizer) */}
            <div className="flex-[2] flex flex-col shadow-[0_8px_32px_0_rgba(0,0,0,0.36)] relative h-[80vh]">
               <ReverseAuctionVisualizer phaseOverride={visualizerPhase} auctionResult={fullAuctionResult} logsOverride={visualizerLogs} />
            </div>
          </motion.div>
        )}

        {activeTab === 'catalog-bot' && (
          <CatalogBotTab 
            activeMerchantId={catalogMerchantId} 
            merchantsList={merchantsList}
            onMerchantChange={handleCatalogMerchantChange}
            onUpdateMerchantName={(id, newName) => {
               setMerchantsList(prev => prev.map(m => m.id === id ? { ...m, name: newName } : m));
            }}
          />
        )}

        {activeTab === 'inventory' && (
          <InventoryTab 
            activeMerchantId={catalogMerchantId} 
            merchantsList={merchantsList}
            onMerchantChange={handleCatalogMerchantChange}
          />
        )}

        {activeTab === 'sales-engine' && (
          <SalesBotEngineTab 
            activeMerchantId={salesMerchantId} 
            merchantsList={merchantsList}
            onMerchantChange={handleSalesMerchantChange}
          />
        )}

        {/* Product Detail Modal Overlay */}
        <AnimatePresence>
          {selectedDealView && (
            <motion.div 
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
              onClick={() => setSelectedDealView(null)}
            >
              <motion.div 
                initial={{ scale: 0.95, y: 20 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.95, y: 20 }}
                className="bg-[#1a202c] border border-white/10 rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl flex flex-col"
                onClick={e => e.stopPropagation()}
              >
                {/* Header */}
                <div className="flex justify-between items-center p-4 border-b border-white/10 bg-[#2d3748]/50">
                  <h3 className="font-semibold text-white text-lg line-clamp-1">{selectedDealView.product_name}</h3>
                  <IconX className="w-6 h-6 text-zinc-400 cursor-pointer hover:text-white" onClick={() => setSelectedDealView(null)} />
                </div>
                
                {/* Content */}
                <div className="p-6 overflow-y-auto max-h-[70vh]">
                  {/* Fake Image Carousel */}
                  <div className="relative w-full aspect-square bg-zinc-800 rounded-xl mb-6 overflow-hidden flex items-center justify-center border border-white/5 shadow-inner">
                    {selectedDealView.image_path ? (
                      <motion.img 
                        key={activeImageIdx}
                        initial={{ opacity: 0, scale: 1.05 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.3 }}
                        src={selectedDealView.image_path} 
                        alt="Product" 
                        className={`w-full h-full object-cover ${activeImageIdx === 1 ? 'scale-110 grayscale-[20%]' : activeImageIdx === 2 ? 'scale-125 saturate-150' : ''}`} 
                      />
                    ) : (
                      <span className="text-zinc-500 font-medium">No Image Available</span>
                    )}
                    
                    {/* Carousel Indicators */}
                    {selectedDealView.image_path && (
                      <div className="absolute bottom-4 left-0 right-0 flex justify-center gap-2">
                        {[0, 1, 2].map(idx => (
                          <div 
                            key={idx} 
                            onClick={() => setActiveImageIdx(idx)}
                            className={`w-2 h-2 rounded-full cursor-pointer transition-all ${activeImageIdx === idx ? 'bg-emerald-400 w-4' : 'bg-white/40 hover:bg-white/60'}`} 
                          />
                        ))}
                      </div>
                    )}
                  </div>
                  
                  {/* Details Grid */}
                  <div className="grid grid-cols-2 gap-4 mb-6">
                    <div className="bg-white/5 rounded-xl p-3 border border-white/5">
                      <div className="text-[10px] text-zinc-400 uppercase tracking-wider font-semibold mb-1">Merchant</div>
                      <div className="text-white font-medium text-sm flex items-center gap-2">
                        {selectedDealView.merchant_name || 'Local Seller'}
                        <span className="text-xs bg-emerald-500/20 text-emerald-400 px-1.5 py-0.5 rounded border border-emerald-500/30">
                          {selectedDealView.reliability_score?.toFixed(1) || '5.0'} ⭐
                        </span>
                      </div>
                    </div>
                    <div className="bg-white/5 rounded-xl p-3 border border-white/5">
                      <div className="text-[10px] text-zinc-400 uppercase tracking-wider font-semibold mb-1">Availability</div>
                      <div className="text-white font-medium text-sm">
                        {selectedDealView.stock_quantity || 'In Stock'}
                      </div>
                    </div>
                  </div>
                  
                  {/* Price Breakdown */}
                  <div className="bg-emerald-500/10 rounded-xl p-4 border border-emerald-500/20 mb-2">
                    <div className="flex justify-between items-end mb-2">
                      <div className="text-xs text-zinc-300 font-medium">AI Negotiated Deal</div>
                      <div className="text-right">
                        <div className="text-xs line-through text-zinc-500 mb-0.5">₹{selectedDealView.original_price}</div>
                        <div className="text-2xl font-bold text-emerald-400 leading-none">₹{selectedDealView.final_price}</div>
                      </div>
                    </div>
                    {selectedDealView.original_price > selectedDealView.final_price && (
                      <div className="w-full bg-emerald-500/20 py-1.5 rounded text-center text-xs text-emerald-300 font-semibold mt-3 border border-emerald-500/30">
                        You save ₹{selectedDealView.original_price - selectedDealView.final_price}!
                      </div>
                    )}
                  </div>
                </div>
                
                {/* Footer Actions */}
                <div className="p-4 border-t border-white/10 bg-[#2d3748]/50 flex gap-3">
                  <button 
                    onClick={() => setSelectedDealView(null)}
                    className="flex-1 py-3 rounded-xl bg-white/5 hover:bg-white/10 text-white font-medium transition-colors"
                  >
                    Cancel
                  </button>
                  <button 
                    onClick={() => {
                      setSelectedDealView(null);
                      handleSelectDeal(selectedDealView);
                    }}
                    className="flex-[2] py-3 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-white font-bold transition-all shadow-[0_0_15px_rgba(16,185,129,0.4)] flex items-center justify-center gap-2"
                  >
                    Proceed to Checkout <IconLock className="w-4 h-4" />
                  </button>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </div>
  );
}
