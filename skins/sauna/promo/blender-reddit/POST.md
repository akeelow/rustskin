# Пост о процессе в r/blender: high-poly → запекание на развёртку Rust

**Зачем:** портфолио, просмотры и доверие. Голосов в Rust отсюда будет мало: это аудитория Blender, а не игроки
**[оценка]**. Пост показывает, что за скинами стоит настоящая геометрия, запечённая в карты, а не картинка из
нейросети.

**Когда:** в любой день после r/playrust (23.11). Утро в США — 15:00–18:00 по Москве **[оценка]**.
**Сколько займёт:** 15 минут на пост и потом ответы на комментарии.

## ⚠ Сначала решить: как написать про ИИ

Все high-poly сделаны **Python-скриптами в Blender**. Их писал ИИ-ассистент (Claude), это видно по коммитам
`fields_v3.py`, `bake_v3.py`, `fields_door.py`, `bake_v2.py`. Нейросеть для картинок или 3D здесь **не**
использовалась: всё — геометрия и запекание в Cycles. Но фразу «сделано без ИИ» написать нельзя: на r/blender
об этом спросят сразу («how did you model 9M polys of nails?»), и если ответ всплывёт позже, пост закончится
скандалом **[оценка]**.

Поэтому в тексте ниже это сказано **одной честной фразой** (абзац про процесс). Убрать её — решение
пользователя, но я не советую. Если правила сабреддита запрещают любую помощь ИИ, пост туда **не делать**.

## Куда: r/blender (совет)

**[оценка]** Правила обоих сабреддитов агент прочитать не смог: Reddit закрыт, зеркала не открылись.

- **r/blender** — совет. Аудитория самая большая из двух (больше миллиона **[оценка]**). Тема «процедурная
  геометрия на Python и запекание на чужую развёртку» — чисто блендеровская, таким постам там рады **[оценка]**.
- **r/3Dmodeling** — запасной. По найденным обрывкам, в 2025 правила там расширили: запрет рекламы теперь
  касается и «скрытого маркетинга», а при спорных постах смотрят, описал ли автор workflow, инструменты и
  время **[факт по поиску, точной формулировки нет]**. Модераторы пишут, что это место для «реальной работы
  реальных художников» **[факт по поиску]**, поэтому пост со скриптами, написанными ИИ, там рискованнее **[оценка]**.

### Что проверить в правилах (полминуты, справа «Rules» и вкладка About)

r/blender:
1. **ИИ:** есть ли запрет на ИИ-контент и распространяется ли он на код, написанный с ИИ. Если запрещено всё —
   не постить.
2. **Флейр:** обязателен ли. Нужен флейр вроде *I Made This* / *Original Content* / *Showcase*. *Need Help* и
   *Critique* не подходят, если не просим разбор.
3. **Описание процесса:** есть ли правило «объясни, как сделано» в посте или первым комментарием. Текст ниже его
   и так закрывает.
4. **Самопиар и ссылки:** можно ли ссылку на свой Steam Workshop. Если не сказано прямо — **без ссылки** (как в
   r/playrust).
5. **Игровой/фанатский контент:** не запрещены ли моды и скины к чужим играм.

r/3Dmodeling (если постим туда):
1. Правило 5 (реклама и скрытый маркетинг) и полные правила по ссылке из сайдбара.
2. Флейр (что-то вроде *Art Showcase*).
3. Нужны ли сетка (wireframe) или процесс — у нас есть пары «high-poly / итог» и развёртка.
4. Правило про ИИ.

**Ссылку на Workshop в посте не даём.** Если спросят «where can I get it?», ответ ниже.

## Шаги

1. Открыть https://www.reddit.com/r/blender/ и прочитать **Rules** по списку выше (2 минуты).
2. **Create Post** → вкладка **Images & Video**.
3. Перетащить **7 картинок** из этой папки по порядку номеров: `1_stove_hp_vs_final.jpg` … `7_stove_ingame.jpg`.
4. Подписи к картинкам в галерее (необязательно; поле Caption у каждой) — из таблицы ниже.
5. **Title** — скопировать строку ниже.
6. **Body** — скопировать блок целиком.
7. Флейр — по правилам (п. 2 выше). **Post.**
8. Ссылку на пост прислать мне; через 1–2 часа и вечером ответить на комментарии (готовые ответы ниже).

