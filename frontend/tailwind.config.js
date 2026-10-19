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
        page: "#F7F9F7",
        surface: "#FFFFFF",
        forest: {
          DEFAULT: "#176B45",
          50: "#E0F2E8",
          100: "#C3E6D2",
          200: "#A7D7BC",
          600: "#176B45",
          700: "#125537",
          800: "#0D3E28",
        },
        attention: {
          DEFAULT: "#E58A2B",
          50: "#FFFBEB",
          100: "#FEF3C7",
          200: "#FDE68A",
          600: "#E58A2B",
          700: "#B45309",
        },
        interactive: {
          DEFAULT: "#356AC3",
          50: "#EFF6FF",
          100: "#DBEAFE",
          200: "#BFDBFE",
          600: "#356AC3",
          700: "#254F99",
        },
        critical: {
          DEFAULT: "#DC2626",
          50: "#FEF2F2",
          100: "#FEE2E2",
          200: "#FECACA",
          600: "#DC2626",
          700: "#991B1B",
        },
        border: {
          DEFAULT: "#E2E8E4",
          subtle: "#EAEFEA",
          strong: "#CBD5E1",
        },
        appText: {
          primary: "#1F2937",
          secondary: "#64748B",
          muted: "#94A3B8",
        },
        // Mapped navy colors for seamless light enterprise theme across legacy styles
        navy: {
          950: "#F7F9F7",
          900: "#FFFFFF",
          850: "#F0F4F1",
          800: "#FFFFFF",
          750: "#EAEFEA",
          700: "#E2E8E4",
          600: "#CBD5E1",
        },
        cluster: {
          glow: "#DC2626",
          node: "#DC2626",
          light: "#F87171",
          dark: "#991B1B",
        },
        accent: {
          blue: "#356AC3",
          emerald: "#176B45",
          amber: "#E58A2B",
          purple: "#7C3AED",
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
