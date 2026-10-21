# ТЗ для ИИ-агента: Workshop-пакет сета Sauna (тюрбан, халат, шкафчик) + коллекция и план публикации

> Составлено 20.10.2026. Репозиторий: `C:/Users/akeel/OneDrive/rustskin`. Общайся с пользователем **по-русски**.
> Прочитай сначала: [README.md](README.md) (сет: идея, правила, палитра, сроки, «Workshop: оформление»),
> **образцы готовых пакетов:** [electric-furnace/workshop/README.md](electric-furnace/workshop/README.md) +
> [electric-furnace/workshop_renders.py](electric-furnace/workshop_renders.py) и
> [bed/workshop/README.md](bed/workshop/README.md) + [bed/workshop_renders.py](bed/workshop_renders.py),
> просмотрщик [../../tools/blender/README.md](../../tools/blender/README.md).

## 1. Контекст

Сет **Sauna** (скины Rust для Steam Workshop) публикуется **одной коллекцией до конца ноября 2026**
(Snow Jacket принимают только с декабря по февраль). Готовы и проверены в игре:

| # | Предмет (модель) | Workshop-имя | Папка | Финальные карты | Пакет |
|---|---|---|---|---|---|
| 1 | Electric Furnace | Sauna Stove | `electric-furnace/` | `export/ElectricFurnace_v2_*` | ✅ есть |
| 2 | Burlap Headwrap | Sauna Towel Wrap | `burlap-headwrap/` | `export/BurlapHeadwrap_v1_*` (diffuse, normal) | ❌ сделать |
| 3 | Snow Jacket | Sauna Robe | `snow-jacket/` | `export/SnowJacket_v2_*` (v2.1: diffuse, normal, specgloss, fuzz) | ❌ сделать |
| 4 | Locker | Sauna Changing Locker | `locker/` | **v5** — `export/Locker_v5_*` (diffuse, normal, specgloss, emission) | ❌ сделать |
| 6 | Bed | Sauna Bench | `bed/` | `export/Bed_v1.2_*` | ✅ есть |
| 7 | Chair | Sauna Chair | `chair/` | `export/Chair_v1.4_*` | ✅ есть |
| 8 | Wood Storage Box | Sauna Stone Box | `wood-storage-box/` | `export/Box_v1.3_*` (+ emission, Alpha Cutoff 0.5) | ✅ есть |

Пончо (№5) пропущено. Кресло (Chair, №7) и ящик (Wood Storage Box, №8) готовы 21.10.2026 вместе с пакетами — их не меняй.

## 2. Что сделать (для каждого из трёх предметов)

Папка `<предмет>/workshop/` + `<предмет>/workshop_renders.py`, по образцу каменки и полока:

1. **Таблица «как загрузить»** — какой файл в какой слот **и значения ползунков** (их чаще всего путают:
   у тюрбана Alpha Cutoff 0.79 и Fuzz 0.58; у халата Fuzz 0.5, Spec Color 255, Alpha Cutoff 0; у шкафчика
   Alpha Cutoff 0.5 и **Emission Color 255** — по умолчанию 0, иначе ничего не светится). Значения бери
   из `README.md` предмета (разделы «Как загрузить», «Заметки») и сверь с последней проверенной версией.
2. **Рендеры для страницы Steam** (Blender, Cycles, 1920×1080, + JPG): главный кадр, 2–4 крупных плана,
   ночь для шкафчика. Одежду (тюрбан, халат) — на манекене из `tools/blender/viewer.py` (функция
   `mannequin()`) или на простом бюсте; без обнажёнки (правило сета). Посмотри рендеры сам, прежде чем отдавать.
3. **Название** — по правилу из `README.md` сета («Workshop: оформление»): **без скобок и без оригинальных
   имён предметов**, только `Sauna …` (`Sauna Towel Wrap`, `Sauna Robe`, `Sauna Changing Locker`).
   **Описание на английском** — коротко, история без просьб о лайках, последняя строка
   «Part of the Sauna set.», без текста на текстурах. Стиль — как у каменки и полока.
4. **Список скриншотов из игры**, которые лучше всего показывают предмет (из `screenshots/`), и какие
   кадры пользователю ещё снять.
5. Вырез альфой, если есть: 3–5 строк, почему насквозь ничего не видно (риск Facepunch по прозрачности):
   у тюрбана — рваные края оригинала, у шкафчика — открытые ниши.

## 3. Шкафчик: публикуем v5

**Решение пользователя 20.10.2026: v5.** Средняя дверца глухая (на неё в игре вешается кодовый или
навесной замок — проверено: замок встаёт на железную площадку v5, ~100 см), с окном, картой,
приборами; крайние ниши открыты, с подсветкой. Загрузка: Diffuse `Locker_v5_diffuse.png` (Alpha
Cutoff 0.5), Normal, Specular/Gloss, Emission `Locker_v5_emission.png` (**Emission Color
255/255/255**), Occlusion — оригинальный. v4.1 в пакет не включать.
Рендеры: днём 3/4, ночью (свет ниш и окна), крупно средняя дверца, и **кадр с замком** — скриншот
пользователя из игры (попроси снять шкафчик со скином v5 и кодовым замком, если будет возможность;
пример позиции — `locker/screenshots/codelock_ingame_default.webp`).

## 4. Коллекция и план публикации

В `README.md` сета, раздел «Workshop: оформление» (или файл `workshop_collection.md` рядом):
- картинка коллекции 1024×1024 (все 7 предметов вместе: каменка, полок, кресло, ящик с углями, шкафчик; на манекене тюрбан
  и халат; вечер, тёплый свет каменки) и описание коллекции на английском;
- **пошаговый чек-лист публикации** всех 7 предметов из редактора Rust: имя на вкладке ITEM →
  загрузить карты, выставить ползунки → PUBLISH → на странице Steam описание и картинки → Contributor
  Agreement → создать коллекцию «Sauna» и добавить все семь; иконку не заменять;
- порядок и даты: всё в один день, до конца ноября; Snow Jacket — сезонный.

## 5. Правила

- Публикует **только пользователь**; ты не нажимаешь Publish и не заходишь в его Steam.
- Финальные карты не меняй (они проверены в игре). Нашёл ошибку — скажи пользователю.
- Коммить и пушь в `origin main` после каждой части, **только свои файлы** (папки `workshop/`,
  `workshop_renders.py`, README предметов, `README.md` сета). `chair/` и `wood-storage-box/` не меняй.
- Blender: `"C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P ...`; numpy/Pillow — `.venv`.

## 6. Готово, когда

У тюрбана, халата и шкафчика есть `workshop/README.md` с таблицей загрузки, описанием, рендерами и
списком скриншотов; есть картинка и описание коллекции и чек-лист публикации; в таблице сета для всех
семи указано «пакет готов»; всё запушено.
