/** @type {import('tailwindcss').Config} */
const v = (name) => `var(--${name})`;
const colors = ['red','red-deep','pink','red-300','red-100','black','grey-900','grey-600','grey-400','grey-300','grey-200','grey-100','white',
  'ground','surface','ink','ink-muted','line','line-soft','accent','on-accent','accent-deep','on-accent-deep','highlight'];
module.exports = {
  content: ['./src/**/*.{html,js,jsx,ts,tsx}'],
  theme: {
    colors: Object.fromEntries(colors.map((c) => [c, v(c)])),
    fontFamily: { mono: [v('font-mono')], serif: [v('font-serif')], kana: [v('font-kana')] },
    borderRadius: { none: '0', DEFAULT: '0' },
    boxShadow: { focus: v('focus-ring'), none: 'none' },
    spacing: Object.fromEntries([0,0.5,1,1.5,2,2.5,3,4,5,6,7,8,9,10,12,14,16,20,24,32].map((n) => [n, `${n * 4}px`])),
    fontSize: {
      micro: ['10px', '12px'], caption: ['11px', '14px'], 'caps-sm': ['12px', { lineHeight: '15px', letterSpacing: '0.04em' }],
      ui: ['13px', '16px'], caps: ['14px', { lineHeight: '17px', letterSpacing: '0.02em' }], lead: ['18px', '24px'],
      word: ['20px', '24px'], title: ['24px', '28px'], quote: ['40px', '52px'],
      display: ['64px', { lineHeight: '64px', letterSpacing: '-0.01em' }], wordmark: ['128px', '1'],
    },
    extend: {
      letterSpacing: { wordmark: '1em', kana: '1em' },
      backgroundImage: { fade: v('grad-fade'), ignite: v('grad-ignite'), hero: v('grad-hero'), tile: v('grad-tile'), ember: v('grad-ember') },
    },
  },
};
