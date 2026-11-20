# Sauna Mitts — публикация в Workshop

> Подготовлено 20.11.2026, обновлено для **v1.2** (файлы `SaunaMitts_v1.2_*`, 1024 — редактор Tactical Gloves держит 1024). Публикует пользователь сам из игрового редактора.
> **До публикации:** проверить v1 в редакторе (список кадров — в [../README.md](../README.md), «Что проверить в игре»)
> и снять кадры. Главный кадр страницы — из игры, не рендер (правило проекта).
> Tactical Gloves принимают круглый год (17 за год, шанс ~1 из 15, `data/item-ranking.csv`).

## Название и описание (англ.)

**Title:** `Sauna Mitts` (правило сета: без скобок и оригинальных имён, `../../README.md`, «Workshop: оформление»).

**Description** (вставить на странице Steam после публикации):

```
Every Rust life starts naked. Might as well warm up properly.

The stoker's gloves that hang on a nail by the stove. Cut from thick
felt and sewn with coarse thread in big uneven stitches, leather patched
over the palm and fingertips, two scraps of birch bark over the knuckles.
The backs are scorched from the stove door, the fingertips black with
soot. The cuffs are an old striped towel, tied shut with a twine loop
over a birch toggle.

Part of the Sauna set.
```

Коротко, без просьб о лайках и без текста на самой текстуре (правила сета и советы Facepunch). Свечения нет.

## Иконка и как загрузить

Иконку **генерирует сам редактор** при Publish, Facepunch просит её не заменять
([Creating Skins](https://wiki.facepunch.com/rust/Creating_Skins)).

Workshop → Create a new item → **Tactical Gloves** → EDIT → вкладка **MAIN** (единственная):

| Слот | Файл / значение |
|---|---|
| Diffuse | `../export/SaunaMitts_v1.2_diffuse.png`, Color 255/255/255, Alpha Cutoff 0.00 (по умолчанию) |
| Normal | `../export/SaunaMitts_v1.2_normal.png`, Normal Scale 1.00 |
| Specular/Gloss | `../export/SaunaMitts_v1.2_specgloss.png`, Spec Color 255/255/255, Glossiness 1.00 |
| Occlusion | `../export/SaunaMitts_v1.2_occlusion.png`, Occlusion Scale 1.00 |
| Emission | нет (пусто), Emission Color 0/0/0 |
| Fuzz Mask | `../export/SaunaMitts_v1.2_fuzz.png`, Fuzz 0.27, Fuzz Scatter 0.70, Fuzz Color 255/235/189, Fuzz Occlusion 1.00 — всё по умолчанию |

Тест `Test_slotsize_*` (20.11): редактор ужимает до 1024 — поэтому v1.1 сразу в 1024.

## Картинки для страницы (Steam → Add/edit images)

**Всё в одной папке, в порядке загрузки:** `skins/sauna/upload/12 Sauna Mitts/` (там же `textures/` — карты v1.2 для
редактора). Папка в `.gitignore`, пересобрать: `.venv/Scripts/python skins/sauna/tactical-gloves/workshop_pack.py`.

Кадры из редактора сняты пользователем 20.11.2026 (F12, v1.2, день), исходники — `../screenshots/editor_f12/`; для
страницы панель редактора снизу обрезана по 16:9, 1920×1080 (`ingame/`). Рендеры Blender (`../gloves_view.py`, v1.2) —
не игровые кадры, идут после.

| # | Файл в папке upload | Что |
|---|---|---|
| 1 | `01_game_back_day.jpg` (`ingame/back_day.jpg`) | **главный кадр**: тыл днём — береста на костяшках, овалы, подпалины, манжета с полосой |
| 2 | `02_game_palm_day.jpg` | ладонь: кожа «короной», подушечки, петля из бечёвки на манжете |
| 3 | `03_game_side_day.jpg` | бок мизинца: швы через край, напёрстки |
| 4 | `04_game_palm_q34_day.jpg` | ладонь в 3/4, большой палец |
| 5 | `05_render_back.jpg` (`back.jpg`) | рендер: тыл |
| 6 | `06_render_palm.jpg` (`palm.jpg`) | рендер: ладонь |
| 7 | `07_render_set.jpg` (`set.jpg`) | рендер: с рукавом Sauna Robe — та же ткань и полоса |
| 8 | `08_render_fp_render.jpg` (`fp_render.jpg`) | рендер: обе руки «от первого лица» |

## Чек-лист публикации

1. Редактор → Tactical Gloves → загрузить пять карт v1.2, ползунки по умолчанию.
2. Вкладка **ITEM**: имя `Sauna Mitts`.
3. Вкладка **PUBLISH** → Publish → страница в браузере.
4. Описание, картинки (порядок выше).
5. Добавить в коллекцию **Sauna** (`../../workshop_collection.md`).
6. Добавить shortname и ID в список `Sauna` в `tools/rust-server/SkinShot.cs` (локальный сервер для кадров).
