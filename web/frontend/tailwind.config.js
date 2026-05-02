/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        ub: {
          blue:      '#005BBB',
          'blue-dk': '#003087',
          'blue-lt': '#1a72cc',
          gold:      '#FFB81C',
          'gold-dk': '#e6a519',
          navy:      '#001F5B',
        },
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
}
