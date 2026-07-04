import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        // PrajaTantra Indian politics palette
        "pt-ink":      "#0C0F14",
        "pt-panel":    "#131820",
        "pt-panel-hi": "#1A2130",
        "pt-line":     "#2A3040",
        "pt-saffron":  "#FF6B00",   // Saffron — ruling energy
        "pt-wheel":    "#0B4EA2",   // Ashoka wheel blue — trust
        "pt-green":    "#138A36",   // Tiranga green — economy
        "pt-white":    "#F4F0E6",   // Khadi parchment — text
        "pt-muted":    "#8A8070",   // Secondary text
        "pt-red":      "#C0292A",   // Corruption / scandal
        "pt-gold":     "#C9962D",   // Treasury gold

        // Legacy aliases so nothing breaks
        "sovereign-ink":    "#0C0F14",
        "sovereign-panel":  "#131820",
        "sovereign-line":   "#2A3040",
        "sovereign-paper":  "#F4F0E6",
        "sovereign-muted":  "#8A8070",
        "sovereign-cyan":   "#0B4EA2",
        "sovereign-amber":  "#C9962D",
        "sovereign-red":    "#C0292A",
        "sovereign-green":  "#138A36",
        "sovereign-blue":   "#0B4EA2",
      },
      boxShadow: {
        command: "0 18px 60px rgba(0, 0, 0, 0.30)",
      },
    },
  },
  plugins: [],
};

export default config;