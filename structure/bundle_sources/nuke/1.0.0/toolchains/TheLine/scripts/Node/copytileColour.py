import nuke


def copy_tile_color():
    nodes = nuke.selectedNodes()

    if len(nodes) < 2:
        nuke.message("Select the source node and at least one target node.")
        return

    node_lookup = {node.fullName(): node for node in nodes}

    panel = nuke.Panel("Copy Tile Colour")
    panel.addEnumerationPulldown(
        "Source node",
        " ".join(node_lookup.keys())
    )

    if not panel.show():
        return

    source = node_lookup[panel.value("Source node")]
    targets = [node for node in nodes if node is not source]

    colour = int(source["tile_color"].value())

    # Zero means the node is using its class's default colour.
    if colour == 0:
        colour = nuke.defaultNodeColor(source.Class())

    for target in targets:
        target["tile_color"].setValue(colour)

    nuke.message(
        "Copied tile colour from {} to {} node(s).".format(
            source.name(),
            len(targets)
        )
    )


copy_tile_color()