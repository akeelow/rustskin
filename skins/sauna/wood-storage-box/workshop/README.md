# Sauna Stone Box — публикация в Workshop

> **Сейчас: обновление до v2.3** — раздел ниже. Всё, что после него, — про публикацию v1.6 (15.11.2026).

> Подготовлено для **v1.5** (27.10.2026): как v1.4 (крышка вырезана альфой, край со стороны печи целый, тёплый свет
> в прорезях ручек и щелях между досками), но камни лежат кучей — три размера, наклон, второй слой (v1.4 — ровные «соты»). Публикует пользователь сам из игрового редактора.
> **v1.6 (12.11.2026, по [CRITIQUE_ART.md](../../CRITIQUE_ART.md)):** угли светятся гнёздами, а не ровной сеткой; пик свечения янтарный `#FFB347`; дерево чуть теплее; обугленный банный лист на камнях. Файлы `Box_v1.6_*`. **В игре не проверено** — посмотреть в редакторе перед публикацией; если не понравится, прежняя версия v1.5 лежит рядом (`Box_v1.5_*`).

## Обновление до v2.3 (25.11.2026)

Опубликованная страница (v1.6): https://steamcommunity.com/sharedfiles/filedetails/?id=3840337593. Обновлять **эту же
страницу**: в редакторе выбрать опубликованный Sauna Stone Box из Workshop → Publish (так обновлён полок v2, 21.11).

| Слот | Файл / значение |
|---|---|
| Diffuse | `../export/Box_v2.3_diffuse.png`, **Color 255/255/255**, **Alpha Cutoff 0.50** |
| Normal | `../export/Box_v2.3_normal.png`, Normal Scale 1.00 |
| Specular/Gloss | `../export/Box_v2.3_specgloss.png`, **Spec Color 255/255/255**, Glossiness 1.00 |
| Occlusion | `../export/Box_v2.3_occlusion.png`, Occlusion Scale 1.00 |
| Emission | `../export/Box_v2.3_emission.png`, **Emission Color 255/255/255** |

Ползунки по умолчанию у ящика не нейтральные — выставить ровно как в таблице.

**Новое описание** (вместо старого):

```
Every Rust life starts naked. Might as well warm up properly.

An old crate kept by the sauna stove for the spare stones and the embers
to light it with. Two hoops off a barrel hold the aspen boards together,
a steel tray on the bottom keeps the coals off the wood. The side facing
the stove has charred to the grain and is nicked by the coal scoop, and
a flattened tin can covers the corner that burnt through. Split basalt,
a few charred logs and a dry leaf lie in the ash; at night the embers
glow between the stones and through the handle grips.

Part of the Sauna set.
```

**Картинки для загрузки — папка `upload_v2/`** (кадры из редактора, F12, обрезаны `../../ingame_import.py place`;
исходники — `../screenshots/editor_16x9/*_v2.jpg`). Добавлять **все по номерам**, первая — обложка:

| # | Файл | Что | Версия |
|---|---|---|---|
| 01 | `upload_v2/01_three_quarter_day_v2.jpg` | 3/4 сверху днём: обугленная кромка у печи, заплата, камни внутри — обложка | v2.3 |
| 02 | `upload_v2/02_top_day_v2.jpg` | сверху днём: колотый базальт, поленья, пепел, совок, лист, жар между камнями | v2.3 |
| 03 | `upload_v2/03_stove_side_v2.jpg` | бок к печи в лоб: уголь «языками», зарубки, заплата из банки, обручи | v2.2 (стенки = v2.3) |
| 04 | `upload_v2/04_top_night_v2.jpg` | сверху ночью: гнёзда жара, свет в прорезях ручек | v2.3 |
| 05 | `upload_v2/05_three_quarter_night_v2.jpg` | 3/4 ночью | v2.2 (свечение = v2.3) |

Кадры v2.2 со дном (сверху днём, 3/4 слева) не берём: там пепел и лист ещё старые. Рендеры Blender (`studio.jpg` и др.)
и `ingame/*.jpg` без `_v2` — v1.6, в обновление не идут.

**Change notes** (если редактор или страница спросят, англ.):

```
v2: remodelled from scratch. Every board, nail, hoop, stone and coal is now
real geometry: weathered aspen with grain, knots and cracks, riveted barrel
hoops, a charred rim and scoop nicks on the stove side, a tin-can patch,
split basalt, charred logs, ash, a coal scoop and a dry leaf on the tray.
```

