##### TL Adapted Version of nukescripts\psd.py
##
##  Uses meta-data from the incoming image stream to break a PSD files into layers
##  Each layer is combined together with a PSDMerge node which emulates the blending modes
##

import nuke_internal as nuke
import random
import math
import threading

class Layer():
  def __init__(self):
    self.attrs = {}

def getLayers(metadata):
  layers = []
  for key in metadata:
    if key.startswith( 'input/psd/layers/' ):
      splitKey = key.split( '/' )
      num = int( splitKey[3] )
      attr = splitKey[4]
      try:
        attr += '/' + splitKey[5]
      except:
        pass
      while ( len(layers) <= num ):
        layers.append( Layer() )
      layers[num].attrs[ attr ] = metadata[key]
  return layers

def breakoutLayers( node, sRGB = True ):
  if not node:
    return

  nuke.Undo().begin()

  blendMap = {}
  blendMap['norm'] = "normal"
  blendMap['scrn'] = "screen"
  blendMap['div '] = "color dodge"
  blendMap['over'] = "overlay"
  blendMap['mul '] = "multiply"
  blendMap['dark'] = "darken"
  blendMap['idiv'] = "color burn"
  blendMap['lbrn'] = "linear burn"
  blendMap['lite'] = "lighten"
  blendMap['lddg'] = "linear dodge"
  blendMap['lgCl'] = "lighter color"
  blendMap['sLit'] = "soft light"
  blendMap['hLit'] = "hard light"
  blendMap['lLit'] = "linear light"
  blendMap['vLit'] = "vivid light"
  blendMap['pLit'] = "pin light"
  blendMap['hMix'] = "hard mix"
  blendMap['diff'] = "difference"
  blendMap['smud'] = "exclusion"
  blendMap['fsub'] = "subtract"
  blendMap['fdiv'] = "divide"
  blendMap['hue '] = "hue"
  blendMap['sat '] = "saturation"
  blendMap['colr'] = "color"
  blendMap['lum '] = "luminosity"

  metaData = node.metadata()
  layers = getLayers(metaData)

  # requested layout values
  xspacing = 220
  spacing  = 70

  # dot offsets
  dotXfudge = 34
  dotYfudge = 4

  x = node.xpos()
  y = node.ypos()
  curY = y + spacing * 2

  if not sRGB:
    colorSpace = nuke.nodes.Colorspace()
    colorSpace['channels'].setValue( 'all' )
    colorSpace['colorspace_out'].setValue( 'sRGB')
    colorSpace.setInput(0, node )
    colorSpace.setXYpos( x, curY )
    inputNode = colorSpace
  else:
    inputNode = node

  curX = x
  curY = y + spacing * 2
  topY  = curY

  lastLayer = None
  i = 0

  for l in layers:
    try:
      if l.attrs['divider/type'] > 0: ## hidden divider or start of group
        continue
    except:
      pass

    i = i + 1
    if i > 100:
      nuke.message( "Too many layers, stopping at layer 100." )
      break

    name = l.attrs['nukeName']
    pretty_label = l.attrs.get('name', name)

    curY = topY

    # dot ABOVE the Shuffle — carries the layer label
    dot = nuke.nodes.Dot()
    dot.setInput(0, inputNode)
    dot.setXYpos(curX + dotXfudge , curY + dotYfudge)

    inputNode = dot
    try:
      dot['label'].setValue(pretty_label)
      dot['note_font_size'].setValue(20)
      dot['note_font_color'].setValue(int(0x8E8A7A00))
    except:
      pass

    curY += spacing

    shuffle = nuke.nodes.Shuffle()
    shuffle['label'].setValue(name)
    shuffle['in'].setValue(name)
    shuffle['in2'].setValue('none')
    shuffle['red'].setValue('red')
    shuffle['green'].setValue('green')
    shuffle['blue'].setValue('blue')
    shuffle['alpha'].setValue('alpha')

    ## if no 'alpha' assume alpha of 1
    alphaChan = name + ".alpha"
    if not alphaChan in inputNode.channels():
      shuffle['alpha'].setValue('white')

    shuffle['black'].setValue('red2')
    shuffle['white'].setValue('green2')
    shuffle['red2'].setValue('blue2')
    shuffle['green2'].setValue('alpha2')

    shuffle['out'].setValue('rgba')
    shuffle['out2'].setValue('none')

    shuffle.setInput(0, inputNode)
    shuffle.setXYpos(curX, curY)

    curY += spacing

    crop = nuke.nodes.Crop()
    crop['box'].setValue(l.attrs['x'], 0)
    crop['box'].setValue(l.attrs['y'], 1)
    crop['box'].setValue(l.attrs['r'], 2)
    crop['box'].setValue(l.attrs['t'], 3)
    crop.setInput(0, shuffle)
    crop.setXYpos(curX, curY)

    curY += spacing * 2

    layer = crop

    try:
      operation = blendMap[l.attrs['blendmode']]
    except:
      print("unknown blending mode " + l.attrs.get('blendmode', ''))
      operation = "normal"

    if lastLayer:
      psdMerge = nuke.nodes.PSDMerge()
      psdMerge['operation'].setValue(operation)
      psdMerge.setInput(0, lastLayer)
      psdMerge.setInput(1, layer)
      psdMerge.setXYpos(curX, curY)
      psdMerge['sRGB'].setValue(sRGB)
      psdMerge['mix'].setValue((l.attrs['opacity'] / 255.0))
      try:
        if (l.attrs['mask/disable'] != True):
          psdMerge['maskChannelInput'].setValue(name + '.mask')
          if (l.attrs['mask/invert'] == True):
            psdMerge['invert_mask'].setValue(True)
      except:
        pass
      lastLayer = psdMerge
    else:
      first_dot = nuke.nodes.Dot()
      first_dot.setInput(0, layer)
      first_dot.setXYpos(curX + dotXfudge, curY + dotYfudge)
      lastLayer = first_dot

    curY += spacing
    curX += xspacing

  if not sRGB:
    colorSpace2 = nuke.nodes.Colorspace()
    colorSpace2['channels'].setValue('all')
    colorSpace2['colorspace_in'].setValue('sRGB')
    colorSpace2.setInput(0, lastLayer)
    colorSpace2.setXYpos(lastLayer.xpos(), lastLayer.ypos() + 2 * spacing)

  nuke.Undo().end()

