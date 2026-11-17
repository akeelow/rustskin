#!/usr/bin/env bash
# Sauna Boiler: полный прогон из корня репозитория.  bash skins/sauna/furnace/build.sh [bake] [tex] [view]
set -e
B="C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe"
D=skins/sauna/furnace
V=$(grep -oE 'VERSION = "[^"]+"' $D/texture_furnace.py | cut -d'"' -f2)
steps="${*:-bake tex view}"
for s in $steps; do
  case $s in
    bake) "$B" -b -P $D/bake_furnace.py -- --size 2048 --blend --preview 2>&1 | grep -v "^Fra:\|Saved:\| Time:\|Deprec\|use_nodes\|^$" | tail -8 ;;
    tex)  .venv/Scripts/python $D/texture_furnace.py | tail -2 ;;
    view) "$B" -b -P tools/blender/viewer.py -- --obj $D/originals/furnace.obj --tex $D/export/Furnace_$V \
            --focus 0.0,0.5,0.45 --sheet $D/renders/${V}_sheet.png --blend $D/renders/${V}_view.blend 2>&1 | grep "^sheet" ;;
  esac
done
