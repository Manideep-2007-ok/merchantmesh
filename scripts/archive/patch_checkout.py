import re

with open('frontend-v2/src/App.jsx', 'r') as f:
    c = f.read()

# 1. Add state for auction result
c = c.replace('const [dealClosed, setDealClosed] = useState(false);', 
              'const [dealClosed, setDealClosed] = useState(false);\n  const [auctionResult, setAuctionResult] = useState(null);')

# 2. Update handleChatSubmit to set the auction result
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
    setAuctionResult(null);
    
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
            setAuctionResult(auction.winner);
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

# Replace the previous new_submit
# We can just do a regex replace on the entire function
pattern = re.compile(r'  const handleChatSubmit = async \(e\) => \{.*?^\s*};\n', re.MULTILINE | re.DOTALL)
c = pattern.sub(new_submit + '\n', c)

# 3. Update the Escrow Checkout UI to use auctionResult
old_escrow = """                        <div className="flex justify-between text-sm">
                          <span className="text-zinc-400">Total Deal Value</span>
                          <span className="text-white font-medium">₹70,000</span>
                        </div>
                        <div className="flex justify-between text-sm">
                          <span className="text-zinc-400">MerchantMesh Escrow Fee (2%)</span>
                          <span className="text-emerald-400 font-medium">₹1,400</span>
                        </div>"""

new_escrow = """                        <div className="flex justify-between text-sm">
                          <span className="text-zinc-400">Total Deal Value</span>
                          <span className="text-white font-medium">₹{auctionResult ? auctionResult.total_price.toLocaleString() : '0'}</span>
                        </div>
                        <div className="flex justify-between text-sm">
                          <span className="text-zinc-400">MerchantMesh Escrow Fee (2%)</span>
                          <span className="text-emerald-400 font-medium">₹{auctionResult ? (auctionResult.total_price * 0.02).toLocaleString() : '0'}</span>
                        </div>"""

c = c.replace(old_escrow, new_escrow)

with open('frontend-v2/src/App.jsx', 'w') as f:
    f.write(c)

