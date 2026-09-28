# InfoSection

Текстовая секция лендинга: манифест, «HOW IT WORKS?» и «KEY FEATURES:» в 12-колоночной сетке, капсом.

- Абзацы — `col-span-8`, боковые пометки (きおく / MEMORY) — справа `text-ink-muted`.
- Заголовок-вопрос в 3 колонках слева, список — в 6 колонках; список без маркеров, каждая строка — один шаг.
- Второстепенные блоки («KEY FEATURES», «BY TC BUREAU») — `text-ink-muted`.
- Между блоками — `mt-24` и больше: воздух — часть стиля.

## Разметка (HTML + Tailwind)

```html
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300&display=swap">

<section class="grid grid-cols-12 gap-x-6 px-12 py-16 text-caps caps">

  <!-- statement + side notes -->
  <div class="col-span-8 space-y-4">
    <p>Traditional translators provide static definitions that are easily forgotten. Users often lack the context and visual associations needed to move a word from their passive vocabulary to active use.</p>
    <p>Kïoku leverages AI to instantly build a mind-map around any selected word. Instead of a simple list of meanings, you see how a word “bonds” with verbs, which adjectives describe it, and the specific contexts where it thrives.</p>
  </div>
  <aside class="col-span-4 flex flex-col items-end gap-16 text-ink-muted">
    <span lang="ja" class="mt-12 font-kana normal-case text-ui font-light">きおく</span>
    <span>Memory</span>
  </aside>

  <!-- how it works -->
  <h2 class="col-span-3 mt-24 font-normal">How it works?</h2>
  <ol class="col-span-6 mt-24">
    <li>Highlight the word</li>
    <li>Plugin analyzes surrounding text to determine the topic</li>
    <li>Plugin creates a mind-map, grouping related words</li>
    <li>Plugin matches the new word with user history</li>
    <li>Add words or entire thematic clusters to your dictionary</li>
  </ol>

  <!-- key features + credit -->
  <div class="col-span-9 mt-8 text-ink-muted">
    <h2 class="font-normal">Key features:</h2>
    <ul class="mt-4">
      <li>Interactive mind-map</li>
      <li>Personalized smart selection</li>
      <li>Structured dictionary</li>
    </ul>
  </div>
  <p class="col-span-3 mt-8 self-end text-right text-ink-muted">By TC Bureau</p>
</section>
```
