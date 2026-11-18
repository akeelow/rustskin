# Sauna Bucket — публикация в Workshop

> Подготовлено 18.11.2026 для **v1**. **В игре не проверено** — сначала посмотреть в редакторе (список в
> [../README.md](../README.md), «Что проверить в игре»), потом публиковать. Публикует пользователь сам из
> игрового редактора.

## Название и описание (англ.)

**Title:** `Sauna Bucket` (правило сета: без скобок и оригинальных имён, `../../README.md`, «Workshop: оформление»).

**Description** (вставить на странице Steam после публикации):

```
Every Rust life starts naked. Might as well warm up properly.

An aspen wash tub from the sauna, turned upside down and jammed on the
head. Two forged hoops, the lower one sawn through where the eye slot
was cut. The rope handle was cut off to make it fit, the knots are
still in the ears. Inside, the old blue bucket nailed in as a lining -
the wood takes the hit, the tin stops it. A birch leaf stuck to the
side and a wet ring on the crown from years on the bathhouse floor.

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
| Diffuse | `../export/SaunaBucket_v1_diffuse.png`, Color 255/255/255, **Alpha Cutoff 0.00** (альфы нет) |
| Normal | `../export/SaunaBucket_v1_normal.png`, Normal Scale 1.00 |
| Specular/Gloss | `../export/SaunaBucket_v1_specgloss.png`, Spec Color 255/255/255, **Glossiness 1.00** (по умолчанию 0.92) |
| Occlusion | `../export/SaunaBucket_v1_occlusion.png` (1024; если редактор покажет «256» — так и оставить), Occlusion Scale 1.00 |
| Emission | не трогать (None, Emission Color 0/0/0 — свечения нет) |
| Fuzz Mask | `../export/SaunaBucket_v1_fuzzmask.png`, Fuzz 1.00, Fuzz Scatter 0.50 (по умолчанию) |
| Dirt | по умолчанию (Dirt Amount 0.40) |

Чаще всего забывают Fuzz Mask: без неё по умолчанию белая маска и Fuzz 1.00 — бархатный отблеск по всему
ведру, обручи станут «пушистыми».

## Картинки для страницы (Steam → Add/edit images)

Главный кадр — **из игры** (правило проекта: рендеры Blender не выдаём за игровые кадры). Снять в редакторе
на весь экран (F12), панель свернуть зелёной стрелкой:

| # | Кадр | Что видно |
|---|---|---|
| 1 | `ingame/front_day` — анфас днём | окно со свежим пропилом и сеткой, перепиленный обруч |
| 2 | `ingame/q34_day` — 3/4 слева | клёпки, нахлёст обруча с заклёпками, лист |
| 3 | `ingame/top_day` — сверху от третьего лица | днище: три доски, латка, мокрое кольцо, утор |
| 4 | `ingame/side_day` — сбоку | ушко с узлом обрезанной верёвки |
| 5 | `ingame/night` — ночью у каменки Sauna Stove | ведро в тёплом свете, без своего свечения |
| 6 | `ingame/set` — с халатом Sauna Robe и полотенцем | сет на персонаже |

Рендеры Blender (если нужны для доп. картинок) — `../renders/v1_*` с подписью «render» в имени файла.
