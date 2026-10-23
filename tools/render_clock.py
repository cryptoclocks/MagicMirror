"""Blender background script; reads the supplied source without saving changes to it."""
import bpy
import math
from pathlib import Path
from mathutils import Vector, Quaternion, Matrix

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('/Users/cryptoclock/Desktop/CryptoClockPro/Videos/Sample1-Emerald/V5/Production/Technical-Speaker-First.blend')
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
s = bpy.context.scene
s.frame_set(681)
bpy.context.view_layer.update()
case = next(o for o in s.objects if o.type == 'MESH' and o.name.startswith('CASE') and not o.hide_render)
coords = [case.matrix_world @ Vector(c) for c in case.bound_box]
center = sum(coords, Vector()) / 8
# Mild emissive emerald finish keeps the rear readable in the dark hologram UI.
for slot in case.material_slots:
    if slot.material:
        slot.material = slot.material.copy()
        slot.material.use_nodes = True
        for node in slot.material.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                node.inputs['Base Color'].default_value = (.025,.16,.12,1)
                node.inputs['Metallic'].default_value = .45
                node.inputs['Roughness'].default_value = .3
                node.inputs['Emission Color'].default_value = (.01,.28,.17,1)
                node.inputs['Emission Strength'].default_value = .3
# Independent camera: scene animation and the original .blend stay untouched.
camdata = bpy.data.cameras.new('AURA turntable camera')
cam = bpy.data.objects.new('AURA turntable camera', camdata)
s.collection.objects.link(cam)
s.camera = cam
camdata.type = 'ORTHO'
camdata.ortho_scale = 142
for o in list(s.objects):
    if o.type == 'LIGHT':
        o.hide_render = True
for name, pos, energy, tint in [
    ('cyan key', (100,150,240), 450000, (.45,1,1)),
    ('white fill', (-150,40,160), 350000, (.8,1,.95)),
    ('emerald rim', (20,-150,20), 500000, (.1,1,.5)),
]:
    data = bpy.data.lights.new(name, 'AREA')
    data.energy, data.color, data.shape, data.size = energy, tint, 'DISK', 140
    obj = bpy.data.objects.new(name, data)
    s.collection.objects.link(obj)
    obj.location = center + Vector(pos)
    obj.rotation_euler = (center-obj.location).to_track_quat('-Z','Y').to_euler()
s.render.engine = 'BLENDER_EEVEE'
s.eevee.taa_render_samples = 8
s.render.resolution_x = s.render.resolution_y = 512
s.render.resolution_percentage = 100
s.render.film_transparent = True
s.render.image_settings.file_format = 'PNG'
s.render.image_settings.color_mode = 'RGBA'
s.render.use_compositing = False
s.render.use_sequencer = False
s.world.use_nodes = True
s.world.node_tree.nodes['Background'].inputs['Strength'].default_value = .35
out = ROOT / 'assets/clock'
out.mkdir(parents=True, exist_ok=True)
up = Vector((0, math.cos(math.radians(27)), -math.sin(math.radians(27))))
base = Vector((0, math.sin(math.radians(27)), math.cos(math.radians(27)))) * 300
for i in range(48):
    cam.location = center + Quaternion(up, i*math.tau/48) @ base
    forward = (center-cam.location).normalized()
    right = forward.cross(up).normalized()
    true_up = right.cross(forward).normalized()
    cam.rotation_euler = Matrix((right, true_up, -forward)).transposed().to_euler()
    s.render.filepath = str(out / f'{i:03d}.png')
    bpy.ops.render.render(write_still=True)
    print('AURA_FRAME', i, flush=True)
