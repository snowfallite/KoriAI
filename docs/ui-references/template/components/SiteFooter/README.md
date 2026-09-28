# SiteFooter

Подвал сайта: полоса `ki-fade`, компактный логотип, ссылки со стрелкой, кредиты TC Bureau и «↑ Top».

- Добавлен для рабочего сайта в языке лендинга: 12 колонок, `text-caps-sm caps`, ссылки — «→ …».
- Полоса `ki-fade` высотой 8px отделяет подвал вместо линии.

## Разметка (HTML + Tailwind)

```html
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300&display=swap">

<footer class="px-12 pt-16 pb-10">
  <div class="ki-fade h-2" aria-hidden="true"></div>
  <div class="mt-12 grid grid-cols-12 gap-x-6 text-caps-sm caps">
    <p class="col-span-3 flex items-start gap-1 normal-case">
      <span class="text-title leading-none">Kïoku</span>
      <span lang="ja" class="font-kana text-micro font-light text-ink-muted">きおく</span>
    </p>
    <nav aria-label="Footer" class="col-span-3 flex flex-col gap-1">
      <a href="#" class="ki-focus hover:text-accent">→ How it works</a>
      <a href="#" class="ki-focus hover:text-accent">→ Features</a>
      <a href="#" class="ki-focus hover:text-accent">→ Dictionary</a>
    </nav>
    <p class="col-span-4 text-ink-muted">Concept &amp; design<br>By TC Bureau</p>
    <a href="#top" class="ki-focus col-span-2 text-right hover:text-accent">↑ Top</a>
  </div>
</footer>
```
