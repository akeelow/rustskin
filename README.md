# rustskin

Учимся и разрабатываем скины для игры [Rust](https://rust.facepunch.com/)
для Steam Workshop.

## С чего начать

- [Руководство по скинам Rust](docs/rust-skins-guide.md) — что такое скин, как
  его сделать и добавить в игру, инструменты, критерии качества, план обучения.
- [Какой предмет скинить](docs/item-selection.md) — топ-5 предметов по шансам
  на принятие и продажам (на данных Workshop + SCMM).
- [Тематика сета](docs/themes.md) — свободные темы для электропечи + одежды.

## В работе

- [Sauna](skins/sauna/README.md) — сет «сауна из мусора»: каменка, полотенце,
  тулуп, шкафчик и др. Первый предмет — [Sauna Stove](skins/sauna/electric-furnace/README.md).

## Структура

```
docs/          руководства и заметки
references/    референсы и разборы чужих скинов
skins/<имя>/   отдельный скин: source/, originals/, export/, screenshots/, README.md
templates/     шаблоны развёрток, smart-материалы, пресеты экспорта
tools/         скрипты сбора и анализа данных
data/          срезы данных Workshop / SCMM и рейтинг предметов
```

Скрипты генерации текстур требуют numpy и Pillow:

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
```

Превью скина в Blender (5.2, установлен через Steam):

```bash
"C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" -b -P tools/blender/preview.py -- <model.obj> <export/ИмяТекстур_v1> <out.png> day 35
```

Живое управление Blender из Claude (MCP): см. [tools/blender/mcp](tools/blender/mcp/README.md).

Тяжёлые исходники (PSD, KRA, SPP, blend, а также PNG/TGA) хранятся через
**Git LFS** — см. `.gitattributes`. Перед первым коммитом с графикой:

```bash
git lfs install
```