class BreakoutThreadClass(threading.Thread):
  def __init__(self, node):
    threading.Thread.__init__(self)
    self.node = node
  def run(self):
    nuke.executeInMainThread(breakoutLayers, self.node)

# ============================================================
# Helper: set Card/Card2 Z safely (tries 'z', 'tz', then translate.z)
# ============================================================
def _set_card_z(card_node, z_value):
  try:
    card_node['z'].setValue(float(z_value))
    return True
  except Exception:
    pass
  try:
    card_node['tz'].setValue(float(z_value))
    return True
  except Exception:
    pass
  try:
    card_node['translate'].setValue(float(z_value), 2)  # index 2 = Z
    return True
  except Exception:
    pass
  return False

# ======================================================================
#  Override: Breakout button pops a menu with THREE actions
#     - Break out layers (stock 2D)
#     - Break out 3D (Card2 → Dot → Scene/Camera/Scanline)
#     - Edit PSD in Photoshop
# ======================================================================

def doReaderBreakout():
  """
  Popup menu on 'Breakout layers' with three options:
    • Break out layers  (2D – stock behavior)
    • Break out 3D      (Shuffle→Dot→Premult→Crop→Card2(1x1)→Dot; Scene/Camera/SLR)
    • Edit PSD in Photoshop
  """
  import os, platform, subprocess, nuke, threading

  node = nuke.thisNode()  # the Read node

  # --- helpers ---
  def _ps_path():
    env = os.environ.get("PHOTOSHOP_PATH", "").strip()
    if env:
      return env
    if platform.system() == "Windows":
      return r"C:\Program Files\Adobe\Adobe Photoshop 2026\Photoshop.exe"
    elif platform.system() == "Darwin":
      return "/Applications/Adobe Photoshop 2025/Adobe Photoshop 2025.app"
    return ""  # Linux/unknown

  def _launch_photoshop(filepath):
    if not filepath or not os.path.isfile(filepath):
      try: nuke.message("File not found:\n{}".format(filepath))
      except: pass
      return
    pspath = _ps_path()
    if not pspath:
      try: nuke.message("Could not determine Photoshop path for this OS.")
      except: pass
      return
    if platform.system() == "Windows":
      filepath_norm = os.path.normpath(os.path.expandvars(os.path.expanduser(filepath)))
      pspath_norm   = os.path.normpath(os.path.expandvars(os.path.expanduser(pspath)))
    else:
      filepath_norm, pspath_norm = filepath, pspath
    try:
      if platform.system() == "Windows":
        subprocess.Popen([pspath_norm, filepath_norm])
      else:
        if pspath_norm.endswith(".app"):
          subprocess.Popen(["open", "-a", pspath_norm, filepath_norm])
        else:
          subprocess.Popen([pspath_norm, filepath_norm])
    except Exception as e:
      try: nuke.message("Failed to launch Photoshop:\n{}".format(e))
      except: pass

  def _breakout_2d():
    # Keep Foundry's original thread workaround
    try:
      global readerBreakoutThread
      readerBreakoutThread = BreakoutThreadClass(node)
      readerBreakoutThread.start()
    except Exception:
      try: nuke.executeInMainThread(breakoutLayers, node)
      except: pass

  def _breakout_3d():
    """
    Build **per layer**:
      Shuffle -> Dot -> Premult -> Crop -> Card2(1x1) -> Dot
    Then put all dots into a Scene; create a Camera (haperture=50) and plug it
    into both the Scene and a ScanlineRender. Place Scene/Camera/SLR under
    the **last layer column**. Set Card Z from 100 (first) to 10 (last),
    evenly spaced (clamped to [10..100]).
    """
    try:
      nuke.Undo().begin("PSD Breakout 3D")

      meta = node.metadata()
      all_layers = getLayers(meta)

      # Filter out group dividers (match stock logic)
      layers = []
      for l in all_layers:
        try:
          if l.attrs.get('divider/type', 0) > 0:
            continue
        except Exception:
          pass
        layers.append(l)

      if not layers:
        nuke.message("No PSD layers found to break out.")
        return

      # Z spacing: first=100, last=10, evenly spaced, clamp to [10..100]
      n = len(layers)
      z_first, z_last = 100.0, 10.0
      if n == 1:
        z_vals = [z_first]
      else:
        step = (z_first - z_last) / float(n - 1)
        z_vals = [z_first - i * step for i in range(n)]
      z_vals = [max(10.0, min(100.0, z)) for z in z_vals]

      # Positions
      x0, y0 = node.xpos(), node.ypos()
      x_spacing = 220
      y_spacing = 80
      dot_dx, dot_dy = 34, 4

      card_dots = []
      last_col_x = x0
      last_col_lowest_y = y0

      # Build streams
      for idx, l in enumerate(layers):
        lname = l.attrs.get('nukeName', 'Layer_%d' % idx)

        # Source dot (connect Shuffle to a dot like the original)
        src_dot = nuke.nodes.Dot()
        src_dot.setInput(0, node)
        src_dot.setXYpos(x0 + idx * x_spacing + dot_dx, y0 + y_spacing * 2 - (spacing := 0) + dot_dy)

        # Shuffle
        sh = nuke.nodes.Shuffle()
        sh['label'].setValue(lname)
        sh['in'].setValue(lname)
        sh['in2'].setValue('none')
        sh['red'].setValue('red')
        sh['green'].setValue('green')
        sh['blue'].setValue('blue')
        sh['alpha'].setValue('alpha')
        # If no alpha, force white so Premult behaves
        alphaChan = lname + ".alpha"
        try:
          if alphaChan not in node.channels():
            sh['alpha'].setValue('white')
        except Exception:
          pass
        sh['out'].setValue('rgba')
        sh['out2'].setValue('none')
        sh.setInput(0, src_dot)
        sh.setXYpos(x0 + idx * x_spacing, y0 + y_spacing * 2)

        # Premult
        pm = nuke.nodes.Premult()
        pm.setInput(0, sh)
        pm.setXYpos(sh.xpos(), sh.ypos() + y_spacing)

        # Crop (to layer bounds)
        cp = nuke.nodes.Crop()
        try:
          cp['box'].setValue(l.attrs['x'], 0)
          cp['box'].setValue(l.attrs['y'], 1)
          cp['box'].setValue(l.attrs['r'], 2)
          cp['box'].setValue(l.attrs['t'], 3)
        except Exception:
          pass
        cp.setInput(0, pm)
        cp.setXYpos(pm.xpos(), pm.ypos() + y_spacing)

        # Card2, subdivisions 1x1
        card = nuke.nodes.Card2()
        for k, v in (('rows', 1), ('columns', 1),
                     ('subdivisions_x', 1), ('subdivisions_y', 1)):
          try:
            card[k].setValue(v)
          except Exception:
            pass
        card.setInput(0, cp)
        card.setXYpos(cp.xpos(), cp.ypos() + y_spacing)

        # Z translate via helper
        _set_card_z(card, z_vals[idx])

        # Dot after Card2 (for tidy Scene wiring)
        d = nuke.nodes.Dot()
        d.setInput(0, card)
        d.setXYpos(card.xpos() + dot_dx, card.ypos() + dot_dy)
        card_dots.append(d)

        # track last column placement
        last_col_x = sh.xpos()
        last_col_lowest_y = max(last_col_lowest_y, d.ypos())

      # Scene under last layer
      scene = nuke.nodes.Scene()
      scene.setXYpos(last_col_x, last_col_lowest_y + y_spacing)

      for i, src in enumerate(card_dots):
        try:
          scene.setInput(i, src)
        except Exception:
          pass

      # Camera (haperture=50), placed under Scene
      try:
        cam = nuke.nodes.Camera2()
      except Exception:
        cam = nuke.nodes.Camera()
      try:
        cam['haperture'].setValue(50.0)
      except Exception:
        pass
      cam.setXYpos(last_col_x, scene.ypos() + y_spacing)

      # Connect camera to Scene as additional input
      try:
        scene.setInput(len(card_dots), cam)
      except Exception:
        pass

      # ScanlineRender under Camera
      sl = nuke.nodes.ScanlineRender()
      sl.setXYpos(last_col_x, cam.ypos() + y_spacing)
      try:
        sl.setInput(1, scene)   # scene input
      except Exception:
        pass
      try:
        sl.setInput(2, cam)     # camera input
      except Exception:
        pass

    finally:
      try: nuke.Undo().end()
      except Exception: pass

  # --- UI menu (Qt) ---
  try:
    try:
      from PySide2 import QtWidgets, QtGui
    except Exception:
      from PySide import QtGui
      QtWidgets = QtGui

    menu = QtWidgets.QMenu("PSD actions")
    act_breakout2d = menu.addAction("Break out layers")
    act_breakout3d = menu.addAction("Break out 3D")
    act_edit       = menu.addAction("Edit PSD in Photoshop")

    choice = menu.exec_(QtGui.QCursor.pos())
    if choice == act_breakout2d:
      _breakout_2d(); return
    if choice == act_breakout3d:
      if threading.current_thread() is threading.main_thread():
        _breakout_3d()
      else:
        nuke.executeInMainThread(_breakout_3d)
      return
    if choice == act_edit:
      try: _launch_photoshop(node["file"].value())
      except: pass
      return
    # dismissed: default to 2D breakout (original behavior)
    _breakout_2d(); return
  except Exception:
    pass

  # --- Fallback panel if Qt missing ---
  try:
    p = nuke.Panel("PSD actions")
    p.addEnumerationPulldown("Action", "Breakout_2D Breakout_3D Edit_in_Photoshop")
    if not p.show():
      return
    action = p.value("Action")
    if action == "Breakout_2D":
      _breakout_2d()
    elif action == "Breakout_3D":
      _breakout_3d()
    else:
      _launch_photoshop(node["file"].value())
  except Exception:
    _breakout_2d()
