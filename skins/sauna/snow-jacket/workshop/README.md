# Sauna Robe — публикация в Workshop

> **v3.2 — обновление готово к публикации (26.11.2026)**, раздел ниже. Всё, что после него, — про публикацию v2.5
> (15.11.2026).

## Обновление до v3.2

Опубликованная страница (v2.5): https://steamcommunity.com/sharedfiles/filedetails/?id=3840344106. Обновлять **эту же
страницу**: в редакторе выбрать опубликованный Sauna Robe из Workshop → Publish (так обновлены полок 21.11 и ящик 25.11).
⚠️ Snow Jacket принимают только **декабрь–февраль** — обновить до начала декабря.

| Слот | Файл / значение |
|---|---|
| Diffuse | `../export/SnowJacket_v3.2_diffuse.png`, Color 255/255/255, Alpha Cutoff 0.00 |
| Normal | `../export/SnowJacket_v3.2_normal.png`, Normal Scale 1.00 |
| Specular/Gloss | `../export/SnowJacket_v3.2_specgloss.png`, Spec Color 255, Glossiness 1.00 |
| Occlusion | `../export/SnowJacket_v3.2_occlusion.png`, Occlusion Scale 1.00 (**новое**: у v2.5 слот был пуст) |
| Emission | нет |
| Fuzz Mask | `../export/SnowJacket_v3.2_fuzz.png`, **Fuzz 0.5**, Fuzz Scatter 0.91 |

**Новое описание** (вместо старого):

```
Every Rust life starts naked. Might as well warm up properly.

A short robe sewn from two old waffle bath towels, for the dash from the
steam room into the snow and back. Wrapped across with a brick-striped
collar band, tied with a belt through side loops, the ends frayed into
fringe. A rolled towel sticks out of one pocket, a birch twig out of the
other. The elbows are patched with pieces of a linen towel, a wet birch
leaf is stuck to the back, a corner is darned, and the hem carries the
towel's stripes and a few spark burns from the stove.

Part of the Sauna set.
```

**Картинки для загрузки — папка `upload_v3/`** (кадры из редактора, F12, обрезаны как у ящика; исходники —
`../screenshots/v3/`). Добавлять **все по номерам**, первая — обложка:

| # | Файл | Что | Версия |
|---|---|---|---|
| 01 | `upload_v3/01_three_quarter_day_v3.jpg` | 3/4 спереди днём: запах с кантом, пояс с узлом, рулон в кармане, веточка — обложка | v3.2 |
| 02 | `upload_v3/02_front_day_v3.jpg` | перёд: узел, концы с бахромой, четыре кармана, подпалины | v3.1 (перёд = v3.2) |
| 03 | `upload_v3/03_back_day_v3.jpg` | сзади: кокетка, мокрый лист, заплаты на локтях, кайма, штопка | v3.2 |
| 04 | `upload_v3/04_side_day_v3.jpg` | сбоку: полоса по кромке, пояс, вафля | v3.2 |

Рендеры Blender (`hero.jpg` и др.) и `ingame/*.jpg` — v2.3–v2.5, в обновление не идут. Сумерки v3.x не сняты
(кадр v3.0 в сумерках — со старым узлом и «манишкой»): можно доснять и добавить пятым.

**Change notes** (если редактор или страница спросят, англ.):

```
v3: remodelled from scratch. The robe is no longer painted on: every
waffle cell, seam, fold and stitch is real geometry. Kimono collar band
along the front edge, a belt through side loops with a wrapped knot and
fringed ends, patch pockets with a rolled towel and a birch twig, towel
patches on the elbows, a darned corner, a wet leaf and spark burns.
```

**После публикации (чек-лист):**
1. Проверить, что обновилась **та же страница** 3840344106 (иконка, описание, дата).
2. Старые картинки не удаляются: на странице *Add/edit images* (`/sharedfiles/managepreviews/?id=3840344106`)
   удалить всё старое (6 рендеров v2.x, кадры v2.5 и автокадры редактора от 15.11) — крестик появляется при
   наведении на миниатюру, удаляет сразу. Оставить новые автокадры редактора и наши 4 из `upload_v3/`.
3. Проверить, что предмет остался в коллекции **Sauna**.
4. Записать дату и что осталось в галерее сюда и в `../README.md` («Заметки»).

---


