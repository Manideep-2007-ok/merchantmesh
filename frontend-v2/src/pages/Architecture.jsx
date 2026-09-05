import React from 'react';
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Server, Database, BrainCircuit, CreditCard } from "lucide-react";

export const Architecture = () => {
  return (
    <div className="max-w-4xl mx-auto space-y-8 pb-10">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight text-zinc-900 mb-2">System Architecture</h1>
        <p className="text-sm text-zinc-500">How the MerchantMesh protocol routes and resolves intent.</p>
      </div>

      <div className="space-y-6 relative before:absolute before:inset-0 before:ml-5 before:-translate-x-px md:before:mx-auto md:before:translate-x-0 before:h-full before:w-0.5 before:bg-gradient-to-b before:from-transparent before:via-zinc-200 before:to-transparent">
        
        <ArchNode 
          title="Natural Language Entry"
          desc="Buyer types intent into the Buyer Agent via WhatsApp or Web interface."
          icon={<BrainCircuit className="w-4 h-4 text-zinc-500" />}
        />

        <ArchNode 
          title="Parallel Reverse Auction (RFQ)"
          desc="Buyer Agent spawns independent concurrent requests to all matching merchant Sales Bots."
          icon={<Server className="w-4 h-4 text-zinc-500" />}
        />

        <ArchNode 
          title="Deterministic Guardrails"
          desc="Sales Bots negotiate dynamically, but final deal logic is enforced by SQLite WAL mode and BEGIN IMMEDIATE locks."
          icon={<Database className="w-4 h-4 text-zinc-500" />}
        />

        <ArchNode 
          title="Human-in-the-Loop Checkout"
          desc="Winning deal is frozen. split settlement is initiated via Razorpay Webhooks (simulated in dev mode) prior to fulfillment."
          icon={<CreditCard className="w-4 h-4 text-zinc-500" />}
        />

      </div>
    </div>
  );
};

const ArchNode = ({ title, desc, icon }) => (
  <div className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group is-active">
    <div className="flex items-center justify-center w-10 h-10 rounded-full border border-zinc-200 bg-white shadow-sm shrink-0 md:order-1 md:group-odd:-translate-x-1/2 md:group-even:translate-x-1/2 z-10">
      {icon}
    </div>
    <Card className="w-[calc(100%-3rem)] md:w-[calc(50%-2.5rem)] shadow-sm border-zinc-200">
      <CardContent className="p-4">
        <h4 className="font-semibold text-sm mb-1">{title}</h4>
        <p className="text-xs text-zinc-500 leading-relaxed">{desc}</p>
      </CardContent>
    </Card>
  </div>
);
