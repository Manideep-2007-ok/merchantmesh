with open('frontend-v2/src/App.jsx', 'r') as f:
    c = f.read()

if "import { playSound } from '@/lib/sounds';" not in c:
    c = c.replace("import { searchBuyerChat, runParallelReverseAuction } from '@/lib/api';",
                  "import { searchBuyerChat, runParallelReverseAuction } from '@/lib/api';\nimport { playSound } from '@/lib/sounds';")

# When user sends message
c = c.replace("setChatInputValue(''); // Clear input eagerly", "setChatInputValue(''); // Clear input eagerly\n    playSound('sent');")

# When AI responds (Search)
c = c.replace("setChatMessages(prev => [...prev, { role: 'ai', text: searchRes.reply }]);", "playSound('received');\n      setChatMessages(prev => [...prev, { role: 'ai', text: searchRes.reply }]);")

# When Deal is closed (Auction Winner)
c = c.replace("setAuctionResult(auction.winner);", "playSound('success');\n            setAuctionResult(auction.winner);")

with open('frontend-v2/src/App.jsx', 'w') as f:
    f.write(c)
