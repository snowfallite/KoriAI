# Wordmark

Логотип Kïoku в трёх записях: разреженный **K Ï O K U** с каной, компактный **Kïoku** с надстрочной きおく и знак **Kï**.

- **Разреженный** — hero, обложки, первый слайд. Пять колонок с зазором 1em (`grid-cols-5 gap-x-[1em]`), кана `font-kana font-light text-ink-muted` строго под Ï, O и вторым K.
- **Компактный** — шапка, подвал, подписи. Кана `text-caps-sm`/`text-micro` прижата к верху.
- **Kï** — иконка расширения (белый квадрат с чёрной рамкой 4px), аватар, фавикон; на `red` — только чёрным.
- Логотип — живой текст JetBrains Mono (`aria-label="Kïoku"` на контейнере) или SVG из `assets/Logos`.

Не делайте: не красьте буквы в `red`, не меняйте трекинг, не ставьте кану над буквами или в строку, не набирайте логотип в serif.

## Разметка (HTML + Tailwind)

```html
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300&display=swap">

<div class="grid grid-cols-[1fr_auto] gap-x-16 gap-y-12 p-12">

  <!-- 1 · spaced wordmark with kana -->
  <div class="col-span-2">
    <div class="grid w-max grid-cols-5 gap-x-[1em] text-[96px] leading-none" aria-label="Kïoku">
      <span>K</span><span>Ï</span><span>O</span><span>K</span><span>U</span>
      <span></span>
      <span lang="ja" class="mt-5 text-center font-kana text-word font-light text-ink-muted">き</span>
      <span lang="ja" class="mt-5 text-center font-kana text-word font-light text-ink-muted">お</span>
      <span lang="ja" class="mt-5 text-center font-kana text-word font-light text-ink-muted">く</span>
      <span></span>
    </div>
  </div>

  <!-- 2 · compact wordmark with superscript kana -->
  <div class="flex items-start gap-1">
    <span class="text-display leading-none">Kïoku</span>
    <span lang="ja" class="font-kana text-caps-sm font-light tracking-normal text-ink-muted">きおく</span>
  </div>

  <!-- 3 · mark and icon -->
  <div class="flex items-end gap-6">
    <span class="text-display leading-none">Kï</span>
    <span class="grid size-16 place-items-center border-4 border-black bg-white text-title text-black">Kï</span>
    <span class="grid size-16 place-items-center bg-red text-title text-black">Kï</span>
  </div>
</div>
```
