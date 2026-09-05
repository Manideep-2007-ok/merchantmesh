
with open('frontend-v2/src/App.jsx', 'r') as f:
    c = f.read()

# 1. Add imports at the top
if 'searchBuyerChat' not in c:
    c = c.replace('import { ReverseAuctionVisualizer } from \'@/components/ReverseAuctionVisualizer\';', 
                  'import { ReverseAuctionVisualizer } from \'@/components/ReverseAuctionVisualizer\';\nimport { searchBuyerChat, runParallelReverseAuction } from \'@/lib/api\';')

# 2. Rewrite handleChatSubmit
old_submit = """  const handleChatSubmit = (e) => {
    e.preventDefault();
    if (!chatInputValue) return;
    
    // Add user message
    setChatMessages(prev => [...prev, { role: 'user', text: chatInputValue }]);
    setIsHaggling(true);
    setShowLogs(true);
    setDealClosed(false);
    
    // Simulate haggling time
    setTimeout(() => {
      setChatMessages(prev => [
        ...prev, 
        { role: 'ai', text: "I have successfully negotiated with 4 sellers. Acme Supplier agreed to ₹140/piece (Total: ₹70,000) down from their original ₹180 quote.\\n\\nI've locked the inventory in SQLite to prevent double-spending.\\n\\nDo you want to proceed to secure the escrow via Razorpay Route?" }
      ]);
      setIsHaggling(false);
      setDealClosed(true);
    }, 7000); // Wait 7 seconds for the AnimatedList to finish
  };"""

new_submit = """  const handleChatSubmit = async (e) => {
    e.preventDefault();
    if (!chatInputValue) return;
    
    const userQuery = chatInputValue;
    setChatInputValue(''); // Clear input eagerly
    
    // Add user message
    setChatMessages(prev => [...prev, { role: 'user', text: userQuery }]);
    setIsHaggling(true);
    setShowLogs(true);
    setDealClosed(false);
    
    try {
      // 1. Natural Language Search
      const searchRes = await searchBuyerChat(userQuery, []);
      setChatMessages(prev => [...prev, { role: 'ai', text: searchRes.reply }]);
      
      if (searchRes.action === 'SEARCH' && searchRes.product_ids?.length > 0) {
         // 2. Run real Parallel Reverse Auction
         const auction = await runParallelReverseAuction({
            product_ids: searchRes.product_ids,
            target_price: searchRes.target_price,
            max_budget: searchRes.max_budget,
            quantity: searchRes.quantity || 1
         });
         
         if (auction.winner) {
            setChatMessages(prev => [
              ...prev, 
              { role: 'ai', text: `I have successfully negotiated with the merchants. ${auction.winner.merchant_id} agreed to ₹${auction.winner.price}/piece (Total: ₹${auction.winner.total_price}) down from their original quote.\\n\\nI've locked the inventory in SQLite to prevent double-spending.\\n\\nDo you want to proceed to secure the escrow via Razorpay Route?` }
            ]);
            setIsHaggling(false);
            setDealClosed(true);
         } else {
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
      setChatMessages(prev => [...prev, { role: 'ai', text: `System Error: ${err.message}` }]);
      setIsHaggling(false);
    }
  };"""

c = c.replace(old_submit, new_submit)

with open('frontend-v2/src/App.jsx', 'w') as f:
    f.write(c)
