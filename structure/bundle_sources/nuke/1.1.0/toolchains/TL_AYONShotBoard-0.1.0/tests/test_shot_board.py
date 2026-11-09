"""Offline integration checks. The real AYON/Nuke environment is still required."""
import copy
import importlib.util
import sys
import types
import unittest
from pathlib import Path


class Knob:
    def __init__(self, name, value=""):
        self.name, self.v = name, value
    def value(self): return self.v
    def setValue(self, value): self.v = value
    def setVisible(self, visible): pass


class Node:
    def __init__(self, host, kind, **values):
        self.host, self.kind = host, kind
        self.name = kind + str(host.counter)
        host.counter += 1
        defaults = dict(
            xpos=0, ypos=0, selected=False, bdwidth=760, bdheight=400,
            first_frame=1001, last_frame=1100, fps=25)
        defaults.update(values)
        self.k = {key: Knob(key, value) for key, value in defaults.items()}
        host.nodes_list.append(self)
    def Class(self): return self.kind
    def fullName(self): return self.name
    def knob(self, key): return self.k.get(key)
    def addKnob(self, knob): self.k[knob.name] = knob
    def __getitem__(self, key): return self.k[key]
    def xpos(self): return self.k["xpos"].value()
    def ypos(self): return self.k["ypos"].value()
    def setXYpos(self, x, y):
        self.k["xpos"].setValue(x); self.k["ypos"].setValue(y)
    def screenWidth(self): return 100
    def screenHeight(self): return 70
    def __enter__(self): return self
    def __exit__(self, *args): pass


class Progress:
    cancelled = False
    def __init__(self, *args): pass
    def setMessage(self, message): pass
    def setProgress(self, value): pass
    def isCancelled(self): return self.cancelled


class Undo:
    depth = 0
    def begin(self, name): Undo.depth += 1
    def end(self): Undo.depth -= 1


class Host(types.ModuleType):
    def __init__(self):
        super().__init__("nuke")
        self.counter = 0
        self.nodes_list = []
        self.root_node = Node(self, "Root")
        self.nodes_list.clear()
        self.String_Knob = lambda name, label: Knob(name)
        self.nodes = types.SimpleNamespace(**{
            kind: (lambda cls=kind, **kw: Node(self, cls, **kw))
            for kind in ("StickyNote", "BackdropNode")})
        self.ProgressTask = Progress
        self.Undo = Undo
        self.GUI = True
    def allNodes(self, **kwargs): return list(self.nodes_list)
    def selectedNodes(self): return [n for n in self.nodes_list if n["selected"].value()]
    def root(self): return self.root_node
    def toNode(self, name): return next((n for n in self.nodes_list if n.name == name), None)
    def delete(self, node): self.nodes_list.remove(node)
    def tprint(self, text): pass
    def message(self, text): pass


class LoadClip:
    enabled = True
    script_start = 1


class API:
    def __init__(self):
        self.folders = [
            dict(id="root", path="/shots", name="shots", parentId=None, folderType="Folder"),
            dict(id="s1", path="/shots/sh010", name="sh010", parentId="root", folderType="Shot"),
            dict(id="s2", path="/shots/sh020", name="sh020", parentId="root", folderType="Shot"),
            dict(id="sub", path="/shots/sh010/ref", name="ref", parentId="s1", folderType="Folder"),
            dict(id="other", path="/shotsOld/sh030", name="sh030", parentId=None, folderType="Shot"),
        ]
        self.products = [
            dict(id="p1", name="plateMain", folderId="s1", productType="plate"),
            dict(id="p2", name="reviewAnim", folderId="sub", productType="review"),
            dict(id="p3", name="reviewLayout", folderId="s2", productBaseType="review"),
            dict(id="p4", name="imageMain", folderId="s2", productType="image"),
            dict(id="p5", name="plateOutside", folderId="other", productType="plate"),
        ]
        self.versions, self.repres = [], []
        for product in self.products:
            self.add_version(product["id"], 1)
        self.add_version("p1", 2)
        self.calls = []
    def add_version(self, product_id, version):
        vid = product_id + "v" + str(version)
        self.versions.append(dict(id=vid, productId=product_id, version=version,
                                  active=True, status="Approved", author="artist"))
        for ext in ("exr", "mov"):
            self.repres.append(dict(id=vid+ext, versionId=vid, name=ext, context={"ext": ext}))
    def get_folders(self, project, **kwargs): return self.folders
    def get_products(self, project, folder_ids):
        assert folder_ids
        return [p for p in self.products if p["folderId"] in folder_ids]
    def get_last_versions(self, project, product_ids):
        assert product_ids
        return {pid: max([v for v in self.versions if v["productId"] == pid],
                         key=lambda v: v["version"]) for pid in product_ids}
    def get_versions(self, project, product_ids, hero):
        assert product_ids and not hero
        return [v for v in self.versions if v["productId"] in product_ids]
    def get_representations(self, project, version_ids):
        assert version_ids
        return [r for r in self.repres if r["versionId"] in version_ids]


