# Sauna Bucket — публикация в Workshop

> Подготовлено 18.11.2026, обновлено 19.11.2026 для **v2 — финал** (полотенце, веник, открытое окно, медь; проверена в игре 19.11).
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

Готово: **[ingame/](ingame/)** — 7 кадров из редактора (v2, Alpha Cutoff 0.50), сняты пользователем 20.11.2026 (F12),
исходники — `../screenshots/editor_v2/`. Нижняя панель редактора и кнопка слева обрезаны, 1920×1080 JPG.
Загружать в этом порядке (первый — главный):

| # | Файл | Что видно |
|---|---|---|
| 1 | `ingame/01_front.jpg` | анфас снизу на фоне неба: лицо с бородой в выпиленном окне, полотенце, медный обруч — главный кадр |
| 2 | `ingame/02_q34_knot.jpg` | 3/4 сверху справа: днище с латкой, полотенце с узлом и концами, лист, лицо в окне |
| 3 | `ingame/03_q34_venik.jpg` | 3/4 слева: веник под полотенцем, синий вкладыш в окне |
| 4 | `ingame/04_back_knot.jpg` | сзади справа: узел и концы с бахромой, ушко с верёвкой |
| 5 | `ingame/05_side_venik.jpg` | сбоку слева: веник, медный обруч, ушко |
| 6 | `ingame/06_back.jpg` | сзади: полотенце по кругу, клёпки, гвозди вкладыша |
| 7 | `ingame/07_full.jpg` | персонаж целиком: шайка на голове |

Не вошли: два кадра 20.11 с сеткой (снято до Alpha Cutoff 0.50 — `20261120182742`, `20261120182811`). Не снято
(по желанию, можно добавить позже): ночью у каменки Sauna Stove и весь сет на персонаже.
