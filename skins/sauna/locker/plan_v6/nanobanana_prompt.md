# Промт для Nano Banana: референс Sauna Changing Locker v6.0

Зачем: картинка-ориентир по материалам, тону и износу для [../PLAN_v6.md](../PLAN_v6.md). Текстурой она не станет:
всё равно моделируем в Blender.

Как пользоваться:
- **Промт 1** — главный. Приложи к нему кадр из редактора `../workshop/ingame/three_quarter_day.jpg` (v5.4, 3/4 днём).
  Тогда Nano Banana сохранит форму шкафчика, ракурс и пропорции и поменяет только материалы.
- **Промты 2–3** — крупные планы. К ним тоже прикладывай этот кадр или результат промта 1, чтобы держать один стиль.
- Если на картинке появится текст, цифры на приборах, логотип, человек или неоновое свечение — перегенерируй:
  по правилам сета их быть не должно.

Промты на английском: на нём модель понимает точнее.

---

## Промт 1 — общий вид, редактирование кадра

```
Edit the attached image. Keep the exact same object shape, proportions, silhouette, camera angle,
lighting and background. Do not add or remove any parts of the cabinet. Change only the surfaces and
materials. The left and right doors stay removed: the two side niches are open.

The object is the changing-room locker of a scrap-built Finnish sauna: an old three-section steel
factory locker that a survivor clad in pale linden tongue-and-groove boards. Photorealistic game asset
look, highly detailed weathered materials, every detail has real physical relief (not painted):

- Outside (sides, top rail, stiles between sections): pale steam-aged linden, silvery honey-grey, low
  saturation. Vertical tongue-and-groove boards 9 cm wide with V-joints, raised weathered grain, small
  dark knots, dry checks, square forged nail heads in pairs on horizontal battens, hammer crescent dents.
  Darker and wet at the bottom 30 cm with white mineral drip lines. Where the boards stop short, the old
  steel of the locker shows: chipped grey-green enamel with rust on the top edge and the plinth, rusty
  steel feet standing in a dried water stain. Ghost marks of removed door hinges (screw holes, a lighter
  rectangle) on the stiles.
- Open side niches: inside darker, tea-brown steamed wood so the contents read. Vertical boards on the
  walls, a slatted shelf with rounded worn front edge, a narrow warm light slot under the shelf fronts.
  On the back wall two turned wooden pegs: a washed off-white linen towel #CFC6B4 with two faded brick-red
  stripes #8E3A30 hangs from one peg with real folds and a hemmed edge, a dried flat birch whisk (leaves
  overlapping, twig handle bound with twine) hangs from the other. A wooden slatted floor grate on the
  niche floor.
- Middle door (closed, for the padlock): hand-made ledged door of vertical boards with three cross ledges.
  A small fogged window with a frame and glazing beads, a heart drawn by a finger in the condensation with
  water runs. Above it two round gauges in brass bezels (a thermometer with a red zone, a hygrometer with a
  blue zone, cream dials with tick marks, no numbers). In the middle a rusty steel plate for the lock with
  key scratches around the keyhole area, the wood around it polished by hands. Tally notches cut into the
  ledge (three groups of five). A muddy boot print and a split board next to the lock where someone tried to
  kick it in. One dry birch leaf stuck to the door. At the bottom a small drawer with a raised panel and a
  steel bow handle.

No text, no numbers, no logos, no people. Daylight.
```

## Промт 2 — крупно средняя дверца

```
Close-up of the middle door from the attached image, straight-on, same materials and style.
Show the real relief: the V-joints between boards, the raised grain, the nail heads and hammer dents,
the window frame with glazing beads and the fogged glass with a finger-drawn heart and water runs, the two
brass-bezel gauges (no numbers), the rusty lock plate with key scratches, the tally notches cut into the
ledge, the dried mud boot print with tread lugs, the split board with torn fibres, the dry birch leaf.
Soft daylight from the upper left so every groove casts a shadow. No text.
```

## Промт 3 — крупно открытая ниша

```
Close-up of one open side niche from the attached image, three-quarter view, same materials and style.
Tea-brown steamed linden inside: vertical boards on the walls and back, a slatted shelf with a worn rounded
front edge and a warm light slot under it, two turned wooden pegs on the back wall, a washed linen towel
with two faded brick-red stripes hanging from one peg with real folds and a stitched hem, a flat dried birch
whisk bound with twine hanging from the other, a slatted wooden floor grate. Dusk light, the warm slot
lights the towel from above. No text, no neon.
```
