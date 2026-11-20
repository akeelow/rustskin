# Промт для Nano Banana: референс Sauna Bench v2.0

Зачем: картинка-ориентир по материалам и износу для [../PLAN_v2.md](../PLAN_v2.md). Текстурой она не станет: всё
равно моделируем в Blender.

Как пользоваться:
- **Промт 1** — главный. Приложи к нему скриншот из игры `../screenshots/v1.2_34_day.webp`. Тогда Nano Banana
  сохранит форму модели, ракурс и пропорции и поменяет только материалы. Без скриншота кровать выйдет другой формы.
- **Промты 2–5** — крупные планы. К каждому тоже можно приложить этот скриншот или результат промта 1, чтобы держать
  один стиль.
- Если на картинке появится текст, клеймо, человек или свечение, перегенерируй: по правилам сета их быть не должно.

Промты на английском: на нём модель понимает точнее.

---

## Промт 1 — общий вид, редактирование скриншота

```
Edit the attached image. Keep the exact same object shape, proportions, silhouette, camera angle,
lighting and background. Do not add or remove any parts. Change only the surfaces and materials.

The object is a sauna bench made by a survivor from an old roadside bed frame. Photorealistic game
asset look, highly detailed weathered materials, every detail has real physical relief (not painted):

- Deck (the flat top): 13 hand-cut aspen slats running lengthwise, 7-10 cm wide, uneven 3-7 mm gaps
  with darkness below, hand-planed chamfers. Steam-aged silver-grey honey wood, deeply weathered raised
  grain (soft wood worn away, hard growth rings standing up). Smoother and slightly polished in the
  middle where people lie. Small dark knots, one knot fallen out. Dry checks and end cracks, more of them
  at the foot end. One slat made of two pieces butted together, one slat freshly replaced (lighter,
  sharp edges), one rough-sawn pallet board with old nail holes. Square forged nail heads in pairs over
  each cross joist, hammer crescent dents next to some nails, one nail bent over. A few shallow dents
  and scratches near the foot end where a wash tub is put down, a faint white mineral ring. Four dry
  birch leaves and two thin birch twigs lying on the boards, one leaf half fallen into a gap.
- Sides of the deck: two horizontal aspen boards on each side, nailed on, square corner blocks with
  end grain at the rounded corners, one short patch board. Wet dark bottom edge with frayed fibres,
  rust streaks running down from the nails, white mineral drip streaks.
- Foot end (toward the stove, the end without the tall headboard): smoked and darker, soot, dried-out
  cracks, the lower corner lightly charred with a cracked "alligator skin" char pattern.
- Pillow: replaced by a folded washed linen towel, off-white #CFC6B4, the front edge rolled into a thick
  bolster with the spiral of rolled layers visible on the ends, the back part stacked folds. Two faded
  brick-red stripes #8E3A30 near each end. Crumpled linen texture, compression creases, a soft dent where
  the head lies, hemmed edges with visible stitching, a short twisted fringe on one end. Slightly damp
  and greyer where it touches the wood.
- Headboard: two boards from an old door, tongue-and-groove V-joint and a moulded bead line. Thick old
  paint mostly peeled: faded green on the upper board with blue primer showing in the chips, faded blue on
  the lower board. Paint has real thickness, chipped edges, crackle pattern, curling flakes. Bare wood
  between paint islands is grey and deeply weathered. Ghost of a removed hinge with three screw holes, a
  small tarnished brass keyhole plate and a round handle hole plugged with a wooden dowel. Top edge worn
  round by hands. Rust halos around the nails.
- Posts: four hand-hewn aspen posts with axe scallop marks, axe-cut sloped tops showing end grain and
  radial cracks, long seasoning checks, darker and frayed at the floor. Head posts worn smooth on top.
- Cross joists under the deck (the ends sticking out above the side rails): rough band-sawn dark wet
  wood, end grain with rings and a crack, white mineral crust on the ends.
- Metal frame (side rails, end rails, low stretchers, corner plates): old steel channel with dark
  almost-black olive enamel, about half of it chipped off, rust pits clustered in the chips and on the
  bottom flanges, rust blisters under the paint, a row of unused punched oval holes, hammer dents,
  hex bolts with washers on the corner plates (one bolt replaced by a bent nail), a lumpy welded repair
  seam on a side rail, twisted wire wrapped around a stretcher.

Palette: aspen #C2A77E aged to grey, steam-darkened wood #7A5A3C, soot #45332A, linen #CFC6B4,
brick stripe #8E3A30, rust #8C4A26. Muted, natural, believable. No text, no logos, no markings,
no glow, no people, no extra objects.
```

## Промт 2 — крупно настил у изножья

```
Close-up photo-real reference of the foot end of a handmade sauna bench deck, low grazing light so every
relief detail casts a shadow. Aspen slats with deeply weathered raised grain, uneven gaps, dark knots,
dry cracks along the grain and at slat ends, square forged nail heads with hammer crescent dents, one
bent nail, shallow dents and scratches from a wash tub, faint white mineral ring, soot darkening toward
the edge, two dry birch leaves with raised veins and curled edges, a thin birch twig. Muted steam-aged
grey-honey wood. No text, no logos, no people.
```

## Промт 3 — крупно полотенце

```
Close-up of a folded washed linen towel used as a headrest on a wooden sauna bench, off-white #CFC6B4
with two faded brick-red #8E3A30 woven stripes near the end. The front edge rolled into a thick bolster,
the end shows the spiral of rolled layers, the rest stacked folds with visible layer edges. Crumpled
linen texture, compression creases, a soft dent where a head rests, double-folded hem with visible
stitching, a short twisted fringe on one end. Slightly damp and greyer where it touches the wet wood.
Soft daylight. No text, no logos, no people.
```

## Промт 4 — крупно спинка из дверных досок

```
Close-up of a sauna bench headboard made of two boards from an old door, nailed to hand-hewn aspen
posts. Tongue-and-groove V-joint and a moulded bead line. Old thick paint mostly peeled off: faded green
upper board with blue primer showing in the chips, faded blue lower board. Paint has real thickness,
chipped stepped edges, crackle pattern, curling flakes. Bare wood between paint islands grey and deeply
weathered. Ghost of a removed hinge with three screw holes, a small tarnished brass keyhole plate, a
round handle hole plugged with a wooden dowel showing end grain, rust halos around forged nails, top edge
worn round. Grazing light. No text, no logos, no people.
```

## Промт 5 — крупно угол каркаса

```
Close-up of the corner of a scrap-built sauna bench frame: an old steel channel rail with dark
almost-black olive enamel, about half chipped off, rust pits clustered in the chips and on the bottom
flange, rust blisters, a row of unused punched oval holes, hammer dents, a corner plate with hex bolts
and washers (one bolt replaced by a bent nail), a lumpy welded repair seam, twisted wire wrapped around
the low stretcher. Above it the ends of dark wet band-sawn wooden joists with end grain and white mineral
crust, a hand-hewn aspen post with axe marks. White mineral drip streaks on the steel. Grazing light.
No text, no logos, no people.
```
