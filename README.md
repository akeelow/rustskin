# rustskin

Учимся и разрабатываем скины для игры [Rust](https://rust.facepunch.com/)
для Steam Workshop.

## С чего начать

- [Руководство по скинам Rust](docs/rust-skins-guide.md) — что такое скин, как
  его сделать и добавить в игру, инструменты, критерии качества, план обучения.
- [Какой предмет скинить](docs/item-selection.md) — топ-5 предметов по шансам
  на принятие и продажам (на данных Workshop + SCMM).

## Структура

```
docs/          руководства и заметки
references/    референсы и разборы чужих скинов
skins/<имя>/   отдельный скин: source/, originals/, export/, screenshots/, README.md
templates/     шаблоны развёрток, smart-материалы, пресеты экспорта
tools/         скрипты сбора и анализа данных
data/          срезы данных Workshop / SCMM и рейтинг предметов
```

Тяжёлые исходники (PSD, KRA, SPP, blend, а также PNG/TGA) хранятся через
**Git LFS** — см. `.gitattributes`. Перед первым коммитом с графикой:

```bash
git lfs install
```
