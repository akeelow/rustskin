# Промт для Nano Banana: референс Sauna Robe v3

Зачем: картинка-ориентир по ткани, швам и деталям для [../PLAN_v3.md](../PLAN_v3.md). Текстурой она не станет: всё
равно моделируем в Blender.

Как пользоваться:
- **Промт 1** — главный. Приложи к нему кадр из игры `../screenshots/editor_16x9/three_quarter_day.jpg`. Тогда
  Nano Banana сохранит форму куртки, позу, ракурс и свет и поменяет только ткань и детали. Без кадра выйдет
  длинный халат другой формы, а длину и рукава у модели менять нельзя.
- **Промты 2–4** — крупные планы. К каждому можно приложить кадр или результат промта 1.
- Если появится текст, логотип, свечение, обнажёнка или халат станет длиннее/шире, перегенерируй.

Промты на английском: на нём модель понимает точнее.

---

## Промт 1 — общий вид, редактирование кадра

```
Edit the attached image. Keep the exact same character, pose, garment silhouette, garment length, sleeve
shape, camera angle, lighting and background. Do not make the garment longer or wider. Change only the
garment's fabric and details.

The garment is a short homemade bathrobe sewn by a survivor from two old waffle-weave cotton bath towels.
Photorealistic game asset look, every detail has real physical relief (not painted):

- Fabric: warm beige waffle-weave cotton #BBA889, large waffle cells about 1 cm with soft raised ridges,
  slightly irregular after many washes, the grid runs vertically on the body, along the sleeves, and
  along the collar band and belt. The waffle pattern breaks and shifts at every seam.
- Wrap: kimono-style flat collar band 7 cm wide, two layers thick, running from the back of the neck down
  both front edges. The bands cross in a V on the chest; below the crossing the top panel's edge runs
  straight down the front to the hem. The band's outer edge is a soft rolled fold with two faded
  brick-red #8E3A30 woven stripes (9 mm and 4 mm) near the edge, the inner edge is top-stitched.
- Belt: 5 cm wide waffle belt round the waist through belt loops at the side seams, both edges stitched,
  fabric gathered in soft vertical folds above and below it, tied in a flat knot a little to the side of
  centre, two tails 20-28 cm hanging with a slight twist, hemmed ends with a few loose threads.
- Pockets: two patch pockets on the hips with a folded top band standing slightly open, top-stitched,
  the left one bulging with a rolled washcloth; a breast patch pocket on the left chest with a thin
  birch twig with two leaves sticking out.
- Sleeves: wide turned-back cuffs 9 cm with a thin brick-red stripe, elbows patched with pieces of an old
  striped towel sewn on with large hand running stitches, soft creases at the inner elbow, one pulled
  thread snag on the forearm, frayed loops along the cuff fold.
- Back: yoke seam across the shoulders, long soft drape folds, a towel border at the hem with two brick
  stripes, a wet birch leaf stuck between the shoulder blades, a small darned corner near the hem.
- Wear: a few small scorch marks from stove sparks on the right sleeve and the front hem, darker damp
  hem and cuffs, uneven tone after washing in a bucket, slightly yellowed neckline.

Palette: waffle cotton #BBA889, brick stripe #8E3A30, birch leaf #5C6A39. Muted, natural, believable.
No text, no logos, no glow, no extra objects.
```

## Промт 2 — крупно перёд: запах, пояс, узел, карман

```
Close-up of the front of a short homemade waffle-cotton bathrobe at the waist, low grazing light so every
relief detail casts a shadow. Warm beige #BBA889 waffle weave with 1 cm cells, kimono collar band two
layers thick with a rolled outer fold, two faded brick-red #8E3A30 woven stripes near the edge and
top-stitching along the inner edge. A 5 cm waffle belt with stitched edges passes through a belt loop and
is tied in a flat knot, fabric gathered in soft folds above and below. Two hemmed belt tails with a
twist and a few loose threads hang over a hip patch pocket whose folded top band stands slightly open.
The waffle grid changes direction between the collar band, the belt and the body. No text, no logos,
no people.
```

## Промт 3 — крупно рукав

```
Close-up of the sleeve of a homemade waffle-cotton bathrobe, grazing light. Beige #BBA889 waffle weave
running along the sleeve, a wide turned-back cuff with a thin faded brick-red #8E3A30 stripe and a rolled
fold, frayed loops along the fold. An elbow patch cut from an old striped towel, edges turned under, sewn
on with large uneven hand running stitches in thick thread. Soft creases at the inner elbow, one pulled
thread snag with puckered cells, a small brown scorch mark from a spark. No text, no logos, no people.
```

## Промт 4 — крупно спина

```
Close-up of the back of a short homemade waffle-cotton bathrobe, soft daylight. Beige #BBA889 waffle
weave, a top-stitched yoke seam across the shoulders where the waffle grid changes direction, long soft
drape folds, the belt passing round the waist with gathered fabric, a towel border at the hem with two
faded brick-red #8E3A30 woven stripes and double top-stitching, a wet birch leaf #5C6A39 stuck flat
between the shoulder blades, a small darned patch of crossed threads near the hem, the hem darker and
damp. No text, no logos, no people.
```
