import nuke

def render_selected_writes_by_input_range():
    # Get selected Write nodes only
    write_nodes = [n for n in nuke.selectedNodes() if n.Class() == "Write"]

    if not write_nodes:
        nuke.message("No Write nodes selected.")
        return

    for w in write_nodes:
        inp = w.input(0)

        if inp is None:
            nuke.message("Write node '{}' has no input – skipping.".format(w.name()))
            continue

        # Try to get the input node's own frame range
        fr = inp.frameRange()

        # If the input node has no explicit frame range, fall back to the root timeline
        if fr is None:
            fr = nuke.Root().frameRange()

        first = int(fr.first())
        last = int(fr.last())

        print("Rendering '{}' from {} to {} (input: '{}')".format(
            w.name(), first, last, inp.name()
        ))

        # Execute the render for this Write node
        nuke.execute(w.name(), first, last)

# Run it directly:
render_selected_writes_by_input_range()