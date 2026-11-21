# Промт для Nano Banana: референс Sauna Stove v3.0

Зачем: картинка-ориентир по материалам и износу для [../PLAN_v3.md](../PLAN_v3.md). Текстурой она не станет: всё равно
моделируем в Blender.

Как пользоваться:
- **Промт 1** — главный. Приложи к нему кадр из игры `../screenshots/editor_16x9/three_quarter_day.jpg`. Тогда Nano Banana
  сохранит форму модели, ракурс и пропорции и поменяет только материалы.
- **Промты 2–4** — крупные планы; к ним можно приложить тот же кадр или результат промта 1.
- Если появится текст, цифры, клеймо, человек или неоновое свечение — перегенерировать (правила сета).

Промты на английском: так модель понимает точнее.

---

## Промт 1 — общий вид, редактирование кадра

```
Edit the attached image. Keep the exact same object shape, proportions, silhouette, camera angle, lighting and
background. Do not add or remove any parts. Change only the surfaces and materials.

The object is a sauna stove a survivor made from an old enamel kitchen cooker. Photorealistic game asset look, highly
detailed weathered materials, every detail has real physical relief (not painted):

- Sides: vertical aspen slats of different widths (6-9 cm), each slat slightly cupped, hand-cut uneven chamfers,
  uneven 3-6 mm gaps showing rusty blistered enamel behind. Steam-aged grey-honey wood with deeply weathered raised
  grain, small dark knots (one knot fallen out), dry end cracks at the top ends, frayed wet bottom ends. Square forged
  nail heads in pairs at the slat ends, hammer crescent dents next to some nails, one bent nail. A few dents. The slat
  next to the firebox door is charred at the top with an alligator-skin char pattern. Frame around the side made of
  rough slab wood with a strip of bark left on one piece. A flat wooden sauna thermometer plaque nailed on the side,
  scale with tick marks only, no numbers.
- Top: old cream enamel cooktop, enamel burned off to black iron around the burners, chipped stepped enamel edges,
  crackle pattern, crusty white mineral scale where water boils off. On each burner a heap of split dark basalt stones
  (sharp facets, chipped edges, white crust on top faces), held by a ring of twisted wire. Deep gaps between the
  lowest stones glow deep red-orange. Wooden rim around the top, inner edge charred. Two dry olive-brown birch leaves.
- Front: birch board with five turned birch knobs with grooves and knife-notch marks above each knob. Firebox door is
  a hand-forged flat-bar grate with hammer facets, round rivets at crossings, forge-welded corners, one bar is a piece
  of rebar; handle wrapped with rope. Behind the grate a heap of split stones and glowing cracked charcoal. Below the
  door a sliding ash damper plate with a bent tab and a little spilled ash.
- Band above the plinth: old olive-painted steel angle, half the paint chipped, rust pits along the bottom edge,
  boot dents, hex bolts at the corners.
- Plinth: three courses of old salvaged sooty bricks, chipped corners, spalled faces, crumbling recessed mortar, one
  missing brick replaced by a flat basalt stone, white salt bloom near the bottom.
- Pallet under it: wet dark rough-sawn boards with circular saw marks, gaps, nails, cracked ends, one broken corner.

Palette: aspen #C2A77E aged to grey, steam-darkened wood #7A5A3C, soot #45332A, basalt #3D3E41, glow #FF6A1F to
#FFB347 only in the deepest gaps, rust #8C4A26, old enamel cream-grey. Muted, natural, believable. No text, no
numbers, no logos, no neon, no people, no extra objects.
```

## Промт 2 — крупно верх плиты

```
Close-up, low grazing light, of the top of a scrap-built sauna stove made from an old enamel cooker: cream enamel
chipped in stepped islands, burned to black scaled iron around the burners, crackle pattern, lumpy white mineral
scale where water boils off. On each burner a heap of split dark basalt sauna stones with sharp facets, chipped edges
and white crust on top faces, held by a ring of twisted two-strand wire; the deepest gaps glow deep red-orange.
Charred wooden rim around the edge, two dry olive-brown birch leaves. No text, no numbers, no logos, no people.
```

## Промт 3 — крупно бок с обшивкой

```
Close-up, low grazing light, of the side of a homemade sauna stove clad in vertical aspen slats of different widths:
cupped slats, hand-cut chamfers, uneven gaps with rusty blistered enamel behind, deeply weathered raised grain, small
dark knots with one fallen out, end cracks at the top, frayed wet bottom ends, square forged nail heads in pairs with
hammer crescent dents, one bent nail, a charred alligator-skin edge on the slat next to the firebox, a slab-wood frame
with a strip of bark. A flat wooden sauna thermometer plaque with tick marks only. No text, no numbers, no people.
```

## Промт 4 — крупно дверца топки

```
Close-up of a hand-forged firebox door of a sauna stove: flat-bar grate with hammer facets and flaking mill scale,
domed rivets at the crossings, forge-welded corners, one bar made of ribbed rebar, a forged strap hinge with a pin, a
handle wrapped with rope. Behind the grate a heap of split basalt stones and cracked glowing charcoal, glow only in the
cracks and deepest gaps. Below, a sliding ash damper plate with a bent tab and a little spilled ash. No text, no
logos, no people.
```
