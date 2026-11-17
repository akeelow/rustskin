# Sauna Boiler — публикация в Workshop

> Подготовлено 17.11.2026 для **v3** (`Furnace_v3_*`). **Проверено в редакторе** (скриншоты `../screenshots/v3_editor_*.webp`). Публикует пользователь из игрового редактора.

## Название и описание (англ.)

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
- [ ] Emission Color = 255/255/255.
- [ ] Title `Sauna Boiler`, описание выше.
- [x] Кадры из игры сняты и разложены (папка загрузки выше).
- [ ] Кадры загружены на страницу в порядке таблицы.
- [ ] Предмет добавлен в коллекцию Sauna; ссылка записана в `../README.md` и в бриф сета (бриф правит
      основная сессия, не эта).
