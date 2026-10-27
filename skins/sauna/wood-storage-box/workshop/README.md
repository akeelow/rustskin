# Sauna Stone Box — публикация в Workshop

> Подготовлено для **v1.4** (22.10.2026): крышка вырезана альфой, край со стороны печи целый, угли светятся между
> камнями, тёплый свет в прорезях ручек и щелях между досками. Публикует пользователь сам из игрового редактора.

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
| Diffuse | `../export/Box_v1.4_diffuse.png`, **Color 255/255/255**, **Alpha Cutoff 0.50** |
| Normal | `../export/Box_v1.4_normal.png`, Normal Scale 1.00 |
| Specular/Gloss | `../export/Box_v1.4_specgloss.png`, **Spec Color 255/255/255**, Glossiness 1.00 |
| Occlusion | `../export/Box_v1.4_occlusion.png`, Occlusion Scale 1.00 |
| Emission | `../export/Box_v1.4_emission.png`, **Emission Color 255/255/255** |

Файлы `Box_v1.3_*.png` в `export/` сейчас побайтно совпадают с v1.4 (перезаписаны 22.10). Прежняя v1.3 с
выгоревшим краем осталась только в git (коммит `4c2a5f6`).

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

Плюс **скриншоты из редактора Workshop** — на весь экран (F12), исходники в `../screenshots/editor_16x9/`; для
загрузки — `ingame/` (1920×1080, панель редактора обрезана). Порядок на странице: рендер `hero`, затем скриншоты в
этом порядке, затем остальные рендеры.

> ⚠️ Кадры в `ingame/` сняты 21.10.2026 на **v1.3** (выгоревший край, тёмное дно). Переснять с v1.4 — список ниже.

| Файл | Что снять с v1.4 |
|---|---|
| `ingame/top_day.jpg` | сверху днём: камни на противне |
| `ingame/top_night.jpg` | сверху ночью: угли между камнями |
| `ingame/stove_side_dusk.jpg` | 3/4 со стороны печи в сумерках: копоть на крае, свет в прорези ручки (вместо `rim_dusk.jpg` — края-выреза больше нет) |
| `ingame/three_quarter_night.jpg` | 3/4 ночью сбоку: свет в прорезях ручек и щелях |

## Альфа: крышка

Вырезана альфой (Alpha Cutoff 0.50) только **крышка целиком**; все четыре стенки и их верхний край целые.
Проверено в клиенте: стенки целые, изнанка показывает наружную сторону (`../screenshots/test_openlid_*`).
Коллизия не меняется (невидимая крышка на игру не влияет — ящик открывается окном). Ящики без крышки на
этой модели уже есть в маркете (Curse of the Drowned Treasure Chest, Easter Chicks Box) — Facepunch их
принимает. Сквозь ящик ничего не просматривается — преимущества в игре нет.

## Чек-лист публикации

1. Редактор → Wood Storage Box → загрузить 5 карт v1.4, ползунки как в таблице.
2. Вкладка **ITEM**: имя `Sauna Stone Box`.
3. Вкладка **PUBLISH** → Publish → страница в браузере.
4. Описание, картинки (6 рендеров + 3–4 скриншота из игры).
5. **Workshop Contributor Agreement** (если ещё не принят).
6. Добавить в коллекцию **Sauna**.
7. Ссылку записать в `../README.md` и в таблицу сета `../../README.md`.

## Как пересобрать картинки

```bash
"C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/wood-storage-box/workshop_renders.py -- --samples 128
```

Кадры: `hero night top rim row set` (можно перечислить нужные), все шесть ~1.5 мин на RTX 3060 Ti.
JPG — пересохранить из PNG (quality 92).
