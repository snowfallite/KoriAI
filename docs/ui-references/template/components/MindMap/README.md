# MindMap

Кластер слов вокруг выделенного: узлы WordNode, связанные прямыми линиями с красным центром, на полотне `grey-100`.

- Данные: центр и список узлов `{ w, x, y, open?, strong? }`; `strong` — прямая связь с центром (`red`, `stroke-map`), остальные — связь с родителем (`grey-400`, `stroke-hair`).
- Линии рисуются в SVG под узлами, узлы — абсолютно позиционированные HTML-кнопки (доступны с клавиатуры).
- Раскрытые узлы (`open`) показывают перевод; в карте одновременно — не больше двух-трёх раскрытых.
- Раскладку по кругу/силам делает приложение; компонент задаёт только вид.

## Разметка (HTML + Tailwind)

```html
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@400;500&display=swap">

<div class="p-8">
  <div id="map" class="relative h-[400px] w-[680px] overflow-hidden bg-grey-100 text-black" aria-label="Mind-map: 震撼力">
    <svg id="links" class="absolute inset-0 h-full w-full" aria-hidden="true"></svg>
  </div>
</div>

<!-- node template: the same stepped cells as WordNode, compact (h-7) -->
<template id="node">
  <div class="absolute inline-flex h-7 items-stretch text-caption">
    <button type="button" class="ki-focus grid w-7 place-items-center bg-grey-400 text-ui hover:bg-red">→</button>
    <span lang="zh-Hant" class="flex items-center bg-grey-300 px-2 text-ui font-medium"></span>
    <button type="button" aria-label="Add" class="ki-focus grid w-7 place-items-center bg-white text-ui hover:bg-grey-200">+</button>
  </div>
</template>

<script>
(function () {
  var map = document.getElementById('map'), svg = document.getElementById('links'), tpl = document.getElementById('node');
  var NS = 'http://www.w3.org/2000/svg';
  var hub = { x: 360, y: 250 };
  // x,y = left-middle of the node; strong = red link to the hub
  var nodes = [
    { w: '壓倒性', x: 200, y: 110, open: 'overwhelming', strong: true },
    { w: '體無完膚', x: 150, y: 40 },  { w: '屈服', x: 470, y: 50 },
    { w: '覺醒', x: 70, y: 150 },     { w: '獨走', x: 330, y: 165 },
    { w: '頓悟', x: 24, y: 215, strong: true },  { w: '銘記', x: 190, y: 205, strong: true },
    { w: '共鳴', x: 520, y: 200, strong: true }, { w: '驚愕', x: 420, y: 250, strong: true },
    { w: '戰慄', x: 470, y: 320, strong: true }, { w: '威圧', x: 250, y: 330, strong: true },
    { w: '衝擊', x: 60, y: 300, open: 'impact', strong: true }, { w: '靈魂', x: 560, y: 370, strong: true }
  ];
  function line(x1, y1, x2, y2, cls) {
    var l = document.createElementNS(NS, 'line');
    l.setAttribute('x1', x1); l.setAttribute('y1', y1); l.setAttribute('x2', x2); l.setAttribute('y2', y2);
    l.setAttribute('style', cls); svg.appendChild(l);
  }
  var parent = nodes[0];
  nodes.forEach(function (n, i) {
    if (n.strong) line(hub.x, hub.y, n.x, n.y, 'stroke:var(--red);stroke-width:var(--stroke-map)');
    else line(parent.x, parent.y, n.x + 20, n.y, 'stroke:var(--grey-400);stroke-width:var(--stroke-hair)');
  });
  nodes.forEach(function (n) {
    var el = tpl.content.firstElementChild.cloneNode(true);
    el.style.left = n.x + 'px'; el.style.top = (n.y - 14) + 'px';
    el.children[1].textContent = n.w;
    el.children[0].setAttribute('aria-label', 'Open ' + n.w);
    if (n.open) {
      el.children[0].textContent = '↓';
      el.children[0].className = 'ki-focus grid w-7 place-items-center bg-red text-ui';
      var tr = document.createElement('span');
      tr.className = 'flex items-center bg-white px-2 text-caption'; tr.textContent = n.open;
      el.insertBefore(tr, el.children[2]);
      el.removeChild(el.children[3]);
    }
    map.appendChild(el);
  });
  var h = document.createElement('span');
  h.className = 'absolute grid size-5 place-items-center bg-red text-caption';
  h.style.left = (hub.x - 10) + 'px'; h.style.top = (hub.y - 10) + 'px'; h.textContent = '→';
  h.setAttribute('aria-hidden', 'true');
  map.appendChild(h);
})();
</script>
```
