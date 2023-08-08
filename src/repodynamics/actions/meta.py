
from repodynamics.metadata import Metadata
from repodynamics.actions.meta_summary import meta_summary
from repodynamics.actions import io


def meta(
    cache_filepath: str = None,
    output_filepath: str = None,
    update_cache: bool = False,
    github_token: str = None,
) -> tuple[None, str]:

    metadata = Metadata(
        path_cache=cache_filepath,
        update_cache=update_cache,
        github_token=github_token,
    )
    metadata.json(write_to_file=True, output_filepath=output_filepath)
    return meta_summary(**io.input(meta_summary))
