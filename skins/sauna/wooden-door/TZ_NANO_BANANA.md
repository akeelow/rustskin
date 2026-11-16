# ТЗ для Nano Banana: референс двери Sauna Door

> 16.11.2026. Цель — получить **референс для 3D-моделирования**, а не текстуру. Картинку никто не
> будет клеить на развёртку: по ней в Blender моделируются доски, окно, полотенце и запекаются на
> модель. Поэтому важнее всего **правильная геометрия двери и материалы сета**, а не «дорогой» вид.

## 1. Почему прошлые генерации не годятся

Кадры прошлой попытки: [спереди](screenshots/prev_attempt/editor_front.png),
[сзади](screenshots/prev_attempt/editor_back.png).

| Что было | Почему нельзя |
|---|---|
| «Luxury», чугунная арочная топка с углями прямо в двери | Это дверь парилки, а не печь. В двери — простое окошко, за которым тёплый свет |
| Латунные термометр и гигрометр с цифрами, номерок с цифрой | Правило сета: без текста и цифр |
| Славянский орнамент на полотенце, резное солнце, жалюзи | Чужая тема и «магазинная» мебель; сет — самоделка из мусора |
| Кованый отбойник с болтами, чугунные рамы, стяжки на брусьях | Дверь выглядит крепче деревянной (тир) |
| Янтарно-оранжевое лакированное дерево | Ошибка шкафчика из [CRITIQUE_ART.md](../CRITIQUE_ART.md): дерево сета бледное, серо-медовое |
| Окно спереди слева, сзади справа | Сзади оно попало под диагональный брус модели — брус перечёркивает стекло |
| Наличник и коробка вокруг двери, тени на стене | Нужно только полотно двери, от края до края кадра |

## 2. Геометрия, которую нельзя менять

Модель `originals/door.hinged.wood.obj`: полотно **1,21 × 2,11 м** (≈ 9:16). Доли ниже — от ширины
и высоты полотна, высота считается **сверху**. Источник: [uv/views.png](uv/views.png) и кадры из игры.

**Перед** ([кадр](screenshots/ingame/front_keylock.jpg)) — плоский щит из вертикальных досок, без брусьев.

- Ручка — маленькая, у **левого** края, на 49 % высоты. Петли справа.
- Замок игра вешает сама: **слева, 8–28 % ширины, 52–70 % высоты**. Здесь — только чистые доски.
- Окно: **справа вверху, 58–90 % ширины, 15–40 % высоты**.

**Зад** ([кадр](screenshots/ingame/back_keylock.jpg)) — те же доски плюс накладные брусья (настоящая геометрия):

- три горизонтальных бруса: верхний 0–11 %, средний 44–54 %, нижний 90–100 % высоты;
- верхний раскос: от правого верхнего угла вниз-влево к середине среднего бруса;
- нижний раскос: от середины среднего бруса вниз-влево в левый нижний угол;
- ручка у **правого** края на 49 % высоты; замок — справа под средним брусом, 80–100 % ширины, 54–68 % высоты;
- окно (то же самое, зеркально): **слева вверху, 10–42 % ширины, 15–40 % высоты** — единственное
  поле, которое не пересекают брусья.

## 3. Как генерировать

1. Модель: Nano Banana (Gemini image), формат **9:16**, по одной стороне за запрос.
2. **Приложить картинки** (без них геометрия уплывёт):
   - сторона двери из игры: `screenshots/ingame/front_keylock.jpg` или `back_keylock.jpg`, **обрезанная
     по полотну двери**;
   - стиль и палитра сета: `../locker/workshop/door.jpg`, `../chair/workshop/towel.jpg`,
     `../bed/workshop/towel.jpg`.
3. Сначала перед. Для зада приложить ещё и **принятый результат переда** — чтобы окно, доски и тон совпали.
4. В запросах нет слов «Rust», «skin», «game», «weapon»: на них генератор рисует оружие.
5. Сгенерировать 4–6 вариантов на сторону, отобрать по чек-листу из раздела 6.

## 4. Запрос: перед (сторона в предбанник)

