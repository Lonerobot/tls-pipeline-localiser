/*
Usage:
- Run normally: align vertically (default to lowest). Hold Ctrl for topmost anchor.
- Hold Shift: align horizontally (default to rightmost). Hold Ctrl for leftmost anchor.
- Hold Alt: distribute evenly in the chosen orientation (works with the above anchors).
*/

function AlignNodes_VH() {

    // --- Modes/Constants ---
    var ORIENT_VERTICAL = 1;
    var ORIENT_HORIZONTAL = 2;

    var ANCHOR_MIN = 1;  // topmost for vertical, leftmost for horizontal
    var ANCHOR_MAX = 2;  // lowest for vertical, rightmost for horizontal

    var verticalOffset = 30;
    var horizontalOffset = 50;

    // --- Modifiers ---
    var horizontal = KeyModifiers.IsShiftPressed();                 // SHIFT = horizontal mode
    var distribute = KeyModifiers.IsAlternatePressed();             // ALT = distribute
    var ctrl = KeyModifiers.IsControlPressed();                     // CTRL = choose min/left/top anchor

    var orientation = horizontal ? ORIENT_HORIZONTAL : ORIENT_VERTICAL;
    var anchorMode = ctrl ? ANCHOR_MIN : ANCHOR_MAX;

    // --- Selection ---
    var selectedNodes = selection.selectedNodes();
    if (selectedNodes.length < 2) {
        MessageBox.warning(
            "Please select at least two nodes to align them.\n\n" +
            "Modes:\n" +
            "- Normal run: align vertically (default to lowest). Hold Ctrl for topmost.\n" +
            "- Hold Shift: align horizontally (default to rightmost). Hold Ctrl for leftmost.\n" +
            "- Hold Alt: distribute evenly (uses chosen orientation and anchor).",
            0, 0, 0, "Info"
        );
        return;
    }

    // --- Collect node data ---
    var nodes = [];
    var minX = Number.MAX_VALUE, maxX = -Number.MAX_VALUE;   // centers
    var minY = Number.MAX_VALUE, maxY = -Number.MAX_VALUE;   // top-left y
    var minXC = Number.MAX_VALUE, maxXC = -Number.MAX_VALUE; // center x
    var minYC = Number.MAX_VALUE, maxYC = -Number.MAX_VALUE; // center y

    selectedNodes.forEach(function(n) {
        var x = node.coordX(n);
        var y = node.coordY(n);
        var w = node.width(n);
        var h = node.height(n);
        var wh = w / 2;
        var hh = h / 2;
        var xc = x + wh;
        var yc = y + hh;

        nodes.push({ node: n, x: x, y: y, w: w, h: h, wh: wh, hh: hh, xc: xc, yc: yc });

        if (xc < minXC) minXC = xc;
        if (xc > maxXC) maxXC = xc;
        if (yc < minYC) minYC = yc;
        if (yc > maxYC) maxYC = yc;
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
    });

    // Sort helpers
    function sortByY(a, b) { return a.y - b.y; }
    function sortByX(a, b) { return a.x - b.x; }

    // Compute totals for distribution
    var totalHeight = 0;
    var totalWidth = 0;
    nodes.forEach(function(nd, i) {
        totalHeight += (i === 0 ? 0 : verticalOffset) + nd.h;
        totalWidth  += (i === 0 ? 0 : horizontalOffset) + nd.w;
    });

    // --- Anchor selection per orientation ---
    function getVerticalAnchorYTopLeft() {
        // Anchor by top-left Y of extreme node; return starting Y for distribution
        if (anchorMode === ANCHOR_MIN) { // topmost
            return minY;
        } else { // lowest -> start so that the last placed node ends at lowest
            // When distributing from bottom, start at: (lowest.y + lowest.h) - totalHeight
            return (maxY + getNodeByTopLeftY(maxY).h) - totalHeight;
        }
    }

    function getHorizontalAnchorXTopLeft() {
        if (anchorMode === ANCHOR_MIN) { // leftmost
            return minX;
        } else { // rightmost -> start so last placed node ends at rightmost edge
            var rightmost = getNodeByTopLeftX(maxX);
            return (maxX + rightmost.w) - totalWidth;
        }
    }

    function getNodeByTopLeftY(targetY) {
        var candidate = nodes[0];
        for (var i = 0; i < nodes.length; i++) {
            if (nodes[i].y === targetY) { candidate = nodes[i]; break; }
            // Fallback to nearest
            if (Math.abs(nodes[i].y - targetY) < Math.abs(candidate.y - targetY)) candidate = nodes[i];
        }
        return candidate;
    }

    function getNodeByTopLeftX(targetX) {
        var candidate = nodes[0];
        for (var i = 0; i < nodes.length; i++) {
            if (nodes[i].x === targetX) { candidate = nodes[i]; break; }
            if (Math.abs(nodes[i].x - targetX) < Math.abs(candidate.x - targetX)) candidate = nodes[i];
        }
        return candidate;
    }

    // Center anchors (for non-distribute)
    function verticalAnchorCenterX() {
        // Keep same center X as extreme node center
        // Choose based on anchorMode: topmost -> that node's center, lowest -> that node's center
        var anchorNode = (anchorMode === ANCHOR_MIN)
            ? nodes.slice().sort(sortByY)[0]
            : nodes.slice().sort(sortByY)[nodes.length - 1];
        return anchorNode.xc;
    }

    function horizontalAnchorCenterY() {
        var anchorNode = (anchorMode === ANCHOR_MIN)
            ? nodes.slice().sort(sortByX)[0]
            : nodes.slice().sort(sortByX)[nodes.length - 1];
        return anchorNode.yc;
    }

    // --- Alignment functions ---
    function alignVertical(xCenter, startY, doDistribute) {
        // For distribution, sort by Y
        var list = nodes.slice();
        list.sort(sortByY);

        var yCursor = startY || 0;
        list.forEach(function(nd) {
            var newX = Math.floor(xCenter - nd.wh);
            var newY = doDistribute ? Math.floor(yCursor) : nd.y; // keep original Y if not distributing
            node.setCoord(nd.node, newX, newY);
            if (doDistribute) yCursor += nd.h + verticalOffset;
        });
    }

    function alignHorizontal(yCenter, startX, doDistribute) {
        // For distribution, sort by X
        var list = nodes.slice();
        list.sort(sortByX);

        var xCursor = startX || 0;
        list.forEach(function(nd) {
            var newX = doDistribute ? Math.floor(xCursor) : Math.floor(nd.x);
            var newY = Math.floor(yCenter - nd.hh); // align all to same center Y
            node.setCoord(nd.node, newX, newY);
            if (doDistribute) xCursor += nd.w + horizontalOffset;
            else {
                // If not distributing horizontally, also align X centers to an anchor edge?
                // We keep original X (like original vertical keeps original Y).
                // Intent is: only align the orthogonal axis unless distributing.
            }
        });
    }

    // --- Execute ---
    scene.beginUndoRedoAccum('Align/Distribute nodes (V/H)');

    if (orientation === ORIENT_VERTICAL) {
        if (distribute) {
            // Distribute vertically, lock center X to anchor node center
            var anchorX = verticalAnchorCenterX();
            var startY = getVerticalAnchorYTopLeft();
            alignVertical(anchorX, startY, true);
        } else {
            // Align vertically (same X center), preserve original Y
            var anchorX2 = verticalAnchorCenterX();
            alignVertical(anchorX2, null, false);
        }
    } else { // ORIENT_HORIZONTAL
        if (distribute) {
            // Distribute horizontally, lock center Y to anchor node center
            var anchorY = horizontalAnchorCenterY();
            var startX = getHorizontalAnchorXTopLeft();
            alignHorizontal(anchorY, startX, true);
        } else {
            // Align horizontally (same Y center), preserve original X
            var anchorY2 = horizontalAnchorCenterY();
            alignHorizontal(anchorY2, null, false);
        }
    }

    scene.endUndoRedoAccum();
}
