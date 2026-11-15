import forms from "@tailwindcss/forms";

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./src/index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        lunar: { ink: "#080A0D", panel: "#151719", silver: "#C7C7C7", muted: "#A6A6A6" },
      },
      fontFamily: {
        display: ["Cormorant Garamond", "Georgia", "serif"],
        sans: ["DM Sans", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [forms],
};
