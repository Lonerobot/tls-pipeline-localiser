# import acv
import nuke

import struct
filepath = 'C:/users/hoge/curve.acv'
luts = []
with open(filepath, 'rb') as f:
    header = f.read(4)
    for i in range(len('mrgba')):
        ncvs = struct.unpack('>BB', f.read(2))[1]
        ipairs = [struct.unpack('>BBBB', f.read(4))[1::2] for k in range(ncvs)]
        pairs = [(ix/255., iy/255.) for iy, ix in ipairs]
        luts.append(pairs)

# set value to ColorLookup
node = nuke.createNode('ColorLookup')
lut_knob = node.knob('lut')
for i, lut in enumerate(luts):
    for x, y in lut:
        lut_knob.setValueAt(y, x, i)