class BoardTests(unittest.TestCase):
    def setUp(self):
        self.host = Host()
        sys.modules["nuke"] = self.host
        path = Path(__file__).parents[1] / "TL_AYONShotBoard/0.1.0/tl_ayon_shot_board.py"
        spec = importlib.util.spec_from_file_location("board", path)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.api = API()
        self.config = dict(copy.deepcopy(self.m.DEFAULTS), project="test")
        self.fail = False
        def containers():
            return [dict(representation=n.representation, node=n, project_name="test")
                    for n in self.host.allNodes() if hasattr(n, "representation")]
        def contexts(project, repres):
            versions = {v["id"]:v for v in self.api.versions}
            products = {p["id"]:p for p in self.api.products}
            folders = {f["id"]:f for f in self.api.folders}
            result = {}
            for r in repres:
                v = versions[r["versionId"]]; p = products[v["productId"]]
                result[r["id"]] = dict(project={"name":"test"}, folder=folders[p["folderId"]],
                                       product=p, version=v, representation=r)
            return result
        def load(loader, context, **kwargs):
            n = Node(self.host, "Read")
            n.representation = context["representation"]["id"]
            assert loader.script_start == 1001
            assert kwargs["options"]["node_type"] == "Read"
            if self.fail: raise RuntimeError("simulated missing media")
            return n
        self.deps = dict(api=self.api, project="test", ls=containers,
                         discover=lambda:[LoadClip], contexts=contexts,
                         compatible=lambda *a:True, load=load)
        self.m.dependencies = lambda:self.deps
    def test_initial_repeat_update_and_recovery(self):
        self.m.run(self.config)
        self.assertEqual(len(self.deps["ls"]()), 3)
        self.assertEqual(len([n for n in self.host.allNodes() if n.kind=="BackdropNode"]), 2)
        self.assertEqual(len([n for n in self.host.allNodes() if n.kind=="StickyNote"]), 3)
        positions = {n.name:(n.xpos(), n.ypos()) for n in self.host.allNodes()}
        self.m.run(self.config)
        self.assertEqual(len(self.deps["ls"]()), 3)
        self.api.add_version("p2", 2)
        self.m.update()
        self.assertEqual(len(self.deps["ls"]()), 4)
        for n in self.host.allNodes():
            if n.name in positions: self.assertEqual((n.xpos(), n.ypos()), positions[n.name])
        self.host.delete(self.deps["ls"]()[-1]["node"])
        self.m.update()
        self.assertEqual(len(self.deps["ls"]()), 4)
        self.assertEqual(Undo.depth, 0)
        self.assertEqual(LoadClip.script_start, 1)
    def test_collection_scope_formats_and_all_versions(self):
        items, skipped, cancelled = self.m.collect(self.config,self.deps,Progress())
        self.assertEqual(len(items), 3)
        self.assertFalse(skipped or cancelled)
        self.assertEqual([i["representation"]["name"] for i in items], ["exr","mov","mov"])
        self.assertEqual(items[1]["shot"]["id"],"s1")
        self.config["versions"] = "All"
        items, _, _ = self.m.collect(self.config,self.deps,Progress())
        self.assertEqual(len(items), 4)
        self.assertEqual([i["version"]["version"] for i in items[:2]], [1,2])
    def test_failure_cleanup_and_retry(self):
        self.fail = True
        self.m.run(self.config)
        self.assertEqual(self.host.allNodes(), [])
        self.assertEqual(LoadClip.script_start, 1)
        self.fail = False
        self.m.update()
        self.assertEqual(len(self.deps["ls"]()), 3)
    def test_empty_products_no_unfiltered_queries(self):
        self.api.products = []
        self.m.run(self.config)
        self.assertEqual(self.host.allNodes(), [])
    def test_manual_ayon_import_not_duplicated(self):
        n = Node(self.host, "Read")
        n.representation = "p1v2exr"
        n.setXYpos(50,60)
        n["selected"].setValue(True)
        self.m.run(self.config)
        self.assertEqual(len(self.deps["ls"]()), 3)
        self.assertEqual((n.xpos(),n.ypos()),(50,60))
        self.assertTrue(n["selected"].value())
    def test_project_mismatch_stops_before_load(self):
        self.config["project"] = "other"
        with self.assertRaises(RuntimeError): self.m.run(self.config)
        self.assertEqual(self.host.allNodes(), [])
    def test_natural_order_and_path_boundaries(self):
        self.assertEqual(sorted(["sh100","sh20","sh010"],key=self.m.natural),
                         ["sh010","sh20","sh100"])
        self.assertFalse(self.m.in_scope("/shotsOld/sh010","/shots"))
    def test_cancelled_scan_leaves_script_untouched(self):
        Progress.cancelled = True
        try: self.m.run(self.config)
        finally: Progress.cancelled = False
        self.assertEqual(self.host.allNodes(), [])
        self.assertIsNone(self.host.root().knob(self.m.SETTINGS))
    def test_scene_inventory_update_uses_live_id(self):
        self.m.run(self.config)
        self.api.add_version("p1", 3)
        old = next(c["node"] for c in self.deps["ls"]() if c["representation"]=="p1v2exr")
        old.representation = "p1v3exr"  # Simulate an update via AYON Scene Inventory
        self.m.update()
        self.assertEqual(len(self.deps["ls"]()), 3)

    def test_layout_failure_restores_existing_backdrop(self):
        self.m.run(self.config)
        before = {n.name for n in self.host.allNodes()}
        geometry = {n.name:(n["bdwidth"].value(),n["bdheight"].value())
                    for n in self.host.allNodes() if n.kind=="BackdropNode"}
        self.api.add_version("p1", 3)
        original = self.m.place_bundle
        def broken(*args):
            original(*args)
            raise RuntimeError("simulated layout failure")
        self.m.place_bundle = broken
        self.m.update()
        self.assertEqual({n.name for n in self.host.allNodes()},before)
        for n in self.host.allNodes():
            if n.name in geometry:
                self.assertEqual((n["bdwidth"].value(),n["bdheight"].value()),geometry[n.name])

    def test_unsupported_representation_is_reported(self):
        self.deps["compatible"] = lambda *args:False
        items, skipped, cancelled = self.m.collect(self.config,self.deps,Progress())
        self.assertFalse(items or cancelled)
        self.assertEqual(len(skipped),3)

    def test_all_versions_repeat_is_idempotent(self):
        self.config["versions"] = "All"
        self.m.run(self.config); self.m.update()
        self.assertEqual(len(self.deps["ls"]()),4)

    def test_loader_cannot_change_script_range_or_fps(self):
        old_load = self.deps["load"]
        def load(*args,**kwargs):
            result = old_load(*args,**kwargs)
            for key,value in dict(first_frame=1,last_frame=500,fps=24).items():
                self.host.root()[key].setValue(value)
            return result
        self.deps["load"] = load
        self.m.run(self.config)
        self.assertEqual(len(self.deps["ls"]()),3)
        self.assertEqual(self.host.root()["first_frame"].value(),1001)
        self.assertEqual(self.host.root()["last_frame"].value(),1100)
        self.assertEqual(self.host.root()["fps"].value(),25)


if __name__ == "__main__":
    unittest.main()
