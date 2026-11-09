import nuke

sep = ""
enumerationPulldown = "35 42 55 75 90 110"
enumerationColour = "Green Blue Red Orange"
appearanceOptions = "Border Fill"

def CY_Backdrop():
    global sep, enumerationPulldown, appearanceOptions
    selNodes = nuke.selectedNodes()
    if not selNodes:
        return nuke.alert("Please select Nodes!!!")

    customPreset = None
    presets = ['Green','Blue','Red','Orange' ]

    p = nuke.Panel('CY_Backdrop')
    p.addEnumerationPulldown('Preset:', ' '.join(presets))
    p.addSingleLineInput("Custom label:", sep)
    p.addEnumerationPulldown("Font Size:", enumerationPulldown)
    p.addEnumerationPulldown("Appearance:", appearanceOptions)
    result = p.show()
    if not result:
        return

    customPreset = p.value('Preset:')
    nameLabel = p.value("Custom label:")
    enumVal = p.value("Font Size:")
    enumCol = p.value("Colour:")
    appearance = p.value("Appearance:")

    # color
    if customPreset == "Green":
        enumCol = "Green"
    elif customPreset == "Blue":
        enumCol = "Blue"
    elif customPreset == "Red":
        enumCol = "Red"
    elif customPreset == "Orange":
        enumCol = "Orange"


    colour_dict = {
        "Green": (0, 0.259, 0.173),
        "Blue": (0.125, 0.278, 0.322),
        "Red": (0.439, 0.145, 0.184),
        "Orange": (0.427, 0.247, 0.165),

    }

    r, g, b = colour_dict.get(enumCol, (0.18, 0.18, 0.18))
    hexColour = int('%02x%02x%02x%02x' % (int(r * 255), int(g * 255), int(b * 255), 255), 16)

    if customPreset in presets:
        presetLabel = customPreset
    else:
        presetLabel = ""

    bdX = min([node.xpos() for node in selNodes])
    bdY = min([node.ypos() for node in selNodes])
    bdW = max([node.xpos() + node.screenWidth() for node in selNodes]) - bdX
    bdH = max([node.ypos() + node.screenHeight() for node in selNodes]) - bdY

    left, top, right, bottom = (-44, -125, 44, 44)
    bdX += left
    bdY += top
    bdW += (right - left)
    bdH += (bottom - top)

    if nameLabel == "":
        label = presetLabel
    else:
        label = nameLabel

    # Determinar el z_order
    selected_backdrops = [n for n in selNodes if n.Class() == "BackdropNode"]
    if selected_backdrops:
        min_selected_z_order = min([n['z_order'].value() for n in selected_backdrops])
        new_z_order = min_selected_z_order - 1
    else:

        existing_backdrops = [n for n in nuke.allNodes() if n.Class() == "BackdropNode"]
        max_z_order = max([n['z_order'].value() for n in existing_backdrops], default=-1)
        new_z_order = max_z_order + 1

    # Asegurarse de que no sea negativo
    if new_z_order < 0:
        new_z_order = 0

    # Crear el BackdropNode
    backdrop = nuke.nodes.BackdropNode(
        xpos=bdX,
        bdwidth=bdW,
        ypos=bdY,
        bdheight=bdH,
        note_font='Verdana',
        label=label,
        note_font_size=int(enumVal),
        note_font_color=hexColour,
        name='CY_Backdrop',
        tile_color=hexColour,
        gl_color=hexColour,
        appearance=appearance,
    )

    # Establecer el z_order calculado
    backdrop['z_order'].setValue(new_z_order)

    # Restaurar la selección original de nodos
    for node in selNodes:
        node['selected'].setValue(True)

    return backdrop

# Asegúrate de agregar esta función al menú o la barra de herramientas de Nuke si es necesario.
# nuke.menu('Nodes').addCommand('Custom/Backdrop', CY_Backdrop)
