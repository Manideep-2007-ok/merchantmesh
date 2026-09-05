import React, { useState, useEffect } from 'react';
import { getProducts } from '../lib/api';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Activity, Database, Network, Box } from "lucide-react";

export const Overview = () => {
  const [stats, setStats] = useState({ products: 0, merchants: 3 });

  useEffect(() => {
    getProducts().then(prods => setStats(prev => ({ ...prev, products: prods.length })));
  }, []);

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight text-zinc-900 mb-2">Platform Overview</h1>
        <p className="text-sm text-zinc-500 max-w-2xl leading-relaxed">
          The autonomous commerce protocol for informal merchants. Dual-agent negotiation, parallel RFQ routing, and secure Razorpay payouts.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={<Box className="w-4 h-4 text-zinc-500" />} label="Indexed Products" value={stats.products} />
        <StatCard icon={<Network className="w-4 h-4 text-zinc-500" />} label="Active Merchants" value={stats.merchants} />
        <StatCard icon={<Activity className="w-4 h-4 text-zinc-500" />} label="Avg Negotiation" value="1.2s" />
        <StatCard icon={<Database className="w-4 h-4 text-zinc-500" />} label="SQLite Post-LLM" value="Strict" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-4">
        <Card className="shadow-sm border-zinc-200">
          <CardHeader>
            <CardTitle className="text-base">The Buyer Agent</CardTitle>
            <CardDescription className="text-xs">Your personal shopper.</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-zinc-600 leading-relaxed">Takes vague requests, queries the mesh, and triggers parallel reverse auctions on your behalf.</p>
          </CardContent>
        </Card>

        <Card className="shadow-sm border-zinc-200">
          <CardHeader>
            <CardTitle className="text-base">The Sales Bot</CardTitle>
            <CardDescription className="text-xs">The merchant's autonomous closer.</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-zinc-600 leading-relaxed">Negotiates fiercely based on real-time inventory and secret floor prices.</p>
          </CardContent>
        </Card>

        <Card className="shadow-sm border-zinc-200">
          <CardHeader>
            <CardTitle className="text-base">The Guardrails</CardTitle>
            <CardDescription className="text-xs">Deterministic protection.</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-zinc-600 leading-relaxed">SQLite constraints prevent LLM hallucinations. Deals cannot execute below floor price.</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

const StatCard = ({ icon, label, value }) => (
  <Card className="shadow-sm border-zinc-200 bg-white">
    <CardHeader className="flex flex-row items-center justify-between pb-2">
      <CardTitle className="text-xs font-medium text-zinc-500 uppercase tracking-wider">{label}</CardTitle>
      {icon}
    </CardHeader>
    <CardContent>
      <div className="text-2xl font-bold font-mono tracking-tight">{value}</div>
    </CardContent>
  </Card>
);
