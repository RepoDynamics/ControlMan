# Standard libraries
import argparse
import json
import os
import subprocess

from repodynamics.meta import data


class MergeLogger:

    def __init__(self, path_event_payload_file: str, path_root: str = None):
        with open(path_event_payload_file) as f:
            self.event = json.load(f)
        self.metadata = data(path_root=path_root)
        return

    def run(self):
        latest_tag = self.latest_tag()
        if not latest_tag:
            self.initial_release()
        else:
            release, docs = self.update_type()
            if any(release):
                self.release(release, latest_tag)
            elif docs:
                self.docs()
            else:
                self.maintenance()
        return

    def release(self, release: list[bool], latest_tag: list[int]):
        log = f"## {self.event['pull_request']['title']}\n{self.event['pull_request']['body']}"
        with open("CHANGELOG.md", "a") as f:
            f.write(log)
        if release[0]:
            new_version = f"v{latest_tag[0] + 1}.0.0"
        elif release[1]:
            new_version = f"v{latest_tag[0]}.{latest_tag[1] + 1}.0"
        else:
            new_version = f"v{latest_tag[0]}.{latest_tag[1]}.{latest_tag[2] + 1}"
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            print(f"tag={new_version}", file=fh)
            print(f"release=true", file=fh)
            print(f"docs=true", file=fh)
        with open("RELEASE.md", "w") as f:
            f.write(log)
        return

    def docs(self):
        with open("docs/CHANGELOG.md", "a") as f:
            f.write(f"## {self.event.pull_request.title}\n{self.event.pull_request.body}\n")
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            print(f"docs=true", file=fh)
            print(f"release=false", file=fh)
        return

    def maintenance(self):
        with open("dev/CHANGELOG.md", "a") as f:
            f.write(f"## {self.event.pull_request.title}\n{self.event.pull_request.body}\n")
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            print(f"docs=false", file=fh)
            print(f"release=false", file=fh)
        return

    def update_type(self):
        release = [False, False, False]
        docs = False
        for label in self.labels:
            if label == "Deploy: docs":
                docs = True
            elif label.startswith("Release: "):
                for segment, release_type in enumerate(["major", "minor", "patch"]):
                    if label == f"Release: {release_type}":
                        release[segment] = True
        return release, docs
