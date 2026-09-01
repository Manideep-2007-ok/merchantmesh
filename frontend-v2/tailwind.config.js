/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        display: ['Plus Jakarta Sans', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        card: "var(--card)",
        "card-foreground": "var(--card-foreground)",
        popover: "var(--popover)",
        "popover-foreground": "var(--popover-foreground)",
        primary: "var(--primary)",
        "primary-foreground": "var(--primary-foreground)",
        secondary: "var(--secondary)",
        "secondary-foreground": "var(--secondary-foreground)",
        muted: "var(--muted)",
        "muted-foreground": "var(--muted-foreground)",
        accent: "var(--accent)",
        "accent-foreground": "var(--accent-foreground)",
        destructive: "var(--destructive)",
        "destructive-foreground": "var(--destructive-foreground)",
        border: "var(--border)",
        input: "var(--input)",
        ring: "var(--ring)",
        obsidian: {
          950: '#030407',
          900: '#080B10',
          850: '#0B0F17',
          800: '#0E131F',
          700: '#161D2E',
          600: '#232E42',
        },
        razorpay: {
          blue: '#0D5FFF',
          navy: '#0C2340',
          light: '#528FF0',
        },
        settlement: {
          emerald: '#10B981',
          dark: '#064E3B',
          light: '#34D399',
        }
      },
      boxShadow: {
        'glass-edge': 'inset 0 1px 0 0 rgba(255,255,255,0.12), 0 12px 32px -8px rgba(0,0,0,0.6)',
        'glass-edge-subtle': 'inset 0 1px 0 0 rgba(255,255,255,0.08), 0 4px 12px -4px rgba(0,0,0,0.5)',
      },
      animation: {
        "border-beam": "border-beam calc(var(--duration)*1s) infinite linear",
        "meteor": "meteor 5s linear infinite",
        "grid": "grid 15s linear infinite",
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "shimmer-slide": "shimmer-slide var(--speed) ease-in-out infinite alternate",
        "spin-around": "spin-around calc(var(--speed) * 2) infinite linear",
      },
      keyframes: {
        "shimmer-slide": {
          to: { transform: "translate(calc(100vw - 100%), 0)" },
        },
        "spin-around": {
          "0%": { transform: "translateZ(0) rotate(0)" },
          "15%, 35%": { transform: "translateZ(0) rotate(90deg)" },
          "65%, 85%": { transform: "translateZ(0) rotate(270deg)" },
          "100%": { transform: "translateZ(0) rotate(360deg)" },
        },
        "border-beam": {
          "100%": {
            "offset-distance": "100%",
          },
        },
        "meteor": {
          "0%": { transform: "rotate(215deg) translateX(0)", opacity: 1 },
          "70%": { opacity: 1 },
          "100%": {
            transform: "rotate(215deg) translateX(-500px)",
            opacity: 0,
          },
        },
        "grid": {
          "0%": { transform: "translateY(-50%)" },
          "100%": { transform: "translateY(0)" },
        },
      }
    },
  },
  plugins: [],
}
