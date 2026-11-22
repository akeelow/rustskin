# Sauna Stove — публикация в Workshop

> Подготовлено 19.10.2026, обновлено для **v2.8** (27.10.2026: неровные пятна накипи вместо концентрических колец и белых точек; файлы `ElectricFurnace_v2.8_*`; v2.7 — `ElectricFurnace_v2_*`). Публикует пользователь сам из игрового редактора.
> **v2.9 (12.11.2026, по [CRITIQUE_ART.md](../../CRITIQUE_ART.md)):** сухой банный лист на плите у переднего края (сквозной мотив сета); первый кадр `studio.jpg` снят с левого бока, топка ярче. Файлы `ElectricFurnace_v2.9_*`. **В игре не проверено** — посмотреть в редакторе перед публикацией; если не понравится, прежняя версия v2.8 лежит рядом (`ElectricFurnace_v2.8_*`).

## Обновление до v3.1 (22.11.2026)

Опубликованная страница (v2.9): https://steamcommunity.com/sharedfiles/filedetails/?id=3840311723. Обновлять **эту же
страницу**: в редакторе выбрать опубликованный Sauna Stove из Workshop → загрузить карты → Publish (так обновлялся полок,
см. гайд §9.7).

| Слот | Файл / значение |
|---|---|
| Diffuse | `../export/ElectricFurnace_v3.1_diffuse_cutout.png`, **Alpha Cutoff 1.00** |
| Normal | `../export/ElectricFurnace_v3.1_normal.png` |
| Metal/Gloss | `../export/ElectricFurnace_v3.1_metalgloss.png` |
| Occlusion | `../export/ElectricFurnace_v3.1_occlusion.png` (2048) |
| Emission | `../export/ElectricFurnace_v3.1_emission.png` (2048), Emission Color 255 |

**Новое описание** (вместо старого):

```
Every Rust life starts naked. Might as well warm up properly.

An old enamel cooker turned into a sauna stove: hand-split aspen slats nailed
over the rusty shell with a wooden thermometer on the side, split basalt piled
on the burners and held by twisted wire, a forged grate with a rope-wrapped
handle over a firebox of rocks and glowing charcoal, old fence boards and a
little hatch on the back, all standing on salvaged bricks and a wet pallet.

Part of the Sauna set.
```

**Change notes** (англ.):

```
v3: remodelled from scratch. Every slat, nail, knot, crack, char block, rivet,
brick and stone is now real modelled relief; chipped enamel top with burned
rings and mineral crust, split basalt heaps, forged door, brick plinth,
fence-board back with a hatch. All maps 2048.
```

**Картинки — папка `upload_v3/`** (кадры из редактора v3.1 в режиме предпросмотра, исходники — `../screenshots/v3.1/`).
Поверх сцены редактор рисует заголовок «SAUNA STOVE / AKEELOW» с кнопками и нижнюю панель — кадры обрезаны 16:9 под
заголовком и над панелью (y 162–984, x ≤ 1635) и увеличены до 1920×1080. Добавлять **все по номерам**, первая — обложка:

| # | Файл | Что |
|---|---|---|
| 01 | `upload_v3/01_three_quarter_day.jpg` | 3/4 спереди-слева днём: дверца, ручки, верёвка, цоколь — обложка |
| 02 | `upload_v3/02_three_quarter_night.jpg` | то же ночью: свет топки |
| 03 | `upload_v3/03_top_three_quarter_day.jpg` | 3/4 сверху: кучи базальта в обручах, эмаль, накипь, листья |
| 04 | `upload_v3/04_top_day.jpg` | сверху: плита целиком, термометр на боку |
| 05 | `upload_v3/05_back_right_day.jpg` | сзади справа: жалюзи, забор с краской, лючок |
| 06 | `upload_v3/06_back_left_day.jpg` | сзади слева: лючок, левый бок с термометром |
| 07 | `upload_v3/07_top_night.jpg` | сверху ночью |

Кадры в анфас (`../screenshots/v3.1/02`, `03`, `10`) не вошли: каменка заходит под заголовок редактора, чисто не
обрезать. Для анфаса днём и ночью — переснять, поставив каменку левее центра кадра или отойдя на шаг.

**Опубликовано 22.11.2026** (обновление той же страницы). Старые картинки v2.9 — 11 штук (рендеры и кадры 15.11) —
удалены 22.11 на managepreviews; на странице 11 картинок v3.1: 4 автокадра редактора (идут первыми) и наши 7.
Порядок меняется перетаскиванием на той же странице («Сохранить и продолжить»).

После публикации старые картинки v2.9 удалить на
`https://steamcommunity.com/sharedfiles/managepreviews/?id=3840311723` (крестик при наведении, удаляется сразу).

## Название и описание (англ.)

**Title:** `Sauna Stove`

**Description** (вставить на странице Steam после публикации):

```
Every Rust life starts naked. Might as well warm up properly.

An old kitchen cooker turned into a sauna stove: clad in aspen slats nailed
to the rusty shell, burners buried under split basalt, a forged grate over a
firebox full of glowing rocks, all sitting on a rubble plinth and a wet pallet.

Part of the Sauna set.
```

Коротко, без просьб о лайках и без текста на самой текстуре (правила сета и
советы Facepunch). Если спросят в комментариях про конфорки: «The coil
cutout only hides the cooker coils under the rocks - there's nothing to see
through.»

## Иконка

