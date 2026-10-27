# Sauna — коллекция в Steam Workshop и план публикации

> Подготовлено 21.10.2026. Публикует **только пользователь** из игрового редактора Rust и на страницах Steam.
> Пакеты предметов — в `<предмет>/workshop/README.md` (таблица загрузки, название, описание, картинки).

## Состав коллекции

| # | Название | Предмет в редакторе | Пакет | Ползунки, которые чаще всего забывают |
|---|---|---|---|---|
| 1 | `Sauna Stove` | Electric Furnace | [electric-furnace/workshop](electric-furnace/workshop/README.md) | Diffuse = `_diffuse_cutout`, **Alpha Cutoff 1.00** |
| 2 | `Sauna Towel Wrap` | Burlap Headwrap | [burlap-headwrap/workshop](burlap-headwrap/workshop/README.md) | **Fuzz 0.58**, Alpha Cutoff 0.79 (не сбрасывать) |
| 3 | `Sauna Robe` | Snow Jacket | [snow-jacket/workshop](snow-jacket/workshop/README.md) | **Fuzz 0.5** |
| 4 | `Sauna Changing Locker` | Locker | [locker/workshop](locker/workshop/README.md) | **Alpha Cutoff 0.50**, **Emission Color 255** |
| 5 | `Sauna Bench` | Bed | [bed/workshop](bed/workshop/README.md) | Alpha Cutoff 0.50 (по умолчанию — не сбрасывать) |
| 6 | `Sauna Chair` | Chair | [chair/workshop](chair/workshop/README.md) | — (всё по умолчанию) |
| 7 | `Sauna Stone Box` | Wood Storage Box | [wood-storage-box/workshop](wood-storage-box/workshop/README.md) | **Alpha Cutoff 0.50**, **Emission Color 255**, Color 255, Spec Color 255 |

Hide Poncho пропущено (20.10.2026).

## Картинка коллекции

`workshop/collection.png` (1024×1024; JPG — `workshop/collection.jpg`): вечер в бане сверху от двери, все семь
предметов в одной комнате — справа светится каменка, перед ней ящик с углями, вдоль стены полок изножьем к
печи, слева шкафчик, халат и тюрбан на стойке-манекене, кресло. Обновлено 27.10.2026 (плотнее кадр, ярче огонь). Скрипт — [workshop_collection.py](workshop_collection.py):

```bash
"C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/workshop_collection.py -- --samples 192 --size 1024
```

![collection](workshop/collection.jpg)

Старая обложка с одной каменкой (`electric-furnace/workshop/collection.*`) удалена 27.10.2026.

## Описание коллекции (англ.)

**Title:** `Sauna`

```
Every Rust life starts naked. Might as well warm up properly.

A sauna scrap-built by a survivor: an old cooker clad in aspen slats with
glowing rocks in the firebox, a bed frame turned into a slatted bench, an
armchair from the changing room, a crate of hot stones and embers by the
stove, a changing locker with lit niches and a door for your lock - and a
towel wrap and a waffle robe for the dash into the snow.

Seven skins, one house.
```

Без просьб о лайках, без текста на текстурах (правила сета и советы Facepunch).

## Порядок и даты

- **Все семь — в один день**, затем сразу коллекция: голоса и просмотры не размазываются, и каждая
  страница ссылается на остальные через коллекцию.
- **Срок — до конца ноября 2026.** Snow Jacket принимают только в декабре–феврале: опубликованный в
  ноябре халат попадает в очередь к сезону.
- **Предлагаемая дата: суббота, 14.11.2026** — до неё время на скриншоты, после неё две недели
  запаса, если Steam или Facepunch что-то попросят исправить.
- **Скриншоты — только из редактора Workshop** (до публикации и покупки скин больше нигде не виден;
  решение пользователя 21.10.2026: искусственные рендеры вместо игровых кадров не делаем — замок,
  снег и сцены с несколькими предметами не изображаем). Пользователь снимает сам; что доснять —
  в пакете каждого предмета (шкафчик v5 снят 21.10.2026 — день, сумерки, ночь; у остальных скриншоты уже есть).

## Скриншоты 16:9 (пересъёмка 21.10.2026)

Все скриншоты для страниц переснимаются в редакторе **на весь экран** (панель свернуть стрелкой «<»,
снимать F12 — скриншот Steam в родном разрешении), чтобы галерея была ровной 16:9, как рендеры.
Куда класть: `<предмет>/screenshots/editor_16x9/` (папки есть у всех семи).

Графика на время съёмки поднята (21.10.2026, игра была закрыта): в `Rust/cfg/client.cfg` — decor,
grass, mesh, tree.meshes 100; drawdistance 2500; DLAA; water quality/reflections 2; SSS в полном
разрешении; мягкие частицы; без агрессивного LOD теней. Остальные ползунки — проверить в Options →
Graphics и дотянуть до максимума вручную. **Прежние настройки** — `client.cfg.before_max_2026-10-21`
рядом; вернуть (при закрытой игре — Rust переписывает конфиг при выходе):

```bash
cp "/c/Program Files (x86)/Steam/steamapps/common/Rust/cfg/client.cfg.before_max_2026-10-21" "/c/Program Files (x86)/Steam/steamapps/common/Rust/cfg/client.cfg"
```

## Чек-лист публикации (в день публикации)

Для **каждого** из семи предметов (порядок: каменка, полок, кресло, ящик, шкафчик, тюрбан, халат):

1. Rust → Workshop → **Create a new item** → предмет → EDIT.
2. Загрузить карты из пакета, **выставить ползунки по таблице пакета** (колонка выше — самые частые ошибки).
3. Посмотреть в редакторе днём и ночью (тумблер времени) — то же, что на скриншотах.
4. Вкладка **ITEM**: имя из колонки «Название» (без скобок, без оригинального имени).
5. Вкладка **PUBLISH** → Publish. Иконку **не заменять** — редактор делает её сам.
6. На открывшейся странице Steam: **описание** из пакета, **картинки** (рендеры JPG + скриншоты из
   игры; `.webp` пересохранить в JPG/PNG), видимость — Public.
7. Ссылку на страницу записать в `<предмет>/README.md` и в таблицу сета `README.md`.

Один раз:

8. Принять **Workshop Contributor Agreement** (без него принятый скин не станет публичным в магазине).
9. Steam → Workshop Rust → **Create Collection** → название `Sauna`, картинка `workshop/collection.jpg`,
   описание выше → добавить все семь предметов → Public.
10. В описание каждого предмета можно добавить ссылку на коллекцию (последней строкой перед
    «Part of the Sauna set.»).
