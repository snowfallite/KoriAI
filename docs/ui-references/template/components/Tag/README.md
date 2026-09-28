# Tag

Чипы тем и фильтров: прямоугольники в рамке 1px, выбранный — залитый, счётчик скрытых — «+N» на `red-deep`.

- В панели расширения — фиксированные `black`/`white`; на странице сайта — семантические `ink`/`ground`/`line`.
- Чипы стыкуются рамками (`-ml-px`, `-mt-px`) и переносятся как текст.
- Пара языков — `zh-Hant → En`, `text-caption`, справа.

## Разметка (HTML + Tailwind)

```html
<div class="flex flex-wrap items-start gap-10 p-8">
  <!-- on the light extension panel -->
  <div class="w-[300px] bg-white p-4 text-black">
    <p class="text-ui font-bold">Topics</p>
    <ul class="mt-2 flex flex-wrap text-caption" aria-label="Topics">
      <li class="border border-black bg-black px-1.5 py-0.5 text-white">Impact &amp; impressions</li>
      <li class="-ml-px border border-black px-1.5 py-0.5">Theater &amp; performance</li>
      <li class="-mt-px border border-black px-1.5 py-0.5">Politics &amp; global affairs</li>
      <li class="-mt-px bg-red-deep px-1.5 py-0.5 font-bold text-white" aria-label="1 more topic">+1</li>
    </ul>
    <p class="mt-4 text-right text-caption">zh-Hant <span aria-hidden="true">→</span> En</p>
  </div>

  <!-- on the page ground, theme-aware -->
  <ul class="flex flex-wrap gap-2 text-caption" aria-label="Filters">
    <li class="border border-line bg-ink px-2 py-1 text-ground">Selected</li>
    <li class="border border-line px-2 py-1">Default</li>
    <li class="border border-line-soft px-2 py-1 text-ink-muted">Muted</li>
    <li class="bg-accent px-2 py-1 text-on-accent">New · 12</li>
  </ul>
</div>
```
