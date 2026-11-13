"""Verify the frozen app's DCC payload using an independent, isolated Python."""
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path


def load_package(name, folder):
    spec = importlib.util.spec_from_file_location(
        name, folder / "__init__.py", submodule_search_locations=[str(folder)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    payload = Path(sys.argv[1]).resolve()
    load_package("localiser", payload / "localiser")

    from localiser import install_pipeline_code, load_local_config, publish_release, sync_release

    for name in list(os.environ):
        if name == "TLS_PIPELINE" or name.startswith("TLS_PIPELINE_"):
            del os.environ[name]

    with tempfile.TemporaryDirectory(prefix="theline-dcc-payload-") as directory:
        work = Path(directory)
        root = work / "Pipeline"
        repository = work / "repository"
        (root / "localiser" / "icons").mkdir(parents=True)

        versions = {"maya": "2026", "blender": "5.2", "nuke": "17.0"}
        (root / "config.json").write_text(json.dumps({
            "schema_version": 1,
            "remote_repository": str(repository),
            "hosts": {host: [series] for host, series in versions.items()},
        }), encoding="utf-8")
        config = load_local_config(root / "config.json", {})
        repository.mkdir()
        (repository / "config.json").write_text(json.dumps({
            "schema_version": 1,
            "hosts": {host: {series: {"bundle_version": "smoke"}} for host, series in versions.items()},
        }), encoding="utf-8")
        for host, series in versions.items():
            source = work / "sources" / host
            entry = source / "startup" if host == "blender" else source
            entry.mkdir(parents=True)
            (entry / "__init__.py").write_text("from .tool import VALUE\n", encoding="utf-8")
            (entry / "tool.py").write_text(f"VALUE = {host!r}\n", encoding="utf-8")
            publish_release(source, repository, host, "smoke", python_root="startup" if host == "blender" else ".")
            sync_release(host, series, config, {})

        repository.rename(work / "offline")
        existing = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
        install_pipeline_code(root, source=payload / "pipeline")
        if any(path.read_bytes() != content for path, content in existing.items()):
            raise RuntimeError("Repair changed existing configuration or bundle data")
        if install_pipeline_code(root, source=payload / "pipeline"):
            raise RuntimeError("The installed DCC payload is not stable on a second install")
        os.environ["TLS_PIPELINE"] = str(root)
        pipeline = load_package("tls_pipeline", root)
        for host, series in versions.items():
            release = pipeline.start(host, series)
            if release is None or release.release_id != "smoke":
                raise RuntimeError(f"{host}: the prepared release did not load")
            if sys.modules[f"tls_bundle_{host}"].VALUE != host:
                raise RuntimeError(f"{host}: the bundle entry did not execute")
            print(f"{host}: copied core and prepared bundle loaded offline")


if __name__ == "__main__":
    main()
