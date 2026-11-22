# Промт для Nano Banana: референс Sauna Boiler v4

Зачем: ориентир по материалам и износу для [../PLAN_v4.md](../PLAN_v4.md). Текстурой картинка не станет, всё
равно моделируем в Blender.

Как пользоваться:
- **Промт 1** — главный. Приложи к нему кадр v3 из редактора `../workshop/ingame/front_day.jpg`. Тогда Nano Banana
  сохранит форму модели, ракурс и пропорции и поменяет только материалы. Без кадра выйдет бочка с трубой и
  дверцей, которых у модели нет.
- **Промты 2–3** — сзади и крупно. Приложи `../workshop/ingame/back_day.jpg` или результат промта 1.
- Если на картинке появится текст, клеймо, человек, труба, дверца или бортик-чаша на крышке, перегенерируй.

Промты на английском: на нём модель понимает точнее.

---

## Промт 1 — 3/4 спереди, редактирование кадра

```
Edit the attached image. Keep the exact same object shape, proportions, silhouette, camera angle,
lighting and background. Do not add or remove any parts: no chimney, no door, no tap, no rim on top.
Change only the surfaces and materials. Every new detail is low relief lying on the surface (max 2 cm).

The object is a wood-fired water boiler for a survivor's sauna, riveted together from scrap iron plates.
Photorealistic game asset, highly detailed weathered materials, every detail has real physical relief
(not painted), details are BIG and bold, readable from 2 metres:

- Tank: dark old iron plates overlapping each other, each plate hand-hammered with visible flat hammer
  facets 3-6 cm, chisel-cut wavy plate edges casting a thin shadow, big dents. Plates differ: one is a
  flattened oil-drum plate with two rolled ridges, one is old roofing sheet with faint corrugation.
  Large round rivet heads (2 cm) in rows along the seams, a few missing rivets leaving holes with rust runs,
  two rivets replaced by square-nut bolts.
- Five wide flat iron hoops (6 cm) made from cart-wheel tyres, worn shiny on the outer face, each with a
  different joint: riveted lap, forge weld, bolted ears. Rust scale lifting the plate edge under the hoops.
- Around the fire opening: a riveted iron frame with flaking heat scale, heat tint straw-to-blue, soot
  fanning upward. Above the opening the plates bulge in "pillows" between rivet rows from the heat, and a
  burnt-through spot is covered with a riveted checker-plate patch. A few horizontal scrape marks on the
  lower edge where logs are pushed in.
- Thick white-grey limescale crust running down from the seams, hoops and rivets: raised drips narrowing
  down with a droplet at the end, layered. Rust blisters with burst flaking edges and round pits under the
  hoops. Rust colour #8C4A26, limescale #CFC6B4.
- Left of the opening: a dark wooden plug with end-grain rings wrapped in a dirty linen rag tied with
  twine, the longest limescale drip and a wet streak below it.
- Right side: a carved birch ladle with knife facets hanging by a twine loop on a riveted iron hook.
- Base: a band of wide horizontal aspen boards (#C2A77E, wet and dark at the bottom #7A5A3C) overlapping
  like siding, each row casting a shadow on the one below, butt joints staggered with pairs of square
  forged nails, raised weathered grain, knots, checks, one old pallet board with saw arcs and nail holes,
  one missing piece showing rusty iron behind. Boards under the fire opening charred into cracked
  "alligator skin". Two strands of twisted rusty wire around the band, tightened with a nail twist.
- Fire opening: inside lined with cracked fireclay bricks, birch logs with white bark and embers.
No text, no logos, no people, no glowing except embers inside the firebox.
```

## Промт 2 — сзади

```
Same boiler, same materials, seen from behind, same camera height. Show the overlapping hammered plates,
the hoop joints, the rows of big rivets, rust blisters and the thick limescale drips on the sunny back
side, and the siding-like wooden band with nails and twisted wire. Keep the exact silhouette.
```

## Промт 3 — крупный план у топки

```
Close-up of the same boiler around the fire opening at knee height: riveted frame with heat scale and
heat tint, heat pillows in the plate, checker-plate patch, scrape marks, the plug wrapped in a rag with a
limescale drip, charred alligator-skin boards below. Raking daylight so every relief casts a shadow.
```
