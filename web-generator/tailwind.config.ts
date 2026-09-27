import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        frost: '#EAF4F7',
        bench: '#D9E5E8',
        ink: '#18262B',
        signal: '#C84C4C',
        slime: '#68A57A',
        honey: '#C69542',
      },
      borderRadius: {
        md: '6px',
        lg: '8px',
      },
    },
  },
  plugins: [],
} satisfies Config

