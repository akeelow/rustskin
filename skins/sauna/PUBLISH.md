# Sauna — публикация по шагам

> 15.11.2026. Все карты проверены в игре, кадры сняты. Публикует только пользователь: из редактора Rust и на
> страницах Steam. Все пути ниже — от папки `skins/sauna/`.

## Перед началом (один раз)

1. Steam запущен, вход в аккаунт выполнен. Браузер, в котором открываются страницы Steam, тоже залогинен в Steam.
2. Принять **Workshop Contributor Agreement**: Steam → Workshop Rust → ссылка вверху страницы о соглашении. Без
   него принятый скин не станет публичным в магазине.
3. Публиковать **все семь подряд, в один заход**, затем собрать коллекцию.

## Шаги для одного предмета

Повторить для каждого из семи по порядку из таблицы ниже.

1. Rust → **Workshop** → **Create a new item** → выбрать предмет (колонка «Предмет в редакторе») → вкладка **EDIT**.
2. Загрузить файлы в слоты и выставить ползунки (раздел предмета ниже). Слот, которого нет в списке, не трогать.
3. Сдвинуть ползунок TIME на день и на ночь, проверить, что предмет выглядит как на скриншотах.
4. Вкладка **ITEM** → имя (колонка «Название»). Без имени кнопка Publish неактивна.
5. Вкладка **PUBLISH** → **Publish**. Иконку не менять — редактор делает её сам. Откроется страница предмета в
   браузере.
