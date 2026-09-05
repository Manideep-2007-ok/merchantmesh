import re


def clear_bubbles(file_path):
    with open(file_path, 'r') as f:
        c = f.read()
    
    # We want to replace everything inside <ChatMessageList>...</ChatMessageList>
    # with just an empty state or maybe just one welcome message?
    # Actually, the user asked to "remove the pre-seeded messages".
    # I'll just remove all ChatBubbles and leave the ChatMessageList empty.
    
    pattern = re.compile(r'<ChatMessageList>.*?</ChatMessageList>', re.DOTALL)
    c = pattern.sub('<ChatMessageList>\n              {/* Messages cleared for live demo */}\n            </ChatMessageList>', c)
    
    with open(file_path, 'w') as f:
        f.write(c)

clear_bubbles('frontend-v2/src/components/SalesBotTab.jsx')
clear_bubbles('frontend-v2/src/components/SalesBotEngineTab.jsx')

