
"""
:module: smeardeform.deformer

Smeardeform deformer functions

In here you have all the basic functions in order to correctly apply Maya's
Lattice deformer inside an animation rig.

:author: Jerome Drese
"""

# imports
from maya import cmds
import random


def _hold_selection(function):
    """Holds the current Maya selection after running the function

    :param function: your decorated function
    :type function: function

    :return: your decorated function
    :rtype: function
    """

    def wrapper_function(*args, **kwars):

        # gets selection
        sel = cmds.ls(selection=True)

        # runs decorated function
        function_exec = function(*args, **kwars)

        # selects back
        cmds.select(sel, replace=True)

        return function_exec

    return wrapper_function


def apply_smear_deformer(shapes, width_div, height_div, depth_div):
    """Apply a Lattice deformer to the given shapes

    :param shapes: Mesh shapes to deform
    :type shapes: list

    :param width_div: number of width divisions
    :type width_div: int

    :param height_div: number of height divisions
    :type height_div: int

    :param depth_div: number of depth divisions
    :type depth_div: int

    :return: The lattice root, cage and base dag nodes and lattice deformer
    :rtype: str, str, str, str

    ..todo:: - add more description about how this works
             - add return values
    """

    # defines unique name
    idx = 1
    deformer_name = "smear_deform_{}"
    while cmds.objExists("{}_grp".format(deformer_name.format(idx))):
        idx += 1

    # defines command flags
    settings = {}
    settings["name"] = deformer_name.format(idx)
    settings["before"] = True
    settings["divisions"] = (int(width_div), int(height_div), int(depth_div))
    settings["commonParent"] = True
    settings["objectCentered"] = True
    settings["ldivisions"] = (2, 2, 2)
    settings["outsideLattice"] = 1

    # creates deformer
    lat_deformer = cmds.lattice(shapes, **settings)

    # sets unique naming
    ffd = cmds.rename(lat_deformer[0], "{}_ffd"
                      .format(deformer_name.format(idx)))
    lattice_cage = cmds.rename(lat_deformer[1], "{}_lattice"
                               .format(deformer_name.format(idx)))
    lattice_base = cmds.rename(lat_deformer[2], "{}_base"
                               .format(deformer_name.format(idx)))
    top_node = cmds.rename("{}Group".format(lat_deformer[1]), "{}_grp"
                           .format(deformer_name.format(idx)))

    # freezes transform values by transmitting them into the top node parent
    position = cmds.xform(lattice_cage, query=True, worldSpace=True,
                          matrix=True)
    [cmds.xform(x, worldSpace=True, matrix=position)
     for x in (top_node, lattice_cage, lattice_base)]

    # hides certain things to avoid conflicts
    cmds.setAttr("{}.hiddenInOutliner".format(top_node), True)
    cmds.setAttr("{}.hiddenInOutliner".format(lattice_cage), True)
    cmds.setAttr("{}.visibility".format(lattice_base), False)
    cmds.setAttr("{}Shape.ihi".format(lattice_cage), False)

    return top_node, lattice_cage, lattice_base, ffd


def create_lattice_control(control_name, control_color):
    """Creates an anim-able control

    :param control_name: Name for the control
    :type control_name: str

    :param control_color: Color for the control
    :type control_color: [float, float, float]
    """

    # create animation control
    lat_ctrl = cmds.circle(name=control_name, sections=16, normal=(0, 1, 0),
                           constructionHistory=False)[0]

    # set properties
    cmds.setAttr("{}.lineWidth".format(lat_ctrl), 2)
    cmds.setAttr("{}Shape.overrideEnabled".format(lat_ctrl), 1)
    cmds.setAttr("{}Shape.overrideRGBColors".format(lat_ctrl), True)
    cmds.setAttr("{}Shape.overrideColorR".format(lat_ctrl), control_color[0])
    cmds.setAttr("{}Shape.overrideColorG".format(lat_ctrl), control_color[1])
    cmds.setAttr("{}Shape.overrideColorB".format(lat_ctrl), control_color[2])

    # set shape form
    points = {"cv[0]": [0.8, 0, -1],
              "cv[2]": [-0.8, 0, -1],
              "cv[3]": [-1, 0, -1],
              "cv[4]": [-1, 0, -0.8],
              "cv[6]": [-1, 0, 0.8],
              "cv[7]": [-1, 0, 1],
              "cv[8]": [-0.8, 0, 1],
              "cv[10]": [0.8, 0, 1],
              "cv[11]": [1, 0, 1],
              "cv[12]": [1, 0, 0.8],
              "cv[14]": [1, 0, -0.8],
              "cv[15]": [1, 0, -1],
              }

    for cv in points:
        cmds.xform("{}.{}".format(lat_ctrl, cv), worldSpace=True,
                   translation=points[cv])

    create_lattice_control_attributes(lat_ctrl)
    return lat_ctrl


