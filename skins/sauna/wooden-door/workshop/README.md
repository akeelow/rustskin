# Sauna Door — публикация в Workshop

> Подготовлено 16.11.2026 для **v1.2** (правки по кадрам v1 и v1.1 из редактора). v1.2 проверена в редакторе днём и ночью; замки редактор не ставит, место сверено наложением
> ([../README.md](../README.md), «Сравнение с оригиналом»). Публикует пользователь сам.

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
| Diffuse | `../export/Door_v1.2_diffuse.png`, Color 255/255/255, Alpha Cutoff 0.00 |
| Normal | `../export/Door_v1.2_normal.png`, Normal Scale 1.00 |
| Specular/Gloss | `../export/Door_v1.2_specgloss.png`, Spec Color 255, Glossiness 1.00 |
| Occlusion | `../export/Door_v1.2_occlusion.png`, Occlusion Scale 0.70 |
| Emission | `../export/Door_v1.2_emission.png`, **Emission Color 255/255/255** |

На кадре v1 Emission Color уже стоял 255 — окно светилось.

## Картинки для страницы

Рендеры Blender (`../workshop_renders.py`, Cycles, 1920×1080, карты v1.2; JPG для загрузки). Это рендеры,
не игровые кадры — в подписи на странице так и назвать.

| Файл | Что |
|---|---|
| `studio.jpg` | **главный рендер**: тёмная студия, тёплый ключевой и холодный контровой свет, окно светится |
| `hero.jpg` | днём, 3/4 спереди |
| `night.jpg` | ночью спереди: окно и полотенце |
| `back.jpg` | днём сзади: раскосы, окно, петли |
| `back_night.jpg` | ночью сзади |
| `window.jpg` | крупно: полотенце и окно |
| `set.jpg` | в стене раздевалки между шкафчиком Sauna Changing Locker и каменкой Sauna Stove, сумерки |

![studio](studio.jpg)

![set](set.jpg)

Игровые кадры снимает пользователь в редакторе на весь экран (F12), как для семи опубликованных:
исходники в `../screenshots/editor_16x9/`, обрезанные 1920×1080 — в `ingame/`. Нужны четыре: перед ночью,
перед днём, зад днём, зад ночью. Кадры v1.2 в `../screenshots/v1.2_editor_*` сняты окном, не 16:9 —
для страницы их стоит переснять.

Порядок на странице: игровой «перед ночью» **первым**, затем `studio`, затем остальные игровые, затем
`hero`, `back`, `window`, `night`, `back_night`, `set`.

## После публикации

- Добавить предмет в коллекцию [Sauna](https://steamcommunity.com/sharedfiles/filedetails/?id=3840348906).
- Строку сета в `../../README.md` правит основная сессия (эта папка её не трогает).
