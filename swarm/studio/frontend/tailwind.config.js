/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        studio: {
          bg: "#0b1120",
          card: "#111827",
          panel: "#1e293b",
          border: "#334155",
          accent: "#0284c7",
          accentHover: "#0369a1",
        },
        drone: {
          d1: "#E69F00",
          d2: "#56B4E9",
          d3: "#009E73",
          d4: "#CC79A7",
        }
      }
    },
  },
  plugins: [],
}
