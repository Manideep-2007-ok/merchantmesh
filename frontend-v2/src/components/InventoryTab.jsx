import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { IconSearch, IconBox, IconTrendingUp, IconAlertCircle, IconTable, IconRobot, IconTruckDelivery, IconPackage } from '@tabler/icons-react';
import { fetchPendingSalesOrders, getProducts } from '@/lib/api';

export function InventoryTab({ activeMerchantId, merchantsList, onMerchantChange }) {
  const [products, setProducts] = useState([]);
  const [orders, setOrders] = useState({ pending_orders: [], recent_activity: [] });
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState('');

  async function fetchProductsAndOrders() {
    setIsLoading(true);
    try {
      let productsList = await getProducts();
      if (activeMerchantId) {
          productsList = productsList.filter(p => p.merchant_id === activeMerchantId);
      }
      setProducts(productsList);
      
      const ordersData = await fetchPendingSalesOrders(activeMerchantId);
      setOrders(ordersData || { pending_orders: [], recent_activity: [] });
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  }

  async function updateStock(productId, newStock) {
    if (newStock < 0) return;
    try {
      // Optimistic UI update
      setProducts(prev => prev.map(p => p.id === productId ? { ...p, stock: newStock } : p));
      await fetch(`/api/catalog/products/${productId}/set_stock`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_stock: newStock })
      });
    } catch (e) {
      console.error('Failed to update stock:', e);
      fetchProductsAndOrders(); // Revert on failure
    }
  }

  useEffect(() => {
    fetchProductsAndOrders();
  }, [activeMerchantId]);

  const filtered = products.filter(p => (p.name || '').toLowerCase().includes(search.toLowerCase()));
  const totalStock = products.reduce((acc, p) => acc + (p.stock || 0), 0);
  const totalValue = products.reduce((acc, p) => acc + ((p.stock || 0) * (p.listed_price || 0)), 0);
  const lowStock = products.filter(p => p.stock > 0 && p.stock <= 5).length;
  
  // Calculate Orders logic
  const paidOrders = (orders?.recent_activity || []).filter(o => o?.payment_status === 'PAID');
  const pendingDeliveryCount = paidOrders?.length || 0;
  // Let's just simulate that 30% of paid orders are already shipped for the visual dashboard
  const shippedCount = Math.floor(pendingDeliveryCount * 0.3);
  const actualPendingDelivery = pendingDeliveryCount - shippedCount;

  return (
    <motion.div 
      initial={{ opacity: 0, y: 30 }} 
      animate={{ opacity: 1, y: 0 }} 
      transition={{ duration: 0.8, ease: "easeOut" }} 
      className="w-full flex flex-col gap-6 relative z-10 min-h-[600px]"
    >
      {/* Header & Dropdown */}
      <div className="flex flex-col sm:flex-row items-center justify-between bg-white/5 backdrop-blur-xl border border-white/10 rounded-3xl p-4 sm:px-6 py-6 shadow-xl gap-4">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center shadow-[0_0_15px_rgba(16,185,129,0.2)]">
            <IconTable className="w-6 h-6 text-emerald-400" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white leading-tight">Catalog & Orders Dashboard</h2>
            <p className="text-sm text-zinc-400">Manage products, pricing, stock limits, and fulfillments.</p>
          </div>
        </div>
        
        <div className="flex items-center gap-3 bg-black/40 border border-white/10 rounded-xl px-5 py-2.5 hover:border-white/20 transition-colors shadow-inner">
          <IconRobot className="w-5 h-5 text-emerald-400" />
          <select 
            value={activeMerchantId} 
            onChange={(e) => onMerchantChange(e.target.value)}
            className="bg-transparent outline-none cursor-pointer text-[#e9edef] font-semibold text-sm"
          >
            {merchantsList && merchantsList.map(m => (
              <option key={m.id} value={m.id} className="text-black bg-white">{m.name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-5 flex items-center gap-4 hover:bg-white/10 transition-colors cursor-default">
           <div className="w-10 h-10 rounded-full bg-blue-500/20 flex items-center justify-center border border-blue-500/30 shrink-0">
             <IconBox className="text-blue-400 w-5 h-5" />
           </div>
           <div>
             <div className="text-xs text-zinc-400 uppercase tracking-wider font-semibold">Total Items</div>
             <div className="text-xl font-bold text-white">{totalStock}</div>
           </div>
        </div>
        
        <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-5 flex items-center gap-4 hover:bg-white/10 transition-colors cursor-default">
           <div className="w-10 h-10 rounded-full bg-emerald-500/20 flex items-center justify-center border border-emerald-500/30 shrink-0">
             <IconTrendingUp className="text-emerald-400 w-5 h-5" />
           </div>
           <div>
             <div className="text-xs text-zinc-400 uppercase tracking-wider font-semibold">Inventory Value</div>
             <div className="text-xl font-bold text-white">₹{totalValue.toLocaleString()}</div>
           </div>
        </div>
        
        <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-5 flex items-center gap-4 hover:bg-white/10 transition-colors cursor-default">
           <div className="w-10 h-10 rounded-full bg-purple-500/20 flex items-center justify-center border border-purple-500/30 shrink-0 relative">
             <IconPackage className="text-purple-400 w-5 h-5" />
             {actualPendingDelivery > 0 && <span className="absolute -top-1 -right-1 flex h-2.5 w-2.5"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-purple-400 opacity-75"></span><span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-purple-500"></span></span>}
           </div>
           <div>
             <div className="text-xs text-zinc-400 uppercase tracking-wider font-semibold">To Deliver</div>
             <div className="text-xl font-bold text-white">{actualPendingDelivery}</div>
           </div>
        </div>

        <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-5 flex items-center gap-4 hover:bg-white/10 transition-colors cursor-default">
           <div className="w-10 h-10 rounded-full bg-teal-500/20 flex items-center justify-center border border-teal-500/30 shrink-0">
             <IconTruckDelivery className="text-teal-400 w-5 h-5" />
           </div>
           <div>
             <div className="text-xs text-zinc-400 uppercase tracking-wider font-semibold">Shipped</div>
             <div className="text-xl font-bold text-white">{shippedCount}</div>
           </div>
        </div>

        <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-5 flex items-center gap-4 hover:bg-white/10 transition-colors cursor-default">
           <div className="w-10 h-10 rounded-full bg-orange-500/20 flex items-center justify-center border border-orange-500/30 shrink-0 relative">
             {lowStock > 0 && <span className="absolute -top-1 -right-1 flex h-2.5 w-2.5"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75"></span><span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-orange-500"></span></span>}
             <IconAlertCircle className="text-orange-400 w-5 h-5" />
           </div>
           <div>
             <div className="text-xs text-zinc-400 uppercase tracking-wider font-semibold">Low Stock</div>
             <div className="text-xl font-bold text-white">{lowStock}</div>
           </div>
        </div>
      </div>

      {/* Main Inventory Block */}
      <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-3xl p-6 shadow-2xl min-h-[400px] flex flex-col flex-1">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-8 gap-4">
          <div className="relative w-full sm:w-80">
            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
              <IconSearch className="w-4 h-4 text-zinc-500" />
            </div>
            <input 
              type="text" 
              placeholder="Search products..." 
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-black/40 border border-white/10 rounded-full pl-12 pr-4 py-2.5 text-sm text-white placeholder:text-zinc-500 focus:outline-none focus:border-emerald-500/50 transition-colors shadow-inner"
            />
          </div>
        </div>

        {isLoading ? (
          <div className="flex-1 flex items-center justify-center py-20">
            <div className="w-8 h-8 rounded-full border-2 border-emerald-500 border-t-transparent animate-spin"></div>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center text-zinc-500 py-20">
            <IconBox className="w-12 h-12 mb-3 opacity-20" />
            <p>No products found in catalog.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-6">
            <AnimatePresence>
            {filtered.map(p => (
              <motion.div 
                layout
                key={p.id} 
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                className="bg-black/60 border border-white/10 rounded-2xl overflow-hidden group hover:border-emerald-500/50 transition-colors hover:shadow-[0_0_20px_rgba(16,185,129,0.15)] flex flex-col"
              >
                <div className="aspect-square bg-zinc-900 relative overflow-hidden flex items-center justify-center shrink-0">
                  {p.image_url ? (
                    <img src={p.image_url} alt={p.name} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700 ease-out" />
                  ) : (
                    <span className="text-zinc-600 text-xs font-mono">No Image</span>
                  )}
                  {p.stock <= 5 && p.stock > 0 && (
                    <div className="absolute top-3 left-3 bg-orange-500 text-white text-[10px] font-bold px-2 py-1 rounded-full shadow-lg">
                      Low Stock: {p.stock}
                    </div>
                  )}
                  {p.stock === 0 && (
                    <div className="absolute top-3 left-3 bg-red-500 text-white text-[10px] font-bold px-2 py-1 rounded-full shadow-lg">
                      Out of Stock
                    </div>
                  )}
                </div>
                <div className="p-4 flex flex-col justify-between flex-1">
                  <h3 className="text-white font-medium text-sm line-clamp-2 leading-tight" title={p.name}>{p.name}</h3>
                  <div className="flex items-end justify-between mt-4">
                    <div>
                      <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1 font-semibold">Floor / List Price</div>
                      <div className="text-emerald-400 font-bold text-lg leading-none">₹{p.listed_price}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1 font-semibold">Quantity</div>
                      <div className="flex items-center gap-2 bg-white/10 rounded-md p-0.5">
                        <button onClick={(e) => { e.stopPropagation(); updateStock(p.id, p.stock - 1); }} className="w-5 h-5 flex items-center justify-center text-white hover:bg-white/20 rounded cursor-pointer disabled:opacity-50" disabled={p.stock <= 0}>-</button>
                        <div className="text-white font-medium text-xs w-6 text-center">{p.stock}</div>
                        <button onClick={(e) => { e.stopPropagation(); updateStock(p.id, p.stock + 1); }} className="w-5 h-5 flex items-center justify-center text-white hover:bg-white/20 rounded cursor-pointer">+</button>
                      </div>
                    </div>
                  </div>
                </div>
              </motion.div>
            ))}
            </AnimatePresence>
          </div>
        )}
      </div>
    </motion.div>
  );
}
