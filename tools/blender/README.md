# Blender: инструменты

| Скрипт | Что делает |
|---|---|
| [viewer.py](viewer.py) | **просмотр скина как в игре** — лист рендеров (спереди, 3/4, сбоку, сзади, сверху, крупно × день/ночь) и сцена `.blend`, чтобы крутить самому |
| [preview.py](preview.py) | один рендер деплоя (день/ночь, угол) |
| [mcp/](mcp/README.md) | живое подключение Claude к открытому Blender |

## viewer.py

```bash
"C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P tools/blender/viewer.py -- --obj <модель.obj> [--obj <ещё.obj>] --tex <префикс> [--cutoff 0.24] [--wear] [--units cm] [--focus x,y,z] --sheet <лист.png> [--blend <сцена.blend>]
```

- `--tex` — префикс карт: `<префикс>_diffuse.png`, `_normal.png`, `_specgloss.png` (одежда) или
  `_metalgloss.png` (деплои), `_emission.png`, `_occlusion.png` — какие есть.
- Как в игре: задние грани не рисуются, альфа режется жёстко по `--cutoff` (= Alpha Cutoff в редакторе),
  свечение ×3.
- `--wear` — манекен под одежду (рост и плечи как у игрока Rust, приблизительно).
- `--units cm` — для моделей в сантиметрах (шкафчик).
- `--up z` — модель экспортирована с Z вверх (3ds Max, кровать); `--focus` тогда в её x,y,z.
- `--focus` — точка крупного плана в координатах OBJ (Y вверх, +Z вперёд).
- `--blend` — сохранить сцену: открыть в Blender, режим **Material Preview** (Z → 2) или Rendered,
  крутить колёсиком/средней кнопкой; ночь — поменять цвет фона мира и солнце.

Пример (полотенце на плече):

```bash
"C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P tools/blender/viewer.py -- --obj skins/sauna/hide-poncho/originals/attire.hide.poncho_poncho.obj --obj skins/sauna/hide-poncho/originals/attire.hide.poncho_fur.obj --tex skins/sauna/hide-poncho/export/HidePoncho_v4_shoulder --cutoff 0.24 --wear --focus 0.17,1.35,0.0 --sheet skins/sauna/hide-poncho/renders/v4_shoulder_sheet.png --blend skins/sauna/hide-poncho/renders/v4_shoulder_view.blend
```

Это проверка до игры: дыры, рваные края, швы, ночное свечение видно сразу. Финально — всё равно в игре.
