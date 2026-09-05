
with open("frontend-v2/src/components/SalesBotEngineTab.jsx", "r") as f:
    content = f.read()

# Replace ChatMessageList block
old_list = """              <ChatMessageList className="p-3 gap-1 pb-4 rounded-none [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
              {messages.map(m => (
                <ChatBubble 
                  key={m.id} 
                  variant={m.role === 'user' ? 'sent' : 'received'}
                >
                  <div className="whitespace-pre-wrap">{m.text}</div>
                </ChatBubble>
              ))}
            </ChatMessageList>"""

new_list = """              <ChatMessageList className="p-3 gap-1 pb-4 rounded-none [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
              {messages.map(m => (
                <ChatBubble 
                  key={m.id} 
                  variant={m.role === 'user' ? 'sent' : 'received'}
                >
                  <div className="whitespace-pre-wrap">{m.text}</div>
                  {m.isMenu && (
                     <div 
                       onClick={() => setShowMenuSheet(true)}
                       className="mt-2 bg-[#2a3942] hover:bg-[#32454f] cursor-pointer text-[#00a884] flex items-center justify-center gap-2 py-2 px-6 rounded-md border border-[#111b21] font-medium transition-colors text-sm shadow-sm"
                     >
                       <IconList className="w-4 h-4" /> View Options
                     </div>
                  )}
                </ChatBubble>
              ))}
            </ChatMessageList>"""

content = content.replace(old_list, new_list)

with open("frontend-v2/src/components/SalesBotEngineTab.jsx", "w") as f:
    f.write(content)
