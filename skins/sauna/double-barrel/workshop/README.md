# Sauna Shotgun — публикация в Workshop

> Подготовлено 17.11.2026 для **v1.10** (файлы `DoubleBarrel_v1.10_*`). Публикует пользователь сам из игрового редактора.
> v1–v1.3 сняты в игре (хром, полоса на стволе, скучный прицел, слишком новая медь, торцы, спусковая скоба, нарисованные трубы, одинаковые ямки, «граница» на прикладе, гранёные стволы — исправлены). **v1.10 в игре ещё не снята.** Сначала загрузить и посмотреть по [../README.md](../README.md), раздел
> «Что проверить в игре», потом публиковать.

## Название и описание (англ.)

**Title:** `Sauna Shotgun` (правило сета: префикс `Sauna`, без скобок и оригинального имени, `../../README.md`).

**Description** (вставить на странице Steam после публикации):

```
Every Rust life starts naked. Might as well warm up properly.

The sauna keeper's shotgun, kept by the changing-room door. Pipe barrels
sleeved in birch bark against the heat and tied off with hemp twine, old
copper fittings at the breech, twine and a leaf on the hammer bar, the
fore-end wrapped in more bark, a strip of old linen towel round the grip
and the break lever. A pale aspen stock gone dark where the hands hold it,
a knot weeping resin, a simple pattern burnt in with a hot nail. Soot at
the muzzles, white streaks from the steam, and a birch leaf or two still
stuck on from the bath broom.

Part of the Sauna set.
```

Тон — как у остальных семи. Без просьб о лайках, без текста на самой текстуре. Строку о коллекции
Steam добавить так же, как в описаниях остальных предметов сета (ссылка на коллекцию Sauna —
`../../workshop_collection.md`).

## Как загрузить

Иконку **генерирует сам редактор** при Publish, Facepunch просит её не заменять. Перед Publish пройти
все пять вкладок (BARREL, GRIP, MAIN, STOCK, SIGHTS) — таблица файлов и ползунков в
[../README.md](../README.md), раздел «Как загрузить». Коротко:

- на каждой вкладке заменить Diffuse, Normal, Specular/Gloss; Occlusion — у BARREL, MAIN, STOCK;
- Emission нигде не трогать (свечения нет);
- ползунки по умолчанию; у SIGHTS Glossiness 0.65 — так и оставить.

## Картинки для страницы (Steam → Add/edit images)

Главный кадр — **из игры** (снимает пользователь): от первого лица, стоя у включённой Sauna Stove ночью,
чтобы были видны полотенце на рычаге, лист на колодке и береста на стволах. Рендеры Blender — только
дополнительные, и на странице это рендеры, а не игровые кадры.

| Порядок | Файл | Что |
|---:|---|---|
| 1 | `screenshots/ingame_fp_night.jpg` (снимает пользователь) | от первого лица ночью у каменки |
| 2 | `screenshots/ingame_side.jpg` (снимает пользователь) | сбоку, левым боком: цевьё, узел, лист, обмотка шейки |
| 3 | `hero.jpg` | рендер: 3/4 слева, студия |
| 4 | `detail.jpg` | рендер: цевьё — береста, узел, лист; манжеты на стволах |
| 5 | `set.jpg` | рендер: рядом с Sauna Chair ночью, тёплый свет |
| 6 | `screenshots/ingame_reload.jpg` (снимает пользователь) | перелом при перезарядке |

Рендеры: [../workshop_renders.py](../workshop_renders.py) (через `gun_view.py`, Eevee, 1920×1080).

## Чек-лист перед Publish

- [ ] Все пять вкладок заменены, ни одна не осталась зелёно-красной (оригинал).
- [ ] От первого лица видны полотенце на рычаге, лист и береста; рычаг слева.
- [ ] На стволах при осмотре нет тёмной продольной полосы.
- [ ] Шейка не мерцает (STOCK и GRIP поверх друг друга).
- [ ] Перелом: казённик и гильзы без надписей и без странных пятен.
- [ ] Название `Sauna Shotgun`, описание вставлено, коллекция Sauna.
