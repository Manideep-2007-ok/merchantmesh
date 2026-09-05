
with open("frontend-v2/src/components/SalesBotEngineTab.jsx", "r") as f:
    content = f.read()

target = """  const handleMenuSelection = (option) => {"""

replace = """  const handleCardClick = (card) => {
    playSound('sent');
    setMessages(prev => [...prev, { id: Date.now(), role: 'user', text: `Review order ${card.order_id.split('-')[0]}` }]);
    
    setTimeout(() => {
       playSound('received');
       setMessages(prev => [...prev, {
          id: card.order_id,
          role: 'ai',
          text: `📱 *Order Review: ${card.order_id.split('-')[0]}*\n\nBuyer wants: *${card.product_name}* (Qty: ${card.quantity})\nNegotiated Price: *₹${card.amount}*\n\nDo you have this in stock? (Reply Yes or No)`,
          isAction: true,
          orderId: card.order_id
       }]);
    }, 800);
  };

  const handleMenuSelection = (option) => {"""

content = content.replace(target, replace)

with open("frontend-v2/src/components/SalesBotEngineTab.jsx", "w") as f:
    f.write(content)
print("handleCardClick added!")
