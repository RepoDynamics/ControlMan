from pathlib import Path as _Path
import os as _os

import pyserials as _ps
import mdit as _mdit

from controlman.datatype import DynamicFile, DynamicFileType


def generate(data: _ps.NestedDict, data_before: _ps.NestedDict, repo_path: _Path) -> list[DynamicFile]:

    generated_files = []
    current_dir = _Path.cwd()
    _os.chdir(repo_path)
    try:
        for doc_id, doc_data in data.get("document", {}).items():
            doc = _mdit.generate(doc_data["content"])
            for output_id, output_data in doc_data["output"].items():
                doc_str = doc.source(
                    target=output_data["target"],
                    filters=output_data.get("filters"),
                    heading_number_explicit=output_data["heading_number_explicit"],
                    separate_sections=False,
                )
                file_info = {
                    "type": DynamicFileType.DOC,
                    "subtype": (f"{doc_id}_{output_id}", f"{doc_id} ({output_id})"),
                    "path": output_data["path"],
                    "path_before": data_before[f"document.{doc_id}.output.{output_id}.path"],
                    "content": doc_str.strip() + "\n",
                }
                generated_files.append(DynamicFile(**file_info))
    finally:
        _os.chdir(current_dir)
    return generated_files
