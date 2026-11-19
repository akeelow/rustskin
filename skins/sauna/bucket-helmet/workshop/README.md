# Sauna Bucket — публикация в Workshop

> Подготовлено 18.11.2026, обновлено 19.11.2026 для **v2** (полотенце, веник, открытое окно, медь).
> [../README.md](../README.md), «Что проверить в игре»), потом публиковать. Публикует пользователь сам из
> игрового редактора.

## Название и описание (англ.)

**Title:** `Sauna Bucket` (правило сета: без скобок и оригинальных имён, `../../README.md`, «Workshop: оформление»).

**Description** (вставить на странице Steam после публикации):

```
Every Rust life starts naked. Might as well warm up properly.

An aspen wash tub from the sauna, turned upside down and jammed on the
head. An old striped sauna towel wound round the top and knotted at the
side, a sprig of the birch whisk tucked under it. The eye slot was sawn
out by hand - no mesh, just a face peeking out of the tub. The rope
handle was cut off to make it fit, the knots are still in the ears.
Inside, the old blue bucket nailed in as a lining: the wood takes the
hit, the tin stops it. Copper at the rim, a wet ring on the crown.

Part of the Sauna set.
```

Коротко, без просьб о лайках и без текста на самой текстуре (правила сета и советы Facepunch).
Ссылку на коллекцию (как у остальных семи) добавить в последнюю строку:
`Part of the [url=https://steamcommunity.com/sharedfiles/filedetails/?id=3840348906]Sauna set[/url].`

## Иконка и как загрузить

Иконку **генерирует сам редактор** при Publish, Facepunch просит её не заменять
([Creating Skins](https://wiki.facepunch.com/rust/Creating_Skins)). Перед Publish выставить:

| Слот | Файл / значение |
|---|---|
| Diffuse | `../export/SaunaBucket_v2_diffuse.png`, Color 255/255/255, **Alpha Cutoff 0.50** (вырезает сетку — окно открыто) |
| Normal | `../export/SaunaBucket_v2_normal.png`, Normal Scale 1.00 |
| Specular/Gloss | `../export/SaunaBucket_v2_specgloss.png`, Spec Color 255/255/255, **Glossiness 1.00** (по умолчанию 0.92) |
| Occlusion | `../export/SaunaBucket_v2_occlusion.png` (1024; если редактор покажет «256» — так и оставить), Occlusion Scale 1.00 |
| Emission | не трогать (None, Emission Color 0/0/0 — свечения нет) |
| Fuzz Mask | `../export/SaunaBucket_v2_fuzzmask.png`, Fuzz 1.00, Fuzz Scatter 0.50 (по умолчанию) |
| Dirt | по умолчанию (Dirt Amount 0.40) |

Чаще всего забывают Fuzz Mask: без неё по умолчанию белая маска и Fuzz 1.00 — бархатный отблеск по всему
ведру, обручи станут «пушистыми».

## Картинки для страницы (Steam → Add/edit images)

Главный кадр — **из игры** (правило проекта: рендеры Blender не выдаём за игровые кадры). Снять в редакторе
на весь экран (F12), панель свернуть зелёной стрелкой:

| # | Кадр | Что видно |
|---|---|---|
| 1 | `ingame/front_day` — анфас днём | лицо в выпиленном окне, полотенце, медный перепиленный обруч |
| 2 | `ingame/q34_day` — 3/4 справа | полотенце с узлом и концами, лист |
| 3 | `ingame/top_day` — сверху от третьего лица | днище: три доски, латка, мокрое кольцо, утор |
| 4 | `ingame/side_day` — 3/4 слева | веник под полотенцем, гнездо дроби, ушко |
| 5 | `ingame/night` — ночью у каменки Sauna Stove | ведро в тёплом свете, без своего свечения |
| 6 | `ingame/set` — с халатом Sauna Robe и полотенцем | сет на персонаже |

Рендеры Blender (если нужны для доп. картинок) — `../renders/v1_*` с подписью «render» в имени файла.
