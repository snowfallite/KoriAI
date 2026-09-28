# CategoryList

Список тем словаря «лесенкой»: плашки `grey-600` по ширине текста, одна под другой, со счётчиком надстрочными цифрами.

- Пункт — ссылка `inline-block bg-grey-600 text-white text-lead font-light`, число — `<sup class="text-micro">`.
- Текущая тема — `bg-red text-black` и `aria-current`; hover — `bg-black`.
- Список не выравнивается по ширине: рваный правый край — часть рисунка.

## Разметка (HTML + Tailwind)

```html
<div class="p-8">
  <nav aria-label="Dictionary topics" class="w-[360px] bg-white py-6">
    <ul class="flex flex-col items-start text-lead font-light text-white">
      <li><a href="#" class="ki-focus inline-block bg-grey-600 py-1 pr-3 pl-2.5 hover:bg-black">Impact &amp; Influence<sup class="ml-1 text-micro">12</sup></a></li>
      <li><a href="#" class="ki-focus inline-block bg-grey-600 py-1 pr-3 pl-2.5 hover:bg-black">Psychology<sup class="ml-1 text-micro">17</sup></a></li>
      <li><a href="#" class="ki-focus inline-block bg-grey-600 py-1 pr-3 pl-2.5 hover:bg-black">Human Behavior<sup class="ml-1 text-micro">58</sup></a></li>
      <li><a href="#" aria-current="true" class="ki-focus inline-block bg-red py-1 pr-3 pl-2.5 text-black">Communication<sup class="ml-1 text-micro">9</sup></a></li>
      <li><a href="#" class="ki-focus inline-block bg-grey-600 py-1 pr-3 pl-2.5 hover:bg-black">Critical Thinking<sup class="ml-1 text-micro">4</sup></a></li>
      <li><a href="#" class="ki-focus inline-block bg-grey-600 py-1 pr-3 pl-2.5 hover:bg-black">Business &amp; Strategy<sup class="ml-1 text-micro">31</sup></a></li>
      <li><a href="#" class="ki-focus inline-block bg-grey-600 py-1 pr-3 pl-2.5 hover:bg-black">Technology<sup class="ml-1 text-micro">46</sup></a></li>
      <li><a href="#" class="ki-focus inline-block bg-grey-600 py-1 pr-3 pl-2.5 hover:bg-black">Science<sup class="ml-1 text-micro">8</sup></a></li>
      <li><a href="#" class="ki-focus inline-block bg-grey-600 py-1 pr-3 pl-2.5 hover:bg-black">Philosophy<sup class="ml-1 text-micro">26</sup></a></li>
    </ul>
  </nav>
</div>
```
