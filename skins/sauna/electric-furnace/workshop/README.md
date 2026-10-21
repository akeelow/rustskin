# Sauna Stove — публикация в Workshop

> Подготовлено 19.10.2026 для v2.6. Публикует пользователь сам из игрового редактора.

## Название и описание (англ.)

**Title:** `Sauna Stove`

**Description** (вставить на странице Steam после публикации):

```
Every Rust life starts naked. Might as well warm up properly.

An old kitchen cooker turned into a sauna stove: clad in aspen slats nailed
to the rusty shell, burners buried under split basalt, a forged grate over a
firebox full of glowing rocks, all sitting on a rubble plinth and a wet pallet.

Part of the Sauna set.
```

Коротко, без просьб о лайках и без текста на самой текстуре (правила сета и
советы Facepunch). Если спросят в комментариях про конфорки: «The coil
cutout only hides the cooker coils under the rocks - there's nothing to see
through.»

## Иконка

Иконку (thumbnail) **генерирует сам редактор** при нажатии Publish, и Facepunch
просит её не заменять: «keep your thumbnail as the default generated thumbnail»
([Creating Skins](https://wiki.facepunch.com/rust/Creating_Skins)). Поэтому
своей иконки не делаем. Перед Publish в редакторе выставить:

- все 5 карт v2 (Diffuse = `ElectricFurnace_v2_diffuse_cutout.png`), **Alpha Cutoff 1.00**
  (проверено в игре; 0.5 тоже работает);
- остальные ползунки по умолчанию.

`collection.png` (1024×1024) — картинка для **Steam-коллекции «Sauna»**, не для предмета.

## Картинки для страницы (Steam → Add/edit images)

Рендеры Blender (`workshop_renders.py`, Cycles, 1920×1080; JPG для загрузки):

| Файл | Что |
|---|---|
| `hero.jpg` | днём, 3/4 спереди — главный кадр |
| `night.jpg` | ночью: свет из топки и жалюзи |
| `firebox.jpg` | крупно топка: куча камней за кованой решёткой |
| `burners.jpg` | крупно конфорки: кучи базальта |
| `back.jpg` | сзади: обшивка, короб-«дверца» с обвязкой |

![hero](hero.jpg)

Плюс **скриншоты из редактора Workshop** — сняты пользователем 21.10.2026 на весь экран (F12), исходники в `../screenshots/editor_16x9/`; для загрузки — `ingame/` (1920×1080, панель редактора обрезана). Порядок на странице: рендер `hero`, затем скриншоты в этом порядке, затем остальные рендеры.

| Файл | Что |
|---|---|
| `ingame/three_quarter_day.jpg` | 3/4 днём |
| `ingame/front_night.jpg` | анфас ночью |
| `ingame/top_night.jpg` | сверху в сумерках: камни на конфорках, свет топки |
| `ingame/back_day.jpg` | сзади днём |

## Вырез альфой — допустимо ли

- **Технически да:** у Diffuse в редакторе есть Alpha Cutoff, PNG с альфой — штатный
  путь; в игре проверено (v2.1–v2.6).
- **Официальных правил про прозрачность нет:** ни [Getting Your Skin Accepted](https://wiki.facepunch.com/rust/Getting_Skin_Accepted),
  ни [Workshop FAQ](https://wiki.facepunch.com/rust/Workshop_FAQ), ни [Creating Skins](https://wiki.facepunch.com/rust/Creating_Skins)
  её не упоминают.
- **Принятые скины с вырезами существуют** — например, двери с прорезями (сообщество
  зовёт их «P2W», потому что сквозь них видно), см. гайд
  [ALL Rust P2W Door Skins (cutouts)](https://steamcommunity.com/sharedfiles/filedetails/?id=3576575985).
- **Отказы тоже были:** по комментарию автора, скин гаражной двери не приняли именно из-за
  прозрачности (единичный рассказ, не официальное заявление).
- **Вывод:** риск — в вырезах, через которые что-то видно (обзор, преимущество в игре). У нас
  вырез только убирает спирали конфорок, под ними цельная чаша (проверено лучами в Blender:
  насквозь ничего не видно), на хитбокс текстура не влияет. Риск низкий — **публикуем с вырезом**.
  Запасной вариант на случай замечаний: `ElectricFurnace_v2_diffuse.png` и Alpha Cutoff 0
  (спирали видны, но покрыты камнями нормалью).

## Чек-лист публикации

1. Редактор → Electric Furnace → загрузить 5 карт v2, Alpha Cutoff 1.00.
2. Вкладка **ITEM**: имя `Sauna Stove` (без имени кнопка Publish неактивна).
3. Вкладка **PUBLISH** → Publish. Откроется страница в браузере (войти в Steam).
4. На странице: вставить описание, добавить картинки (5 рендеров + 2–4 скриншота из игры).
5. Принять **Workshop Contributor Agreement** (без него принятый скин не станет публичным).
6. Создать/дополнить коллекцию **Sauna** (картинка `collection.png`), когда будут другие предметы.
7. Ссылку на страницу записать в `../README.md` (статус) и `../HANDOFF.md`.

> По плану сета публиковать **одновременно, как коллекцию** (см. `../../README.md`):
> можно опубликовать каменку сейчас и держать страницу, но голосование и внимание
> лучше собирать, когда в коллекции будут 3–5 предметов.

## Как пересобрать картинки

```bash
"C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P skins/sauna/electric-furnace/workshop_renders.py -- --samples 128
```

Кадры: `hero night burners firebox back collection` (можно перечислить нужные). Все шесть — ~5 мин на RTX 3060 Ti (дольше всех firebox).
JPG — пересохранить из PNG (quality 92).
