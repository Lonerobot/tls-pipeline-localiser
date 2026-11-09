# Legacy-class alias: the node class was renamed HigxBokeh -> HigxOptics
# (the product name). Old saved scripts and suites that
# say HigxBokeh resolve through this forwarding proc (stock FrameSelect.tcl
# pattern); knob script names never changed, so values restore 1:1.
load HigxOptics
proc HigxBokeh {args} { eval [concat HigxOptics $args] }
