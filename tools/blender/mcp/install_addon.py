"""Install and enable the MCP for Blender addon into the user's Blender prefs.

Run: "<blender.exe>" -b -P tools/blender/mcp/install_addon.py
"""
from pathlib import Path

import bpy

addon = Path(__file__).resolve().parent / "blender_mcp.py"
bpy.ops.preferences.addon_install(filepath=str(addon), overwrite=True)
bpy.ops.preferences.addon_enable(module="blender_mcp")
bpy.ops.wm.save_userpref()
print("BLENDER_MCP_INSTALLED", bpy.utils.user_resource("SCRIPTS", path="addons"))
