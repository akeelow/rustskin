# Sauna Stone Box — публикация в Workshop

> Подготовлено для v1.4 (22.10.2026, исправления по CRITIQUE.md: убрана неоновая кромка, свечение в трещинах углей, сглажен вырез угла, устранён пересвет). Публикует пользователь сам из игрового редактора.

## Название и описание (англ.)

**Title:** `Sauna Stone Box` (правило сета: без скобок и оригинальных имён, `../../README.md`, «Workshop: оформление»).

**Description** (вставить на странице Steam после публикации):

```
Every Rust life starts naked. Might as well warm up properly.

An old crate kept by the sauna stove for the spare stones and the embers
to light it with. Bound with two hoops off a barrel so the heat wouldn't
split it, a sheet of steel on the bottom so it wouldn't catch. The basalt
on the steel is still hot: at night radiant embers glow between the stones,
and warm firelight spills through the handle grips and plank seams.

Part of the Sauna set.
```

Коротко, без просьб о лайках и без текста на самой текстуре (правила сета и советы Facepunch).
Строку «This skin glows in the dark» Steam добавляет сам.

## Иконка

Иконку **генерирует сам редактор** при Publish, Facepunch просит её не заменять
([Creating Skins](https://wiki.facepunch.com/rust/Creating_Skins)). Перед Publish выставить:

| Слот | Файл / значение |
|---|---|
| Diffuse | `../export/Box_v1.4_diffuse.png` (или `Box_v1.3`), **Color 255/255/255**, **Alpha Cutoff 0.50** |
| Normal | `../export/Box_v1.4_normal.png` (или `Box_v1.3`), Normal Scale 1.00 |
| Specular/Gloss | `../export/Box_v1.4_specgloss.png` (или `Box_v1.3`), **Spec Color 255/255/255**, Glossiness 1.00 |
| Occlusion | `../export/Box_v1.4_occlusion.png` (или `Box_v1.3`), Occlusion Scale 1.00 |
| Emission | `../export/Box_v1.4_emission.png` (или `Box_v1.3`), **Emission Color 255/255/255** |

Ползунки по умолчанию у ящика **не нейтральные** (Color 189/186/178, Spec Color 51, Emission Color 0) —
выставить ровно как в таблице, иначе ящик темнее, блестит иначе и не светится.

## Картинки для страницы (Steam → Add/edit images)

Рендеры Blender (`../workshop_renders.py`, Cycles, 1920×1080; JPG для загрузки):

| Файл | Что |
|---|---|
| `hero.jpg` | днём, 3/4 спереди сверху — главный кадр: обручи, камни внутри, цельные 3D-стенки |
| `night.jpg` | ночью тот же ракурс — яркое многозонное свечение углей, ручек и щелей |
| `top.jpg` | вид внутрь: базальт на противне, сияющие раскалённые угли |
| `rim.jpg` | крупно: цельный деревянный край со стороны печи, естественная копоть без среза альфой |
| `row.jpg` | ночью три ящика в ряд на полке: видимость со всех сторон в темноте |
| `set.jpg` | рядом с каменкой Sauna Stove — единый стиль сета |

![hero](hero.jpg)

![night](night.jpg)

Плюс **скриншоты из редактора Workshop** — сняты пользователем 21.10.2026 на весь экран (F12), исходники в `../screenshots/editor_16x9/`; для загрузки — `ingame/` (1920×1080, панель редактора обрезана). Порядок на странице: рендер `hero`, затем скриншоты в этом порядке, затем остальные рендеры.

| Файл | Что |
|---|---|
| `ingame/top_day.jpg` | сверху днём: камни на противне |
| `ingame/top_night.jpg` | сверху ночью: светятся только угли между камнями и край |
| `ingame/rim_dusk.jpg` | выгоревший край в сумерках |

## Альфа: крышка и выгоревший край

Вырезаны альфой (Alpha Cutoff 0.50): **крышка целиком** и **край со стороны печи** (неровно, 0.4–3 см).
Проверено в клиенте: стенки целые, изнанка показывает наружную сторону (`../screenshots/test_openlid_*`).
Коллизия не меняется (невидимая крышка на игру не влияет — ящик открывается окном). Ящики без крышки на
этой модели уже есть в маркете (Curse of the Drowned Treasure Chest, Easter Chicks Box) — Facepunch их
принимает. Сквозь ящик ничего не просматривается — преимущества в игре нет.

## Чек-лист публикации

1. Редактор → Wood Storage Box → загрузить 5 карт v1.3, ползунки как в таблице.
2. Вкладка **ITEM**: имя `Sauna Stone Box`.
3. Вкладка **PUBLISH** → Publish → страница в браузере.
4. Описание, картинки (6 рендеров + 2–3 скриншота из игры).
5. **Workshop Contributor Agreement** (если ещё не принят).
6. Добавить в коллекцию **Sauna**.
7. Ссылку записать в `../README.md` и в таблицу сета `../../README.md`.

## Как пересобрать картинки

```bash
"C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/wood-storage-box/workshop_renders.py -- --samples 128
```

Кадры: `hero night top rim row set` (можно перечислить нужные), все шесть ~1.5 мин на RTX 3060 Ti.
JPG — пересохранить из PNG (quality 92).
