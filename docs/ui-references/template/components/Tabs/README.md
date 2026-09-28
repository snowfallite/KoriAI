# Tabs

Переключатель сортировки словаря: чёрная плашка «Sort by → Topic» и ряд вкладок в рамках, выровненный вправо.

- Активная вкладка — `bg-red-deep text-white`, остальные — рамка `border-black`, стык `-ml-px`.
- `role="tablist"`/`role="tab"` и `aria-selected`; текущее значение дублируется справа в плашке.
- Подписи вкладок — `text-caption`, как есть в данных (`Part-of-speech`).

## Разметка (HTML + Tailwind)

```html
<div class="p-8">
  <div class="w-[420px] bg-white text-black">
    <div class="flex items-baseline justify-between bg-black px-4 py-5 text-title text-white">
      <span>Sort by <span aria-hidden="true">→</span></span>
      <span id="sort-current">Topic</span>
    </div>
    <div role="tablist" aria-label="Sort by" class="flex justify-end pl-8 text-caption">
      <button role="tab" aria-selected="true" class="ki-focus border border-red-deep bg-red-deep px-2 py-0.5 text-white">Topic</button>
      <button role="tab" aria-selected="false" class="ki-focus -ml-px border border-black px-2 py-0.5 hover:bg-grey-200">Language</button>
      <button role="tab" aria-selected="false" class="ki-focus -ml-px border border-black px-2 py-0.5 hover:bg-grey-200">Part-of-speech</button>
      <button role="tab" aria-selected="false" class="ki-focus -ml-px border border-black px-2 py-0.5 hover:bg-grey-200">Alphabet</button>
    </div>
    <div class="h-8"></div>
  </div>
</div>
<script>
  document.querySelectorAll('[role=tab]').forEach(function (tab) {
    tab.addEventListener('click', function () {
      document.querySelectorAll('[role=tab]').forEach(function (t) {
        var on = t === tab;
        t.setAttribute('aria-selected', on);
        t.classList.toggle('bg-red-deep', on); t.classList.toggle('border-red-deep', on); t.classList.toggle('text-white', on);
        t.classList.toggle('border-black', !on);
      });
      document.getElementById('sort-current').textContent = tab.textContent;
    });
  });
</script>
```
