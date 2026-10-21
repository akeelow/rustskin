# Sauna Chair — публикация в Workshop

> Подготовлено 21.10.2026 для v1.4. Публикует пользователь сам из игрового редактора.

## Название и описание (англ.)

**Title:** `Sauna Chair` (правило сета: без скобок и оригинальных имён, `../../README.md`, «Workshop: оформление»).

**Description** (вставить на странице Steam после публикации):

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

Коротко, без просьб о лайках и без текста на самой текстуре (правила сета и советы Facepunch).

## Иконка

Иконку **генерирует сам редактор** при Publish, Facepunch просит её не заменять
([Creating Skins](https://wiki.facepunch.com/rust/Creating_Skins)). Перед Publish выставить:

| Слот | Файл / значение |
|---|---|
| Diffuse | `../export/Chair_v1.4_diffuse.png`, Color 255/255/255, Alpha Cutoff 0.00 (по умолчанию) |
| Normal | `../export/Chair_v1.4_normal.png`, Normal Scale 1.00 |
| Specular/Gloss | `../export/Chair_v1.4_specgloss.png`, Spec Color 255, Glossiness 1.00 |
| Occlusion | `../export/Chair_v1.4_occlusion.png`, Occlusion Scale 1.00 |
| Emission | не трогать |

Остальные ползунки — по умолчанию.

## Картинки для страницы (Steam → Add/edit images)

Рендеры Blender (`../workshop_renders.py`, Cycles, 1920×1080; JPG для загрузки):

| Файл | Что |
|---|---|
| `hero.jpg` | днём, 3/4 спереди — главный кадр |
| `towel.jpg` | крупно: полотенце с полосой и берёзовым листом, вагонка, стыки крыла с гвоздями |
| `seat.jpg` | сверху на сиденье: дубовый лист, мокрое пятно, трещина со скобой, гвозди, торец подлокотника |
| `back.jpg` | сзади: вагонка, две планки, полотенце, швеллер |
| `dusk.jpg` | сумерки, тёплый свет от каменки |
| `set.jpg` | рядом с полоком Sauna Bench — «из одного дома» |

![hero](hero.jpg)

Плюс **скриншоты из редактора Workshop** — сняты пользователем 21.10.2026 на весь экран (F12), исходники в `../screenshots/editor_16x9/`; для загрузки — `ingame/` (1920×1080, панель редактора обрезана). Порядок на странице: рендер `hero`, затем скриншоты в этом порядке, затем остальные рендеры.

| Файл | Что |
|---|---|
| `ingame/three_quarter_day.jpg` | 3/4 днём |
| `ingame/side_day.jpg` | сбоку днём |
| `ingame/back_day.jpg` | сзади днём |

## Без альфы

Ничего не вырезано: Alpha Cutoff 0.00 (по умолчанию), силуэт и хитбокс — оригинальные. Спинку
сознательно не прятали (табуретка через альфу оставила бы невидимую твёрдую спинку — риск отказа).

## Чек-лист публикации

1. Редактор → Chair → загрузить 4 карты v1.4 (Alpha Cutoff 0.00).
2. Вкладка **ITEM**: имя `Sauna Chair`.
3. Вкладка **PUBLISH** → Publish → страница в браузере.
4. Описание, картинки (6 рендеров + 2–3 скриншота из игры).
5. **Workshop Contributor Agreement** (если ещё не принят).
6. Добавить в коллекцию **Sauna**.
7. Ссылку записать в `../README.md` и в таблицу сета `../../README.md`.

## Как пересобрать картинки

```bash
"C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/chair/workshop_renders.py -- --samples 128
```

Кадры: `hero towel seat back dusk set` (можно перечислить нужные), все шесть ~1.5 мин на RTX 3060 Ti.
JPG — пересохранить из PNG (quality 92).