def create_lattice_control_attributes(lat_ctrl):
    """Creates channel box attributes for the given lat control

    :param lat_ctrl: lattice control name
    :type lat_ctrl: str
    """

    # adds extra attributes
    cmds.addAttr(lat_ctrl, longName="latticePoints", attributeType="message",
                 keyable=False)
    cmds.addAttr(lat_ctrl, longName="settings", niceName="-- SETTINGS --",
                 attributeType="bool", keyable=True)
    cmds.setAttr("{}.settings".format(lat_ctrl), keyable=False,
                 channelBox=True, lock=True)
    # playback attribute remap
    cmds.addAttr(lat_ctrl, longName="showLatticeCage",
                 attributeType="bool", keyable=True, defaultValue=True)
    cmds.setAttr("{}.showLatticeCage".format(lat_ctrl), keyable=False,
                 channelBox=True)
    cmds.addAttr(lat_ctrl, longName="hideplayback",
                 niceName="Hide while playing",
                 attributeType="bool", keyable=True)
    cmds.setAttr("{}.hideplayback".format(lat_ctrl), keyable=False,
                 channelBox=True)
    cmds.setAttr("{}.hideplayback".format(lat_ctrl), True)
    cmds.connectAttr("{}.hideplayback".format(lat_ctrl),
                     "{}.hideOnPlayback".format(lat_ctrl))

    # smear type
    cmds.addAttr(lat_ctrl, longName="smearType", niceName="Smear Type",
                 attributeType="enum", enumName="Inside:All", keyable=True,
                 dv=1)
    cmds.setAttr("{}.smearType".format(lat_ctrl), keyable=False,
                 channelBox=True)

    # smear attribute
    cmds.addAttr(lat_ctrl, longName="smear", niceName="Smear on/off",
                 attributeType="double", minValue=0.0, maxValue=1.0,
                 defaultValue=1.0, keyable=True)

    # visibility attr tweak
    cmds.setAttr("{}.visibility".format(lat_ctrl), keyable=False,
                 channelBox=True)


def delete_smear_deformer():
    """Deletes selected smear deformer
    """

    selection = cmds.ls(selection=True)

    if not len(selection):
        return

    for sel in selection:
        if not cmds.objExists("{}.root_node".format(sel)):
            continue
        try:
            cmds.delete(cmds.listConnections("{}.root_node".format(sel)))
        except RuntimeError as error:
            raise error


def get_geometry_grp_from_selection(geo_group_name="geo_grp"):
    """Returns the GEO transform DAG node from selected animation control

    :returns: The rig **GEO** group DAG node
    :rtype: str
    """

    # gets current selection
    selection = cmds.ls(selection=True)

    if len(selection) > 0:
        has_namespace = ":" in selection[0]

        if not has_namespace:
            cmds.inViewMessage(message="Please make sure you have a referenced rig before using Smear Deform",
                        fade=True, position="midCenter", fontSize=40,
                        fadeStayTime=800, fadeOutTime=100, dragKill=True,
                        bkc=0x00154060, alpha=0.7)
            return

        # returns if invalid selection
        if len(selection) != 1:
            cmds.inViewMessage(message="Select (only) one animation control",
                            fade=True, position="midCenter", fontSize=40,
                            fadeStayTime=800, fadeOutTime=100, dragKill=True,
                            bkc=0x00154060, alpha=0.7)
            return
        
        # split to get the namespace
        namespace = selection[0].split(":")[0]

        # returns if GEO group doesn't exists inside that namespace
        if not cmds.objExists("{}:{}".format(namespace, geo_group_name)):
            cmds.inViewMessage(
                message="Couldn't find {0} from selection".format(geo_group_name),
                fade=True, position="midCenter", fontSize=40,
                fadeStayTime=800, fadeOutTime=100,
                dragKill=True, bkc=0x00154060, alpha=0.7)
            return

        return "{}:{}".format(namespace, geo_group_name)
    else:
        cmds.inViewMessage(
            message="Please select a rig control",
            fade=True, position="midCenter", fontSize=40,
            fadeStayTime=800, fadeOutTime=100,
            dragKill=True, bkc=0x00154060, alpha=0.7)

