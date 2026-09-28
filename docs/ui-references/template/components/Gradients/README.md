# Gradients

Шесть градиентов и полутон бренда в виде утилит Tailwind: `ki-fade`, `ki-ignite`, `ki-ember`, `ki-highlight`, `ki-hero`, `ki-tile`, `ki-halftone`.

- Все градиенты линейные и идут от красного: к белому (fade), из чёрного (ignite), к бледно-красному (ember), вниз к чёрному (hero) или серому (tile).
- Значения — токены семейства Gradient (`--grad-*`), утилиты — в разделе «Tailwind».
- На одном экране — максимум два градиента.

## Разметка (HTML + Tailwind)

```html
<div class="grid grid-cols-4 gap-6 p-8 text-caption">
  <figure><div class="ki-fade h-20"></div><figcaption class="mt-2">ki-fade · <span class="text-ink-muted">red → white</span></figcaption></figure>
  <figure><div class="ki-ignite h-20"></div><figcaption class="mt-2">ki-ignite · <span class="text-ink-muted">black → red</span></figcaption></figure>
  <figure><div class="ki-ember h-20"></div><figcaption class="mt-2">ki-ember · <span class="text-ink-muted">red → red-300</span></figcaption></figure>
  <figure><div class="h-20 bg-white p-3"><span class="ki-highlight px-1 text-ui text-black">highlighted phrase</span></div><figcaption class="mt-2">ki-highlight · <span class="text-ink-muted">pink → clear + dots</span></figcaption></figure>
  <figure class="col-span-2"><div class="ki-hero h-24"></div><figcaption class="mt-2">ki-hero · <span class="text-ink-muted">pink → red → black, vertical</span></figcaption></figure>
  <figure><div class="ki-tile h-24"></div><figcaption class="mt-2">ki-tile · <span class="text-ink-muted">pink → red → grey-200</span></figcaption></figure>
  <figure><div class="ki-halftone h-24 bg-white"></div><figcaption class="mt-2">ki-halftone · <span class="text-ink-muted">red dot, 4px pitch</span></figcaption></figure>
</div>
```
