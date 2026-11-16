"""Export native COMSOL renders and embed them in one Origin project."""

import shutil
import tempfile
from pathlib import Path

from PIL import Image

from .adapters.comsol_adapter import COMSOLAdapter
from .adapters.origin_adapter import OriginAdapter, quoted
from .exceptions import OriginExportError


def embed_images(files, destination, visible):
    origin = OriginAdapter(
        {
            "origin": {
                "visible": visible,
                "new_instance": True,
                "close_on_finish": not visible,
                "save_project": True,
                "project_file": destination,
            }
        }
    )
    try:
        origin.connect()
        with tempfile.TemporaryDirectory(prefix="origin_comsol_images_") as temporary:
            for index, path in enumerate(files, 1):
                source = Path(temporary) / f"image-{index:02d}.png"
                shutil.copyfile(path, source)
                with Image.open(source) as image:
                    width, height = image.size
                page = origin.op.new_image()
                if page is None or not page.from_file(quoted(source)):
                    raise OriginExportError(f"Origin 无法嵌入图片：{path.name}")
                if (page.get_int("Width"), page.get_int("Height")) != (width, height):
                    raise OriginExportError(f"Origin 图片尺寸与原图不符：{path.name}")
                # Loading an image replaces the window's long name with its input path.
                page.lname = path.stem
            project = origin.save_project()
        origin.success = True
        return project
    finally:
        origin.close()


def export_native_plots(config):
    adapter = COMSOLAdapter(config)
    try:
        result = adapter.export_plot_groups(config["tags"], config["directory"])
    finally:
        adapter.close()
    result.update(project=None, project_error=None)
    if result["files"]:
        try:
            result["project"] = embed_images(
                result["files"], result["directory"] / "COMSOL 原图.opju", config["visible"]
            )
        except Exception as exc:
            result["project_error"] = str(exc)
    return result