> Подготовлено 21.10.2026, обновлено для **v2.3** (27.10.2026: двойной кирпичный кант, как у полотенец, пояс без полосок, мягкая тень в горловине вместо тёмных пятен, ткань менее жёлтая; файлы `SnowJacket_v2.3_*`; v2.2 — `SnowJacket_v2_*`). Публикует пользователь сам из игрового редактора.
> ⚠️ Snow Jacket принимают **только в декабре–феврале** — опубликовать до конца ноября, чтобы скин был
> в очереди к сезону.
> **v2.4 (12.11.2026, по [CRITIQUE_ART.md](../../CRITIQUE_ART.md)):** кайма полотенца по подолу на спине, тонкий кант у манжет, банный лист между лопаток. Файлы `SnowJacket_v2.5_*`. **В игре не проверено** — посмотреть в редакторе перед публикацией; если не понравится, прежняя версия v2.3 лежит рядом (`SnowJacket_v2.3_*`).
> **v2.5 (15.11.2026):** v2.4 в игре — рукав опущен вниз, и кант у манжеты, заданный плоскостью по ширине, ложился длинной косой линией вдоль предплечья, как лампас. Манжета и кант теперь считаются вдоль оси рукава и ложатся кольцом. Файлы `SnowJacket_v2.5_*`. Кадры v2.4 отброшены — переснять.

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
| Diffuse | `../export/SnowJacket_v2.5_diffuse.png`, Color 255/255/255, Alpha Cutoff 0.00 (по умолчанию; вырез V не используем) |
| Normal | `../export/SnowJacket_v2.5_normal.png`, Normal Scale 1.00 |
| Specular/Gloss | `../export/SnowJacket_v2.5_specgloss.png`, **Spec Color 255**, Glossiness 1.00 |
| Occlusion | нет (пусто, как у оригинала) |
| Emission | нет |
| Fuzz Mask | `../export/SnowJacket_v2.5_fuzz.png`, **Fuzz 0.5** (по умолчанию 0.09), Fuzz Scatter 0.91 (по умолчанию) |

Остальные ползунки — по умолчанию. Чаще всего забывают **Fuzz 0.5** — без него вафля плоская.

## Картинки для страницы (Steam → Add/edit images)

Рендеры Blender (`../workshop_renders.py`, Cycles, 1920×1080; JPG для загрузки). Тела нет (правило
сета — без обнажёнки): халат на деревянной стойке-манекене, изнутри видна его же ткань.

| Файл | Что |
|---|---|
| `hero.jpg` | днём, 3/4 спереди — главный кадр (кирпичные полосы сета, вафля) |
| `front.jpg` | анфас: запах крест-накрест с кантом #8E3A30, пояс с узлом и полосками на концах |
| `back.jpg` | сзади: шалевый воротник, пояс, вафля |
| `belt.jpg` | крупно: узел пояса, двойная кайма на концах, вафля, карманы |
| `sleeve.jpg` | крупно: рукав, отворот манжеты, фактура вафельной ткани |
| `set.jpg` | с полотенцем Sauna Towel Wrap у каменки Sauna Stove, вечер |

![hero](hero.jpg)

Плюс **скриншоты из редактора Workshop** — v2.5, сняты пользователем 15.11.2026 на весь экран (F12), исходники в `../screenshots/editor_16x9/`; для загрузки — `ingame/` (1920×1080, панель редактора обрезана). Порядок на странице: игровой `three_quarter_day` **первым**, затем рендер `hero`, затем `back_day`, затем рендеры.

| Файл | Что |
|---|---|
| `ingame/three_quarter_day.jpg` | 3/4 спереди: перекрещенный кант, пояс, кант на манжетах |
| `ingame/back_day.jpg` | сзади: кайма полотенца по подолу, банный лист между лопаток |

## Альфа

Вырезов нет: Alpha Cutoff 0.00. Вырез V пробовали (v2) — в нём видна зелёная майка игры,
поэтому запах закрыт тканью.

## Чек-лист публикации

1. Редактор → Snow Jacket → загрузить Diffuse, Normal, Specular/Gloss, Fuzz Mask v2.
2. **Fuzz 0.5**, Spec Color 255, Alpha Cutoff 0.00.
3. Вкладка **ITEM**: имя `Sauna Robe`.
4. Вкладка **PUBLISH** → Publish → страница в браузере.
5. Описание, картинки (6 рендеров + скриншоты из игры).
6. **Workshop Contributor Agreement** (если ещё не принят).
7. Добавить в коллекцию **Sauna** (`../../workshop_collection.md`).
8. Ссылку записать в `../README.md` и в таблицу сета `../../README.md`.

## Как пересобрать картинки

```bash
"C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/snow-jacket/workshop_renders.py -- --samples 128
```

Кадры: `hero front back belt set` (можно перечислить нужные). Общие настройки сцены (материалы,
стойка-манекен, пол, стена, свет) — `../../showcase.py`. JPG — пересохранить из PNG (quality 92).
