# Sauna Robe — публикация в Workshop

> Подготовлено 21.10.2026 для **v2.1** (вафельный халат; тулуп отложен). Публикует пользователь сам из игрового редактора.
> ⚠️ Snow Jacket принимают **только в декабре–феврале** — опубликовать до конца ноября, чтобы скин был
> в очереди к сезону.

## Название и описание (англ.)

**Title:** `Sauna Robe` (правило сета: без скобок и оригинальных имён, `../../README.md`, «Workshop: оформление»).

**Description** (вставить на странице Steam после публикации):

```
Every Rust life starts naked. Might as well warm up properly.

A short waffle robe for the dash from the steam room into the snow and
back. Wrapped across and tied with a belt, patch pockets, wide cuffs.
Washed a hundred times in a bucket and never quite dry: the beige has
gone uneven, with damp patches that never fade.

Part of the Sauna set.
```

Коротко, без просьб о лайках и без текста на самой текстуре (правила сета и советы Facepunch).

## Иконка и как загрузить

Иконку **генерирует сам редактор** при Publish, Facepunch просит её не заменять
([Creating Skins](https://wiki.facepunch.com/rust/Creating_Skins)). Перед Publish выставить:

| Слот | Файл / значение |
|---|---|
| Diffuse | `../export/SnowJacket_v2_diffuse.png`, Color 255/255/255, Alpha Cutoff 0.00 (по умолчанию; вырез V не используем) |
| Normal | `../export/SnowJacket_v2_normal.png`, Normal Scale 1.00 |
| Specular/Gloss | `../export/SnowJacket_v2_specgloss.png`, **Spec Color 255**, Glossiness 1.00 |
| Occlusion | нет (пусто, как у оригинала) |
| Emission | нет |
| Fuzz Mask | `../export/SnowJacket_v2_fuzz.png`, **Fuzz 0.5** (по умолчанию 0.09), Fuzz Scatter 0.91 (по умолчанию) |

Остальные ползунки — по умолчанию. Чаще всего забывают **Fuzz 0.5** — без него вафля плоская.

## Картинки для страницы (Steam → Add/edit images)

Рендеры Blender (`../workshop_renders.py`, Cycles, 1920×1080; JPG для загрузки). Тела нет (правило
сета — без обнажёнки): халат на деревянной стойке-манекене, изнутри видна его же ткань.

| Файл | Что |
|---|---|
| `hero.jpg` | днём, 3/4 спереди — главный кадр |
| `front.jpg` | анфас: запах крест-накрест, пояс с узлом, карманы |
| `back.jpg` | сзади: шалевый воротник, пояс, вафля |
| `belt.jpg` | крупно: узел пояса, вафля, карманы |
| `set.jpg` | с полотенцем Sauna Towel Wrap у каменки Sauna Stove, вечер |

![hero](hero.jpg)

Плюс **скриншоты из редактора Workshop** на игроке (главное для одежды; пользователь снимает сам —
до публикации скин виден только в редакторе): `../screenshots/v2.1_front_day.webp`,
`v2.1_back_night.png`, `v2.1_icon_day.png`, `v2.1_editor_three_quarter_day.webp` (3/4 сверху, днём,
снят 21.10.2026 — второй кадр страницы после рендера `hero`). В вороте видна зелёная майка игры
(под курткой, перекрасить нельзя) — так у всех скинов Snow Jacket.
Steam принимает JPG/PNG — `.webp` пересохранить.

## Альфа

Вырезов нет: Alpha Cutoff 0.00. Вырез V пробовали (v2) — в нём видна зелёная майка игры,
поэтому запах закрыт тканью.

## Чек-лист публикации

1. Редактор → Snow Jacket → загрузить Diffuse, Normal, Specular/Gloss, Fuzz Mask v2.
2. **Fuzz 0.5**, Spec Color 255, Alpha Cutoff 0.00.
3. Вкладка **ITEM**: имя `Sauna Robe`.
4. Вкладка **PUBLISH** → Publish → страница в браузере.
5. Описание, картинки (5 рендеров + скриншоты из игры).
6. **Workshop Contributor Agreement** (если ещё не принят).
7. Добавить в коллекцию **Sauna** (`../../workshop_collection.md`).
8. Ссылку записать в `../README.md` и в таблицу сета `../../README.md`.

## Как пересобрать картинки

```bash
"C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/snow-jacket/workshop_renders.py -- --samples 128
```

Кадры: `hero front back belt set` (можно перечислить нужные). Общие настройки сцены (материалы,
стойка-манекен, пол, стена, свет) — `../../showcase.py`. JPG — пересохранить из PNG (quality 92).