def get_scene_cameras():
    """Returns the non orthographic scene cameras
    """

    # stores good cameras
    cams = []

    [cams.append(x) for x in cmds.ls(type="camera")
     if not cmds.getAttr("{}.orthographic".format(x))]

    return cams


def get_valid_deform_shapes(dag_group, ignore_hidden=True):
    """Returns valid shapes to deform inside the given dag group

    This function takes a dag group node name and will search for children
    shapes inside of it and only return valid mesh shapes.

    The term **valid** here means that we will ignore shapes that are inside
    the dag group that are intermediate objects or shapes that are used on
    the chain of deformation of another shape. We filter this to avoid having
    double transformations when applying a deformer to the query result.

    :param dag_group: Maya DAG group name
    :type dag_group: str

    :param ignore_hidden: Filtering will ignore hidden shapes
    :type ignore_hidden: bool

    :returns: Mesh shapes
    :rtype: list
    """

    # query all mesh shapes inside the dag_group by filtering intermediates
    shapes = cmds.ls(cmds.listRelatives(dag_group, allDescendents=True,
                                        type="mesh"), noIntermediate=True)

    # will store invalid shapes
    invalid_shapes = []

    # filter shapes used on another shape deformation history
    for shape in shapes:
        [invalid_shapes.append(x)
         for x in cmds.ls(cmds.listHistory(shape), type="mesh")
         if x != shape and x in shapes and x not in invalid_shapes]

        # filters non visible shapes
        if not len(cmds.ls(shape, visible=ignore_hidden)):
            invalid_shapes.append(shape)

    # removes invalid shapes from shapes
    [shapes.remove(x) for x in invalid_shapes]

    return shapes


def key_control(control, attribute):
    """Key the given control and attribute at frame, before and after

    :param control: the control name
    :type control: str

    :param attribute: the attribute name
    :type attribute: str
    """

    current_time = cmds.currentTime(query=True)
    cmds.setKeyframe("{}.{}".format(control, attribute), time=current_time,
                     inTangentType="linear", outTangentType="linear",
                     value=1.0)
    cmds.setKeyframe("{}.{}".format(control, attribute), time=current_time - 1,
                     inTangentType="linear", outTangentType="linear",
                     value=0.0,)
    cmds.setKeyframe("{}.{}".format(control, attribute), time=current_time + 1,
                     inTangentType="linear", outTangentType="linear",
                     value=0.0,)


def key_points():
    """Key lattice cage from selection
    """

    print("Keying lattice cage")

    # gets current selection
    selection = cmds.ls(selection=True)

    # returns if invalid selection
    if len(selection) != 1:
        cmds.inViewMessage(message="Select (only) one animation control",
                           fade=True, position="midCenter", fontSize=40,
                           fadeStayTime=800, fadeOutTime=100, dragKill=True,
                           bkc=0x00154060, alpha=0.7)
        return

    if not cmds.objExists("{}.latticePoints".format(selection[0])):
        cmds.inViewMessage(message="Select a Smear control",
                           fade=True, position="midCenter", fontSize=40,
                           fadeStayTime=800, fadeOutTime=100, dragKill=True,
                           bkc=0x00154060, alpha=0.7)
        return

    try:
        cmds.setKeyframe("{}.pnts[*]".format(selection[0]))
    except ValueError:
        cage = cmds.listConnections("{}.latticePoints".format(selection[0]))
        cmds.setKeyframe("{}.pt[*]".format(cage[0]))


