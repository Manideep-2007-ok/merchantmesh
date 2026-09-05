with open('frontend-v2/src/components/SalesBotTab.jsx', 'r') as f:
    c = f.read()
if "import { playSound } from '@/lib/sounds';" not in c:
    c = c.replace("import { AnimatedList } from './ui/animated-list';", "import { AnimatedList } from './ui/animated-list';\nimport { playSound } from '@/lib/sounds';")
c = c.replace('className="w-11 h-11 bg-[#00a884] rounded-full flex items-center justify-center shrink-0 shadow-lg cursor-pointer hover:bg-[#008f6f] transition-colors"',
              'className="w-11 h-11 bg-[#00a884] rounded-full flex items-center justify-center shrink-0 shadow-lg cursor-pointer hover:bg-[#008f6f] transition-colors" onClick={() => playSound(\'sent\')}')
with open('frontend-v2/src/components/SalesBotTab.jsx', 'w') as f:
    f.write(c)

with open('frontend-v2/src/components/SalesBotEngineTab.jsx', 'r') as f:
    c = f.read()
if "import { playSound } from '@/lib/sounds';" not in c:
    c = c.replace("import { Timeline } from '@/components/ui/timeline';", "import { Timeline } from '@/components/ui/timeline';\nimport { playSound } from '@/lib/sounds';")
c = c.replace('className="w-11 h-11 bg-[#00a884] rounded-full flex items-center justify-center shrink-0 shadow-lg cursor-pointer hover:bg-[#008f6f] transition-colors"',
              'className="w-11 h-11 bg-[#00a884] rounded-full flex items-center justify-center shrink-0 shadow-lg cursor-pointer hover:bg-[#008f6f] transition-colors" onClick={() => playSound(\'sent\')}')
with open('frontend-v2/src/components/SalesBotEngineTab.jsx', 'w') as f:
    f.write(c)
