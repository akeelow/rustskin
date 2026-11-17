# ТЗ для Nano Banana: референс Sauna Boiler

> Референс нужен для настроения и раскладки материалов. Истина для скина — модель и развёртка: всё, что
> генератор дорисует сверх силуэта, в игру не попадёт.

## Показывать ли оригинал

**Да, обязательно.** Скин — это только текстуры: форму печи менять нельзя. Без картинки оригинала генератор
нарисует бочку с трубой и дверцей, которых у модели нет (печь — глиняный «кувшин» 1.6 м на каменном
основании, с дырой топки и маленьким отверстием на макушке). Со скриншотом он перекрасит ту же форму.

Что приложить:

1. `original_day_crop.png` — оригинал днём, без интерфейса редактора. **Главная картинка**, её и редактируем.
2. По желанию `../../electric-furnace/workshop/studio.jpg` — Sauna Stove, как образец палитры и износа
   (в тексте сказать: «только палитра и степень износа, форму и детали не копировать»).

Ночной кадр оригинала не прикладывать вместе с дневным: генератор смешает освещение. Ночь — отдельным
запросом по уже готовой дневной картинке (текст ниже).

## Запрос 1 — день

```
Edit image 1. Keep the object's silhouette, proportions, camera angle and background EXACTLY as they are:
a bottle-shaped furnace — wide blocky base, bulging body, narrow neck, flared flat cap, one arched fire
opening low on the front. Do not add, remove or reshape any geometry: no chimney pipe, no door, no legs,
no handles sticking out, no objects standing next to it. Change only the surface materials, as if it were
repainted and re-clad. Every new detail must be low relief lying on the surface, no thicker than 2 cm.

New look: a scrap-built wood-fired water boiler for a survivor's sauna.

- Body, neck and cap: old dark riveted iron tank made of overlapping hammered plates, dented, held by
  three flat iron hoops with rivets. Rust (#8C4A26) along seams. White-grey limescale streaks and mineral
  runs dripping down from the seams and hoops, matte, uneven.
- Low on the body, to the side of the fire opening: a short wooden plug wrapped in a dirty linen rag
  (#CFC6B4) used as a tap, with a wet dark streak and limescale below it.
- On the side of the body: a small carved wooden ladle hanging flat against the iron on a bent nail.
- Base: a low wooden surround made of five rows of thin horizontal aspen slats (#C2A77E, darker and wet at
  the bottom #7A5A3C) bent round the base like the staves of a tub, uneven joints, a piece missing in the
  top row showing rusty iron behind, nailed with rusty nails and tied with two strands of rusty wire.
  Thin scrap boards, not armour.
- Fire opening: birch logs with white bark and glowing embers on dark ash inside. Embers glow in separate
  small clusters, deep orange (#FF6A1F) with amber edges (#FFB347), dark ash between them. Soot above the
  opening.
- Flat top of the cap: a pile of dark basalt stones (#3D3E41), not glowing, soot around the small smoke
  hole in the middle.

Style: realistic game asset, Rust (Facepunch) survival look, worn, handmade, matte. Mostly iron, wood only
at the base. No text, no letters, no numbers, no logos, no gauges with digits. No neon, no lava, no flames
shooting out, no glow on the metal or wood.
```

## Запрос 2 — ночь (по результату запроса 1)

```
Same object, same camera, same materials. Change only the lighting to night: dark blue ambient, no sun.
The only light is the fire opening: embers glowing in separate clusters, deep orange with amber edges,
dark ash between them, warm light spilling a short distance onto the lower rim of the opening and the
top of the wooden slats. The stones on top stay dark. No neon, no lava, no glow on the iron body.
```

## Запрос 3 — другие ракурсы (по желанию)

```
Same object and materials, viewed from the back-left, eye level. The back has no opening: riveted plates,
hoops, limescale streaks, slat fence around the base. Do not add any new parts.
```

## Как читать результат

- Годится: расклад «железо сверху — ряды реек снизу», ширина листов и шаг клёпок, где и как текут подтёки накипи,
  цвет золы и поленьев, насколько тёмный бак.
- Не годится, даже если красиво: всё, что торчит из силуэта (кран трубой, ковш на весу, труба, ножки),
  вертикальные рейки на бугристом основании (в v1 рейки горизонтальные: вертикальные на буграх ломались зигзагом), свечение на корпусе.
- Положить удачные картинки сюда же: `references/nb_day_*.png`, `nb_night_*.png`.