**После публикации:**
1. Проверить, что обновилась **та же страница** 3840337593 (иконка, описание, дата).
2. Старые картинки не удаляются: на странице *Add/edit images* (`/sharedfiles/managepreviews/?id=3840337593`)
   удалить всё старое (рендеры v1.6, кадры v1.6 и автокадры редактора от 15.11) — крестик при наведении, удаляет
   сразу. Оставить 4 новых автокадра редактора и наши 5 из `upload_v2/`.
3. Записать дату и что осталось в галерее сюда и в `../README.md` («Заметки»).

---

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
| Diffuse | `../export/Box_v1.6_diffuse.png`, **Color 255/255/255**, **Alpha Cutoff 0.50** |
| Normal | `../export/Box_v1.6_normal.png`, Normal Scale 1.00 |
| Specular/Gloss | `../export/Box_v1.6_specgloss.png`, **Spec Color 255/255/255**, Glossiness 1.00 |
| Occlusion | `../export/Box_v1.6_occlusion.png`, Occlusion Scale 1.00 |
| Emission | `../export/Box_v1.6_emission.png`, **Emission Color 255/255/255** |

Файлы `Box_v1.3_*.png` в `export/` сейчас побайтно совпадают с v1.4 (перезаписаны 22.10). Прежняя v1.3 с
выгоревшим краем осталась только в git (коммит `4c2a5f6`).

Ползунки по умолчанию у ящика **не нейтральные** (Color 189/186/178, Spec Color 51, Emission Color 0) —
выставить ровно как в таблице, иначе ящик темнее, блестит иначе и не светится.

## Картинки для страницы (Steam → Add/edit images)

Рендеры Blender (`../workshop_renders.py`, Cycles, 1920×1080; JPG для загрузки):

| Файл | Что |
|---|---|
| `studio.jpg` | **главный кадр**: тёмная студия, тёплый ключевой и холодный контровой свет (27.10.2026) |
| `hero.jpg` | днём, 3/4 спереди сверху: обручи, камни внутри, цельные 3D-стенки |
| `night.jpg` | ночью тот же ракурс — яркое многозонное свечение углей, ручек и щелей |
| `top.jpg` | вид внутрь: базальт на противне, сияющие раскалённые угли |
| `rim.jpg` | крупно: цельный деревянный край со стороны печи, естественная копоть без среза альфой |
| `row.jpg` | ночью три ящика в ряд на полке: видимость со всех сторон в темноте |
| `set.jpg` | рядом с каменкой Sauna Stove — единый стиль сета |

![studio](studio.jpg)

![night](night.jpg)

Плюс **скриншоты из редактора Workshop** — v1.6, сняты пользователем 15.11.2026 на весь экран (F12), исходники в `../screenshots/editor_16x9/`; для загрузки — `ingame/` (1920×1080, панель редактора обрезана). Порядок на странице: игровой `top_night` **первым**, затем рендер `studio`, затем остальные скриншоты в этом порядке, затем рендеры.

| Файл | Что |
|---|---|
| `ingame/top_night.jpg` | сверху спереди ночью без фонаря: угли гнёздами, отсвет в прорезях ручек |
| `ingame/top_day.jpg` | сверху днём: камни на противне, обугленный лист |
| `ingame/three_quarter_day.jpg` | 3/4 днём с высоты глаз: обручи, доски |

Запасной (не загружать): `ingame/top_night_flashlight.jpg` — тот же ракурс ночью с фонарём.

## Альфа: крышка

Вырезана альфой (Alpha Cutoff 0.50) только **крышка целиком**; все четыре стенки и их верхний край целые.
Проверено в клиенте: стенки целые, изнанка показывает наружную сторону (`../screenshots/test_openlid_*`).
Коллизия не меняется (невидимая крышка на игру не влияет — ящик открывается окном). Ящики без крышки на
этой модели уже есть в маркете (Curse of the Drowned Treasure Chest, Easter Chicks Box) — Facepunch их
принимает. Сквозь ящик ничего не просматривается — преимущества в игре нет.

## Чек-лист публикации

1. Редактор → Wood Storage Box → загрузить 5 карт v1.6, ползунки как в таблице.
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

Кадры: `studio hero night top rim row set` (можно перечислить нужные), все семь ~2 мин на RTX 3060 Ti.
JPG — пересохранить из PNG (quality 92).
