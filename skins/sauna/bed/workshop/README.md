# Sauna Bench — публикация в Workshop

> Подготовлено 20.10.2026 для v1.2. Публикует пользователь сам из игрового редактора.

## Название и описание (англ.)

**Title:** `Sauna Bench`

**Description** (вставить на странице Steam после публикации):

```
Every Rust life starts naked. Might as well warm up properly.

A roadside bed frame dragged into a scrap-built sauna: the mattress went
out, a deck of aspen slats from an old pallet went on, two boards from a
paint-chipped door became the headrest. Polished by years of lying in the
steam, smoked at the end facing the stove, with a rolled linen towel
waiting under your head.

Part of the Sauna set.
```

Коротко, без просьб о лайках и без текста на самой текстуре (правила сета и советы Facepunch).

## Иконка

Иконку **генерирует сам редактор** при Publish, Facepunch просит её не заменять
([Creating Skins](https://wiki.facepunch.com/rust/Creating_Skins)). Перед Publish выставить:

| Слот | Файл / значение |
|---|---|
| Diffuse | `../export/Bed_v1.2_diffuse.png`, **Alpha Cutoff 0.50** (по умолчанию) |
| Normal | `../export/Bed_v1.2_normal.png` |
| Specular/Gloss | `../export/Bed_v1.2_specgloss.png` |
| Occlusion | `../export/Bed_v1.2_occlusion.png` |
| Emission | не трогать |

Остальные ползунки — по умолчанию.

## Картинки для страницы (Steam → Add/edit images)

Рендеры Blender (`../workshop_renders.py`, Cycles, 1920×1080; JPG для загрузки):

| Файл | Что |
|---|---|
| `hero.jpg` | днём, 3/4 от изножья — главный кадр |
| `towel.jpg` | крупно: полотенце-рулон, спинка из дверных досок |
| `side.jpg` | сбоку: настил, фартук, лаги на швеллере |
| `foot.jpg` | крупно изножье: гвозди, листья, след шайки, подкопчённый край |
| `dusk.jpg` | сумерки, тёплый свет от каменки со стороны ног |

![hero](hero.jpg)

Плюс **скриншоты из игры**: `../screenshots/v1.2_34_day.webp`, `v1.2_34_dusk.webp`,
`v1.2_foot_day.webp` (Steam принимает JPG/PNG — пересохранить). Хорошо бы снять кадр в «живой»
сцене: полок в доме рядом с каменкой Sauna Stove, ночью.

## Вырез альфой

Альфой убрано только **одеяло** (и отворот простыни): под ним цельный верх матраса — насквозь
ничего не видно, на хитбокс текстура не влияет. У оригинала одеяло уже резалось альфой (рваные
края), Alpha Cutoff 0.50 — значение редактора по умолчанию. Риск отказа из-за прозрачности —
низкий (см. разбор в [../../electric-furnace/workshop/README.md](../../electric-furnace/workshop/README.md)).

## Чек-лист публикации

1. Редактор → Bed → загрузить 4 карты v1.2 (Alpha Cutoff 0.50).
2. Вкладка **ITEM**: имя `Sauna Bench`.
3. Вкладка **PUBLISH** → Publish → страница в браузере.
4. Описание, картинки (5 рендеров + 2–3 скриншота из игры).
5. **Workshop Contributor Agreement** (если ещё не принят).
6. Добавить в коллекцию **Sauna**.
7. Ссылку записать в `../README.md` и в таблицу сета `../../README.md`.

## Как пересобрать картинки

```bash
"C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/bed/workshop_renders.py -- --samples 128
```

Кадры: `hero towel side foot dusk` (можно перечислить нужные), все пять ~1 мин на RTX 3060 Ti.
JPG — пересохранить из PNG (quality 92).
