# Sauna Changing Locker — публикация в Workshop

> Подготовлено 21.10.2026 для **v5** (решение пользователя 20.10.2026; v4.1 в пакет не входит), обновлено 27.10.2026 для
> **v5.2**: та же дверь и ниши, дерево ближе к бледной осине сета, низ потемнел от пара (файлы `Locker_v5.2_*`; v5.1 — `Locker_v5_*`).
> Публикует пользователь сам из игрового редактора.
> **v5.3 (12.11.2026, по [CRITIQUE_ART.md](../../CRITIQUE_ART.md)):** дерево ещё бледнее и менее насыщенное (как у полока и кресла), в открытых нишах на колышке висит полотенце сета с кирпичными полосами. Файлы `Locker_v5.4_*`. **В игре не проверено** — посмотреть в редакторе перед публикацией; если не понравится, прежняя версия v5.2 лежит рядом (`Locker_v5.2_*`).
> **v5.4 (15.11.2026):** v5.3 в игре ночью — ниши почти не светились: 24.10 свечение ослабили в ~2,6 раза (против засветки днём) и после этого в игре не смотрели. Вся карта свечения ×2 (между прежней и ослабленной); вентиляционные прорези под полотенцем убраны — светились точками из-под его края. Дерево и полотенце как в v5.3. Файлы `Locker_v5.4_*`.

## Обновление до v6.2 (22.11.2026)

Опубликованная страница (v5.4): https://steamcommunity.com/sharedfiles/filedetails/?id=3840340102. Обновлять **эту же
страницу**: в редакторе выбрать опубликованный Sauna Changing Locker из Workshop → загрузить карты → Publish (как
обновлялись полок и каменка, гайд §9.7). Редактор заново попросит описание и картинки и добавит 4 своих автокадра.

| Слот | Файл / значение |
|---|---|
| Diffuse | `../export/Locker_v6.2_diffuse.png`, **Alpha Cutoff 0.50** (по умолчанию 0.00 — тогда ниши закрыты дверцами) |
| Normal | `../export/Locker_v6.2_normal.png`, Normal Scale 1.00 |
| Specular/Gloss | `../export/Locker_v6.2_specgloss.png`, Spec Color 255, Glossiness 1.00 |
| Occlusion | `../export/Locker_v6.2_occlusion.png` (2048, **новый** — раньше оставался оригинальный), Occlusion Scale 0.75 |
| Emission | `../export/Locker_v6.2_emission.png` (2048), **Emission Color 255/255/255** (по умолчанию 0 — ничего не светится) |

**Новое описание** (вместо старого: карты с крестиком на дверце больше нет):

```
Every Rust life starts naked. Might as well warm up properly.

The changing room of a scrap-built sauna: an old three-door steel locker,
its side doors torn off for stove sheet metal and the shell clad in pale
linden boards. The two open niches have turned pegs with a striped linen
towel and a dried birch whisk, a lamp behind a wooden grille, slatted
shelves lit from beneath and a duckboard on the floor. The middle door stays
shut for your lock: a fogged window with a heart drawn by a finger, a
thermometer and a hygrometer, days counted in notches, and a scratched steel
plate next to a muddy boot print and a split board where someone tried to
kick it in.

Part of the Sauna set.
```

**Change notes** (англ.):

```
v6: remodelled from scratch. Every board, nail, knot, crack, rivet, louvre,
hinge stub, fold and leaf is now real modelled relief. Steel shell with
chipped enamel, a linen towel and a birch whisk in both niches, a wooden
lamp grille, duckboard floor and slatted shelves, a lock case and a bolt
inside the middle door, warmer niche light at night. All maps 2048.
```

**Картинки — папка `upload_v6/`** (кадры v6.2 из редактора в режиме предпросмотра, исходники — `../screenshots/v6.2/`;
обрезка — `../workshop_upload_v6.py`). Кнопки предпросмотра стоят прямо над шкафом, поэтому кадр режется по полосе
между ними и нижней панелью (y 292–984, 16:9) и увеличивается до 1920×1080: верх шкафа близко к краю, ножки чуть срезаны.
Добавлять **все по номерам**, первая — обложка:

| # | Файл | Что |
|---|---|---|
| 01 | `upload_v6/01_three_quarter_day.jpg` | 3/4 спереди-слева днём: стальная рама, бок из вагонки, ниши, дверца — обложка |
| 02 | `upload_v6/02_front_day.jpg` | анфас днём: обе ниши с полотенцем и веником, дверца с приборами, окном и следами |
| 03 | `upload_v6/03_three_quarter_night.jpg` | ночью без фонаря: тёплые ниши, плафон, сердечко на стекле |
| 04 | `upload_v6/04_drawer_and_shelves.jpg` | низ крупно: ящик с филёнкой, полки, решётка-трап, жалюзи цоколя |
| 05 | `upload_v6/05_back_day.jpg` | сзади: стальная спина с рёбрами и жалюзи, бок из вагонки |

