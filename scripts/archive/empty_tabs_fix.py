import re


def clear_bubbles(file_path):
    with open(file_path, 'r') as f:
        c = f.read()
    
    # Match <ChatMessageList ...> ... </ChatMessageList>
    pattern = re.compile(r'(<ChatMessageList\b[^>]*>).*?(</ChatMessageList>)', re.DOTALL)
    
    # Keep the opening tag, replace the content, keep the closing tag
    c = pattern.sub(r'\1\n              {/* Messages cleared for live demo */}\n            \2', c)
    
    with open(file_path, 'w') as f:
        f.write(c)

clear_bubbles('frontend-v2/src/components/SalesBotTab.jsx')
clear_bubbles('frontend-v2/src/components/SalesBotEngineTab.jsx')