def lock_attributes(node, tr=True, rt=True, sc=True, vis=True):
    """Locks and hides attributes on the given node

    :param node: Node to interact with
    :type node: str
    """

    axes = ("x", "y", "z")
    {cmds.setAttr("{}.t{}".format(node, axe), lock=True, keyable=False)
     for axe in axes if tr}
    {cmds.setAttr("{}.r{}".format(node, axe), lock=True, keyable=False)
     for axe in axes if rt}
    {cmds.setAttr("{}.s{}".format(node, axe), lock=True, keyable=False)
     for axe in axes if sc}

    if vis:
        cmds.setAttr("{}.visibility".format(node), lock=True, keyable=False)


def reset_smear_deformer_points():
    """Reset points on selected smear deformer
    """

    cmds.undoInfo(openChunk=True)
    try:
        cmds.lattice(edit=True, latticeReset=True)
    except RuntimeError:
        for pnt in cmds.ls(".pnts[*]", flatten=True):
            cmds.setAttr("{}.pntx".format(pnt), 0.0)
            cmds.setAttr("{}.pnty".format(pnt), 0.0)
            cmds.setAttr("{}.pntz".format(pnt), 0.0)
    cmds.undoInfo(closeChunk=True)


@_hold_selection
def setup_smear_deformer(space, resolution=[3, 3, 3], ignore_hidden=True,
                         color=[random.random(),
                                random.random(),
                                random.random()],
                         autokey=True,
                         camera=None,
                         follow=True):
    """Creates a Smear deformer setup on the given space

    :param space: object / camera
    :type space: str

    :param resolution: Resolution for the Smear deformer
    :type resolution: [int, int int]

    :param ignore_hidden: Hidden shapes wont be deformed
    :type ignore_hidden: bool

    :param color: Color for the deformer and control
    :type color: [float, float, float]

    :param autokey: Add keyframes on and off automate
    :type autokey: bool

    :param camera: Camera to use for the camera space deformer
    :type camera: str

    :param follow: Smear follows camera view
    :type follow: bool
    """

    cmds.undoInfo(openChunk=True)
    if space == "object":
        setup_smear_deformer_object(color, resolution, ignore_hidden, autokey)
    else:
        setup_smear_deformer_camera(camera, color, resolution, ignore_hidden,
                                    autokey, follow)
    cmds.undoInfo(closeChunk=True)


