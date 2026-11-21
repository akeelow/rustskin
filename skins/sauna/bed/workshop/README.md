# Sauna Bench — публикация в Workshop

> Подготовлено для публикации в Steam Workshop (обновлено 24.10.2026 по CRITIQUE.md: усилен градиент копоти у изножья, добавлены микротрещины). Публикует пользователь сам из игрового редактора.

## Обновление до v2.5 (21.11.2026)

Опубликованная страница (v1.2): https://steamcommunity.com/sharedfiles/filedetails/?id=3840333377. Обновлять **эту же
страницу**, не новым предметом. Как это делается из редактора, ещё не проверено.

| Слот | Файл / значение |
|---|---|
| Diffuse | `../export/Bed_v2.5_diffuse.png`, **Alpha Cutoff 0.50** |
| Normal | `../export/Bed_v2.5_normal.png` |
| Specular/Gloss | `../export/Bed_v2.5_specgloss.png` |
| Occlusion | `../export/Bed_v2.5_occlusion.png` |
| Emission | не трогать |

**Новое описание** (вместо старого):

```
Every Rust life starts naked. Might as well warm up properly.

A roadside bed frame dragged into a scrap-built sauna: the mattress went
out, a deck of aspen slats from an old pallet went on, two boards from a
paint-chipped door became the headrest, and scraps of tin covered the
corners. Polished by years of lying in the steam, charred at the end facing
the stove, with a birch whisk drying on the slats and a folded linen towel
waiting under your head.

Part of the Sauna set.
```

**Картинки для загрузки — папка `upload_v2/`** (кадры из редактора v2.5, F12, обрезаны `../../ingame_import.py place`;
исходники — `../screenshots/editor_16x9/`). Добавлять **все по номерам**, первая — обложка страницы:

| # | Файл | Что |
|---|---|---|
| 01 | `upload_v2/01_three_quarter_day_v2.jpg` | 3/4 днём со стороны изножья — обложка |
| 02 | `upload_v2/02_towel_v2.jpg` | полотенце крупно: спираль валика, хвост с бахромой, спинка из двери |
| 03 | `upload_v2/03_top_v2.jpg` | сверху: веник, листья, гвозди, кольцо от шайки, обугленный угол |
| 04 | `upload_v2/04_foot_end_v2.jpg` | изножье низко: тёсаные стойки, фартук, эмаль со сколами |
| 05 | `upload_v2/05_corner_foot_v2.jpg` | угол изножья: стойка, пластина, распорка с проволокой |
| 06 | `upload_v2/06_headboard_back_v2.jpg` | спинка сзади |
| 07 | `upload_v2/07_dusk_v2.jpg` | сумерки |

Рендеры Blender (`hero.jpg` и др.) и старые кадры `ingame/*_day.jpg` — v1.2, в обновление не идут.

**Change notes** (если редактор или страница спросят, англ.):

```
v2: remodelled from scratch. Weathered slats with real grain, knots, cracks and
nails, a pressed birch whisk, a folded linen towel with fringe, door-board
headrest with layered chipped paint, hand-hewn posts, chipped enamel steel frame.
```

**Как обновлять (21.11.2026):** в редакторе выбран опубликованный Sauna Bench из Workshop — редактор просит заново
заполнить описание и приложить картинки. Описание — блок «Новое описание» выше, картинки — `upload_v2/` по номерам.
Что получилось (та же страница или новая, сохранились ли подписчики/голоса) — записать сюда после публикации.

## Название и описание (англ.)

**Title:** `Sauna Bench`

**Description** (вставить на странице Steam после публикации):

```
Every Rust life starts naked. Might as well warm up properly.

A roadside bed frame dragged into a scrap-built sauna: the mattress went
out, a deck of aspen slats from an old pallet went on, two boards from a
paint-chipped door became the headrest. Polished by years of lying in the
steam, smoked at the end facing the stove, with a rolled linen towel
waiting under your head.

Part of the Sauna set.
```

Коротко, без просьб о лайках и без текста на самой текстуре (правила сета и советы Facepunch).

## Иконка

Иконку **генерирует сам редактор** при Publish, Facepunch просит её не заменять
([Creating Skins](https://wiki.facepunch.com/rust/Creating_Skins)). Перед Publish выставить:

| Слот | Файл / значение |
|---|---|
| Diffuse | `../export/Bed_v1.2_diffuse.png`, **Alpha Cutoff 0.50** (по умолчанию) |
| Normal | `../export/Bed_v1.2_normal.png` |
| Specular/Gloss | `../export/Bed_v1.2_specgloss.png` |
| Occlusion | `../export/Bed_v1.2_occlusion.png` |
| Emission | не трогать |

Остальные ползунки — по умолчанию.

## Картинки для страницы (Steam → Add/edit images)

Рендеры Blender (`../workshop_renders.py`, Cycles, 1920×1080; JPG для загрузки):

| Файл | Что |
|---|---|
| `hero.jpg` | днём, 3/4 от изножья — главный кадр |
| `towel.jpg` | крупно: полотенце-рулон, спинка из дверных досок |
| `side.jpg` | сбоку: настил, фартук, лаги на швеллере |
| `foot.jpg` | крупно изножье: гвозди, листья, след шайки, подкопчённый край |
| `dusk.jpg` | сумерки, тёплый свет от каменки со стороны ног |

![hero](hero.jpg)

Плюс **скриншоты из редактора Workshop** — сняты пользователем 21.10.2026 на весь экран (F12), исходники в `../screenshots/editor_16x9/`; для загрузки — `ingame/` (1920×1080, панель редактора обрезана). Порядок на странице: рендер `hero`, затем скриншоты в этом порядке, затем остальные рендеры.

| Файл | Что |
|---|---|
| `ingame/three_quarter_day.jpg` | 3/4 днём |
| `ingame/headrest_day.jpg` | крупно подголовник с полотенцем, днём |
| `ingame/foot_day.jpg` | со стороны изножья днём |

## Вырез альфой

Альфой убрано только **одеяло** (и отворот простыни): под ним цельный верх матраса — насквозь
ничего не видно, на хитбокс текстура не влияет. У оригинала одеяло уже резалось альфой (рваные
края), Alpha Cutoff 0.50 — значение редактора по умолчанию. Риск отказа из-за прозрачности —
низкий (см. разбор в [../../electric-furnace/workshop/README.md](../../electric-furnace/workshop/README.md)).

## Чек-лист публикации

1. Редактор → Bed → загрузить 4 карты v1.2 (Alpha Cutoff 0.50).
2. Вкладка **ITEM**: имя `Sauna Bench`.
3. Вкладка **PUBLISH** → Publish → страница в браузере.
4. Описание, картинки (5 рендеров + 2–3 скриншота из игры).
5. **Workshop Contributor Agreement** (если ещё не принят).
6. Добавить в коллекцию **Sauna**.
7. Ссылку записать в `../README.md` и в таблицу сета `../../README.md`.

## Как пересобрать картинки

```bash
"C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/bed/workshop_renders.py -- --samples 128
```

Кадры: `hero towel side foot dusk` (можно перечислить нужные), все пять ~1 мин на RTX 3060 Ti.
JPG — пересохранить из PNG (quality 92).
