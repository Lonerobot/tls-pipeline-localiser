'''
Bake Expressions
Author: Nathan Rusch
Updated: January 27, 2013
'''
import nuke


def bakeExpressions(nodes=None, start=None, end=None, views=None):
    '''
    Bakes all expression-driven Array_Knob-derived knob components to keyframes
    over a given input frame range and list of views.

    'nodes': Optional iterable of nodes. If omitted, the current node selection
    will be used.

    'start'/'end': Optional frame values defining the range to bake. If 'start'
    is omitted, the script's first frame will be used; likewise, if 'end' is
    omitted, the last frame of the script will be used.

    'views': Optional list of views to bake. If omitted, all script views will
    be used.
    '''
    if nodes is None:
        nodes = nuke.selectedNodes()
    if not nodes:
        nuke.message('No nodes to bake')
        return

    scriptRange = nuke.root().frameRange()
    if start is None:
        start = scriptRange.first()
    if end is None:
        end = scriptRange.last()

    if views is None:
        views = nuke.views()
    elif not views:
        nuke.message('No views to bake')
        return
    elif not set(views).issubset(nuke.views()):
        nuke.message('Not all views in %s exist in script' % views)
        return

    for node in nodes:
        for knob in node.knobs().values():
            if isinstance(knob, nuke.Array_Knob):
                for view in views:
                    # There's currently no way to ask a knob if it has an
                    # expression at a given view, so we have to check the
                    # AnimationCurve objects for that. However, we can still
                    # use knob.isAnimated() to partially optimize this.
                    if knob.isAnimated(view=view):
                        aSize = 1 if knob.singleValue(view) else knob.arraySize()
                        for index in range(aSize):
                            anim = knob.animation(index, view=view)
                            if anim is None or anim.noExpression():
                                continue
                            for f in range(start, end + 1):
                                #knob.setValueAt(anim.evaluate(f), f, index)
                                anim.setKey(f, anim.evaluate(f))
                            knob.setExpression('curve', channel=index, view=view)
                            # Even if the expression would have evaluated to a
                            # constant (flat) curve, we can't tell until after
                            # it has been baked and the expression is gone.
                            if anim.constant():
                                knob.clearAnimated(index, view=view)


def promptAndBake():
    '''
    Simple GUI wrapper for the ``bakeExpressions`` function that prompts for an
    input frame range and view list, and always operates on the selected nodes.
    '''
    nodes = nuke.selectedNodes()
    if not nodes:
        nuke.message('No nodes selected')
        return
    fr = nuke.getFramesAndViews("Range to Bake", str(nuke.root().frameRange()))
    if fr is None:
        return
    fr, v = fr
    try:
        fr = nuke.FrameRange(fr)
    except ValueError as e:
        nuke.message(str(e))
        return
    bakeExpressions(nodes=nodes, start=fr.first(), end=fr.last(), views=v)
