/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          dark: "#0f172a",    // Azul muy oscuro profesional
          primary: "#3b82f6", // Azul moderno
          accent: "#10b981",  // Verde éxito
        }
      }
    },
  },
  plugins: [],
}