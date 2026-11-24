# Промт для Nano Banana: референс Sauna Stone Box v2.0

Зачем: картинка-ориентир по материалам и износу для [../PLAN_v2.md](../PLAN_v2.md). Текстурой она не станет: всё
равно моделируем в Blender.

Как пользоваться:
- **Промт 1** — общий вид. Приложи кадр из редактора `../screenshots/editor_16x9/three_quarter_day.jpg`: тогда
  Nano Banana сохранит форму ящика, ракурс и пропорции и поменяет только материалы.
- **Промт 2** — вид сверху внутрь, приложи `../screenshots/editor_16x9/top_day.jpg`.
- **Промт 3** — крупный план угла и обруча (можно приложить результат промта 1).
- Если появится текст, клеймо, человек, крышка или неоновое свечение — перегенерируй: по правилам сета их быть не должно.

Промты на английском: на нём модель понимает точнее.

---

## Промт 1 — 3/4 сверху, днём

```
Edit the attached image. Keep the exact same object shape, proportions, silhouette, camera angle,
lighting and background. The crate has no lid. Do not add or remove any parts. Change only the
surfaces and materials.

The object is an old open wooden crate kept next to a sauna stove for spare sauna stones and embers.
Photorealistic game asset, highly detailed weathered materials, every detail has real physical relief
(not painted):

- Walls: four horizontal aspen boards on each side, rough-sawn and weathered grey-brown honey wood,
  raised grain (soft wood worn away, hard rings standing up), a few small dark knots with the grain
  flowing around them, dry checks running from the board ends, real thin gaps between the boards.
  Board ends at the corners show end grain with saw marks, nailed with pairs of square forged nail
  heads, hammer crescent dents next to some nails. Top edges worn round and dented, the handle slots
  on the short ends worn smooth and darkened by hands.
- Two iron hoops cut from an old barrel run around the crate: 4.5 cm wide strap with rolled edges,
  dark scaly iron with rust pits, an overlapping joint with three domed rivets, nailed to the boards
  every 15-20 cm, the strap slightly lifting off the wood at the corners. Rust streaks run down from
  the nails.
- The side facing the stove (the right long side) is drier, darker and smoked, more cracks, the top
  edge charred into small "alligator skin" char cells and nicked by a coal shovel. A flattened tin-can
  patch with crimped edges is nailed over a burnt hole at its bottom corner.
- Inside, on a warped steel tray with a turned-up rim: a heap of dark grey-black gabbro-diabase sauna
  stones, chipped angular pieces 3-9 cm with sharp fracture faces and chipped edges, a few rounded
  older stones, two stones cracked from the heat. Between and under the stones lumps of charcoal with
  cracked alligator surface, deep red-orange embers glowing only inside the cracks and deep gaps,
  grey ash piled in the corners. One scorched curled birch leaf on the stones.

No text, no logos, no people, no lid, no neon. Natural warm ember glow only, weak in daylight.
```

## Промт 2 — сверху внутрь, днём

```
Edit the attached image. Keep the exact same crate, camera angle, lighting and background, the crate
has no lid. Change only the surfaces and materials, as in this description: [вставить описание из
промта 1]. Focus on the inside: the stone heap on the steel tray, chipped angular dark stones with
fracture faces and chipped edges, charcoal lumps with cracked surface and embers glowing deep in the
cracks, grey ash in the corners, the tray rim visible along the walls, a scorched curled birch leaf.
The inner faces of the walls show the same weathered boards and the two iron hoops.
```

## Промт 3 — крупно: угол ящика со стороны печи

```
Close-up photo of the corner of an old weathered aspen crate next to a sauna stove: horizontal
rough-sawn boards with raised grain and dry checks, board ends with end grain and saw marks, pairs of
square forged nail heads with hammer dents, an iron barrel hoop with rolled edges, rust pits and a
riveted overlap joint bent around the corner and nailed to the boards, rust streaks below the nails.
The top edge is charred into small cracked char cells and nicked by a coal shovel. Soft side light.
Photorealistic, no text, no logos.
```
