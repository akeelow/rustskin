# Sauna — публикация по шагам

> 15.11.2026. Все карты проверены в игре, кадры сняты. Картинки для страниц разложены по папкам с номерами в
> `C:\Users\akeel\OneDrive\rustskin\skins\sauna\upload` (собирает `make_upload.py`; если папки нет — попросить агента пересобрать). Публикует только пользователь: из редактора Rust и на
> страницах Steam. Все пути ниже — от папки `skins/sauna/`.

## Перед началом (один раз)

1. Steam запущен, вход в аккаунт выполнен. Браузер, в котором открываются страницы Steam, тоже залогинен в Steam.
2. Принять **Workshop Contributor Agreement**: Steam → Workshop Rust → ссылка вверху страницы о соглашении. Без
   него принятый скин не станет публичным в магазине.
3. Публиковать **все семь подряд, в один заход**, затем собрать коллекцию.
4. ✅ 15.11: платёжная и налоговая информация (W-8BEN) заполнена и подтверждена.

## Шаги для одного предмета

Повторить для каждого из семи по порядку из таблицы ниже.

1. Rust → **Workshop** → **Create a new item** → выбрать предмет (колонка «Предмет в редакторе») → вкладка **EDIT**.
2. Загрузить файлы в слоты и выставить ползунки (раздел предмета ниже). Слот, которого нет в списке, не трогать.
   Плашка «This item uses the Metal/Smoothness workflow» у каменки — просто информация, наша карта сделана под
   эту схему.
3. Сдвинуть ползунок TIME на день и на ночь, проверить, что предмет выглядит как на скриншотах.
4. Вкладка **ITEM** → имя (колонка «Название»). Без имени кнопка Publish неактивна.
5. Вкладка **PUBLISH**:
   - **Description** — вставить текст из раздела предмета ниже (блок «Описание», целиком).
   - **Additional Preview Images** → «+» → добавить картинки из папки предмета (раздел ниже) **по номерам 01, 02, 03…**. Если редактор
     какую-то не примет — добавить её потом на странице Steam (Add/edit images & videos).
   - **Icon Override** — не трогать (None): иконку редактор делает сам. **Change Log** — пусто.
   - Нажать **PUBLISH**. Откроется страница предмета в браузере.
6. На странице Steam:
   - **Add/edit images & videos** → удалить **автоскрины редактора** — общие планы, где предмет маленький
     (редактор сам добавляет несколько штук перед нашими). Первой должна стать наша `01_`.
   - Под описанием, блок «Распределение доходов» → **Завершить** (100% тебе; потом изменить нельзя). Пока не
     нажато, предмет **скрыт** (плашка «Почти готово!»).
   - Проверить: описание с переносами строк, все картинки на месте, видимость **Public**.
   - Вопрос «Хотели бы вы, чтобы эту работу официально выпустили» — голосование для посетителей, пропустить.
7. Скопировать ссылку на страницу и прислать агенту (запишет в README).

## Порядок и названия

