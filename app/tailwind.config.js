/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      screens: {
        wide: "1440px",
      },
      colors: {
        // Guest (night) chrome — key names kept, values migrated to the night set (#30).
        bg: "#221b18", // night-canvas (was #1a0f12)
        card: "#2c231f", // night-card (was #24151a)
        ink: "#f3ece1", // night-ink (was #f7efe6)
        muted: "#b3a08f", // night-muted (was #c9b3a6)
        hairline: "#3a2f28", // night-hairline — decorative card borders
        tile: "#382d26", // night-tile — photo-tile background
        gold: "#e0a63a",
        rose: "#d9556a",
        haldi: "#f2c14e",
        maroon: "#4a1020",
        ws: {
          bg: "#f6f4ef",
          panel: "#ffffff",
          ink: "#1a1a19",
          muted: "#6b6963",
          accent: "#b8862b", // fills / rings / borders only
          accentText: "#8a6410", // text-safe marigold (#19) — 4.89:1 on ws.bg
          ok: "#12724a", // text-safe success green (#22) — 5.95:1 on white
          warn: "#c8462f",
          line: "#e4e1d8",
          soft: "#f0ede6",
        },
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "Roboto",
          '"Helvetica Neue"',
          "Arial",
          "sans-serif",
        ],
        serif: [
          '"Iowan Old Style"',
          '"Palatino Linotype"',
          "Palatino",
          "Georgia",
          "serif",
        ],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}