def setup_smear_deformer_camera(camera, color, resolution=[3, 3],
                                ignore_hidden=True, autokey=True, follow=True):
    """Creates an anim-able Smear deformer rig

    :param camera: Camera to use for the camera space deformer
    :type camera: str

    :param color: Color for the deformer and control
    :type color: [float, float, float]

    :param resolution: Resolution for the Smear deformer
    :type resolution: [int, int]

    :param ignore_hidden: Hidden shapes wont be deformed
    :type ignore_hidden: bool

    :param autokey: Add keyframes on and off automate
    :type autokey: bool

    :param follow: Smear follows camera view
    :type follow: bool
    """

    # gets geometry group from selection
    geo_group = get_geometry_grp_from_selection()

    if not geo_group:
        return

    # query shapes to deform inside that geometry group
    shapes = get_valid_deform_shapes(geo_group, ignore_hidden)

    # gets camera transform
    camera_transform = cmds.listRelatives(camera, parent=True)[0]

    # creates lattice Maya deformer
    lattice_group, cage, base, ffd = apply_smear_deformer(shapes,
                                                          resolution[1] + 2,
                                                          resolution[0] + 2,
                                                          2)

    cmds.setAttr("{}Shape.overrideEnabled".format(cage), 1)
    cmds.setAttr("{}Shape.overrideRGBColors".format(cage), True)
    cmds.setAttr("{}Shape.overrideColorR".format(cage), color[0])
    cmds.setAttr("{}Shape.overrideColorG".format(cage), color[1])
    cmds.setAttr("{}Shape.overrideColorB".format(cage), color[2])

    # gets lattice creation position
    lattice_position = cmds.xform(lattice_group, query=True, worldSpace=True,
                                  translation=True)

    # sets lattice group position and orientation
    camera_position = cmds.xform(camera_transform, query=True, worldSpace=True,
                                 translation=True)
    camera_orientation = cmds.xform(camera_transform, query=True,
                                    worldSpace=True, rotation=True)
    cmds.xform(lattice_group, worldSpace=True, translation=camera_position)
    cmds.xform(lattice_group, worldSpace=True, rotation=camera_orientation)

    # creates rig root
    root = cmds.createNode("transform", name=lattice_group.replace("grp",
                                                                   "rig"))
    cmds.xform(root, worldSpace=True, translation=lattice_position)
    cmds.xform(root, worldSpace=True, rotation=camera_orientation)

    # creates rig hierarchy
    cmds.parent(lattice_group, root)
    cmds.setAttr("{}.translateZ".format(lattice_group), 0.0)

    # reset lattice points absolute position by applying an intermediate shape
    cmds.delete(cmds.cluster(cage))

    # creates control plane
    control_plane = cmds.polyPlane(name=lattice_group.replace(
                                   "grp", "ctrl"),
                                   constructionHistory=False,
                                   subdivisionsWidth=resolution[1] + 1,
                                   subdivisionsHeight=resolution[0] + 1)[0]
    cmds.setAttr("{}.rotateX".format(control_plane), 90)
    cmds.makeIdentity(control_plane, apply=True, rotate=True)
    create_lattice_control_attributes(control_plane)
    cmds.connectAttr("{}.message".format(control_plane),
                     "{}.latticePoints".format(control_plane))
    cmds.setAttr("{}Shape.overrideEnabled".format(control_plane), True)
    cmds.setAttr("{}Shape.overrideShading".format(control_plane), False)
    [cmds.setAttr("{}Shape.{}".format(control_plane, x), False)
     for x in ("castsShadows", "primaryVisibility", "visibleInReflections",
               "visibleInRefractions")]
    cmds.setAttr("{}Shape.overrideEnabled".format(control_plane), 1)
    cmds.setAttr("{}Shape.overrideRGBColors".format(control_plane), True)
    cmds.setAttr("{}Shape.overrideColorR".format(control_plane), color[0])
    cmds.setAttr("{}Shape.overrideColorG".format(control_plane), color[1])
    cmds.setAttr("{}Shape.overrideColorB".format(control_plane), color[2])
    cmds.setAttr("{}.showLatticeCage".format(control_plane), False)

    # set control position and reset size to match lattice
    cmds.parent(control_plane, lattice_group)
    cmds.makeIdentity(control_plane, translate=True, rotate=True, scale=True)

    # resets control plane vertices position values
    cmds.delete(control_plane, cmds.cluster(control_plane),
                constructionHistory=True)

    # sets smear size to match camera view resolution gate
    width = cmds.getAttr("defaultResolution.width")
    height = cmds.getAttr("defaultResolution.height")
    cmds.setAttr("{}.scaleX".format(lattice_group), width * 0.04)
    cmds.setAttr("{}.scaleY".format(lattice_group), height * 0.04)

    # creates offset node
    lat_ctrl_offset = cmds.createNode("transform", name=lattice_group.replace(
                                      "grp", "offset"), parent=lattice_group)
    cmds.setAttr("{}.scale".format(lat_ctrl_offset), 0.5, 0.5, 0.5)

    # parents offset node to root
    cmds.parent(lat_ctrl_offset, root)
    cmds.parent(control_plane, lat_ctrl_offset)
    cmds.parent(lattice_group, control_plane)
    cmds.makeIdentity(control_plane, translate=True, rotate=True, scale=True)

    # connects control plane vertices position to the lattice points position
    idx = 0

    # we loop twice to get the matching lattice point
    # this is needed due to the lattice points attribute structure been a
    # 3 digits list [x][y][z]
    for y in range(resolution[0] + 2):
        for x in range(resolution[1] + 2):
            for z in range(2):
                cmds.connectAttr("{}.pnts[{}]".format(control_plane, idx),
                                 "{}.pt[{}][{}][{}]".format(cage, x, y, z),
                                 force=True)
            idx += 1

    # connects attributes
    cmds.connectAttr("{}.smear".format(control_plane),
                     "{}.envelope".format(ffd))
    cmds.connectAttr("{}.smearType".format(control_plane),
                     "{}.outsideLattice".format(ffd))
    cmds.connectAttr("{}.showLatticeCage".format(control_plane),
                     "{}.lodVisibility".format(cage))

    # sets default for camera base
    cmds.setAttr("{}.smearType".format(control_plane), 0)

    # the following code is a hack for the evaluation manager.
    # the lattice points not been updated while evaluating frames, we create
    # an expression that will force evaluation on the lattice cage on a frame
    # basis
    cmds.expression(name=lattice_group.replace("grp", "force_eval_exp"),
                    object=lattice_group, string="tx=time*0;")

    if follow:
        # we constraint the smear rig to the camera
        _cst = cmds.parentConstraint(camera_transform, root,
                                     maintainOffset=True)
        cmds.setAttr("{}.hiddenInOutliner".format(_cst[0]), True)

    # clean up attributes
    [lock_attributes(x) for x in (base, cage, lattice_group, lat_ctrl_offset)]
    lock_attributes(root, vis=False)
    cmds.setAttr("{}.visibility".format(root), keyable=False, channelBox=True)

    [cmds.addAttr(x, longName="root_node", attributeType="message")
     for x in (cage, control_plane, root)]
    [cmds.connectAttr("{}.message".format(root), "{}.root_node".format(x))
     for x in (cage, control_plane, root)]

    if autokey:
        key_control(control_plane, "smear")


