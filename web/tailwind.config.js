/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Custom colors for job sources
        indeed: {
          DEFAULT: '#2164f3',
          light: '#4a82f5',
          dark: '#1a4fc2',
        },
        glassdoor: {
          DEFAULT: '#0caa41',
          light: '#10d452',
          dark: '#098833',
        },
        // Match score colors
        score: {
          excellent: '#22c55e',
          good: '#84cc16',
          fair: '#eab308',
          poor: '#ef4444',
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
