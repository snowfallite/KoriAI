# LetterBurst

Декоративный паттерн: буквы K ï o k u на плитках `red-300`, каждая связана лучом с одной точкой, плюс поле полутона и подпись-цитата.

- Только для обложек, разделов и презентаций; всегда `aria-hidden="true"`.
- Генерируется детерминированно (сид), чтобы паттерн не «прыгал» между загрузками.
- Контраст красных букв на `red-300` низкий — поэтому паттерн никогда не несёт смысла.

## Разметка (HTML + Tailwind)

```html
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@400&display=swap">

<figure class="relative px-10 pt-8 pb-10">
  <!-- halftone field with the mark -->
  <div class="relative h-[120px] ki-halftone">
    <span class="absolute top-4 right-8 text-[72px] leading-none text-black">Kï</span>
  </div>
  <p lang="zh-Hant" class="mt-6 text-title">歌舞伎的劇目內容大多取自傳統典故與文學</p>
  <svg id="burst" class="mt-2 block w-full" viewBox="0 0 880 260" aria-hidden="true"></svg>
  <figcaption class="absolute bottom-10 left-10 ki-ember px-2 py-1 text-ui">Most Kabuki plays are based on traditional legends</figcaption>
</figure>

<script>
/* LetterBurst — rows of K ï o k u on red-300 tiles, every tile tied to one focal point by a hairline. */
(function () {
  var svg = document.getElementById('burst'), NS = 'http://www.w3.org/2000/svg';
  var W = 880, H = 260, FX = 400, FY = 90, TW = 30, TH = 36, word = 'Kïoku';
  function el(tag, a, p) { var n = document.createElementNS(NS, tag); for (var k in a) n.setAttribute(k, a[k]); (p || svg).appendChild(n); return n; }
  var rays = el('g', { style: 'stroke:var(--red);stroke-width:var(--stroke-hair)' });
  var tiles = el('g', {});
  // deterministic pseudo-random so the pattern is stable
  var seed = 7; function rnd() { seed = (seed * 9301 + 49297) % 233280; return seed / 233280; }
  for (var row = 0; row < 6; row++) {
    var y = row * 44, x = rnd() * 60 - 40, i = Math.floor(rnd() * 5);
    while (x < W) {
      var ch = word[i % 5]; i++;
      if (rnd() > 0.28) {
        el('line', { x1: FX, y1: FY, x2: x + TW / 2, y2: y + TH / 2 }, rays);
        el('rect', { x: x, y: y, width: TW, height: TH, style: 'fill:var(--red-300)' }, tiles);
        var t = el('text', { x: x + TW / 2, y: y + 27, 'text-anchor': 'middle', style: 'fill:var(--red);font:500 26px var(--font-mono)' }, tiles);
        t.textContent = ch;
      }
      x += TW + 8 + Math.floor(rnd() * 3) * 38;
    }
  }
})();
</script>
```
