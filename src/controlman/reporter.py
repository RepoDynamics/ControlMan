
from markitup.html import elem as _html
from markitup import doc as _doc
from controlman.datatype import (
    DynamicFileChangeType,
    DynamicDirType,
    DynamicFile as _GeneratedFile,
    DynamicDir as _DynamicDir,
)


class ControlCenterReporter:

    def __init__(
        self,
        metadata: list[tuple[str, DynamicFileChangeType]],
        files: list[_GeneratedFile],
        dirs: list[_DynamicDir],
    ):
        self.metadata = metadata
        self.files = files
        self.dirs = dirs
        self.has_changed_metadata = bool(self.metadata)
        self.has_changed_files = any(
            file.change not in (DynamicFileChangeType.DISABLED, DynamicFileChangeType.UNCHANGED)
            for file in self.files
        )
        self.has_changed_dirs = any(
            dir_.change not in (DynamicFileChangeType.DISABLED, DynamicFileChangeType.UNCHANGED)
            for dir_ in self.dirs
        )
        self.has_changes = self.has_changed_metadata or self.has_changed_files or self.has_changed_dirs
        return

    def report(self) -> _doc.Document:
        if not self.has_changes:
            content = (
                "All dynamic content were in sync with control center configurations. No changes were made."
            )
            return self._create_document(content=content)
        changed_categories = []
        category_details = []
        for category_name, category_changed, category_reporter in (
            ("metadata", self.has_changed_metadata, self._report_metadata),
            ("files", self.has_changed_files, self._report_files),
            ("directories", self.has_changed_dirs, self._report_dirs),
        ):
            if category_changed:
                changed_categories.append(category_name)
                category_details.append(category_reporter())
        changed_categories_str = self._comma_list(changed_categories)
        verb = "was" if len(changed_categories) == 1 else "were"
        content = f"Project's {changed_categories_str} {verb} out of sync with control center configurations."
        section = _html.ul([_html.li(detail) for detail in category_details])
        return self._create_document(content=content, section=section)

    def _create_document(self, content, section=None) -> _doc.Document:
        details_section = _doc.from_contents(
            heading="Changes",
            content={"details": section},
        )
        return _doc.from_contents(
            heading="Control Center Report",
            content={"summary": content},
            section={"changes": details_section} if section else None,
        )

    def _report_metadata(self):
        rows = []
        for changed_key, change_type in sorted(self.metadata, key=lambda elem: elem[0]):
            change = change_type.value
            rows.append([_html.code(changed_key), (change.emoji, {"title": change.title})])
        figure = _html.table_from_rows(
            rows_body=rows,
            rows_head=[["Path", "Change"]],
            as_figure=True,
            caption=f"Changes in the project's metadata.",
        )
        return _html.details([_html.summary("ℹ️ Metadata"), figure])

    def _report_files(self):
        rows = []
        for file in sorted(
            self.files,
            key=lambda elem: (elem.type.value[1], elem.subtype[1]),
        ):
            if file.change in (DynamicFileChangeType.DISABLED, DynamicFileChangeType.UNCHANGED):
                continue
            change = file.change.value
            rows.append(
                [
                    file.type.value[1],
                    file.subtype[1],
                    (change.emoji, {"title": change.title}),
                    _html.code(file.path),
                    _html.code(file.path_before) if file.path_before else "—"
                ]
            )
        if not rows:
            return
        figure = _html.table_from_rows(
            rows_body=rows,
            rows_head=[["Type", "Subtype", "Change", "Path", "Old Path"]],
            as_figure=True,
            caption=f"Changes in the project's dynamic files.",
        )
        return _html.details([_html.summary("📝 Files"), figure])

    def _report_dirs(self):
        rows = []
        for dir_ in sorted(self.dirs, key=lambda elem: elem.type.value):
            if dir_.change in (DynamicFileChangeType.DISABLED, DynamicFileChangeType.UNCHANGED):
                continue
            change = dir_.change.value
            rows.append(
                [
                    dir_.type.value,
                    (change.emoji, {"title": change.title}),
                    _html.code(dir_.path),
                    _html.code(dir_.path_before or "—"),
                ]
            )
        if not rows:
            return
        figure = _html.table_from_rows(
            rows_body=rows,
            rows_head=[["Type", "Change", "Path", "Old Path"]],
            as_figure=True,
            caption=f"Changes in the project's dynamic directories.",
        )
        return _html.details([_html.summary("🗂 Directories"), figure])

    @staticmethod
    def _comma_list(l):
        if len(l) == 1:
            return l[0]
        if len(l) == 2:
            return f"{l[0]} and {l[1]}"
        return f"{", ".join(l[:-1])}, and {l[-1]}"