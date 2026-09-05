with open('frontend-v2/src/components/ReverseAuctionVisualizer.jsx', 'r') as f:
    c = f.read()

if "import { playSound } from '@/lib/sounds';" not in c:
    c = c.replace("import React, { useState, useEffect, useRef } from 'react';", "import React, { useState, useEffect, useRef } from 'react';\nimport { playSound } from '@/lib/sounds';")

# When phase advances manually
c = c.replace("const next = (prev + 1) % 4;", "const next = (prev + 1) % 4;\n          if (next === 1 || next === 2) playSound('ping');\n          if (next === 3) playSound('success');")

with open('frontend-v2/src/components/ReverseAuctionVisualizer.jsx', 'w') as f:
    f.write(c)
