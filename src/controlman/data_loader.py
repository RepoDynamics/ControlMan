from pathlib import Path as _Path

import jsonpath_ng as _jsonpath
import ruamel.yaml as _yaml

import pyserials as _ps
import pylinks as _pl

from controlman import exception as _exception
from controlman.cache_manager import CacheManager as _CacheManager
from controlman import const as _const


def load(control_center_path: _Path, cache_manager: _CacheManager | None = None) -> dict:
    full_data = {}
    for filepath in control_center_path.glob('*'):
        if filepath.is_file() and filepath.suffix.lower() in ['.yaml', '.yml']:
            filename = filepath.relative_to(control_center_path)
            data = _ps.read.yaml_from_file(
                path=filepath,
                safe=True,
                constructors={
                    _const.CC_EXTENSION_TAG: _create_external_tag_constructor(
                        tag_name=_const.CC_EXTENSION_TAG,
                        cache_manager=cache_manager
                    )
                },
            )
            duplicate_keys = set(data.keys()) & set(full_data.keys())
            if duplicate_keys:
                raise RuntimeError(f"Duplicate keys '{", ".join(duplicate_keys)}' in project config")
            full_data.update(data)
    return full_data


def _create_external_tag_constructor(tag_name: str = u"!ext", cache_manager: _CacheManager | None = None):

    def load_external_data(loader: _yaml.SafeConstructor, node: _yaml.ScalarNode):
        tag_value = loader.construct_scalar(node)
        if not tag_value:
            raise _exception.ControlManSchemaValidationError(f"Found {tag_name} tag with no value")
        if cache_manager:
            cached_data = cache_manager.get(typ="extension", key=tag_value)
            if cached_data:
                return cached_data
        url, jsonpath_expr = tag_value.split(' ', 1)
        try:
            data_raw_whole = _pl.http.request(
                url=url,
                verb="GET",
                response_type="str",
            )
        except _pl.exceptions.WebAPIError as e:
            raise _exception.ControlManFileReadError(
                path=url,
                msg=f"Failed to download external data from URL '{url}'"
            ) from e
        data_whole = _ps.read.yaml_from_string(
            data=data_raw_whole,
            safe=True,
            constructors={tag_name: load_external_data},
        )
        if jsonpath_expr:
            jsonpath_expr = _jsonpath.parse(jsonpath_expr)
            match = jsonpath_expr.find(data_whole)
            if not match:
                raise ValueError(
                    f"No match found for JSONPath '{jsonpath_expr}' in the JSON data from '{url}'")
            value = match[0].value
        else:
            value = data_whole
        if cache_manager:
            cache_manager.set(typ="extension", key=tag_value, value=value)
        return value

    return load_external_data
