# Sauna Door — публикация в Workshop

> Подготовлено 16.11.2026 для **v1**. **В игре не проверено** — сначала посмотреть в редакторе
> (список в [../README.md](../README.md), «Что не проверено без игры»). Публикует пользователь сам.

## Название и описание (англ.)

**Title:** `Sauna Door` (правило сета: префикс `Sauna`, без оригинального имени предмета).

**Description** (вставить на странице Steam после публикации):

```
Every Rust life starts naked. Might as well warm up properly.

The door to a scrap-built steam room. Pale aspen boards nailed onto an
old steel sheet, rust running from every nail, the foot of the door dark
from years of water. A washed-out towel hangs on a bent nail. Behind the
fogged little window the stove is hot - at night it is the only light
you need to find your way back in.

Inside, the same boards are steamed brown and sooty under the top rail,
and one hinge is held on with wire.

Part of the Sauna set:
https://steamcommunity.com/sharedfiles/filedetails/?id=3840348906
```

Без просьб о лайках и без текста на текстуре. Строку «This skin glows in the dark» Steam добавляет сам.

## Иконка и как загрузить

Иконку генерирует сам редактор при Publish, Facepunch просит её не заменять. Перед Publish выставить:

| Слот | Файл / значение |
|---|---|
| Diffuse | `../export/Door_v1_diffuse.png`, **Color 255/255/255**, Alpha Cutoff 0.00 |
| Normal | `../export/Door_v1_normal.png`, Normal Scale 1.00 |
| Specular/Gloss | `../export/Door_v1_specgloss.png`, ползунки по умолчанию |
| Occlusion | `../export/Door_v1_occlusion.png`, Occlusion Scale по умолчанию |
| Emission | `../export/Door_v1_emission.png`, **Emission Color 255/255/255** |

Чаще всего забывают **Emission Color 255**: если по умолчанию там 0, окно не светится.

## Картинки для страницы

Студийных рендеров для двери ещё нет — их стоит делать после проверки в игре, чтобы не переснимать.
Порядок, как у остальных семи: игровой ночной кадр первым.

| # | Кадр | Кто снимает |
|---|---|---|
| 1 | перед ночью без фонаря: светится окно, видно полотенце | пользователь, редактор |
| 2 | перед днём, анфас | пользователь, редактор |
| 3 | зад днём: раскосы, окно, петли | пользователь, редактор |
| 4 | зад ночью | пользователь, редактор |
| 5 | крупно: окно и полотенце | пользователь, редактор |
| 6 | дверь в стене деревянной базы рядом с каменкой и шкафчиком, сумерки | пользователь, игра |
| 7–8 | студийные рендеры Blender (3/4 и крупный план), подписаны как рендеры | агент, после проверки v1 |

Кадры редактора — на весь экран (F12), как для семи опубликованных: исходники в
`../screenshots/editor_16x9/`, обрезанные 1920×1080 — в `ingame/`.

## После публикации

- Добавить предмет в коллекцию [Sauna](https://steamcommunity.com/sharedfiles/filedetails/?id=3840348906).
- Строку сета в `../../README.md` правит основная сессия (эта папка её не трогает).
