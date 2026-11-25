# Промт для Nano Banana: референс Sauna Towel Wrap v2.0

Зачем: картинка-ориентир по материалам и износу для [../PLAN_v2.md](../PLAN_v2.md). Текстурой она не станет: всё
равно моделируем в Blender.

Как пользоваться:
- **Промт 1** — главный. Приложи к нему кадр из игры `../workshop/ingame/front_day.jpg` (v1.3 анфас). Тогда форма
  модели, ракурс и пропорции сохранятся, поменяются только материалы.
- **Промт 2** — затылок с узлом: приложи `../workshop/ingame/side_day.jpg` или результат промта 1.
- Если на картинке появится текст, логотип или свечение, перегенерируй: по правилам сета их быть не должно.

Промты на английском: на нём модель понимает точнее.

---

## Промт 1 — анфас, редактирование кадра

```
Edit the attached image. Keep the exact same head wrap shape, silhouette, eye opening, camera angle,
lighting, the man's face and the background. Do not add or remove parts. Change only the surfaces.

The head wrap is an old washed sauna towel wound around the head and neck like a balaclava by a
survivor, tied with jute twine. Photorealistic game asset look, every detail has real physical relief,
nothing painted:

- Fabric: off-white washed terry cloth #CFC6B4, clearly visible terry loops about 3 mm, slightly
  yellowed and greyed from use, damp and darker around the eye opening and under the nose.
- One long hemmed edge of the towel runs straight across the forehead just above the eyes: folded hem
  about 1.5 cm wide with a visible line of stitching. Two faded brick-red woven stripes #8E3A30 (one
  wide, one narrow) along that hem. The opening for the eyes has clean hemmed edges, not torn.
- Visible wrap layers: the edge of each turn of the towel overlaps the turn below with a soft step.
- Jute twine #B8A27A, about 5 mm thick, clearly twisted from three strands, wound three times around
  the head over the forehead and temples, pressing into the fabric with small compression folds on
  both sides. Where turns cross, one lies over the other.
- A dry birch leaf stuck flat to the left temple.
- Neck: the towel end wraps the neck as a scarf with soft deep folds, ending on the chest with a short
  twisted fringe of small tassels, brick-red stripes near the fringe. Slightly damp at the front.
- A small darned patch and one or two pulled-out loops; the crown a little worn flat.
No text, no logos, no glow, no blood.
```

## Промт 2 — затылок, узел

```
Same towel head wrap as in the attached image, seen from behind at the same distance. Show the back of
the head: the three turns of twisted jute twine meet at the back and are tied in a flat square knot
about 4 cm wide, two loose twine ends 6-9 cm long hang down with frayed tufted tips. Terry loops on the
fabric, compression folds radiating from the knot, a small darned square patch near it, the wrap layers
spiral toward the crown. Same colours and lighting. No text, no logos, no glow.
```
