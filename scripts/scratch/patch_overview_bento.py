
with open('frontend-v2/src/App.jsx', 'r') as f:
    c = f.read()

# 1. Define new components
new_components = """
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
          {`{\n  "item": "Black Hoodie",\n  "price": 1200,\n  "stock": 20\n}`}
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
"""

# Insert new components before PlatformRevenueHeader
if "const PlatformRevenueHeader" in c:
    c = c.replace("const PlatformRevenueHeader = ({ revenue }) => {", new_components + "\nconst PlatformRevenueHeader = ({ revenue }) => {")

# 2. Update the metrics array
old_metrics = """  const metrics = [
    {
      title: "Live GMV & Bidding",
      description: "Agents haggling in real-time.",
      header: <LiveGMVChart data={chartData} />,
      icon: <IconRobot className="h-4 w-4 text-emerald-500" />,
      className: "md:col-span-2",
    },
    {
      title: "Platform Revenue",
      description: "2.0% Razorpay Route capture.",
      header: <PlatformRevenueHeader revenue={revenue} />,
      icon: <IconReceipt2 className="h-4 w-4 text-blue-500" />,
      className: "md:col-span-1",
    },
    {
      title: "Conversion Rates",
      description: "Successful vs Deadlocks.",
      header: <LiveConversionDonut />,
      icon: <IconShieldCheck className="h-4 w-4 text-orange-500" />,
      className: "md:col-span-1",
    },
    {
      title: "Net Profit Margin (LLM Token Log)",
      description: "Verifiable operational costs in real-time.",
      header: <MarginTerminalHeader logs={logs} />,
      icon: <IconUserSearch className="h-4 w-4 text-purple-500" />,
      className: "md:col-span-2",
    },
  ];"""

new_metrics = """  const metrics = [
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
    },
    {
      title: "Conversion Rates",
      description: "Successful sales vs Deadlocks.",
      header: <LiveConversionDonut />,
      icon: <IconShieldCheck className="h-4 w-4 text-orange-500" />,
      className: "md:col-span-1",
    },
    {
      title: "Live GMV & Bidding",
      description: "System-wide transaction volume.",
      header: <LiveGMVChart data={chartData} />,
      icon: <IconChartBar className="h-4 w-4 text-emerald-500" />,
      className: "md:col-span-2",
    },
  ];"""

c = c.replace(old_metrics, new_metrics)

# 3. Add IconMicrophone to imports if missing
if "IconMicrophone" not in c:
    c = c.replace("IconChartBar\n}", "IconChartBar,\n  IconMicrophone\n}")

with open('frontend-v2/src/App.jsx', 'w') as f:
    f.write(c)
