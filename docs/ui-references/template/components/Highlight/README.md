# Highlight

Выделения в тексте: выбранное слово (`bg-red` + курсор), вставленный перевод (`ki-highlight` — розовый, уходящий в полутон) и подпись-цитата на `ki-ember`.

- `ki-highlight` рассчитан на белый фон чужой страницы: переносится по строкам (`box-decoration-break: clone`), текст — `black` моно.
- Выбранное слово — `<mark class="bg-red text-black">`, без скругления.
- Иероглифы — `lang="zh-Hant"` / `lang="ja"`, перевод — `lang` целевого языка.

## Разметка (HTML + Tailwind)

```html
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@400;500&display=swap">

<div class="grid grid-cols-[1fr_400px] gap-10 p-10">
  <!-- a host page's text, always on white -->
  <article class="bg-white px-8 py-6 text-black">
    <p lang="zh-Hant" class="text-word leading-[34px]">
      歌舞伎與其它日本表演藝術有些區別，其中最為明顯的是被稱為「隈取」的濃妝臉譜與演員們身著的華美戲服。使得歌舞伎的舞臺視覺效果深具衝擊力與<mark class="bg-red text-black">震撼力</mark>。<span lang="ru" class="ki-highlight px-1 font-mono text-lead text-black">В основе большинства пьес кабуки лежат традиционные предания.</span>
    </p>
  </article>

  <div class="flex flex-col items-start justify-center gap-6">
    <p class="text-caps-sm caps text-ink-muted">Selection</p>
    <p lang="zh-Hant" class="text-title"><mark class="bg-red px-0.5 text-black">震撼力</mark><span class="ml-0.5 inline-block h-7 w-px translate-y-1 bg-ink" aria-hidden="true"></span></p>
    <p class="text-caps-sm caps text-ink-muted">Caption</p>
    <p class="ki-ember px-2 py-1 text-ui text-black">Most Kabuki plays are based on traditional legends</p>
  </div>
</div>
```
