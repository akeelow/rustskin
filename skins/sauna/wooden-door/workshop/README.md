# Sauna Door — публикация в Workshop

> Подготовлено 16.11.2026 для **v1.2** (правки по кадрам v1 и v1.1 из редактора). v1.2 проверена в редакторе днём и ночью; замки редактор не ставит, место сверено наложением
> ([../README.md](../README.md), «Сравнение с оригиналом»). Публикует пользователь сам.

## Название и описание (англ.)

**Title:** `Sauna Door` (правило сета: префикс `Sauna`, без оригинального имени предмета).

**Description** (вставить на странице Steam после публикации):

```
Every Rust life starts naked. Might as well warm up properly.

The door to a scrap-built steam room. Pale aspen boards nailed onto an
old steel sheet, rust running from every nail, the foot of the door dark
from years of water. A washed-out towel hangs on a bent nail. Behind the
fogged little window the stove is hot - at night it is the only light
you need to find your way back in.

Inside, the same boards are steamed brown and sooty under the top rail,
and one hinge is held on with wire.

Part of the Sauna set:
https://steamcommunity.com/sharedfiles/filedetails/?id=3840348906
```

Без просьб о лайках и без текста на текстуре. Строку «This skin glows in the dark» Steam добавляет сам.

## Что загружать: всё в одной папке

Всё для публикации лежит в **`skins/sauna/upload/8 Sauna Door/`** (как у остальных семи предметов). Файлы там —
копии; исходники остаются в этой папке. Если карты или кадры изменятся, папку нужно пересобрать.

### 1. В редакторе Rust (вкладка EDIT) — папка `textures/`

| Слот | Файл | Ползунки |
|---|---|---|
| Diffuse | `textures/Door_v1.2_diffuse.png` | Color 255/255/255, Alpha Cutoff 0.00 |
| Normal | `textures/Door_v1.2_normal.png` | Normal Scale 1.00 |
| Specular/Gloss | `textures/Door_v1.2_specgloss.png` | Spec Color 255/255/255, Glossiness 1.00 |
| Occlusion | `textures/Door_v1.2_occlusion.png` | Occlusion Scale 0.70 |
| Emission | `textures/Door_v1.2_emission.png` | **Emission Color 255/255/255** |

**Пробный вариант с прозрачными потёками (v1.3):** в слот Diffuse вместо `Door_v1.2_diffuse.png` загрузить
`textures/Door_v1.3_diffuse_cutout.png` и поставить **Alpha Cutoff 0.50**; остальные слоты те же. Сквозь три
потёка на стекле видно, что за дверью. В игре не проверено; картинки страницы сняты с v1.2 — если публиковать
v1.3, ночные кадры нужно переснять.

Иконку генерирует сам редактор при Publish, Facepunch просит её не заменять.

### 2. На странице Steam (Add/edit images) — в этом порядке

| # | Файл | Что | Откуда |
|---:|---|---|---|
| 1 | `01_game_front_night.jpg` | перед ночью, окно светится | редактор, F12 |
| 2 | `02_render_studio.jpg` | тёмная студия, главный рендер | Blender |
| 3 | `03_game_front_day.jpg` | перед днём, 3/4 | редактор, F12 |
| 4 | `04_game_back_day.jpg` | зад днём: раскосы, окно, петля с проволокой | редактор, F12 |
| 5 | `05_game_back_night.jpg` | зад ночью | редактор, F12 |
| 6 | `06_render_hero.jpg` | днём, 3/4 спереди | Blender |
| 7 | `07_render_back.jpg` | днём сзади | Blender |
| 8 | `08_render_window.jpg` | крупно: полотенце и окно | Blender |
| 9 | `09_render_night.jpg` | ночью спереди | Blender |
| 10 | `10_render_back_night.jpg` | ночью сзади | Blender |
| 11 | `11_render_set.jpg` | в стене раздевалки со шкафчиком и каменкой | Blender |

Номер в имени файла = порядок на странице. Файлы `*_game_*` — кадры из редактора (v1.2, 16.11.2026), `*_render_*` —
рендеры Blender (`../workshop_renders.py`); рендеры игровыми кадрами не называть.

Откуда копии: игровые — `ingame/` (исходники с панелью редактора — `../screenshots/editor_16x9/`), рендеры —
`*.jpg` в этой папке, карты — `../export/`.

Оба ночных игровых кадра сняты с фонарём редактора: дверь освещена, окно светится слабее, чем в темноте.

## После публикации

- Добавить предмет в коллекцию [Sauna](https://steamcommunity.com/sharedfiles/filedetails/?id=3840348906).
- Строку сета в `../../README.md` правит основная сессия (эта папка её не трогает).
