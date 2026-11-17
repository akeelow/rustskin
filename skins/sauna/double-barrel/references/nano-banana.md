# Референс для Sauna Shotgun: ТЗ для Nano Banana

> 17.11.2026. Цель — картинка-ориентир для запекания: какие детали, где, каких цветов и насколько изношены.
> Это **не** картинка для Workshop и не «игровой кадр»: на странице Steam её не публикуем (правило проекта —
> показываем только рендеры с нашими текстурами и кадры из игры).

## Как пользоваться

1. Приложить к запросу скриншот оригинальной двустволки из редактора (лучше строго сбоку, левая сторона).
2. Вставить **промпт 1** целиком. Сгенерировать 3–4 варианта, выбрать один.
3. Если что-то не так — не переписывать промпт, а дописать правку из раздела «Правки» в тот же чат.
4. Для вида от первого лица — **промпт 2** в том же чате (модель помнит выбранный вариант).
5. Лучшие картинки сохранить сюда: `ref_side.png`, `ref_fp.png`.

Промпты на английском: Nano Banana так точнее держит детали.

## Промпт 1 — вид сбоку (главный)

```
Use the attached screenshot as the exact base. It is a crude homemade double-barrel shotgun from the game Rust. Keep its shape, proportions, silhouette and every part exactly as in the screenshot: same pipe barrels, same receiver, same hammers, same trigger guard, same stock outline. Do not add, remove, lengthen or reshape any part. Change only the surface materials, as if it were a new texture skin painted on the same 3D model.

Theme: "the sauna keeper's shotgun". A survivor built a sauna out of scrap and keeps this gun by its door. Everything looks handmade, old, dirty and well used. Muted, natural colours.

Materials, part by part:
- Stock and grip: pale birch or aspen wood (#C2A77E), straight grain with visible fibres. Darker and slightly greasy where hands hold it - the wrist of the stock and the cheek area (#7A5A3C). One knot with a drop of dark amber resin (#45332A).
- Middle of the stock: a strip of old washed-out linen towel (off-white #CFC6B4) wrapped around it 3-4 times, with one faded brick-red stripe (#8E3A30) running along the strip. The fabric has small folds, a folded-under end and frayed threads. It is a few millimetres thick, tight to the wood.
- Near the butt: a simple pattern burnt into the wood with a red-hot nail - rows of dots and small zigzags. No letters, no numbers, no symbols that read as words.
- Fore-end under the barrels: wrapped in strips of birch bark (white #E3DDCF with dark horizontal lenticels and thin black flecks), each turn overlapping the previous one with a curled raw edge. Tied at both ends with thin hemp twine (light grey-brown), one small knot with short loose ends.
- Barrels and receiver: old dark iron, not polished. Black soot around the muzzles fading back along the barrels. Orange-brown rust (#8C4A26) in seams, recesses, around screws and where wood meets metal. Pale white mineral streaks and dried water spots from steam running down the barrels.
- One small wet birch leaf (olive green #5C6A39, serrated edge, visible veins) stuck flat to the birch bark on the fore-end, on the left side of the gun.
- A few small hand-forged nails hold the bark and the towel strip in place.

Wood must look like wood and metal like metal: bark and fabric are matte, iron has a dull satin sheen only on worn edges, wood is matte with slight polish where held.

Strictly: no text, no letters, no logos, no numbers, no brand marks anywhere. No glowing parts, no neon, no emissive light. No gold, no chrome, no gems, no decorative engraving. Not armoured, not futuristic, not cartoonish.

Presentation: the whole gun in strict side view, left side facing the camera, centred, entire gun visible with margin around it. Neutral light-grey studio background, soft even daylight from above, soft shadow under the gun. Photorealistic game-asset look, sharp focus, high detail on materials.
```

## Промпт 2 — вид от первого лица

```
Now show the same shotgun with exactly the same materials from the first-person view of a game: the camera is behind the gun, slightly above and to the left; the stock is in the lower right corner of the frame, close to the camera, and the barrels go forward and slightly left into the distance. We see the top of the receiver, both hammers, the top of the barrels, the left side of the fore-end with the birch bark, the twine knot and the birch leaf, and the towel strip on the stock. No hands, no arms, no character. Keep the same shape as the screenshot, no text, no logos, no glow. Neutral background: the wooden wall of a sauna slightly out of focus, warm soft light.
```

## Правки (дописывать в чат по одной)

- Форма поплыла: `Keep the gun shape exactly like the attached screenshot - same barrel length, same stock outline, same receiver. Only the textures change.`
- Слишком нарядно: `Make it dirtier and more worn: scratches, grime in the grain, chipped bark edges, faded towel. It should look like a cheap homemade gun used for years.`
- Береста похожа на краску: `The birch bark must look like real bark strips wrapped around: visible thickness, curled edges, overlaps, peeling layers.`
- Полотенце выглядит толстым или как бинт: `The towel strip is thin washed linen with a faded brick-red stripe, wrapped tightly, a few millimetres thick, not a bandage and not a thick cloth.`
- Появились буквы или знаки: `Remove all text, letters, numbers and symbols. The burnt pattern is only dots and zigzags.`
- Металл стал хромом или ржавчина повсюду: `Barrels are dull dark iron; rust only in recesses and seams, soot only near the muzzles.`
- Лист потерялся: `Make the birch leaf clearly visible on the left side of the fore-end, about the size of two fingers.`

## Что брать из референса, а что нет

Берём: расположение деталей, соотношение площадей (сколько бересты, где полотенце), тон дерева и износа,
как читается от первого лица. **Не берём** форму оружия, если генератор её изменил: скин — только текстуры
на геометрии оригинала, всё раскладывается по реальной развёртке после разбора `.obj`.
