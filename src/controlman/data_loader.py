from pathlib import Path as _Path

import jsonpath_ng as _jsonpath
import ruamel.yaml as _yaml

import pyserials as _ps
import pylinks as _pl
from pylinks.exception.api import WebAPIError as _WebAPIError

from controlman.exception import load as _exception
from controlman.cache_manager import CacheManager as _CacheManager
from controlman import const as _const
import mdit as _mdit
from loggerman import logger as _logger


def load(
    path_cc: _Path,
    cache_manager: _CacheManager | None = None
) -> dict:

    def _load_file(filepath: _Path):
        file_content = filepath.read_text().strip()
        if not file_content:
            _logger.notice(
                "Empty Configuration File",
                _mdit.inline_container(
                    "The control center configuration file at ",
                    _mdit.element.code_span(str(filepath)),
                    " is empty.",
                ),
            )
            return
        try:
            data = _ps.read.yaml_from_file(
                path=filepath,
                safe=True,
                constructors={
                    _const.CC_EXTENSION_TAG: _create_external_tag_constructor(
                        tag_name=_const.CC_EXTENSION_TAG,
                        cache_manager=cache_manager,
                        filepath=filepath,
                        file_content=file_content,
                    )
                },
            )
        except _ps.exception.read.PySerialsInvalidDataError as e:
            raise _exception.ControlManInvalidConfigFileDataError(cause=e) from None
        try:
            log = _ps.update.dict_from_addon(
                data=full_data,
                addon=data,
                append_list=True,
                append_dict=True,
                raise_duplicates=True,
                raise_type_mismatch=True,
            )
        except _ps.exception.update.PySerialsUpdateDictFromAddonError as e:
            raise _exception.ControlManDuplicateConfigFileDataError(filepath=filepath, cause=e) from None
        log_admonitions = []
        for key, title in (
            ("added", "Added"),
            ("list_appended", "Appended List"),
            ("skipped", "Skipped"),
        ):
            if not log[key]:
                continue
            key_list = _mdit.element.unordered_list(
                [_mdit.element.code_span(item) for item in sorted(log[key])]
            )
            log_admonitions.append(
                _mdit.element.admonition(
                    title=f"{title} Keys",
                    body=key_list,
                    dropdown=True,
                )
            )
        _logger.success(
            "Loaded Configurations",
            _mdit.block_container(*log_admonitions),
        )
        return

    full_data = {}
    hook_dir = path_cc / _const.DIRNAME_CC_HOOK
    for path in sorted(path_cc.rglob('*'), key=lambda p: (p.parts, p)):
        if hook_dir not in path.parents and path.is_file() and path.suffix.lower() in ['.yaml', '.yml']:
            with _logger.sectioning(_mdit.element.code_span(str(path.relative_to(path_cc)))):
                _load_file(filepath=path)
    return full_data


def _create_external_tag_constructor(
    filepath: _Path,
    file_content: str,
    tag_name: str = u"!ext",
    cache_manager: _CacheManager | None = None
):

    def load_external_data(loader: _yaml.SafeConstructor, node: _yaml.ScalarNode):

        tag_value = loader.construct_scalar(node)
        if not tag_value:
            raise _exception.ControlManEmptyTagInConfigFileError(
                filepath=filepath,
                data=file_content,
                node=node,
            )
        if cache_manager:
            cached_data = cache_manager.get(typ="extension", key=tag_value)
            if cached_data:
                return cached_data
        url, *jsonpath_expr = tag_value.split(' ', 1)
        try:
            data_raw_whole = _pl.http.request(
                url=url,
                verb="GET",
                response_type="str",
            )
        except _WebAPIError as e:
            raise _exception.ControlManUnreachableTagInConfigFileError(
                filepath=filepath,
                data=file_content,
                node=node,
                url=url,
                cause=e,
            ) from None
        data = _ps.read.yaml_from_string(
            data=data_raw_whole,
            safe=True,
            constructors={tag_name: load_external_data},
        )
        if jsonpath_expr:
            jsonpath_expr = _jsonpath.parse(jsonpath_expr[0])
            matches = jsonpath_expr.find(data)
            if not matches:
                raise ValueError(
                    f"No match found for JSONPath '{jsonpath_expr}' in the JSON data from '{url}'")
            data = [match.value for match in matches]
            if len(data) == 1:
                data = data[0]
        if cache_manager:
            cache_manager.set(typ="extension", key=tag_value, value=data)
        return data

    return load_external_data