```text
Use image 1 as the exact shape reference: a plain flat slab door made of vertical planks, same
proportions, same small handle position on the left edge at mid height. Use images 2-4 only as
style and colour reference (pale weathered wood, washed-out linen towel with a faded brick-red
stripe).

Create a straight-on orthographic front view of a homemade sauna door, the door leaf only, filling
the whole 9:16 frame edge to edge, no door frame, no wall, no floor, no background, no cast shadow
outside the door. Flat, even, shadowless diffuse lighting, no perspective, no lens distortion.

The door is built by a survivor from scrap: narrow vertical aspen boards of uneven width (8 to 12
boards across), nailed onto an old rusty steel sheet. Rust-brown metal shows through the gaps
between boards and as a thin ragged strip along the outer edges. Boards are pale, dry, greyish-honey
unfinished wood (#C2A77E), matte, no varnish, no orange or amber tint, with visible grain, a few
knots with dark resin, slightly different tone from board to board, crooked joints. The lowest
quarter of the door and the area around the handle are darker from steam and water (#7A5A3C).
Small rusty nail heads in rows, each with a faint rust halo. Vertical water drip marks and white
mineral streaks running down from the window and near the bottom.

Upper right (58-90% of the width, 15-40% of the height from the top): one small rectangular window
with slightly rounded corners in a rough frame made of four short wooden slats nailed on, with a
small wooden sill. The glass is fully fogged with condensation and drops, nothing is visible
behind it except a soft warm orange glow, brighter at the bottom, deep orange (#FF6A1F) fading to
amber (#FFB347), like a hot stove somewhere behind. No flames, no coals, no grille, no objects
behind the glass.

Upper left (10-40% of the width, 12-45% of the height): a bent rusty nail or simple forged hook
with a washed-out off-white linen towel (#CFC6B4) hanging in soft folds, with one wide and one
narrow faded brick-red stripe (#8E3A30) near the bottom hem, plain weave, no pattern, no fringe
ornament.

Left edge at mid height: a small simple wooden handle, polished and darkened by hands, fixed with
twisted wire. Directly below the handle (8-28% of the width, 52-70% of the height) leave plain
empty boards with no details at all.

Near the bottom: one small wet birch leaf stuck to the dark damp wood.

Realistic materials, worn, hand-made, modest. Do not include: any text, letters, numbers, dials,
thermometers, gauges, signs, logos, carvings, ornaments, folk patterns, brass, cast iron, metal
plates, kick plate, armour, bolts, louvers, vents, arches, fire, embers, neon, a whisk or broom,
a door frame, a wall, people.
```

## 5. Запрос: зад (сторона в парилку)

```text
Use image 1 as the exact shape reference for the construction: vertical planks with three
horizontal rails (top, middle, bottom) and two diagonal braces running from the upper right corner
down to the lower left corner, interrupted by the middle rail; small handle on the right edge at
mid height. Keep every rail and brace exactly where it is in image 1. Use image 2 (the front side
of the same door) for the window, wood and wear, and images 3-5 only as style reference.

Create a straight-on orthographic view of the inner side of the same homemade sauna door, as seen
from inside the hot steam room, the door leaf only, filling the whole 9:16 frame edge to edge, no
door frame, no wall, no background. Flat, even, shadowless diffuse lighting, no perspective.

Same aspen boards, but darkened by years of steam: brown (#7A5A3C) in the lower half, getting
darker towards the top (#45332A) with a soft layer of soot along the upper rail and upper corners.
Matte, slightly damp wood, no varnish, no orange tint. The rails and braces are rough-sawn planks
of the same wood, a little lighter on the worn edges, nailed with rusty nails. Water drip marks,
white mineral streaks, a few dark wet patches near the bottom rail.

Upper left panel (10-42% of the width, 15-40% of the height from the top), in the free area that
no rail or brace crosses: the same small rectangular window with rounded corners in a rough frame
of nailed wooden slats. Fogged glass with running drops, soft warm orange glow behind it, brighter
at the bottom (#FF6A1F fading to #FFB347). No flames, no coals, no grille. The window must not
touch or overlap any rail or brace.

Right edge at mid height: a small simple wooden handle darkened by hands. Below the middle rail on
the right (80-100% of the width, 54-68% of the height) leave plain empty boards.

On the hinge side (left edge) two simple hand-forged strap hinges, flat, thin, rusty, one on the
top rail and one on the bottom rail, with one joint repaired with twisted wire.

No towel on this side. Realistic materials, worn, hand-made, modest. Do not include: any text,
letters, numbers, dials, thermometers, logos, carvings, ornaments, brass, cast iron, steel
brackets, corner plates, bolts, armour, fire, embers, neon, a door frame, a wall, people.
```

## 6. Чек-лист приёмки картинки

Картинка годится как референс, только если **все** пункты выполнены:

- [ ] Только полотно двери, прямо, без перспективы, без коробки, стены и теней вокруг.
- [ ] Перед — плоский щит без брусьев. Зад — три бруса и два раскоса там же, где на кадре из игры.
- [ ] Окно: спереди справа вверху, сзади слева вверху; сзади ни один брус его не касается.
- [ ] Под ручкой (спереди слева, сзади справа) чистые доски — место под замок.
- [ ] Дерево бледное, серо-медовое, матовое; оранжевого лака нет. Зад заметно темнее переда.
- [ ] Железо — только ржавый лист в щелях и по кромке, плоские петли и гвозди. Накладок и уголков нет.
- [ ] В окне только запотевшее стекло и тёплый свет: без углей, пламени и решётки.
- [ ] Полотенце только спереди: грязно-белое, одна широкая и одна узкая кирпичная полоса, без узора.
- [ ] Нет букв, цифр, шкал, знаков, резьбы и орнамента.
- [ ] Крупных деталей мало: окно, полотенце, ручка, лист. Остальное — доски и износ.

## 7. Что делать с результатом

Принятые картинки положить в `references/` этой папки как `ref_front.png` и `ref_back.png`. Дальше
по ним — `bake_door.py`: high-poly геометрия и запекание на развёртку оригинала. Сама картинка в
текстуру не идёт.
