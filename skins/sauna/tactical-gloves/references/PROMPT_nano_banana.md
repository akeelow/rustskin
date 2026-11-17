# Референс Sauna Mitts: промпт для Nano Banana

> 17.11.2026. Сгенерированная картинка — **только референс образа** (цвета, материалы, где какие детали).
> Ни в текстуру, ни в Workshop она не идёт: в текстуре всё моделируется в Blender и запекается на
> развёртку оригинала, а на странице Workshop показываем рендеры и кадры из игры.

## Как использовать

1. Приложить к запросу **скриншот оригинала Tactical Gloves из редактора** (тыльная сторона, лучше
   ещё и ладонь). Модель держит форму перчатки по картинке: крой, накладки на костяшках, манжету.
2. Вставить основной промпт. Промпт на английском: на нём модель точнее держит материалы.
3. Если получилось не то — правки из раздела «Если не получилось» отдельным сообщением в тот же чат.
4. Удачные картинки сохранить в `references/` (`ref_back.png`, `ref_palm.png`, `ref_fp.png`).

## Основной промпт (тыльная сторона и ладонь)

```
Use the attached screenshot as the exact shape reference: keep the same glove
silhouette, five separate fingers, the same knuckle pads, seam layout and wrist
cuff length. Only change the materials. Do not turn them into mittens.

Redesign these tactical gloves as handmade "sauna stoker's gloves" sewn by a
survivor from scraps:
- Base: thick grey-beige pressed wool felt (#B3A48A), matte, slightly fuzzy,
  pilled, 3-4 mm thick, soft rounded edges.
- Seams: coarse undyed linen thread, big uneven hand stitches 4-6 mm long that
  slightly pucker the felt, running along the sides of the fingers and around
  every patch.
- Palm and fingertip pads: patches of reddish-brown sheepskin leather (#8A6646)
  with a folded-under edge, stitched on by hand, worn smooth and slightly shiny
  where the hand grips.
- Knuckle pads: in place of the hard plastic plates, overlapping pieces of birch
  bark (#E3DDCF with dark lenticels) or thick old leather, sewn on with the same
  thread, edges frayed and lifting a little. Thin, flexible, not armor.
- Cuff: a strip of an old washed linen towel (off-white #CFC6B4) with one faded
  brick-red stripe (#8E3A30) running AROUND the wrist, hem folded over and
  top-stitched.
- A short loop of twisted jute twine sewn to the cuff, for hanging the gloves
  on a nail by the stove.
- Wear: scorch marks and a few small burnt-through holes on the back of the hand
  from a hot stove door (dark brown #45332A, singed fibres at the edges); soot
  on the fingertips; darker felt on the palm from use.
No glow, no text, no logos, no metal studs, no rivets, no plastic.

Show a pair: left glove back of the hand up, right glove palm up, lying on an
old wooden sauna bench of light aspen boards. Soft daylight from a small
window, neutral colours, realistic photo, product-style framing, the whole
glove in frame, 3:2.
```

## Вид от первого лица

Главный ракурс скина: в игре руки видны от первого лица всё время.

```
Same handmade felt sauna stoker's gloves, same materials and colours as before.
First-person view: two hands in the gloves held in front of the camera, backs of
the hands facing the viewer, as if gripping an old wooden-stock shotgun or an
axe handle. Visible: scorched felt on the backs, birch-bark knuckle pads,
towel cuffs with the brick-red stripe around the wrists, soot on the fingertips.
Behind: a dim log sauna with a stone stove, warm light from the stove on one
side, cool snowy daylight from the door on the other. Realistic, 16:9.
```

## Если не получилось

| Что вышло | Что дописать |
|---|---|
| Варежки, слились пальцы | `Five separate fingers exactly as in the attached screenshot. Not mittens.` |
| Кухонная прихватка, мило, чисто | `These are rough work gloves, dirty and scorched, not an oven mitt and not a craft item. More soot, more wear.` |
| Броня, жёсткие пластины | `Knuckle pads are thin flexible birch bark or leather, sewn on, no plates, no armor.` |
| Полоса на манжете вдоль руки | `The brick-red stripe goes around the wrist, across the forearm, like a ring.` |
| Слишком мелкие стежки, машинная строчка | `Hand-sewn, big uneven stitches, each about 5 mm, thick thread.` |
| Свечение, угли на перчатках | `No glow, no embers on the gloves, only old dark scorch marks.` |
| Ушла форма оригинала | `Match the attached screenshot exactly: proportions, knuckle pads, cuff length. Change only materials.` |
