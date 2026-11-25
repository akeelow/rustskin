# Промт для Nano Banana: референс Sauna Chair v2.0

Зачем: картинка-ориентир по материалам и износу для [../PLAN_v2.md](../PLAN_v2.md). Текстурой она не станет: всё
равно моделируем в Blender. Образец — [../../bed/plan_v2/nanobanana_prompt.md](../../bed/plan_v2/nanobanana_prompt.md).

Как пользоваться:
- **Промт 1** — главный. Приложи к нему кадр из игры `../screenshots/v1.4_front.webp` (или новый кадр 3/4). Тогда
  Nano Banana сохранит форму кресла, ракурс и пропорции и поменяет только материалы.
- **Промт 2** — сзади и снизу: приложи `../screenshots/v1.4_low_back.webp`.
- **Промты 3–4** — крупные планы. К ним можно приложить результат промта 1, чтобы держать один стиль.
- Если на картинке появится текст, клеймо, человек, подушка, свечение или новые части, перегенерируй: по правилам
  сета их быть не должно, а силуэт модели менять нельзя.

Промты на английском: на нём модель понимает точнее.

---

## Промт 1 — спереди / 3/4, редактирование скриншота

```
Edit the attached image. Keep the exact same object shape, proportions, silhouette, camera angle,
lighting and background. Do not add or remove any parts. Change only the surfaces and materials.

The object is an armchair in a sauna dressing room, rebuilt by a survivor from an old steel-framed
garden chair found in a roadside house. Photorealistic game asset look, highly detailed weathered
materials, every detail has real physical relief (not painted):

- Seat: six rough pallet boards running across (left to right), 8-10 cm wide, uneven 4-6 mm gaps with
  darkness below. Steam-aged grey-brown aspen with deeply weathered raised grain, circular saw arcs on
  two boards, groups of old pallet nail holes. Square forged nail heads at both ends of every board,
  hammer crescent dents next to some. The front board has a split near the left end held by a flat
  steel staple with two nails. Worn smooth and slightly polished in the middle where people sit. A few
  shallow dents and scratches on the right front where a wooden wash tub is put down, a damp darker
  patch there. One steamed brown oak leaf lying on the seat near the front edge.
- Front edge of the seat: a front board with its top edge worn round by legs, end grain on the board
  ends at the sides.
- Backrest front: six narrow vertical tongue-and-groove sauna lining boards (clapboard offcuts) with
  V-grooves between them, grey-brown, darker in the middle where sweaty backs lean, small dark knots,
  nail heads at top and bottom.
- Curved side frame of the backrest and arms: assembled from three straight aspen offcuts per side,
  butted with visible end-grain joints and a slight step, two nails on each side of every joint.
- Armrests: aspen bars, front ends with end grain and growth rings, greasy darker polished ends,
  two nails into each post. A dry yellow-brown birch leaf on the right armrest.
- Towel: a washed linen towel #CFC6B4 folded lengthwise and thrown over the top rail, hanging on the
  front; real cloth thickness, drape folds getting deeper toward the hem, crumpled linen texture,
  double-folded hem with visible stitching, two faded brick-red woven stripes #8E3A30 near the hem.
  A small green birch leaf stuck to it.
- Rear legs and seat side rails: old steel channel with dark almost-black olive enamel, about half
  chipped off, rust pits clustered in the chips and near the floor, hammer dents, a lumpy welded
  repair seam at the bend under the seat, a row of unused punched holes.
- Front left leg: an old shovel handle, dark hand-polished hardwood, the split bottom wrapped tightly
  with twisted steel wire over an old rubber tip. Front right leg: a square aspen post, frayed and dark
  at the floor.
- Small parts: steel corner brackets under the front of the seat, hex bolts, a bent steel strap
  joining the armrest to the backrest.

Palette: aged aspen #6D6862 (grey-brown, low saturation), warm board #72695D, linen #CFC6B4,
brick stripe #8E3A30, enamel #23251F, rust #8C4A26. Muted, natural, believable. No text, no logos,
no markings, no glow, no people, no cushions, no extra objects.
```

## Промт 2 — сзади и снизу, редактирование скриншота

```
Edit the attached image. Keep the exact same object shape, silhouette, camera angle and background.
Change only the surfaces and materials. Back view of the same sauna armchair: rough back side of the
vertical lining boards with two shallow relief grooves along each board, two horizontal aspen battens
across them with nail tips bent over and hammered flat into the battens, the linen towel hanging down
the back to mid-height. Underside of the seat: dark wet wooden lags under the boards. Steel channel legs
with dark olive enamel half chipped, rust pits and a rust crust at the floor, white mineral drip marks.
No text, no logos, no glow, no people, no extra objects.
```

## Промт 3 — крупно сиденье

```
Close-up of the seat of a handmade sauna armchair, low grazing light so every relief detail casts a
shadow. Six rough pallet boards running across, deeply weathered raised grain, circular saw arcs, old
pallet nail holes, uneven gaps with darkness below, square forged nail heads with hammer crescent
dents, a split in the front board held by a flat steel staple with two nails, shallow dents and
scratches from a wash tub, a steamed brown oak leaf with raised veins and curled edges. Muted
steam-aged grey-brown aspen. No text, no logos, no people.
```

## Промт 4 — крупно полотенце на спинке

```
Close-up of a washed linen towel #CFC6B4 thrown over the top rail of a wooden sauna chair backrest
made of narrow vertical tongue-and-groove boards. Real cloth thickness, the lengthwise fold visible at
one edge, drape folds deepening toward the hem, crumpled linen texture, double-folded hem with visible
stitching, two faded brick-red #8E3A30 woven stripes, a small green birch leaf stuck to the cloth. The
towel casts a soft shadow on the boards. Soft daylight. No text, no logos, no people.
```
