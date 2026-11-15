# Оригиналы Double Barrel Shotgun: что скачать

Скачать может только пользователь, из редактора Rust. Все файлы — в эту папку.

## Шаги

1. Rust → **Workshop** → **Create a new item** → в списке слева **Double Barrel Shotgun** → **EDIT**.
2. Вверху панели MATERIALS — **Download**: сохранить модель как `double_barrel.obj`.
3. Если материалов несколько (переключатель или список над слотами) — пройти **каждый** и записать их названия.
4. У каждого слота каждого материала — **жёлтая стрелка**: сохранить оригинальную текстуру.

## Файлы

| Файл | Откуда |
|---|---|
| `double_barrel.obj` | Download |
| `double_barrel_bc.png` | слот Diffuse |
| `double_barrel_nrm.png` | слот Normal |
| `double_barrel_sg.png` | слот Specular/Gloss или Metal/Gloss (как назван в редакторе) |
| `double_barrel_ao.png` | слот Occlusion |
| `double_barrel_em.png` | слот Emission, если он не пустой |

Для второго и следующих материалов — те же имена с суффиксом материала, например `double_barrel_shells_bc.png`.

## Скриншоты (в `../screenshots/`)

1. `editor_panel.png` — панель EDIT целиком для каждого материала: видны все слоты, подписи «Default (W x H)»
   и **все ползунки** (Color, Alpha Cutoff, Normal Scale, Spec Color / Metalness, Glossiness, Occlusion Scale,
   Emission Color). По ним выставляются значения в таблице загрузки.
2. `orig_side_left.png`, `orig_side_right.png` — оригинал строго сбоку, с обеих сторон.
3. `orig_top.png` — сверху-сзади, примерно как от первого лица (стволы уходят от нижнего правого угла вперёд).
4. Если получится: один кадр из игры от первого лица с обычной двустволкой и один в момент перелома при
   перезарядке — по ним видно, что закрывают руки и что открывается внутри.