## Картинки

| Файл | Что | Подпись (Caption) |
|---|---|---|
| `1_stove_hp_vs_final.jpg` | каменка: high-poly и итог | `Blender render. Left: 9.4M-face high-poly. Right: the original 21k-tri Rust mesh with the baked maps.` |
| `2_stove_side_closeup.jpg` | бок: рейки, гвозди, термометр | `Blender render. Side panel close-up.` |
| `3_stove_top_closeup.jpg` | плита: эмаль, накипь; камни под оригинальными спиралями | `Blender render. Cooktop close-up.` |
| `4_stove_uv_layout.jpg` | итоговый диффуз на исходной развёртке | `The final diffuse on the vanilla UV layout.` |
| `5_door_hp_vs_final.jpg` | дверь: high-poly и итог | `Blender render. Door: 4.2M-face high-poly onto an 864-tri mesh.` |
| `6_door_window.jpg` | окно: ладонь только в текстуре | `Blender render. The palm print is texture-only - the glass is flat.` |
| `7_stove_ingame.jpg` | кадр из игры, ночь | `In-game, Rust skin editor.` |

Рендеры 1–6 подписаны на самой картинке: «Blender renders (Cycles), not in-game». 7 — кадр из игры
(`../reddit/1_stove_night.jpg` с плашкой «IN-GAME»).

## Title

```
Baking 9M polys of junk onto Rust's original 21k-tri stove: game skins can't change the mesh or the UVs, so all the detail has to live in the bake
```

Перевод: «Запекаю 9 млн полигонов хлама на оригинальную печку Rust в 21 тыс. треугольников: скины не могут
менять ни сетку, ни развёртку, поэтому вся детализация живёт в запекании».

Короче, если длинный не нравится:

```
Scrap sauna stove for Rust: 9.4M-poly high-poly baked onto the vanilla item's UVs
```

Перевод: «Печка для сауны из хлама для Rust: high-poly в 9,4 млн полигонов, запечённый на развёртку оригинального
предмета».

## Body

Абзацы без переносов внутри (редактор Reddit превращает каждый перенос в отдельную строку):

```
Rust skins have one hard rule: you get the game's own mesh and its own UV layout, and you can only replace the textures. So for a sauna-themed set I built the detail as high-poly geometry in Blender and baked it onto the vanilla UVs.

How it was made:
1. Imported the original item (OBJ, 21k tris for the stove, 864 for the door) and mapped every UV island to a surface: "left side, aspen slats", "cooktop, enamel", "firebox, stones" and so on.
2. Built the high-poly over each island with Python (bpy + numpy): split slats with knots and nails, chipped enamel with scale, a heap of stones, bricks, a towel with a hook. The stove ended up at 9.4M faces, the door at 4.2M.
3. Material masks are written into vertex attributes of the same geometry, so colour, wear and soot are baked from the shape, not painted by hand.
4. Baked in Cycles at 4096 per island group (normal, AO, masks), then merged by texel masks and exported at 2048 (stove) and 1024 (door).
5. Checked every surface in the Rust skin editor, day and night, and went back to the high-poly wherever something read badly.

Honest note on tools: the modelling is procedural, and the Python scripts were written by an AI coding assistant (Claude) under my direction. I set the look, reviewed every piece and checked each one in-game. There's no AI image or 3D generation anywhere: every pixel comes from a Cycles bake of real geometry.

Images 1-6 are Blender renders; the last one is an in-game editor shot. The palm print on the door glass is texture-only - the glass itself is flat.

Happy to answer questions about the bake setup. Feedback welcome, especially on where the bake doesn't hold up at game distance.
```

<details><summary>Перевод</summary>

У скинов Rust одно жёсткое правило: сетка и развёртка остаются игровыми, менять можно только текстуры. Поэтому для
сета на тему сауны я построил детали как high-poly геометрию в Blender и запёк их на оригинальную развёртку.