6. На странице Steam:
   - **Edit title & description** → вставить описание из пакета предмета (`<папка>/workshop/README.md`, блок
     `Description`, текст между ``` целиком).
   - **Add/edit images & videos** → загрузить картинки **в порядке из раздела предмета** (первая — обложка
     галереи).
   - Видимость — **Public**.
7. Скопировать ссылку на страницу и прислать агенту (запишет в README).

## Порядок и названия

| # | Название | Предмет в редакторе | Папка |
|---|---|---|---|
| 1 | `Sauna Stove` | Electric Furnace | `electric-furnace` |
| 2 | `Sauna Bench` | Bed | `bed` |
| 3 | `Sauna Chair` | Chair | `chair` |
| 4 | `Sauna Stone Box` | Wood Storage Box | `wood-storage-box` |
| 5 | `Sauna Changing Locker` | Locker | `locker` |
| 6 | `Sauna Towel Wrap` | Burlap Headwrap | `burlap-headwrap` |
| 7 | `Sauna Robe` | Snow Jacket | `snow-jacket` |

---

## 1. Sauna Stove — Electric Furnace

**Файлы** (`electric-furnace/export/`):

| Слот | Файл | Ползунки |
|---|---|---|
| Diffuse | `ElectricFurnace_v2.9_diffuse_cutout.png` (именно `_cutout`) | **Alpha Cutoff 1.00** |
| Normal | `ElectricFurnace_v2.9_normal.png` | |
| Metal/Gloss | `ElectricFurnace_v2.9_metalgloss.png` | |
| Occlusion | `ElectricFurnace_v2.9_occlusion.png` | |
| Emission | `ElectricFurnace_v2.9_emission.png` | |

**Картинки** (`electric-furnace/workshop/`), по порядку:
`ingame/front_night.jpg` → `studio.jpg` → `ingame/three_quarter_day.jpg` → `ingame/top_night.jpg` →
`ingame/top_day.jpg` → `hero.jpg` → `night.jpg` → `firebox.jpg` → `burners.jpg` → `back.jpg`

## 2. Sauna Bench — Bed

**Файлы** (`bed/export/`):

| Слот | Файл | Ползунки |
|---|---|---|
| Diffuse | `Bed_v1.2_diffuse.png` | Alpha Cutoff **0.50** (по умолчанию, не сбрасывать) |
| Normal | `Bed_v1.2_normal.png` | |
| Specular/Gloss | `Bed_v1.2_specgloss.png` | |
| Occlusion | `Bed_v1.2_occlusion.png` | |

**Картинки** (`bed/workshop/`):
`hero.jpg` → `ingame/three_quarter_day.jpg` → `ingame/headrest_day.jpg` → `ingame/foot_day.jpg` →
`towel.jpg` → `side.jpg` → `foot.jpg` → `dusk.jpg`

## 3. Sauna Chair — Chair

**Файлы** (`chair/export/`), все ползунки по умолчанию:

| Слот | Файл |
|---|---|
| Diffuse | `Chair_v1.4_diffuse.png` |
| Normal | `Chair_v1.4_normal.png` |
| Specular/Gloss | `Chair_v1.4_specgloss.png` |
| Occlusion | `Chair_v1.4_occlusion.png` |

**Картинки** (`chair/workshop/`):
`hero.jpg` → `ingame/three_quarter_day.jpg` → `ingame/side_day.jpg` → `ingame/back_day.jpg` →
`towel.jpg` → `seat.jpg` → `back.jpg` → `dusk.jpg` → `set.jpg`

## 4. Sauna Stone Box — Wood Storage Box

**Файлы** (`wood-storage-box/export/`):

| Слот | Файл | Ползунки |
|---|---|---|
| Diffuse | `Box_v1.6_diffuse.png` | **Color 255/255/255**, **Alpha Cutoff 0.50** |
| Normal | `Box_v1.6_normal.png` | |
| Specular/Gloss | `Box_v1.6_specgloss.png` | **Spec Color 255/255/255** |
| Occlusion | `Box_v1.6_occlusion.png` | |
| Emission | `Box_v1.6_emission.png` | **Emission Color 255/255/255** |

**Картинки** (`wood-storage-box/workshop/`):
`ingame/top_night.jpg` → `studio.jpg` → `ingame/top_day.jpg` → `ingame/three_quarter_day.jpg` →
`hero.jpg` → `night.jpg` → `top.jpg` → `row.jpg` → `set.jpg`

## 5. Sauna Changing Locker — Locker

**Файлы** (`locker/export/`):

| Слот | Файл | Ползунки |
|---|---|---|
| Diffuse | `Locker_v5.4_diffuse.png` (**не** `_solid`) | **Alpha Cutoff 0.50** |
| Normal | `Locker_v5.4_normal.png` | |
| Specular/Gloss | `Locker_v5.4_specgloss.png` | |
| Occlusion | не трогать (оригинальный) | |
| Emission | `Locker_v5.4_emission.png` | **Emission Color 255/255/255** |

**Картинки** (`locker/workshop/`):
`ingame/front_night.jpg` → `studio.jpg` → `ingame/front_day.jpg` → `ingame/three_quarter_day.jpg` →
`ingame/three_quarter_night.jpg` → `door.jpg` → `hero.jpg` → `night.jpg` → `set.jpg`

## 6. Sauna Towel Wrap — Burlap Headwrap

**Файлы** (`burlap-headwrap/export/`):

| Слот | Файл | Ползунки |
|---|---|---|
| Diffuse | `BurlapHeadwrap_v1.3_diffuse.png` | Alpha Cutoff **0.79** (по умолчанию, не сбрасывать) |
| Normal | `BurlapHeadwrap_v1.3_normal.png` | |
| Specular/Gloss | `BurlapHeadwrap_v1.3_specgloss.png` | |
| Occlusion | не трогать (оригинальный) | |
| Fuzz Mask | не трогать | **Fuzz 0.58** |

**Картинки** (`burlap-headwrap/workshop/`):
`ingame/front_day.jpg` → `hero.jpg` → `ingame/side_day.jpg` → `ingame/three_quarter_night.jpg` →
`front.jpg` → `side.jpg` → `set.jpg`

## 7. Sauna Robe — Snow Jacket

**Файлы** (`snow-jacket/export/`):

| Слот | Файл | Ползунки |
|---|---|---|
| Diffuse | `SnowJacket_v2.5_diffuse.png` | |
| Normal | `SnowJacket_v2.5_normal.png` | |
| Specular/Gloss | `SnowJacket_v2.5_specgloss.png` | **Spec Color 255** |
| Fuzz Mask | `SnowJacket_v2.5_fuzz.png` | **Fuzz 0.5** |

**Картинки** (`snow-jacket/workshop/`):
`ingame/three_quarter_day.jpg` → `hero.jpg` → `ingame/back_day.jpg` → `back.jpg` → `belt.jpg` → `set.jpg`

---

## После семи предметов: коллекция

1. Steam → Workshop Rust → **Create Collection**.
2. Название `Sauna`, картинка `workshop/collection.jpg`, описание — из [workshop_collection.md](workshop_collection.md)
   («Описание коллекции»).
3. Добавить все семь предметов в порядке из таблицы выше → видимость **Public**.
4. Прислать агенту ссылку на коллекцию.

## Если что-то пошло не так

- **Предмет выглядит иначе, чем на скриншотах** — почти всегда забыт ползунок: Alpha Cutoff, Emission Color
  или Fuzz. Сверить с таблицей предмета.
- **Опубликовал с ошибкой** — пока предмет не принят, его можно обновить из того же редактора (на этом не
  настаивать без проверки: если кнопки обновления нет, сообщить агенту).
- **Facepunch просит убрать прозрачность у шкафчика** — в Diffuse поставить `Locker_v5.4_diffuse_solid.png`,
  Alpha Cutoff 0.00.
