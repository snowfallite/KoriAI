# Tailwind

Сайт Kïoku собирается на **Tailwind CSS v4**. Тема заменяет стандартную палитру, шрифты, радиусы и тени Tailwind на токены бренда — в проекте остаются только цвета Kïoku, три семейства, шкала текста бренда и шаг 4px. Цвета подключены через `@theme inline`, поэтому утилиты читают живой токен: `bg-ground`, `text-ink` и остальные семантические цвета переключаются вместе с `data-theme`.

## Установка

1. Скопируйте шрифты из системы (`fonts/JetBrainsMono-Variable.woff2`, `fonts/NotoSerif-Variable.woff2`) в `public/fonts/`. Noto Serif TC/JP и Noto Sans JP подключаются с Google Fonts — только нужные страницам начертания.
2. Положите рядом два файла: `kioku-tokens.css` (переменные токенов) и `kioku.css` (тема Tailwind), и подключите `kioku.css` как входной файл Tailwind.
3. На `<html>` поставьте тему: `data-theme="night"` для сайта, `data-theme="day"` для светлых страниц. Интерфейс расширения всегда использует фиксированные цвета (`bg-white`, `bg-grey-*`, `bg-red`), а не семантические.

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300&family=Noto+Serif+TC:wght@400;500&family=Noto+Serif+JP:wght@400;500&display=swap">
<html lang="en" data-theme="night">
```

## kioku-tokens.css

```css
:root, [data-theme="night"] {
  --red: #FE2627;
  --red-deep: #DF342F;
  --pink: #FD4B61;
  --red-300: #FFA5A5;
  --red-100: #FFDCDC;
  --black: #000000;
  --grey-900: #1C1C1C;
  --grey-600: #757575;
  --grey-400: #AAAAAA;
  --grey-300: #CBCBCB;
  --grey-200: #DBDBDB;
  --grey-100: #F6F6F6;
  --white: #FFFFFF;
  --ground: var(--black);
  --surface: var(--grey-900);
  --ink: var(--white);
  --ink-muted: var(--grey-400);
  --line: var(--white);
  --line-soft: var(--grey-600);
  --accent: var(--red);
  --on-accent: var(--black);
  --accent-deep: var(--red-deep);
  --on-accent-deep: var(--white);
  --highlight: var(--pink);
  --focus-ring: 0 0 0 2px #000000, 0 0 0 4px #FE2627;
}
[data-theme="day"] {
  --ground: var(--white);
  --surface: var(--grey-200);
  --ink: var(--black);
  --ink-muted: var(--grey-600);
  --line: var(--black);
  --line-soft: var(--grey-400);
  --accent: var(--red);
  --on-accent: var(--black);
  --accent-deep: var(--red-deep);
  --on-accent-deep: var(--white);
  --highlight: var(--pink);
  --focus-ring: 0 0 0 2px #FFFFFF, 0 0 0 4px #000000;
}
:root {
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-6: 24px;
  --space-8: 32px;
  --space-12: 48px;
  --space-16: 64px;
  --space-24: 96px;
  --space-32: 128px;
  --radius-none: 0px;
  --grad-fade: linear-gradient(90deg, #FE2627 0%, #FFFFFF 100%);
  --grad-ignite: linear-gradient(90deg, #000000 0%, #FE2627 100%);
  --grad-highlight: linear-gradient(90deg, #FD4B61 0%, #FD4B6100 100%);
  --grad-hero: linear-gradient(180deg, #FD4B61 0%, #FE2627 50%, #000000 100%);
  --grad-tile: linear-gradient(180deg, #FD4B61 0%, #FE2627 30%, #DBDBDB 100%);
  --grad-ember: linear-gradient(90deg, #FE2627 0%, #FFA5A5 100%);
  --stroke-hair: 1px;
  --stroke-map: 1.5px;
  --font-mono: "JetBrains Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  --font-serif: "Noto Serif", "Noto Serif TC", "Noto Serif JP", Georgia, serif;
  --font-kana: "Noto Sans JP", sans-serif;
}
@font-face { font-family: "JetBrains Mono"; src: url("/fonts/JetBrainsMono-Variable.woff2") format("woff2"); font-weight: 100 800; font-style: normal; font-display: swap; }
@font-face { font-family: "Noto Serif"; src: url("/fonts/NotoSerif-Variable.woff2") format("woff2"); font-weight: 100 900; font-style: normal; font-display: swap; }
```

## kioku.css (тема Tailwind v4)

```css
/* Kïoku × Tailwind CSS v4 — theme layer.
   Values come from the Kïoku tokens (tokens.css defines --red, --ink, --grad-* …);
   colours are mapped with `@theme inline`, so utilities read the live token and follow [data-theme]. */
@import "tailwindcss";
@import "./kioku-tokens.css";

@theme {
  --color-*: initial;
  --font-*: initial;
  --radius-*: initial;
  --shadow-*: initial;
  --inset-shadow-*: initial;
  --drop-shadow-*: initial;
  --text-*: initial;

  --spacing: 4px;

  --font-mono: "JetBrains Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  --font-serif: "Noto Serif", "Noto Serif TC", "Noto Serif JP", Georgia, serif;
  --font-kana: "Noto Sans JP", sans-serif;
  --default-font-family: var(--font-mono);
  --default-mono-font-family: var(--font-mono);

  --text-micro: 10px;
  --text-micro--line-height: 12px;
  --text-caption: 11px;
  --text-caption--line-height: 14px;
  --text-caps-sm: 12px;
  --text-caps-sm--line-height: 15px;
  --text-caps-sm--letter-spacing: 0.04em;
  --text-ui: 13px;
  --text-ui--line-height: 16px;
  --text-caps: 14px;
  --text-caps--line-height: 17px;
  --text-caps--letter-spacing: 0.02em;
  --text-lead: 18px;
  --text-lead--line-height: 24px;
  --text-word: 20px;
  --text-word--line-height: 24px;
  --text-title: 24px;
  --text-title--line-height: 28px;
  --text-quote: 40px;
  --text-quote--line-height: 52px;
  --text-display: 64px;
  --text-display--line-height: 64px;
  --text-display--letter-spacing: -0.01em;
  --text-wordmark: 128px;
  --text-wordmark--line-height: 1;

  --tracking-wordmark: 1em;
  --tracking-kana: 1em;
}

@theme inline {
  --color-red: var(--red);
  --color-red-deep: var(--red-deep);
  --color-pink: var(--pink);
  --color-red-300: var(--red-300);
  --color-red-100: var(--red-100);
  --color-black: var(--black);
  --color-grey-900: var(--grey-900);
  --color-grey-600: var(--grey-600);
  --color-grey-400: var(--grey-400);
  --color-grey-300: var(--grey-300);
  --color-grey-200: var(--grey-200);
  --color-grey-100: var(--grey-100);
  --color-white: var(--white);

  --color-ground: var(--ground);
  --color-surface: var(--surface);
  --color-ink: var(--ink);
  --color-ink-muted: var(--ink-muted);
  --color-line: var(--line);
  --color-line-soft: var(--line-soft);
  --color-accent: var(--accent);
  --color-on-accent: var(--on-accent);
  --color-accent-deep: var(--accent-deep);
  --color-on-accent-deep: var(--on-accent-deep);
  --color-highlight: var(--highlight);
}

/* Brand gradients and textures */
@utility ki-fade { background-image: var(--grad-fade); }
@utility ki-ignite { background-image: var(--grad-ignite); }
@utility ki-hero { background-image: var(--grad-hero); }
@utility ki-tile { background-image: var(--grad-tile); }
@utility ki-ember { background-image: var(--grad-ember); }
@utility ki-highlight {
  background-image: var(--grad-highlight), linear-gradient(90deg, #FFFFFF00 45%, #FFFFFF 100%), radial-gradient(circle, #FD4B61 0.9px, #FD4B6100 1.3px);
  background-size: 100% 100%, 100% 100%, 3px 3px;
  -webkit-box-decoration-break: clone;
  box-decoration-break: clone;
}
@utility ki-halftone {
  background-image: radial-gradient(circle, var(--red) 1.2px, #FE262700 1.7px);
  background-size: 4px 4px;
}
@utility ki-focus {
  &:focus-visible { outline: 2px solid transparent; box-shadow: var(--focus-ring); }
}
@utility caps { text-transform: uppercase; }

@layer base {
  body { background: var(--ground); color: var(--ink); font-family: var(--font-mono); -webkit-font-smoothing: antialiased; }
  :lang(zh-Hant), :lang(ja), :lang(zh) { font-family: var(--font-serif); }
}
```

## Словарь классов

| Что | Классы |
| --- | --- |
| Фон / текст страницы | `bg-ground text-ink`, вторичный — `text-ink-muted` |
| Акцент | `bg-accent text-on-accent` (red + black), `bg-accent-deep text-on-accent-deep` (red-deep + white) |
| Лесенка серых | `bg-grey-400` → `bg-grey-300` → `bg-grey-200` → `bg-grey-100` / `bg-white` |
| Рамки | `border border-line` (смысловые), `border-line-soft` (декор); стык соседей — `-ml-px` / `-mt-px` |
| Шрифты | `font-mono` (по умолчанию), `font-serif` для иероглифов, `font-kana` для きおく |
| Текст | `text-wordmark` `text-display` `text-quote` `text-title` `text-word` `text-lead` `text-caps` `text-ui` `text-caps-sm` `text-caption` `text-micro` |
| Капс | `caps` + `text-caps` / `text-caps-sm` |
| Трекинг логотипа | `tracking-wordmark` (1em) или сетка `grid-cols-5 gap-x-[1em]` |
| Градиенты | `ki-fade` `ki-ignite` `ki-hero` `ki-tile` `ki-ember` |
| Текстуры | `ki-highlight` (подсветка фразы), `ki-halftone` (полутон) |
| Фокус | `ki-focus` на каждом интерактивном элементе |
| Отступы | шаг 4px: `p-4` = 16px, `px-12` = 48px, `mt-24` = 96px |

## Tailwind v3

Если проект ещё на v3, та же тема в `tailwind.config.js` (переменные — из `kioku-tokens.css`):

```js
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
```

В v3 градиенты — `bg-fade`, `bg-hero` и т.д.; `ki-highlight`, `ki-halftone` и `ki-focus` перенесите в `@layer utilities` как обычный CSS из блока выше.