Иконку (thumbnail) **генерирует сам редактор** при нажатии Publish, и Facepunch
просит её не заменять: «keep your thumbnail as the default generated thumbnail»
([Creating Skins](https://wiki.facepunch.com/rust/Creating_Skins)). Поэтому
своей иконки не делаем. Перед Publish в редакторе выставить:

- все 5 карт v2.9, **Alpha Cutoff 1.00** (проверено в игре; 0.5 тоже работает):

| Слот | Файл |
|---|---|
| Diffuse | `../export/ElectricFurnace_v2.9_diffuse_cutout.png`, **Alpha Cutoff 1.00** |
| Normal | `../export/ElectricFurnace_v2.9_normal.png` |
| Metal/Gloss | `../export/ElectricFurnace_v2.9_metalgloss.png` |
| Occlusion | `../export/ElectricFurnace_v2.9_occlusion.png` |
| Emission | `../export/ElectricFurnace_v2.9_emission.png` |

- остальные ползунки по умолчанию.

Картинка для **Steam-коллекции «Sauna»** — общая, `../../workshop/collection.jpg` (см. `../../workshop_collection.md`), не для предмета.

## Картинки для страницы (Steam → Add/edit images)

Рендеры Blender (`workshop_renders.py`, Cycles, 1920×1080; JPG для загрузки):

| Файл | Что |
|---|---|
| `studio.jpg` | **главный кадр**: тёмная студия, тёплый ключевой и холодный контровой свет (27.10.2026) |
| `hero.jpg` | днём, 3/4 спереди |
| `night.jpg` | ночью: свет из топки и жалюзи |
| `firebox.jpg` | крупно топка: куча камней за кованой решёткой |
| `burners.jpg` | крупно конфорки: кучи базальта |
| `back.jpg` | сзади: обшивка, короб-«дверца» с обвязкой |

![studio](studio.jpg)

Плюс **скриншоты из редактора Workshop** — v2.9, сняты пользователем 15.11.2026 на весь экран (F12), исходники в `../screenshots/editor_16x9/`; для загрузки — `ingame/` (1920×1080, панель редактора обрезана). Порядок на странице: игровой `front_night` **первым**, затем рендер `studio`, затем остальные скриншоты в этом порядке, затем рендеры.

| Файл | Что |
|---|---|
| `ingame/front_night.jpg` | анфас в полной темноте: светится только топка — первый кадр страницы |
| `ingame/three_quarter_night.jpg` | 3/4 слева в темноте |
| `ingame/three_quarter_day.jpg` | 3/4 слева днём: рейки, плита с камнями, лист |
| `ingame/top_day.jpg` | сверху днём |
| `ingame/top_night.jpg` | сверху ночью с фонарём: камни на конфорках, свет в щелях |

Кадры сняты 15.11 с Alpha Cutoff 1.00 (`top_night` — утром, с 0.00; на виде плиты разницы нет). Тонкая серая дуга
поверх камней на конфорках — внешний виток спирали, оставленный в v2.2 намеренно (под ним щель внутрь корпуса).
Запасные (не загружать): `ingame/front_night_flashlight.jpg`, `ingame/top_night_dark.jpg`.

## Вырез альфой — допустимо ли

- **Технически да:** у Diffuse в редакторе есть Alpha Cutoff, PNG с альфой — штатный
  путь; в игре проверено (v2.1–v2.6).
- **Официальных правил про прозрачность нет:** ни [Getting Your Skin Accepted](https://wiki.facepunch.com/rust/Getting_Skin_Accepted),
  ни [Workshop FAQ](https://wiki.facepunch.com/rust/Workshop_FAQ), ни [Creating Skins](https://wiki.facepunch.com/rust/Creating_Skins)
  её не упоминают.
- **Принятые скины с вырезами существуют** — например, двери с прорезями (сообщество
  зовёт их «P2W», потому что сквозь них видно), см. гайд
  [ALL Rust P2W Door Skins (cutouts)](https://steamcommunity.com/sharedfiles/filedetails/?id=3576575985).
- **Отказы тоже были:** по комментарию автора, скин гаражной двери не приняли именно из-за
  прозрачности (единичный рассказ, не официальное заявление).
- **Вывод:** риск — в вырезах, через которые что-то видно (обзор, преимущество в игре). У нас
  вырез только убирает спирали конфорок, под ними цельная чаша (проверено лучами в Blender:
  насквозь ничего не видно), на хитбокс текстура не влияет. Риск низкий — **публикуем с вырезом**.
  Запасной вариант на случай замечаний: `ElectricFurnace_v2.9_diffuse.png` и Alpha Cutoff 0
  (спирали видны, но покрыты камнями нормалью).

## Чек-лист публикации

1. Редактор → Electric Furnace → загрузить 5 карт v2.9 (таблица выше), Alpha Cutoff 1.00.
2. Вкладка **ITEM**: имя `Sauna Stove` (без имени кнопка Publish неактивна).
3. Вкладка **PUBLISH** → Publish. Откроется страница в браузере (войти в Steam).
4. На странице: вставить описание, добавить картинки (5 рендеров + 2–4 скриншота из игры).
5. Принять **Workshop Contributor Agreement** (без него принятый скин не станет публичным).
6. Добавить в коллекцию **Sauna** (`../../workshop_collection.md`, картинка `../../workshop/collection.jpg`).
7. Ссылку на страницу записать в `../README.md` (статус) и `../HANDOFF.md`.

> По плану сета публиковать **одновременно, как коллекцию** (см. `../../README.md`):
> можно опубликовать каменку сейчас и держать страницу, но голосование и внимание
> лучше собирать, когда в коллекции будут 3–5 предметов.

## Как пересобрать картинки

```bash
"C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/electric-furnace/workshop_renders.py -- --samples 128
```

Кадры: `studio hero night burners firebox back` (можно перечислить нужные). Все шесть — ~5 мин на RTX 3060 Ti (дольше всех firebox).
JPG — пересохранить из PNG (quality 92).
