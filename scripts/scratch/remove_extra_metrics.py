
with open('frontend-v2/src/App.jsx', 'r') as f:
    c = f.read()

old_metrics = """  const metrics = [
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
    }
  ];"""

c = c.replace(old_metrics, new_metrics)

with open('frontend-v2/src/App.jsx', 'w') as f:
    f.write(c)
