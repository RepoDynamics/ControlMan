from pathlib import Path as _Path

import pyserials as _ps

from controlman import datatype as _dtype, const as _const
from controlman.file_gen.config import ConfigFileGenerator as _ConfigFileGenerator
from controlman.file_gen.forms import FormGenerator as _FormGenerator
from controlman.file_gen.python import PythonPackageFileGenerator as _PythonPackageFileGenerator
from controlman.file_gen import readme as _readme_gen


def generate(
    data: _ps.NestedDict,
    data_before: _ps.NestedDict,
    repo_path: _Path,
):
    metadata_file = _dtype.GeneratedFile(
        type=_dtype.DynamicFile_.METADATA,
        content=_ps.write.to_json_string(data=data(), sort_keys=True, indent=None),
        path=_const.FILEPATH_METADATA,
        path_before=_const.FILEPATH_METADATA,
    )
    generated_files = [metadata_file]
    form_files = _FormGenerator(
        data=data,
        repo_path=repo_path,
    ).generate()
    generated_files.extend(form_files)
    config_files, pyproject_pkg, pyproject_test = _ConfigFileGenerator(
        data=data,
        data_before=data_before,
        repo_path=repo_path,
    ).generate()
    generated_files.extend(config_files)
    if data["pkg"]:
        package_files = _PythonPackageFileGenerator(
            data=data,
            data_before=data_before,
            repo_path=repo_path,
        ).generate(typ="pkg", pyproject_tool_config=pyproject_pkg)
        generated_files.extend(package_files)
    if data["test"]:
        test_files = _PythonPackageFileGenerator(
            data=data,
            data_before=data_before,
            repo_path=repo_path,
        ).generate(typ="test", pyproject_tool_config=pyproject_test)
        generated_files.extend(test_files)
    readme_files = _readme_gen.generate(
        data=data,
        data_before=data_before,
        root_path=repo_path
    )
    generated_files.extend(readme_files)
    return [
        (generated_file, _compare_file(generated_file, repo_path=repo_path))
        for generated_file in generated_files
    ]


def _compare_file(file: _dtype.GeneratedFile, repo_path: _Path) -> _dtype.DynamicFileChangeType:
    if not file.content:
        if not file.path_before:
            return _dtype.DynamicFileChangeType.DISABLED
        filepath_before = repo_path / file.path_before
        if filepath_before.is_file():
            return _dtype.DynamicFileChangeType.REMOVED
        return _dtype.DynamicFileChangeType.DISABLED
    if not file.path:
        return _dtype.DynamicFileChangeType.DISABLED
    if not file.path_before:
        return _dtype.DynamicFileChangeType.CREATED
    fullpath_before = repo_path / file.path_before
    if not fullpath_before.is_file():
        return _dtype.DynamicFileChangeType.CREATED
    with open(repo_path / file.path_before) as f:
        content_before = f.read()
    contents_identical = file.content.strip() == content_before.strip()
    paths_identical = file.path == file.path_before
    change_type = {
        (True, True): _dtype.DynamicFileChangeType.UNCHANGED,
        (True, False): _dtype.DynamicFileChangeType.MOVED,
        (False, True): _dtype.DynamicFileChangeType.MODIFIED,
        (False, False): _dtype.DynamicFileChangeType.MOVED_MODIFIED,
    }
    return change_type[(contents_identical, paths_identical)]