| # | Название | Предмет в редакторе | Папка | Страница |
|---|---|---|---|---|
| 1 | `Sauna Stove` | Electric Furnace | `electric-furnace` | [3840311723](https://steamcommunity.com/sharedfiles/filedetails/?id=3840311723) |
| 2 | `Sauna Bench` | Bed | `bed` | [3840333377](https://steamcommunity.com/sharedfiles/filedetails/?id=3840333377) |
| 3 | `Sauna Chair` | Chair | `chair` | [3840335380](https://steamcommunity.com/sharedfiles/filedetails/?id=3840335380) |
| 4 | `Sauna Stone Box` | Wood Storage Box | `wood-storage-box` | |
| 5 | `Sauna Changing Locker` | Locker | `locker` | |
| 6 | `Sauna Towel Wrap` | Burlap Headwrap | `burlap-headwrap` | |
| 7 | `Sauna Robe` | Snow Jacket | `snow-jacket` | |

---

## 1. Sauna Stove — Electric Furnace

**Описание** (поле Description):

```
Every Rust life starts naked. Might as well warm up properly.

An old kitchen cooker turned into a sauna stove: clad in aspen slats nailed
to the rusty shell, burners buried under split basalt, a forged grate over a
firebox full of glowing rocks, all sitting on a rubble plinth and a wet pallet.

Part of the Sauna set.
```

**Файлы** (`electric-furnace/export/`):

| Слот | Файл | Ползунки |
|---|---|---|
| Diffuse | `ElectricFurnace_v2.9_diffuse_cutout.png` (именно `_cutout`) | **Alpha Cutoff 1.00** — ползунок до упора вправо; при 0.00 сквозь камни видны спирали конфорок |
| Normal | `ElectricFurnace_v2.9_normal.png` | |
| Metal/Gloss | `ElectricFurnace_v2.9_metalgloss.png` | |
| Occlusion | `ElectricFurnace_v2.9_occlusion.png` | |
| Emission | `ElectricFurnace_v2.9_emission.png` | |

**Картинки:** папка `C:\Users\akeel\OneDrive\rustskin\skins\sauna\upload\1 Sauna Stove` — 11 файлов. Добавить **все по номерам**, от `01_` до `11_`
(первая станет обложкой галереи). `game_` — кадры из игры, `render_` — рендеры.

## 2. Sauna Bench — Bed

**Описание** (поле Description):

```
Every Rust life starts naked. Might as well warm up properly.

A roadside bed frame dragged into a scrap-built sauna: the mattress went
out, a deck of aspen slats from an old pallet went on, two boards from a
paint-chipped door became the headrest. Polished by years of lying in the
steam, smoked at the end facing the stove, with a rolled linen towel
waiting under your head.

Part of the Sauna set.
```

**Файлы** (`bed/export/`):

| Слот | Файл | Ползунки |
|---|---|---|
| Diffuse | `Bed_v1.2_diffuse.png` | Alpha Cutoff **0.50** (по умолчанию, не сбрасывать) |
| Normal | `Bed_v1.2_normal.png` | |
| Specular/Gloss | `Bed_v1.2_specgloss.png` | |
| Occlusion | `Bed_v1.2_occlusion.png` | |

**Картинки:** папка `C:\Users\akeel\OneDrive\rustskin\skins\sauna\upload\2 Sauna Bench` — 8 файлов. Добавить **все по номерам**, от `01_` до `08_`
(первая станет обложкой галереи). `game_` — кадры из игры, `render_` — рендеры.

## 3. Sauna Chair — Chair

**Описание** (поле Description):

```
Every Rust life starts naked. Might as well warm up properly.

An old armchair on a steel-channel frame, dragged from the same roadside
house as the bench and set in the changing room, where you cool off after
the steam. The back is clad in lining off-cuts left over from the sauna
walls, the seat in aspen slats, and a shovel handle stands in for the
missing leg, its split end bound with wire. Greasy where the hands rest,
a wet patch where the wash basin stood, a few leaves off the bath broom,
and a linen towel thrown over the back.

Part of the Sauna set.
```

**Файлы** (`chair/export/`), все ползунки по умолчанию:

| Слот | Файл |
|---|---|
| Diffuse | `Chair_v1.4_diffuse.png` |
| Normal | `Chair_v1.4_normal.png` |
| Specular/Gloss | `Chair_v1.4_specgloss.png` |
| Occlusion | `Chair_v1.4_occlusion.png` |

**Картинки:** папка `C:\Users\akeel\OneDrive\rustskin\skins\sauna\upload\3 Sauna Chair` — 9 файлов. Добавить **все по номерам**, от `01_` до `09_`
(первая станет обложкой галереи). `game_` — кадры из игры, `render_` — рендеры.

## 4. Sauna Stone Box — Wood Storage Box

**Описание** (поле Description):

```
Every Rust life starts naked. Might as well warm up properly.

An old crate kept by the sauna stove for the spare stones and the embers
to light it with. Bound with two hoops off a barrel so the heat wouldn't
split it, a sheet of steel on the bottom so it wouldn't catch. The basalt
on the steel is still hot: at night radiant embers glow between the stones,
and warm firelight spills through the handle grips and plank seams.

Part of the Sauna set.
```

**Файлы** (`wood-storage-box/export/`):

| Слот | Файл | Ползунки |
|---|---|---|
| Diffuse | `Box_v1.6_diffuse.png` | **Color 255/255/255**, **Alpha Cutoff 0.50** |
| Normal | `Box_v1.6_normal.png` | |
| Specular/Gloss | `Box_v1.6_specgloss.png` | **Spec Color 255/255/255** |
| Occlusion | `Box_v1.6_occlusion.png` | |
| Emission | `Box_v1.6_emission.png` | **Emission Color 255/255/255** |

**Картинки:** папка `C:\Users\akeel\OneDrive\rustskin\skins\sauna\upload\4 Sauna Stone Box` — 9 файлов. Добавить **все по номерам**, от `01_` до `09_`
(первая станет обложкой галереи). `game_` — кадры из игры, `render_` — рендеры.

## 5. Sauna Changing Locker — Locker

**Описание** (поле Description):

```
Every Rust life starts naked. Might as well warm up properly.

The changing room of a scrap-built sauna. Two open niches in lime
boards, pegs for the towels, shelves lit from beneath for the dash back
from the steam. The middle door stays shut: a fogged window with a heart
drawn by a finger, a map burnt into the boards with a trail to an X, days
counted in notches, a thermometer and a hygrometer, and a steel plate for
your lock - scratched by keys, next to a boot print and a split board
where someone tried to kick it in.

Part of the Sauna set.
```

**Файлы** (`locker/export/`):

| Слот | Файл | Ползунки |
|---|---|---|
| Diffuse | `Locker_v5.4_diffuse.png` (**не** `_solid`) | **Alpha Cutoff 0.50** |
| Normal | `Locker_v5.4_normal.png` | |
| Specular/Gloss | `Locker_v5.4_specgloss.png` | |
| Occlusion | не трогать (оригинальный) | |
| Emission | `Locker_v5.4_emission.png` | **Emission Color 255/255/255** |

**Картинки:** папка `C:\Users\akeel\OneDrive\rustskin\skins\sauna\upload\5 Sauna Changing Locker` — 9 файлов. Добавить **все по номерам**, от `01_` до `09_`
(первая станет обложкой галереи). `game_` — кадры из игры, `render_` — рендеры.

## 6. Sauna Towel Wrap — Burlap Headwrap

**Описание** (поле Description):

```
Every Rust life starts naked. Might as well warm up properly.

An old linen sauna towel with two faded brick stripes, wound round the
head and neck and tied with twine, to keep the ears warm between the
steam room and the snow. Washed grey, yellowed where you breathe, and
frayed at every edge.

Part of the Sauna set.
```

**Файлы** (`burlap-headwrap/export/`):

| Слот | Файл | Ползунки |
|---|---|---|
| Diffuse | `BurlapHeadwrap_v1.3_diffuse.png` | Alpha Cutoff **0.79** (по умолчанию, не сбрасывать) |
| Normal | `BurlapHeadwrap_v1.3_normal.png` | |
| Specular/Gloss | `BurlapHeadwrap_v1.3_specgloss.png` | |
| Occlusion | не трогать (оригинальный) | |
| Fuzz Mask | не трогать | **Fuzz 0.58** |

**Картинки:** папка `C:\Users\akeel\OneDrive\rustskin\skins\sauna\upload\6 Sauna Towel Wrap` — 7 файлов. Добавить **все по номерам**, от `01_` до `07_`
(первая станет обложкой галереи). `game_` — кадры из игры, `render_` — рендеры.

## 7. Sauna Robe — Snow Jacket

**Описание** (поле Description):

```
Every Rust life starts naked. Might as well warm up properly.

A short waffle robe for the dash from the steam room into the snow and
back. Wrapped across and tied with a belt, patch pockets, wide cuffs.
Washed a hundred times in a bucket and never quite dry: the beige has
gone uneven, with damp patches that never fade.

Part of the Sauna set.
```

**Файлы** (`snow-jacket/export/`):

| Слот | Файл | Ползунки |
|---|---|---|
| Diffuse | `SnowJacket_v2.5_diffuse.png` | |
| Normal | `SnowJacket_v2.5_normal.png` | |
| Specular/Gloss | `SnowJacket_v2.5_specgloss.png` | **Spec Color 255** |
| Fuzz Mask | `SnowJacket_v2.5_fuzz.png` | **Fuzz 0.5** |

**Картинки:** папка `C:\Users\akeel\OneDrive\rustskin\skins\sauna\upload\7 Sauna Robe` — 6 файлов. Добавить **все по номерам**, от `01_` до `06_`
(первая станет обложкой галереи). `game_` — кадры из игры, `render_` — рендеры.

---

## После семи предметов: коллекция

1. Steam → Workshop Rust → **Create Collection**.
2. Название `Sauna`, картинка `C:\Users\akeel\OneDrive\rustskin\skins\sauna\upload\collection.jpg`, описание:

   ```
   Every Rust life starts naked. Might as well warm up properly.

   A sauna scrap-built by a survivor: an old cooker clad in aspen slats with
   glowing rocks in the firebox, a bed frame turned into a slatted bench, an
   armchair from the changing room, a crate of hot stones and embers by the
   stove, a changing locker with lit niches and a door for your lock - and a
   towel wrap and a waffle robe for the dash into the snow.

   Seven skins, one house.
   ```

3. Добавить все семь предметов в порядке из таблицы выше → видимость **Public**.
4. Прислать агенту ссылку на коллекцию.

## Если что-то пошло не так

- **Предмет выглядит иначе, чем на скриншотах** — почти всегда забыт ползунок: Alpha Cutoff, Emission Color
  или Fuzz. Сверить с таблицей предмета.
- **Опубликовал с ошибкой** — пока предмет не принят, его можно обновить из того же редактора (на этом не
  настаивать без проверки: если кнопки обновления нет, сообщить агенту).
- **Facepunch просит убрать прозрачность у шкафчика** — в Diffuse поставить `Locker_v5.4_diffuse_solid.png`,
  Alpha Cutoff 0.00.