Как сделано:
1. Импортировал оригинальный предмет (OBJ, 21 тыс. треугольников у печки, 864 у двери) и сопоставил каждый остров
   развёртки с поверхностью: «левый бок, осиновые рейки», «плита, эмаль», «топка, камни» и т. д.
2. Построил high-poly над каждым островом на Python (bpy + numpy): колотые рейки с сучками и гвоздями, эмаль со
   сколами и окалиной, куча камней, кирпичи, полотенце на крючке. У печки вышло 9,4 млн граней, у двери 4,2 млн.
3. Маски материалов записаны в атрибуты вершин той же геометрии, поэтому цвет, износ и копоть запекаются из формы,
   а не рисуются вручную.
4. Запекание в Cycles в 4096 по группам островов (нормаль, AO, маски), слияние по маскам текселей, экспорт в
   2048 (печка) и 1024 (дверь).
5. Проверил каждую поверхность в редакторе скинов Rust днём и ночью и возвращался к high-poly там, где что-то
   читалось плохо.

Честно про инструменты: моделирование процедурное, Python-скрипты писал ИИ-ассистент для кода (Claude) по моим
указаниям. Облик задавал я, каждую деталь смотрел и проверял в игре. Генерации картинок или 3D нейросетью нет нигде: каждый
пиксель — запекание настоящей геометрии в Cycles.

Картинки 1–6 — рендеры Blender; последняя — кадр из редактора игры. Отпечаток ладони на стекле двери есть только
в текстуре — само стекло плоское.

Отвечу на вопросы про настройку запекания. Рад отзывам, особенно о том, где запекание не держится на игровой
дистанции.
</details>

## Если спросят

- *What's the poly count / texture size?* — уже в тексте. Коротко:
  ```
  Stove: 21k tris in-game, 9.4M-face high-poly, baked at 4096 and shipped at 2048. Door: 864 tris, 4.2M-face high-poly, shipped at 1024.
  ```
  Печка: 21 тыс. треугольников в игре, high-poly 9,4 млн граней, запекание 4096, в игре 2048. Дверь: 864
  треугольника, high-poly 4,2 млн, в игре 1024.

- *Why not sculpt it?*
  ```
  The UV islands are fixed and oddly shaped, so I needed the detail to follow each island exactly. Generating it per island in code made that easy to redo when an island read badly in-game.
  ```
  Острова развёртки заданы и неудобной формы, детали должны точно ложиться на каждый. Генерация кодом по островам
  позволяла легко переделать остров, который плохо читался в игре.

- *So it's AI?*
  ```
  The scripts were written by an AI coding assistant under my direction, I said so in the post. The result is ordinary geometry and a Cycles bake - no image or mesh generators. Happy to share how a part was built.
  ```
  Скрипты писал ИИ-ассистент по моим указаниям, это сказано в посте. Результат — обычная геометрия и запекание в Cycles, без
  генераторов картинок и моделей. Могу рассказать, как сделана любая деталь.

- *Tangent space issues / seams?*
  ```
  Rust smooths some edges, so I baked object-space from a flat-shaded copy first, then converted to tangent space (MikkTSpace) on the smoothed mesh. Seams on the original UV borders were the hardest part.
  ```
  Rust сглаживает часть рёбер, поэтому сначала пёк в object space с копии с плоскими гранями, потом переводил в
  касательное (MikkTSpace) на сглаженной сетке. Швы на границах исходной развёртки — самое трудное.

- *Where can I get it?* — без ссылки:
  ```
  It's called Sauna on the Rust Steam Workshop.
  ```
  Называется Sauna в Steam Workshop игры Rust.

- Похвала — «Thanks!». Грубость — не отвечать.

## Чего не писать

- Не просить голосов в Workshop и апвоутов на Reddit.
- Не писать «hand-sculpted», «no AI», «modelled by hand» — это неправда.
- Не выдавать рендеры 1–6 за кадры из игры.

## Файлы

- `render_stove.py`, `render_door.py` — рендеры Blender (`blender -b -P …`), high-poly собирается из
  `bake_v3.py` / `bake_v2.py`; папки предметов не меняются. Сырые кадры — `src/`.
- `make_process.py` — пары с подписями, развёртка, плашка на игровом кадре.