def setup_smear_deformer_object(color, resolution=[3, 3, 3],
                                ignore_hidden=True,
                                autokey=True):
    """Creates an anim-able Smear deformer rig

    :param color: Color for the deformer and control
    :type color: [float, float, float]

    :param resolution: Resolution for the Smear deformer
    :type resolution: [int, int int]

    :param ignore_hidden: Hidden shapes wont be deformed
    :type ignore_hidden: bool

    :param autokey: Add keyframes on and off automate
    :type autokey: bool
    """

    # gets geometry group from selection
    geo_group = get_geometry_grp_from_selection()

    if not geo_group:
        return

    # query shapes to deform inside that geometry group
    shapes = get_valid_deform_shapes(geo_group, ignore_hidden)

    # creates lattice Maya deformer
    lattice_group, cage, base, ffd = apply_smear_deformer(shapes,
                                                          resolution[1],
                                                          resolution[0],
                                                          resolution[2])

    cmds.setAttr("{}Shape.overrideEnabled".format(cage), 1)
    cmds.setAttr("{}Shape.overrideRGBColors".format(cage), True)
    cmds.setAttr("{}Shape.overrideColorR".format(cage), color[0])
    cmds.setAttr("{}Shape.overrideColorG".format(cage), color[1])
    cmds.setAttr("{}Shape.overrideColorB".format(cage), color[2])

    # creates rig root
    root = cmds.createNode("transform", name=lattice_group.replace("grp",
                                                                   "rig"))
    position = cmds.xform(lattice_group, query=True, worldSpace=True,
                          matrix=True)
    cmds.xform(root, worldSpace=True, matrix=position)

    # create animation control
    lat_ctrl = create_lattice_control(control_name=lattice_group.replace(
                                      "grp", "ctl"), control_color=color)
    cmds.addAttr(cage, longName="latticePoints", attributeType="message",
                 keyable=False)

    # creates rig hierarchy
    cmds.parent(lat_ctrl, root)
    cmds.xform(lat_ctrl, worldSpace=True, matrix=position)
    cmds.makeIdentity(root, apply=True, scale=True)
    cmds.parent(lattice_group, lat_ctrl)
    cmds.parent(cage, lat_ctrl)
    cmds.connectAttr("{}.smear".format(lat_ctrl), "{}.envelope".format(ffd))
    cmds.connectAttr("{}.smearType".format(lat_ctrl),
                     "{}.outsideLattice".format(ffd))
    cmds.connectAttr("{}.showLatticeCage".format(lat_ctrl),
                     "{}.lodVisibility".format(cage))
    [lock_attributes(x) for x in (base, cage, lattice_group)]
    cmds.setAttr("{}.visibility".format(root), keyable=False, channelBox=True)

    cmds.connectAttr("{}.message".format(cage),
                     "{}.latticePoints".format(lat_ctrl))
    cmds.connectAttr("{}.message".format(cage),
                     "{}.latticePoints".format(cage))
    [cmds.addAttr(x, longName="root_node", attributeType="message")
     for x in (cage, lat_ctrl, root)]
    [cmds.connectAttr("{}.message".format(root), "{}.root_node".format(x))
     for x in (cage, lat_ctrl, root)]

    if autokey:
        key_control(lat_ctrl, "smear")

    return root
