# Sauna Boiler — публикация в Workshop

**Опубликован 17.11.2026:** https://steamcommunity.com/sharedfiles/filedetails/?id=3841360723

> Подготовлено 17.11.2026 для **v3** (`Furnace_v3_*`). **Проверено в редакторе** (скриншоты `../screenshots/v3_editor_*.webp`). Публикует пользователь из игрового редактора.

## Обновление до v4.4 (22.11.2026)

Опубликованная страница (v3): https://steamcommunity.com/sharedfiles/filedetails/?id=3841360723. Обновлять **эту же
страницу**: в редакторе выбрать опубликованный Sauna Boiler из Workshop → загрузить карты → Publish (как обновлялись
полок, каменка и шкафчик, гайд §9.7). Редактор заново попросит описание и картинки и добавит 4 своих автокадра.
v4.4 проверена в редакторе по кадрам v4.0–v4.4 (`../screenshots/editor_16x9/v4.*`, разбор — `../README.md`).

**Все карты для загрузки — в одной папке:** `skins/sauna/upload/9 Sauna Boiler/v4.4/textures/` (копии `../export/Furnace_v4.4_*`,
в git не попадает).

| Слот | Файл / значение |
|---|---|
| Diffuse | `../export/Furnace_v4.4_diffuse.png` · Color 255/255/255 · Alpha Cutoff 0.00 |
| Normal | `../export/Furnace_v4.4_normal.png` · Normal Scale 1.00 |
| Specular/Gloss | `../export/Furnace_v4.4_specgloss.png` · Spec Color 255/255/255 · Glossiness 1.00 |
| Occlusion | `../export/Furnace_v4.4_occlusion.png` (**1024**, у v3 был 512) · Occlusion Scale 0.65 |
| Emission | `../export/Furnace_v4.4_emission.png` · **Emission Color 255/255/255** (по умолчанию 255/107/36 — сменить) |
| Detail-слоты | по умолчанию |

Все карты 1024 — предел редактора для Furnace (`../PLAN_v4.md` §0.2).

**Новое описание** (вместо прежнего):

```
Every Rust life starts naked. Might as well have hot water.

A wood-fired sauna boiler riveted together from scrap: hand-hammered plates
from an old drum and a roof, cart-wheel tyres for hoops, a checker-plate
patch over a burnt-through spot and the hinges of a door long gone.
Limescale runs down from the seams, a wooden plug wrapped in a rag stands in
for a tap, a carved ladle hangs on a hook. Inside, a firebrick lining, birch
logs and embers; on the lid, a heap of split basalt. Aspen boards are lapped
round the base, nailed and tied with twisted wire.

Part of the Sauna set.
```

**Change notes** (англ.):

```
v4: remodelled from scratch. Every plate, rivet, dent, seam, nail and board
is now real modelled relief: hammered plates with chisel-cut laps, hoops
with riveted and bolted locks, a checker-plate patch, door hinges, a limescale
crust, lapped aspen boards with shadow gaps, split basalt on the lid, and a
firebrick lining with birch logs and embers inside. Occlusion map at full
resolution.
```

### Картинки для страницы — `upload_v4/`

Кадры v4.4 из редактора 22.11 (F12, режим предпросмотра; исходники — `../screenshots/v4.4/`). Поверх сцены справа вверху
заголовок «SAUNA BOILER» и кнопки, слева язычок панели, внизу панель: общие кадры обрезаны **4:5** (800 × 990) левее
заголовка, топка крупно — полосой 16:9 ниже него (1920 × 1080). Скрипт — `../workshop_upload_v4.py`. Копии лежат и в
папке загрузки `skins/sauna/upload/9 Sauna Boiler/v4.4/` рядом с `textures/`. Добавлять **все по номерам**, первая — обложка:

| # | Файл | Что |
|---|---|---|
| 01 | `upload_v4/01_front_day.jpg` | 3/4 спереди днём, топка горит: кованые листы, обручи, рамка с петлями, затычка, пояс реек — обложка |
| 02 | `upload_v4/02_back_day.jpg` | сзади на солнце: ковка, обручи с замками, накипь, выпавшая доска с железом |
| 03 | `upload_v4/03_front_night.jpg` | ночь: огонь в топке, отсвет на рамке |
| 04 | `upload_v4/04_firebox_cold.jpg` | топка без огня крупно: кирпичная кладка, угли, рамка с петлями и заклёпками |
| 05 | `upload_v4/05_top.jpg` | сверху: колотый базальт на крышке, кольцо заклёпок, ковш на боку |

