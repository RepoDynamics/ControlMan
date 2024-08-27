from pathlib import Path as _Path

import jsonpath_ng as _jsonpath
import ruamel.yaml as _yaml

import pyserials as _ps
import pylinks as _pl

from controlman.exception import load as _exception
from controlman.cache_manager import CacheManager as _CacheManager
from controlman import const as _const


def load(control_center_path: _Path, cache_manager: _CacheManager | None = None) -> dict:
    full_data = {}
    for filepath in control_center_path.glob('*'):
        if filepath.is_file() and filepath.suffix.lower() in ['.yaml', '.yml']:
            file_content = filepath.read_text().strip()
            if not file_content:
                continue
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
                _ps.update.dict_from_addon(
                    data=full_data,
                    addon=data,
                    append_list=False,
                    append_dict=True,
                    raise_duplicates=True,
                    raise_type_mismatch=True,
                )
            except _ps.exception.update.PySerialsUpdateDictFromAddonError as e:
                raise _exception.ControlManDuplicateConfigFileDataError(filepath=filepath, cause=e) from None
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
        except _pl.exceptions.WebAPIError as e:
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
