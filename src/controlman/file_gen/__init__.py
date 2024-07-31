from controlman.file_gen.config import ConfigFileGenerator
from controlman.file_gen.forms import FormGenerator
from controlman.file_gen.package import PythonPackageFileGenerator
from controlman.file_gen.readme import ReadmeFileGenerator



# @_logger.sectioner("Generate Metadata File")
# def _generate_metadata(
#     content_manager: _ControlCenterContentManager,
#     path_manager: _PathManager,
# ) -> list[tuple[_DynamicFile, str]]:
#     file_info = path_manager.metadata
#     file_content = _pyserials.write.to_json_string(
#         data=content_manager.content.as_dict, sort_keys=True, indent=None
#     )
#     _logger.info(code_title="File info", code=str(file_info))
#     _logger.debug(code_title="File content", code=file_content)
#     return [(file_info, file_content)]


