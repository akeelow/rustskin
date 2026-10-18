# rustskin

Учимся и разрабатываем скины для игры [Rust](https://rust.facepunch.com/)
для Steam Workshop.

## С чего начать

- [Руководство по скинам Rust](docs/rust-skins-guide.md) — что такое скин, как
  его сделать и добавить в игру, инструменты, критерии качества, план обучения.

## Структура

```
docs/          руководства и заметки
references/    референсы и разборы чужих скинов
skins/<имя>/   отдельный скин: source/, originals/, export/, screenshots/, README.md
templates/     шаблоны развёрток, smart-материалы, пресеты экспорта
```

Тяжёлые исходники (PSD, KRA, SPP, blend, а также PNG/TGA) хранятся через
**Git LFS** — см. `.gitattributes`. Перед первым коммитом с графикой:

```bash
git lfs install
```
