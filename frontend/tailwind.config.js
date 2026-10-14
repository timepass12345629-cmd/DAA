/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        navy: {
          950: "#060A12",
          900: "#0B1120",
          850: "#0F172A",
          800: "#1E293B",
          700: "#334155",
          600: "#475569",
        },
        cluster: {
          glow: "#DC2626",
          node: "#EF4444",
          light: "#F87171",
          dark: "#991B1B",
        },
        accent: {
          blue: "#38BDF8",
          emerald: "#10B981",
          amber: "#F59E0B",
          purple: "#A855F7",
        }
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "ui-monospace", "SFMono-Regular", "monospace"],
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
      }
    },
  },
  plugins: [],
}
