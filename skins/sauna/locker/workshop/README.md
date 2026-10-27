# Sauna Changing Locker — публикация в Workshop

> Подготовлено 21.10.2026 для **v5** (решение пользователя 20.10.2026; v4.1 в пакет не входит), обновлено 27.10.2026 для
> **v5.2**: та же дверь и ниши, дерево ближе к бледной осине сета, низ потемнел от пара (файлы `Locker_v5.2_*`; v5.1 — `Locker_v5_*`).
> Публикует пользователь сам из игрового редактора.

## Название и описание (англ.)

**Title:** `Sauna Changing Locker` (правило сета: без скобок и оригинальных имён, `../../README.md`, «Workshop: оформление»).

**Description** (вставить на странице Steam после публикации):

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

Коротко, без просьб о лайках и без текста на самой текстуре (правила сета и советы Facepunch).
Строку «This skin glows in the dark» Steam добавляет сам.

## Иконка и как загрузить

Иконку **генерирует сам редактор** при Publish, Facepunch просит её не заменять
([Creating Skins](https://wiki.facepunch.com/rust/Creating_Skins)). Перед Publish выставить:

| Слот | Файл / значение |
|---|---|
| Diffuse | `../export/Locker_v5.2_diffuse.png`, **Alpha Cutoff 0.50** (по умолчанию 0.00 — без него ниши закрыты дверцами) |
| Normal | `../export/Locker_v5.2_normal.png`, Normal Scale 1.00 |
| Specular/Gloss | `../export/Locker_v5.2_specgloss.png`, Spec Color 255, Glossiness 1.00 |
| Occlusion | **оригинальный** (не заменять), Occlusion Scale 0.75 (по умолчанию) |
| Emission | `../export/Locker_v5.2_emission.png`, **Emission Color 255/255/255** (по умолчанию 0/0/0 — ничего не светится) |

Остальные ползунки — по умолчанию. Два значения, которые чаще всего забывают: **Alpha Cutoff 0.50**
и **Emission Color 255**.

## Картинки для страницы (Steam → Add/edit images)

Рендеры Blender (`../workshop_renders.py`, Cycles, 1920×1080; JPG для загрузки):

| Файл | Что |
|---|---|
| `studio.jpg` | **главный кадр**: тёмная студия, тёплый ключевой и холодный контровой свет (27.10.2026) |
| `hero.jpg` | днём, 3/4 спереди |
| `night.jpg` | ночью: подсветка ниш, полок и цоколя, окно и пролом в средней дверце |
| `front.jpg` | анфас днём: весь шкафчик |
| `door.jpg` | крупно средняя дверца: термометр, гигрометр, окно с сердечком, карта с тропой к X |
| `set.jpg` | в раздевалке у стены из вагонки, рядом кресло Sauna Chair, сумерки |

![studio](studio.jpg)

![night](night.jpg)

Плюс **скриншоты из редактора Workshop** — сняты пользователем 21.10.2026 на весь экран (F12), исходники в `../screenshots/editor_16x9/`; для загрузки — `ingame/` (1920×1080, панель редактора обрезана). Порядок на странице: рендер `studio`, затем скриншоты в этом порядке, затем остальные рендеры.

| Файл | Что |
|---|---|
| `ingame/front_night.jpg` | анфас ночью |
| `ingame/three_quarter_day.jpg` | 3/4 днём |
| `ingame/front_day.jpg` | анфас днём |
| `ingame/three_quarter_night.jpg` | 3/4 ночью |

## Вырез альфой

Крайние дверцы вырезаны альфой (Alpha Cutoff 0.50) — ниши открыты; средняя дверца непрозрачная.
- **Насквозь ничего не видно:** за нишами — глухая задняя стенка, боковины и полки корпуса
  (это геометрия шкафа, а не дверцы), так что сквозь шкафчик не смотрят ни внутрь базы, ни наружу.
- **Невидимая дверца остаётся твёрдой**, но она стоит в плоскости фасада: внутрь ниши всё равно
  ничего не положить и не залезть — игрок ничего не теряет и не выигрывает.
- **Лут скрыт как обычно:** содержимое шкафчика не рисуется в нишах, это только текстура.
- Официального запрета на прозрачность нет, принятые скины с вырезами есть, но были и отказы
  (разбор у каменки: `../../electric-furnace/workshop/README.md`). Риск — средний: вырез большой.
- **Запасной вариант без вырезов готов:** в папке `../export/Locker_v5.2_diffuse_solid.png` сгенерирована полностью глухая версия (все три дверцы глухие, Alpha Cutoff 0.00: слева и справа деревянные жалюзи из v1, по центру — дверь v5 с картой и приборами). Если куратор Facepunch потребует цельный фасад, её можно выставить за 1 минуту.

## Чек-лист публикации

1. Редактор → Locker → загрузить Diffuse, Normal, Specular/Gloss, Emission v5.2 (Occlusion не трогать).
2. **Alpha Cutoff 0.50**, **Emission Color 255/255/255**.
3. Вкладка **ITEM**: имя `Sauna Changing Locker`.
4. Вкладка **PUBLISH** → Publish → страница в браузере.
5. Описание, картинки (5 рендеров + скриншоты из редактора).
6. **Workshop Contributor Agreement** (если ещё не принят).
7. Добавить в коллекцию **Sauna** (`../../workshop_collection.md`).
8. Ссылку записать в `../README.md` и в таблицу сета `../../README.md`.

## Как пересобрать картинки

```bash
"C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/locker/workshop_renders.py -- --samples 128
```

Кадры: `hero night front door set` (можно перечислить нужные), все пять ~3 мин на RTX 3060 Ti.
Общие настройки сцены (материалы, пол, стена, свет) — `../../showcase.py`.
JPG — пересохранить из PNG (quality 92).
