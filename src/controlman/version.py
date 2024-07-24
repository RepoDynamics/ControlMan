import versionman as _versionman
import gittidy as _git


def get_latest_version(
    version_tag_prefix: str,
    git_manager: _git.Git,
    dev_only: bool = False,
) -> tuple[_versionman.PEP440SemVer | None, int | None]:

    def get_latest_version() -> _versionman.PEP440SemVer | None:
        tags_lists = git_manager.get_tags()
        if not tags_lists:
            return
        for tags_list in tags_lists:
            ver_tags = []
            for tag in tags_list:
                if tag.startswith(version_tag_prefix):
                    ver_tags.append(_versionman.PEP440SemVer(tag.removeprefix(version_tag_prefix)))
            if ver_tags:
                if dev_only:
                    ver_tags = sorted(ver_tags, reverse=True)
                    for ver_tag in ver_tags:
                        if ver_tag.release_type == "dev":
                            return ver_tag
                else:
                    return max(ver_tags)
        return

    latest_version = get_latest_version()
    if not latest_version:
        return None, None
    distance = git_manager.get_distance(
        ref_start=f"refs/tags/{version_tag_prefix}{latest_version.input}"
    )
    return latest_version, distance
