from pathlib import Path as _Path
import copy

import pybadger as _bdg
import pylinks as _pl
import pyserials as _ps
import markitup as _miu
import pycolorit as _pcit

from controlman.nested_dict import NestedDict as _NestedDict


def create_badges(
    settings: dict,
    themed: bool,
    root_path: _Path,
) -> list[_bdg.Badge | _bdg.ThemedBadge]:
    """Create badges from a dictionary of settings.

    Parameters
    ----------
    settings : dict
        The settings to create the badges from.
    themed : bool
        Whether to create themed badges.
    root_path : pathlib.Path
        The root path to the project.

    Returns
    -------
    list[pybadger.Badge | pybadger.ThemedBadge]
        The list of badges.
    """
    gradient_color = {}
    default = copy.deepcopy(settings.get("default", {}))
    for part in ("label", "message"):
        default_color_part = default.get(part, {}).get("color", {})
        for theme in ("light", "dark"):
            if isinstance(default_color_part.get(theme), list):
                color_gradient = default_color_part.pop(theme)
                colors = _pcit.gradient.interpolate_rgb(
                    color_start=_pcit.color.hexa(color_gradient[0]),
                    color_end=_pcit.color.hexa(color_gradient[1]),
                    count=len(settings["elements"]),
                ).hex()
                gradient_color.setdefault(part, {})[theme] = colors
    badges = []
    for idx, badge_settings in enumerate(settings["elements"]):
        if isinstance(badge_settings, str):
            badge_settings = {"message": {"text": badge_settings}}
        badge_settings = copy.deepcopy(badge_settings)
        _ps.update.dict_from_addon(
            data=badge_settings,
            addon=default,
            append_list=False,
            append_dict=True,
            raise_duplicates=False
        )
        badge_settings = _NestedDict(badge_settings)
        for part in ("label", "message"):
            for theme in ("light", "dark"):
                gradient_colors = gradient_color.get(part, {}).get(theme)
                if not badge_settings[f"{part}.color.{theme}"] and gradient_colors is not None:
                    badge_settings[f"{part}.color.{theme}"] = gradient_colors[idx]
        badge_settings = badge_settings()
        if "name" in badge_settings:
            badge = create_auto_badge(badge_settings, themed, root_path)
        elif "url" in badge_settings:
            badge = create_dynamic_badge(badge_settings, themed, root_path)
        else:
            badge = create_static_badge(badge_settings, themed, root_path)
        badges.append(badge)
    return badges


def create_auto_badge(settings: dict, themed: bool, root_path: _Path) -> _bdg.Badge | _bdg.ThemedBadge:
    name = settings["name"]
    if name == "pypackit":
        pypackit_badge_settings = pypackit_badge()
        _ps.update.dict_from_addon(
            data=settings,
            addon=pypackit_badge_settings,
            append_list=False,
            append_dict=True,
            raise_duplicates=False
        )
        return create_static_badge(pypackit_badge_settings, themed=themed, root_path=root_path)
    module_name, *name_parts = settings["name"].split(".")
    module = getattr(_bdg.shields, module_name)
    if len(name_parts) == 2:
        class_ = getattr(module, name_parts[0])
        instance = class_(**settings["class_kwargs"])
        method = getattr(instance, name_parts[1])
    else:
        method = getattr(module, name_parts[0])
    return method(
        shields_settings=make_pybadger_shields_settings(settings, themed, root_path),
        badge_settings=make_pybadger_badge_settings(settings),
        **settings["method_kwargs"],
    )


def create_dynamic_badge(settings: dict, themed: bool, root_path: _Path) -> _bdg.Badge | _bdg.ThemedBadge:
    return _bdg.shields.core.dynamic(
        url=settings["url"],
        query=settings["query"],
        prefix=settings.get("prefix"),
        suffix=settings.get("suffix"),
        typ=settings.get("type"),
        shields_settings=make_pybadger_shields_settings(settings, themed, root_path),
        badge_settings=make_pybadger_badge_settings(settings),
    )


def create_static_badge(settings: dict, themed: bool, root_path: _Path) -> _bdg.Badge | _bdg.ThemedBadge:
    return _bdg.shields.core.static(
        message=settings["message"]["text"],
        shields_settings=make_pybadger_shields_settings(settings, themed, root_path),
        badge_settings=make_pybadger_badge_settings(settings),
    )


def make_pybadger_shields_settings(settings: dict, themed: bool, root_path: _Path) -> _bdg.shields.ShieldsSettings:
    """Create a `ShieldsSettings` instance from a dictionary.

    Parameters
    ----------
    settings : dict
        The settings to create the `ShieldsSettings` instance from.

    Returns
    -------
    pybadger.shields.ShieldsSettings
        The `ShieldsSettings` instance.
    """
    shields_settings = {}
    settings = _NestedDict(settings)
    for self_key, shields_key in (
        ("style", "style"),
        ("label.text", "label"),
        ("label.color.light", "label_color"),
        ("message.color.light", "color"),
        ("logo.size", "logo_size"),
        ("logo.width", "logo_width"),
        ("logo.light.color", "logo_color"),
    ):
        if settings.get(self_key):
            shields_settings[shields_key] = settings[self_key]
    if themed:
        for self_key, shields_key in (
            ("label.color.dark", "label_color_dark"),
            ("message.color.dark", "color_dark"),
            ("logo.dark.color", "logo_color_dark"),
        ):
            if settings.get(self_key):
                shields_settings[shields_key] = settings[self_key]
    for self_key, shields_key in (
        ("logo.light", "logo"),
        ("logo.dark", "logo_dark"),
    ):
        if self_key == "logo.dark" and not themed:
            continue
        logo_data = settings.get(self_key)
        if not logo_data:
            continue
        typ = logo_data["type"]
        src = logo_data["src"]
        if typ == "name":
            shields_settings[shields_key] = src
            continue
        if typ == "path":
            logo = root_path / src
        elif typ == "url":
            logo = _pl.url.URL(src)
        else:
            logo = src
        ext = logo_data.get("ext")
        if ext:
            logo = (ext, logo)
        shields_settings[shields_key] = logo
    return _bdg.shields.ShieldsSettings(**shields_settings)


