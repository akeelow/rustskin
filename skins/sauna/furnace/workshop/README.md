# Sauna Boiler — публикация в Workshop

> Подготовлено 17.11.2026 для **v1** (`Furnace_v1_*`). **В игре не проверено** — сначала пройти список
> «Что проверить в игре» в [../README.md](../README.md). Публикует пользователь из игрового редактора.

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
| Diffuse | `../export/Furnace_v1_diffuse.png` · Color 255/255/255 · Alpha Cutoff 0.00 |
| Normal | `../export/Furnace_v1_normal.png` · Normal Scale 1.00 |
| Specular/Gloss | `../export/Furnace_v1_specgloss.png` · Spec Color 255/255/255 · Glossiness 1.00 |
| Occlusion | `../export/Furnace_v1_occlusion.png` · Occlusion Scale 0.65 |
| Emission | `../export/Furnace_v1_emission.png` · **Emission Color 255/255/255** (по умолчанию 255/107/36 — сменить) |
| Detail-слоты | по умолчанию |

Иконку генерирует редактор при Publish — не заменять.

## Картинки для страницы

Кадры из игры снимает пользователь (F12, на весь экран, панель редактора потом обрезается до 1920×1080 —
как для первых семи, см. `../../SHOOTING.md`). Рендеров Blender для страницы пока нет: листы в `../renders/`
— рабочая проверка, на страницу их не ставить.

Порядок:

| # | Файл (положить в `ingame/`) | Что |
|---|---|---|
| 1 | `front_night.jpg` | анфас ночью: светятся только гнёзда углей в топке — первый кадр |
| 2 | `three_quarter_day.jpg` | 3/4 справа днём: бак с обручами, ковш, рейки |
| 3 | `firebox_day.jpg` | крупно топка: поленья, зола, угли, рамка с клёпками |
| 4 | `three_quarter_night.jpg` | 3/4 ночью |
| 5 | `plug_day.jpg` | крупно слева: затычка с тряпкой и подтёк накипи |
| 6 | `back_day.jpg` | сзади: швы листов, замки обручей, стыки реек |
| 7 | `top_day.jpg` | сверху: камни на крышке |
| 8 | `with_stove_night.jpg` | рядом с Sauna Stove ночью, если получится поставить обе в одной сцене |

## Чек-лист публикации

- [ ] v1 проверен в игре, замечания исправлены (или записаны как известные).
- [ ] Emission Color = 255/255/255.
- [ ] Title `Sauna Boiler`, описание выше.
- [ ] Кадры из игры загружены в порядке таблицы.
- [ ] Предмет добавлен в коллекцию Sauna; ссылка записана в `../README.md` и в бриф сета (бриф правит
      основная сессия, не эта).