Кадр `../screenshots/v6.2/01_*` не вошёл — почти повтор 03.

**Опубликовано 22.11.2026** (обновление той же страницы, v6.2). Старые картинки v5.4 — 13 штук (рендеры и кадры 15.11) —
удалены 22.11 на managepreviews; на странице 9 картинок v6.2: первым — наш `01_three_quarter_day` (переставлен 22.11), затем 4 автокадра редактора и остальные наши.

**После Publish:** удалить все старые картинки v5.4 (рендеры `studio`, `hero`, `night`, `front`, `door`, `set`, кадры
`ingame/*` и автокадры редактора v5.4) на `https://steamcommunity.com/sharedfiles/managepreviews/?id=3840340102`
(крестик при наведении, удаляется сразу). Порядок — перетаскиванием на той же странице («Сохранить и продолжить»).
Описание и change notes — на странице предмета (редактировать описание; заметки — «Добавить заметку об изменениях»).

## Название и описание (англ.) — v5.4, прежнее

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
| Diffuse | `../export/Locker_v5.4_diffuse.png`, **Alpha Cutoff 0.50** (по умолчанию 0.00 — без него ниши закрыты дверцами) |
| Normal | `../export/Locker_v5.4_normal.png`, Normal Scale 1.00 |
| Specular/Gloss | `../export/Locker_v5.4_specgloss.png`, Spec Color 255, Glossiness 1.00 |
| Occlusion | **оригинальный** (не заменять), Occlusion Scale 0.75 (по умолчанию) |
| Emission | `../export/Locker_v5.4_emission.png`, **Emission Color 255/255/255** (по умолчанию 0/0/0 — ничего не светится) |

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

Плюс **скриншоты из редактора Workshop** — v5.4, сняты пользователем 15.11.2026 на весь экран (F12), исходники в `../screenshots/editor_16x9/`; для загрузки — `ingame/` (1920×1080, панель редактора обрезана). Порядок на странице: игровой `front_night` **первым**, затем рендер `studio`, затем остальные скриншоты, затем рендеры.

| Файл | Что |
|---|---|
| `ingame/front_night.jpg` | анфас ночью без фонаря: тёплый свет в нишах, полотенца, сердечко на стекле |
| `ingame/front_day.jpg` | анфас днём: бледное дерево, полотенца в нишах |
| `ingame/three_quarter_day.jpg` | 3/4 днём |
| `ingame/three_quarter_night.jpg` | 3/4 ночью без фонаря |

**`Locker_v5.4_diffuse_solid.png` — не загружать.** Это запасной Diffuse без вырезов (крайние дверцы закрыты, ниш не
видно) на случай, если Facepunch попросит убрать прозрачность. Тогда его ставят в слот Diffuse вместо обычного,
Alpha Cutoff 0.00.

## Вырез альфой

Крайние дверцы вырезаны альфой (Alpha Cutoff 0.50) — ниши открыты; средняя дверца непрозрачная.
- **Насквозь ничего не видно:** за нишами — глухая задняя стенка, боковины и полки корпуса
  (это геометрия шкафа, а не дверцы), так что сквозь шкафчик не смотрят ни внутрь базы, ни наружу.
- **Невидимая дверца остаётся твёрдой**, но она стоит в плоскости фасада: внутрь ниши всё равно
  ничего не положить и не залезть — игрок ничего не теряет и не выигрывает.
- **Лут скрыт как обычно:** содержимое шкафчика не рисуется в нишах, это только текстура.
- Официального запрета на прозрачность нет, принятые скины с вырезами есть, но были и отказы
  (разбор у каменки: `../../electric-furnace/workshop/README.md`). Риск — средний: вырез большой.
- **Запасной вариант без вырезов готов:** в папке `../export/Locker_v5.4_diffuse_solid.png` сгенерирована полностью глухая версия (все три дверцы глухие, Alpha Cutoff 0.00: слева и справа деревянные жалюзи из v1, по центру — дверь v5 с картой и приборами). Если куратор Facepunch потребует цельный фасад, её можно выставить за 1 минуту.

## Чек-лист публикации

1. Редактор → Locker → загрузить Diffuse, Normal, Specular/Gloss, Emission v5.3 (Occlusion не трогать).
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
