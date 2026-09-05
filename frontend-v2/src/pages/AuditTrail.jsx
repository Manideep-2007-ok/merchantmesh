import React, { useState, useEffect } from 'react';
import { fetchAuditLogs } from '../lib/api';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

export const AuditTrail = () => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let interval;
    const loadLogs = async () => {
      try {
        const data = await fetchAuditLogs();
        setLogs(data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    loadLogs();
    interval = setInterval(loadLogs, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 mb-1">Trust & Audit Log</h1>
        <p className="text-sm text-zinc-500">Immutable record of agent decisions and deterministic guardrail checks.</p>
      </div>

      <div className="rounded-md border border-zinc-200 bg-white shadow-sm overflow-hidden">
        <Table>
          <TableHeader className="bg-zinc-50">
            <TableRow>
              <TableHead className="w-[100px] text-xs font-medium uppercase tracking-wider text-zinc-500">Time</TableHead>
              <TableHead className="text-xs font-medium uppercase tracking-wider text-zinc-500">Action</TableHead>
              <TableHead className="text-xs font-medium uppercase tracking-wider text-zinc-500">Agent</TableHead>
              <TableHead className="text-xs font-medium uppercase tracking-wider text-zinc-500">Reasoning</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {logs.length === 0 && !loading && (
              <TableRow>
                <TableCell colSpan={4} className="h-24 text-center text-sm text-zinc-500">
                  No audit logs found.
                </TableCell>
              </TableRow>
            )}
            {logs.map((l) => (
              <TableRow key={l.id} className="text-sm">
                <TableCell className="font-mono text-xs text-zinc-500">{new Date(l.timestamp).toLocaleTimeString()}</TableCell>
                <TableCell>
                  <Badge variant="outline" className="font-mono text-[10px] uppercase bg-zinc-50 font-normal">
                    {l.action}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Badge variant="secondary" className={`font-mono text-[10px] font-medium ${l.agent === 'SYSTEM' ? 'bg-emerald-100 text-emerald-700 hover:bg-emerald-100' : 'bg-red-100 text-red-700 hover:bg-red-100'}`}>
                    {l.agent}
                  </Badge>
                </TableCell>
                <TableCell className="text-zinc-600 max-w-sm truncate">{l.reasoning}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
};
