# SiteHeader

Шапка сайта: мета-строка лендинга в три колонки и навигационная полоса со знаком Kï и CTA.

- **Мета-строка** (как на лендинге) — `grid-cols-12`: 3 колонки «CONCEPT & DESIGN», 7 — описание продукта, 2 — «KÏOKU» справа. Всё `text-caps-sm caps`.
- **Навигация** — добавлена для рабочего сайта: знак Kï, ссылки капсом (текущая — `text-ink`, остальные — `text-ink-muted`, hover — `text-accent`), CTA из ячейки `ki-ignite` со стрелкой и поля `bg-red`.
- Потребитель задаёт ссылки и текст CTA. Разделители — `border-line-soft`.

## Разметка (HTML + Tailwind)

```html

<!-- A · meta line (as on the landing): three columns, caps-sm -->
<header class="grid grid-cols-12 gap-x-6 px-12 py-8 text-caps-sm caps">
  <p class="col-span-3">Concept &amp; design</p>
  <p class="col-span-7">AI-powered browser extension for contextual language learning</p>
  <p class="col-span-2 text-right">Kïoku</p>
</header>

<!-- B · navigation bar: mark, links, CTA -->
<header class="flex items-stretch border-y border-line-soft">
  <a href="#" class="ki-focus flex items-center px-12 text-title">Kï</a>
  <nav aria-label="Main" class="flex flex-1 items-center gap-10 text-caps-sm caps">
    <a href="#" class="ki-focus text-ink hover:text-accent">Concept</a>
    <a href="#" class="ki-focus text-ink-muted hover:text-accent">How it works</a>
    <a href="#" class="ki-focus text-ink-muted hover:text-accent">Features</a>
    <a href="#" class="ki-focus text-ink-muted hover:text-accent">Dictionary</a>
  </nav>
  <a href="#" class="ki-focus group flex items-stretch text-caps-sm caps text-black">
    <span class="grid w-14 place-items-center ki-ignite text-lead text-white">→</span>
    <span class="flex items-center bg-red px-8 py-6 group-hover:bg-white">Add to Chrome</span>
  </a>
</header>
```
