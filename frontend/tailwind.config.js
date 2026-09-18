export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Manrope"', 'system-ui', 'sans-serif'],
        sans: ['"Inter"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      colors: {
        ink: {
          950: '#0a0b0d',
          900: '#0e1013',
          800: '#14171b',
          700: '#1b1f25',
          600: '#262b33',
          500: '#3a4048',
        },
        bone: {
          50: '#f7f5f1',
          100: '#eeeae2',
          300: '#c9c2b3',
          500: '#8f887a',
          700: '#5a5548',
        },
        brass: {
          300: '#e8c583',
          400: '#dcae5e',
          500: '#c9974a',
          600: '#a87b38',
        },
        teal: {
          400: '#5fd4c4',
          500: '#3bb8a7',
        },
      },
      boxShadow: {
        glass: '0 1px 1px rgba(0,0,0,.2), 0 12px 40px -12px rgba(0,0,0,.55)',
        'glass-sm': '0 1px 0 rgba(255,255,255,.04) inset, 0 8px 24px -10px rgba(0,0,0,.5)',
        glow: '0 0 0 1px rgba(220,174,94,.25), 0 0 32px -4px rgba(220,174,94,.35)',
      },
      backdropBlur: { xs: '2px' },
      keyframes: {
        'fade-up': { '0%': { opacity: 0, transform: 'translateY(8px)' }, '100%': { opacity: 1, transform: 'translateY(0)' } },
        shimmer: { '0%': { backgroundPosition: '-200% 0' }, '100%': { backgroundPosition: '200% 0' } },
        'pulse-ring': { '0%': { boxShadow: '0 0 0 0 rgba(220,174,94,.45)' }, '100%': { boxShadow: '0 0 0 10px rgba(220,174,94,0)' } },
      },
      animation: {
        'fade-up': 'fade-up .5s cubic-bezier(.16,1,.3,1) both',
        shimmer: 'shimmer 2.2s linear infinite',
        'pulse-ring': 'pulse-ring 1.6s cubic-bezier(.4,0,.6,1) infinite',
      },
    },
  },
  plugins: [],
}
