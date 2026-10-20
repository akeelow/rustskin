"""Preview of the stool concept: the chair with the backrest and arms removed (faces, not texels).

A rough stand-in for the alpha cut, to judge the silhouette before any texture work. Islands are
numbered as in uv/islands.md. Drops the top rail and both arms whole (2, 7, 9, 11-13, 20), cuts the
shell, back/underside and rear uprights (0, 5, 6, 8) above y 0.53 m and the arm post strip (1)
above y 0.50 m.

Usage: .venv/Scripts/python skins/sauna/chair/cut_preview.py <out.obj>
then viewer.py with the original maps.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "tools"))
sys.path.insert(0, str(HERE))
from islands import islands  # noqa: E402
from uv_zones import load_obj  # noqa: E402

DROP = {2, 7, 9, 11, 12, 13, 20}
CUT, CUT_Y = {0, 5, 6, 8}, 0.53
POST, POST_Y = 1, 0.50


def main(out):
    V, T, F = load_obj(HERE / "originals" / "chair.obj")
    isl = {f: n for n, fs in enumerate(islands(F)) for f in fs}
    keep = []
    for f, (vi, _) in enumerate(F):
        n, top = isl[f], max(V[i][1] for i in vi)
        if n in DROP or (n in CUT and top > CUT_Y) or (n == POST and top > POST_Y):
            continue
        keep.append(f)
    with open(out, "w") as o:
        o.writelines("v %f %f %f\n" % tuple(v) for v in V)
        o.writelines("vt %f %f\n" % tuple(t[:2]) for t in T)
        for f in keep:
            o.write("f " + " ".join(f"{a + 1}/{b + 1}" for a, b in zip(*F[f])) + "\n")
    print(f"kept {len(keep)} of {len(F)} triangles")


if __name__ == "__main__":
    main(sys.argv[1])
