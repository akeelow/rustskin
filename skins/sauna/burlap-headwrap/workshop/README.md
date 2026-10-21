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
| Specular/Gloss | пусто, как у оригинала (Spec Color 51, Glossiness 0.28 — по умолчанию) |
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

Плюс **скриншоты из редактора Workshop** на игроке (главное для одежды; пользователь снимает сам —
до публикации скин виден только в редакторе): `../screenshots/v1_front_day.webp`, `v1_side_day.webp`,
`v1_night.webp` — этого достаточно. Steam принимает JPG/PNG — `.webp` пересохранить.

## Альфа

Новых вырезов нет: альфа **та же, что у оригинала** (проверено попиксельно — совпадает): рваная
кромка шарфа, края прорези для глаз и пара прорех на капюшоне. Сквозь них видно лицо и голову
игрока, как у обычного Burlap Headwrap; Alpha Cutoff 0.79 — значение оригинала.

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
