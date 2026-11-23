# Sauna Door — публикация в Workshop

> **Сейчас: v2.7 опубликована 23.11.2026, галерея обновлена — раздел ниже.** Остальное — пакет первой публикации.
>
> Подготовлено 16.11.2026 для **v1.2** (правки по кадрам v1 и v1.1 из редактора). v1.2 проверена в редакторе днём и ночью; замки редактор не ставит, место сверено наложением
> ([../README.md](../README.md), «Сравнение с оригиналом»). Публикует пользователь сам.

## Обновление до v2.7 (23.11.2026)

Опубликованная страница (v1.2): https://steamcommunity.com/sharedfiles/filedetails/?id=3841006157. Обновлять **эту же
страницу**: в редакторе выбрать опубликованный Sauna Door из Workshop → Publish (как у Sauna Bench 21.11.2026).

| Слот | Файл | Ползунки |
|---|---|---|
| Diffuse | `../export/Door_v2.7_diffuse.png` | Color 255/255/255, **Alpha Cutoff 0.50** (потёки на окне — насквозь) |
| Normal | `../export/Door_v2.7_normal.png` | Normal Scale 1.00 |
| Specular/Gloss | `../export/Door_v2.7_specgloss.png` | Spec Color 255/255/255, Glossiness 1.00 |
| Occlusion | `../export/Door_v2.7_occlusion.png` | Occlusion Scale 0.70 |
| Emission | `../export/Door_v2.7_emission.png` | **Emission Color 255/255/255** |

Alpha Cutoff изменился: в v1.2 стоял 0.00, теперь **0.50** — иначе потёки на окне глухие.

**Новое описание** (вместо старого):

```
Every Rust life starts naked. Might as well warm up properly.

The door to a scrap-built steam room. Pale aspen boards nailed onto an
old steel sheet, rust running from every nail, the foot of the door dark
and streaked with dried minerals. A washed-out towel hangs on a bent nail.
The steam on the little window has run down in clear streaks - you can
see straight through them, so check who is waiting outside before you
open up. At night the stove behind the glass lights your way back in.

Inside, the boards are steamed brown and sooty under the top rail, the
rails are hand-hewn, the nails go right through, and one hinge is held
on with wire. The handle got too hot to hold, so it is wrapped in jute.

Part of the Sauna set:
https://steamcommunity.com/sharedfiles/filedetails/?id=3840348906
```

**Change notes** (если редактор или страница спросят):

```
v2: remodelled from scratch. Every board, crack, knot, dent and nail is now
real geometry, front and back. The window streaks are see-through: watch the
street before you open the door. Hewn rails and braces with through-nails,
wire-bound hinge, jute-wrapped handle, soaked mineral stains.
```

**Картинки — папка `upload_v2/`** (кадры из редактора, F12, обрезка 16:9 как у `../../ingame_import.py`;
исходники — `../screenshots/v2.*/` и `../screenshots/workshop_v2/`, сняты 23.11.2026). Добавлять **все по номерам**, первая — обложка страницы:

| # | Файл | Что | Кадр |
|---|---|---|---|
| 01 | `upload_v2/01_front_34_day_v2.jpg` | перед 3/4 днём на уровне глаз — обложка | `workshop_v2/front_34_day.jpg` (v2.7) |
| 02 | `upload_v2/02_window_see_through_v2.jpg` | окно спереди вплотную днём: сквозь потёки виден пикап за дверью | `workshop_v2/window_see_through.jpg` (v2.7) |
| 03 | `upload_v2/03_front_night_v2.jpg` | перед ночью: окно светится, ободок по потёкам | v2.4_5 (ночью перед не отличается от v2.7) |
| 04 | `upload_v2/04_handle_front_v2.jpg` | ручка в бечёвке, низ переда: шляпки, загнутые концы | v2.7_1 |
| 05 | `upload_v2/05_back_34_day_v2.jpg` | зад 3/4 днём | `workshop_v2/back_34_day.jpg` (v2.7) |
| 06 | `upload_v2/06_back_rail_handle_v2.jpg` | средний брус сзади, раскосы, ручка | v2.7_2 |
| 07 | `upload_v2/07_back_hinge_wire_v2.jpg` | верхний брус, петля с проволокой, окно сзади | v2.4_2 (эта часть с v2.4 не менялась) |
| 08 | `upload_v2/08_back_night_v2.jpg` | зад ночью | v2.4_4 |

Кадры v2.0 и v2.3 сняты с открытой панелью материалов — в галерею не идут. Рендеры Blender (`hero.jpg` и др.) и
`ingame/` — v1.2, в обновление не идут.

**После Publish:** старые картинки остаются. Удалить на
https://steamcommunity.com/sharedfiles/managepreviews/?id=3841006157 (крестик при наведении, удаляет сразу): все
рендеры и кадры v1.2 и автокадры редактора от 16.11. Оставить автокадры редактора v2.7 и наши 8 из `upload_v2/`.

**Опубликовано 23.11.2026** пользователем из редактора (та же страница 3841006157). **Старые картинки удалены
23.11.2026** на managepreviews: 15 штук от 16.11 (11 рендеров и кадров v1.2 и 4 автокадра редактора v1.2). Сейчас в
галерее 12: 4 автокадра редактора v2.7, затем наши 8 из `upload_v2/` по порядку (проверено перезагрузкой страницы).

Папка `../../upload/8 Sauna Door/` — пакет v1.2; её пересобирает основная сессия (эта папка её не трогает).

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
