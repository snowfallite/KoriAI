# LogoTile

Плитка-логотип: серая рамка `grey-200`, поле градиента `ki-tile` и разреженный KÏOKU или Kï под ним.

- Для аватаров, обложек соцсетей, карточки в сторе, превью ссылок.
- Рамка — 8px (`p-2`), в маленькой версии 4px; буквы всегда `black`.
- Пропорции поля и подписи свободные, но поле градиента не меньше половины высоты плитки.

## Разметка (HTML + Tailwind)

```html
<div class="flex flex-wrap items-end gap-8 p-8">

  <!-- default: grey frame, gradient field, spaced wordmark -->
  <figure class="w-[260px] bg-grey-200 p-2">
    <div class="ki-tile h-20"></div>
    <figcaption class="grid grid-cols-5 place-items-center pt-4 pb-2 text-[34px] leading-none text-black" aria-label="Kïoku">
      <span>K</span><span>Ï</span><span>O</span><span>K</span><span>U</span>
    </figcaption>
  </figure>

  <!-- square: for avatars and store icons -->
  <figure class="grid size-[184px] grid-rows-[1fr_auto] bg-grey-200 p-2">
    <div class="ki-tile"></div>
    <figcaption class="pt-3 pb-1 text-center text-title text-black">Kï</figcaption>
  </figure>

  <!-- small: favicon-size, the gradient field shrinks to a strip -->
  <figure class="w-[88px] bg-grey-200 p-1">
    <div class="ki-tile h-6"></div>
    <figcaption class="pt-1.5 text-center text-ui text-black">Kï</figcaption>
  </figure>
</div>
```
