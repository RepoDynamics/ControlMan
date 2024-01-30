import actionman

from repodynamics import action

if __name__ == "__main__":
    actionman.logger.create(
        realtime_output=True,
        github_console=True,
        initial_section_number=2,
        exit_code_critical=1,
        output_html_filepath="log.html",
        root_heading="Execute Action",
        html_title="ProMan Action Log",
    )
    action.run()
