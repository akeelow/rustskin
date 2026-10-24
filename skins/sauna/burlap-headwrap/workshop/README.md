# Sauna Towel Wrap — публикация в Workshop

> Подготовлено 21.10.2026 для **v1** (проверен в игре 19.10.2026). Публикует пользователь сам из игрового редактора.

## Название и описание (англ.)

**Title:** `Sauna Towel Wrap` (правило сета: без скобок и оригинальных имён, `../../README.md`, «Workshop: оформление»).

**Description** (вставить на странице Steam после публикации):

```
Every Rust life starts naked. Might as well warm up properly.

An old linen sauna towel with two faded brick stripes, wound round the
head and neck and tied with twine, to keep the ears warm between the
steam room and the snow. Washed grey, yellowed where you breathe, and
frayed at every edge.

Part of the Sauna set.
```

Коротко, без просьб о лайках и без текста на самой текстуре (правила сета и советы Facepunch).

## Иконка и как загрузить

Иконку **генерирует сам редактор** при Publish, Facepunch просит её не заменять
([Creating Skins](https://wiki.facepunch.com/rust/Creating_Skins)). Перед Publish выставить:

| Слот | Файл / значение |
|---|---|
| Diffuse | `../export/BurlapHeadwrap_v1_diffuse.png`, **Alpha Cutoff 0.79** (по умолчанию) |
| Normal | `../export/BurlapHeadwrap_v1_normal.png`, Normal Scale 1.00 |
| Specular/Gloss | `../export/BurlapHeadwrap_v1_specgloss.png` (влажный блеск на затылке и складках; или оставить пустым 51 / 0.28) |
| Occlusion | **оригинальный** (не заменять), Occlusion Scale 1.00 |
| Emission | нет |
| Fuzz Mask | пусто (белый), **Fuzz 0.58** (по умолчанию 0.23 — махра без ворса плоская), Fuzz Scatter 0.53 |

Остальные ползунки — по умолчанию. Чаще всего забывают **Fuzz 0.58** и сбрасывают Alpha Cutoff
(должен остаться **0.79**, иначе вокруг рваных краёв серые лоскуты).

## Картинки для страницы (Steam → Add/edit images)

Рендеры Blender (`../workshop_renders.py`, Cycles, 1920×1080; JPG для загрузки). Тела нет (правило
сета — без обнажёнки): полотенце на деревянной голове-болванке.

| Файл | Что |
|---|---|
| `hero.jpg` | днём, 3/4 спереди — главный кадр |
| `front.jpg` | анфас: прорезь для глаз, полоски, бечёвка |
| `side.jpg` | сбоку: намотка, рваная кромка шарфа |
| `set.jpg` | вместе с халатом Sauna Robe у каменки Sauna Stove, вечер |

![hero](hero.jpg)

Плюс **скриншоты из редактора Workshop** — сняты пользователем 21.10.2026 на весь экран (F12), исходники в `../screenshots/editor_16x9/`; для загрузки — `ingame/` (1920×1080, панель редактора обрезана). Порядок на странице: рендер `hero`, затем скриншоты в этом порядке, затем остальные рендеры.

| Файл | Что |
|---|---|
| `ingame/three_quarter_day.jpg` | 3/4 днём |
| `ingame/front_day.jpg` | анфас днём |
| `ingame/three_quarter_night.jpg` | 3/4 ночью |

## Альфа

Альфа оптимизирована по ревью: устранена точечная перфорация «дырявой марли» на лобной ткани капюшона, сквозь которую ранее просвечивали пиксели лица персонажа. Прорезь для глаз сохранена открытой с естественной бахромой нитей, рваная кромка шарфа и прореха на виске сохранены как у оригинала; Alpha Cutoff **0.79**.

## Чек-лист публикации

1. Редактор → Burlap Headwrap → загрузить Diffuse и Normal v1 (Occlusion не трогать).
2. **Fuzz 0.58**, Alpha Cutoff 0.79.
3. Вкладка **ITEM**: имя `Sauna Towel Wrap`.
4. Вкладка **PUBLISH** → Publish → страница в браузере.
5. Описание, картинки (4 рендера + скриншоты из игры).
6. **Workshop Contributor Agreement** (если ещё не принят).
7. Добавить в коллекцию **Sauna** (`../../workshop_collection.md`).
8. Ссылку записать в `../README.md` и в таблицу сета `../../README.md`.

## Как пересобрать картинки

```bash
"C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/burlap-headwrap/workshop_renders.py -- --samples 128
```

Кадры: `hero front side set` (можно перечислить нужные). Общие настройки сцены (материалы, болванка,
пол, стена, свет) — `../../showcase.py`. В Blender у тюрбана включено отсечение задних граней, как в
игре (модель Rust намотана по часовой стрелке — лицевая сторона в Blender считается задней).
JPG — пересохранить из PNG (quality 92).
