# Toolbar

Верхняя строка боковой панели: Kï и ↓ на `red`, слово и перевод на сегментах `ki-fade`, звук и галочка в ячейках `red-100`, под ней — выпадающая тема.

- Каждый текстовый сегмент получает свой `ki-fade` — красный выгорает к белому внутри сегмента, создавая ритм «ступенек».
- Иконочные ячейки — `bg-red-100`, hover — `bg-red-300`.
- Тема под строкой — `bg-grey-200 text-caption` с глифом ⌄.

## Разметка (HTML + Tailwind)

```html
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@400;500&display=swap">

<div class="p-8">
  <div class="w-[620px] bg-grey-100 text-black">
    <div class="flex h-10 items-stretch" role="toolbar" aria-label="Kïoku">
      <span class="flex items-center bg-red px-3 text-title">Kï</span>
      <button type="button" aria-label="Collapse" class="ki-focus grid w-8 place-items-center bg-red text-lead">↓</button>
      <span lang="zh-Hant" class="ki-fade flex items-center pr-10 pl-3 text-word font-medium">震撼力</span>
      <button type="button" aria-label="Listen" class="ki-focus grid w-9 place-items-center bg-red-100 hover:bg-red-300">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linecap="square" aria-hidden="true"><path d="M2 6h2.5L8 3v10L4.5 10H2z"/><path d="M10.5 6a2.5 2.5 0 0 1 0 4"/><path d="M12 4a5 5 0 0 1 0 8"/></svg>
      </button>
      <span class="ki-fade flex flex-1 items-center px-3 text-ui font-bold">mind-blowing effect</span>
      <button type="button" aria-label="Added to dictionary" class="ki-focus grid w-10 place-items-center bg-red-100 hover:bg-red-300">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linecap="square" aria-hidden="true"><path d="M3 8.5l3 3 7-7"/></svg>
      </button>
    </div>
    <button type="button" class="ki-focus ml-11 bg-grey-200 px-2 py-0.5 text-caption hover:bg-grey-300">Impact &amp; impressions <span aria-hidden="true">⌄</span></button>
    <div class="h-10"></div>
  </div>
</div>
```