![обложка](upload_v4/01_front_day.jpg)

**После Publish:** удалить все старые картинки v3 (кадры `front_night`, `front_day`, `back_day`, `back_night` и 4
автокадра редактора v3) на `https://steamcommunity.com/sharedfiles/managepreviews/?id=3841360723` (крестик при
наведении, удаляется сразу), обложку `01_front_day` перетащить первой. Описание — «Редактировать описание», заметки
— «Добавить заметку об изменениях».

## Название и описание (англ.) — v3, прежнее

**Title:** `Sauna Boiler`

**Description** (вставить на странице Steam после публикации):

```
Every Rust life starts naked. Might as well have hot water.

A wood-fired sauna boiler riveted together from scrap plate: iron hoops,
limescale running down the seams, a wooden plug wrapped in a rag instead of
a tap. Birch logs and embers smoulder in the firebox, aspen slats are nailed
round the base, and a pile of basalt sits on the lid next to the ladle hook.

Part of the Sauna set.
```

Без просьб о лайках, без текста на текстуре. В описание остальных предметов сета и в коллекцию ссылку
добавлять после публикации (как делали 15.11 для первых семи).

## Что выставить в редакторе перед Publish

| Слот | Файл / значение |
|---|---|
| Diffuse | `../export/Furnace_v3_diffuse.png` · Color 255/255/255 · Alpha Cutoff 0.00 |
| Normal | `../export/Furnace_v3_normal.png` · Normal Scale 1.00 |
| Specular/Gloss | `../export/Furnace_v3_specgloss.png` · Spec Color 255/255/255 · Glossiness 1.00 |
| Occlusion | `../export/Furnace_v3_occlusion.png` · Occlusion Scale 0.65 |
| Emission | `../export/Furnace_v3_emission.png` · **Emission Color 255/255/255** (по умолчанию 255/107/36 — сменить) |
| Detail-слоты | по умолчанию |

Иконку генерирует редактор при Publish — не заменять.

## Картинки для страницы

**Всё для загрузки — в одной папке:** `skins/sauna/upload/9 Sauna Boiler/` (копии, в git не попадает):
кадры по порядку страницы и `textures/` — пять карт v3 для редактора.

Кадры сняты пользователем в редакторе 17.11.2026 (F12, v3, Detail-слоты по умолчанию), обрезаны до 1920×1080
скриптом `../../ingame_import.py`. Рендеров Blender на странице нет.

| # | Файл в папке загрузки | Исходник в репозитории | Что |
|---|---|---|---|
| 1 | `01_game_front_night.jpg` | `ingame/front_night.jpg` | 3/4 спереди ночью: огонь в топке — первый кадр |
| 2 | `02_game_front_day.jpg` | `ingame/front_day.jpg` | 3/4 спереди днём: топка, затычка, обручи |
| 3 | `03_game_back_day.jpg` | `ingame/back_day.jpg` | сзади днём: потёки накипи под обручами, рейки с проволокой |
| 4 | `04_game_back_night.jpg` | `ingame/back_night.jpg` | сзади ночью, с фонарём |

Сырые кадры с панелью редактора — `../screenshots/editor_16x9/`.

## Чек-лист публикации

- [x] v3 проверен в игре, замечания исправлены (или записаны как известные).
- [x] Опубликован.
- [x] Title `Sauna Boiler`, описание выше; последняя строка — ссылка на коллекцию
      (`Part of the [url=https://steamcommunity.com/sharedfiles/filedetails/?id=3840348906]Sauna set[/url].`).
- [x] Кадры из игры сняты и разложены (папка загрузки выше).
- [x] Галерея: наши кадры (`custom_preview_0…3` = 01…04 папки загрузки) первыми, автоскрины редактора
      `screenshot_*` — в конце (сортировка по имени).
- [x] Предмет добавлен в коллекцию Sauna (17.11, 9 предметов). [ ] ссылка записана в `../README.md` и в бриф сета (бриф правит
      основная сессия, не эта).