def make_pybadger_badge_settings(settings: dict) -> _bdg.BadgeSettings:
    """Create a `BadgeSettings` instance from a dictionary.

    Parameters
    ----------
    settings : dict
        The settings to create the `BadgeSettings` instance from.

    Returns
    -------
    pybadger.BadgeSettings
        The `BadgeSettings` instance.
    """
    return _bdg.BadgeSettings(
        **{k: v for k, v in settings.items() if k in ("href", "title", "alt", "width", "height", "align")}
    )


def pypackit_badge():
    logo_light = (
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAACXBIWXMAAAsPAAALDwGS"
        "+QOlAAADxklEQVRYhb1XbWxTZRR+3vvR3rt+OsJ2M5CWrKIxZJsm/gITk0XBjYQ4IJshAcJHjIq4HyyKgjJBPiLqwg"
        "8Tk6L80qATgwkLGpUE94OYSBgSIZnTFoK93VxhpV1v73s/TGu6rOu69nZlz6/zvue85zw55z73vZeYpgkraDr85IX7"
        "NLEGFHDrrtDQ8d+WW0owA4yV4LVH2juHyV9rQuYthPQwrqnX/U/3PHNswQhEmbFNCpS8vZgWW71gBFJECRQkIMyK+R"
        "DgZtvsOtV2Om5OBmomPZv795wLz/RLpB5gTMiIImEkF8+HQEEHXvr0xdXjzsjWO67QqiSX6J3uSyPdLEDAI2jc9Tj7"
        "2AGBCPOpnUVBB1Re6UrZkvDEa5HkkgXzlcw6XOr9OZixl/esOATDmopKEtBZKi2JBX7VVTIa4aLr5pW9DBSMQGPVAA"
        "Fu1FDXTw+6eAazqsCpeK+WOti6/zmfYiqlwkpiVhWUAzuxvyDrUfixbM7oXR+s7055wttEkcDBi1yN/lD7kc3np5RV"
        "MYHZsHbP853/mndes4mGkxe1gCDCwTvTgGMMuosBXATC3eaMsrbljlt6ETFgksV8ra8/6/t94npwOHVzVZgON8tmyD"
        "HO3kKCG82L073y1oNft/sqIsCD/7OYTzXUlyNKxFkqh+4eAwjeya2rNoIJbaKl3FhTTKx/v7+jlVXcgqUOzAXVoFK5"
        "sWTS2ff2xrN+tvbuxgICJjGn2iiL/2DDhx3d5SQ1YJRsfwbcmC96cNP5wxm7p+3cYHYE+z7f0UkpWpL2+EqGZRqDr3"
        "7Rt+VkV1mFc6AGbcyYdTYp4bM1fGMngKAxUKm8wcRolhyj2cHG607nEXo3+IqZXirjnn0c96kKQZa+t1J4Jlyse+TH"
        "45enZLbjRFuQ3Fv2BhB7SkiJV492/vBmHoHenZ+QfZ/t7PZwHkmkWEx14z0rBUNqGG171xXt1qm9A4MABov5syM4uj"
        "3YZ6VoNVE1FVSKigkY0CO5D5IbqZsfy+lo1nawjpIX2XRUTODCoYEzEluftUNKGIpR2c1Y9RGwhEssGAE7sQ1NXwus"
        "ADfr+WXBCHgZb568logN0e9ODJypKoEYH5u6ZDRoEg9+JLe+fGxwd5OwMuQXfPCLPjQIDfutFM+g5G14W7jd0XTyiR"
        "ZCWc8I+3f9ozQgT/cPfXTlwfwbUkb9tja9CHFuwjVsH2m+ZvvDn9m3gZeLnakqgS93nw07NFf+Q2YK8Jre/moSmHME"
        "Ts351lL94a+SuupQqY46bdHFSwf+/ympCgD8BxQORGJUan2aAAAAAElFTkSuQmCC"
    )
    out = {
        "label": {"text": "Powered By"},
        "message": {
            "text": f"PyPackIT",
            "color": {"light": "rgb(0, 100, 0)", "dark": "rgb(0, 100, 0)",}
        },
        "logo": {
            "light": {"type": "data", "src": logo_light},
            "dark": {"type": "data", "src": logo_light},
        },
        "title": f"Project management and DevOps by PyPackIT",
        "alt": "Powered by PyPackIT",
        "href": "https://pypackit.repodynamics.com",
    }
    return out


