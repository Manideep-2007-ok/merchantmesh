
with open('frontend-v2/src/App.jsx', 'r') as f:
    c = f.read()

old_heading = '<h2 className="text-3xl font-bold tracking-tight text-white">Live Unit Economics</h2>'
new_heading = '<h2 className="text-3xl font-bold tracking-tight text-white">Core Agentic Architecture</h2>'

old_subtext = '<p className="text-zinc-400 text-sm mt-2 max-w-lg">\n                  Watch our multi-dealer Reverse Auction engine haggle and capture platform fees in real-time.\n                </p>'
new_subtext = '<p className="text-zinc-400 text-sm mt-2 max-w-lg">\n                  Watch our multimodal AI parse chaotic WhatsApp drops while autonomous buyer and seller agents negotiate deals in real-time.\n                </p>'

c = c.replace(old_heading, new_heading)
c = c.replace(old_subtext, new_subtext)

with open('frontend-v2/src/App.jsx', 'w') as f:
    f.write(c)
