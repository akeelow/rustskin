# ТЗ для Nano Banana: референс Sauna Bucket

> 17.11.2026. Картинка — **только референс для запекания** (цвета, материалы, где какая деталь).
> В Workshop её не выкладываем и за игровой кадр не выдаём. Готовые картинки класть сюда же:
> `references/nb_<что>_v1.png`.

## Как пользоваться

1. Приложить к запросу **скриншот оригинала** Bucket Helmet из редактора (лучше 3/4 спереди; если есть —
   ещё сбоку и сзади, все сразу).
2. Вставить промпт 1 (главный). Промпты пишем по-английски: так модель точнее держит материалы.
3. Если форма ведра поплыла (стало выше, шире, появилась новая ручка или дно), ответить одной фразой из
   раздела «Правки» и перегенерировать. Не дописывать новые детали в тот же запрос: модель начинает
   менять силуэт.
4. Когда главный кадр понравился — промпты 2 и 3 с тем же скриншотом **и** с удачной картинкой.

## Промпт 1 — главный кадр (3/4 спереди, на голове)

```
Use the attached screenshot as the exact shape reference. It is the Bucket Helmet
from the video game Rust: a bucket worn upside down on the head, with a cut-out
eye opening.

Repaint this exact helmet as a skin. Keep the silhouette, proportions, height,
taper, rim, eye opening, handle and every other part of the geometry exactly as
in the screenshot. Do not add, remove or reshape any part. Only the surface
material and colour change, as if a new texture were painted on the same 3D model.

Theme: an old wooden sauna wash tub that a survivor jammed on his head as armour.

Surface:
- Vertical wooden staves of pale aspen (#C2A77E) with small bevels and thin dark
  gaps between them, all staves equal width around the bucket.
- Wood gets darker and swollen towards the open bottom rim, soaked from years of
  water (#7A5A3C, and #45332A in the wettest spots). Top of the helmet stays pale
  and dry.
- Two old iron hoops around the bucket, dark grey-brown, held by small domed
  rivets, one hoop joined with an overlapping patch. Orange-brown rust streaks run
  down the wood under each hoop (#8C4A26).
- Around the eye opening: a rough hand-sawn edge, jagged saw marks, fresh light
  raw wood visible on the cut face, a few splinters.
- Through the eye opening and at the rim you can see a dented tin sheet lining the
  inside, fixed with nail heads. A few nail heads also show on the outside between
  the hoops. This lining is why the bucket stops bullets; the wood itself is not
  armour.
- Handle: a frayed linen rope (#B8A27A) with one knot, following the place where
  the original handle is. If the original has no handle, a short torn rope stub
  tied to one hoop.
- One wet birch leaf stuck flat on the side (olive #5C6A39).
- White mineral water stains on the staves, a darker wet ring around the bottom
  rim, drips following the wood grain.

Style: realistic game asset texture like Rust by Facepunch: grounded, worn, dirty,
handmade from scrap, muted natural colours, physically plausible materials.
Neutral grey studio background, soft daylight from the upper left, 3/4 front view,
the helmet on a plain grey mannequin head with no face details. Square image.

No text, no letters, no numbers, no logos, no symbols, no glow, no emission, no
fire, no shiny metal, no varnish, no cartoon style, no extra objects.
```

## Промпт 2 — развёртка видов (после удачного промпта 1)

```
Same helmet as in the second attached image, same materials and details, shape
exactly as in the first attached screenshot. Make a turnaround sheet on a neutral
grey background: four views in one row - front, left side, back, top - same scale,
same soft daylight, orthographic-looking camera, no mannequin, helmet floating.
The birch leaf is only on the left side, the rope knot only on one side - do not
repeat them on every view. No text or labels, no glow.
```

## Промпт 3 — материалы крупно

```
Close-up material study of the same helmet from the attached images, neutral grey
background, four square tiles in a 2x2 grid with thin gaps:
1) the hand-sawn eye opening edge with fresh raw wood and the dented tin lining
   with nail heads behind it;
2) an iron hoop with domed rivets, the overlapping joint and rust streaks running
   down the staves below;
3) the bottom rim: dark swollen wet wood, white mineral stains, a dark water ring;
4) the birch leaf stuck on dry pale aspen staves with thin gaps.
Realistic, worn, muted, game texture reference. No text, no labels, no glow.
```

## Правки (если пошло не так — одна фраза на перегенерацию)

| Что видно | Ответ модели |
|---|---|
| ведро стало выше / шире / сменилась форма | `Keep the exact shape of the first screenshot, change only the surface.` |
| появилась новая ручка, ушки, крышка | `Remove the added parts, keep only the geometry of the screenshot.` |
| дерево лакированное, рыжее, «новая кадка» | `Wood must be pale grey-honey aspen, matte, old and water-stained, not orange, not varnished.` |
| обручи блестят, как хром | `Hoops are dull old iron, dark and rusty, no shine.` |
| лист / узел на каждом виде | `Only one leaf on the left side and one rope knot.` |
| на ведре буквы, знаки, клеймо | `No text, letters or symbols anywhere.` |
| вкладыша не видно | `Show the dented tin lining with nail heads inside the eye opening.` |
| слишком мило, мультяшно | `Gritty survival game realism, dirty and worn, like Rust.` |

## Что из этого берём, а что нет

- **Берём:** тон дерева сверху и снизу, где и как ложатся потёки, вид пропила и вкладыша, размер листа
  и узла относительно ведра, общую «банность».
- **Не берём:** форму, число клёпок, точное место ручки и прорези — это задаёт модель из `originals/`.
  Клёпки пересчитываются по окружности развёртки, детали моделируются и запекаются в `bake_bucket.py`.
- Палитра сверяется по HEX из [../../README.md](../../README.md), а не по картинке: генератор её
  сдвигает.
