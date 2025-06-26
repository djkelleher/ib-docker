import argparse
import hashlib
import json
import logging
import os
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from functools import cache, cached_property
from pathlib import Path
from subprocess import run
from typing import List, Literal, Union
from urllib.request import urlopen, urlretrieve

from github import Github

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s][%(levelname)s] %(message)s"
)
logger = logging.getLogger("CI")

downloads_dir = Path(__file__).parent / "downloads"
downloads_dir.mkdir(exist_ok=True)

docker_user = os.environ["DOCKERHUB_USERNAME"]
docker_password = os.environ["DOCKERHUB_TOKEN"]
github_token = os.environ["GITHUB_TOKEN"]


class IBRelease:
    def __init__(
        self, release: Literal["latest", "stable"], program: Literal["ibgateway", "tws"]
    ) -> None:
        self.release = release
        self.program = program
        self.base_url = f"https://download2.interactivebrokers.com/installers/{program}/{release}-standalone"

    @property
    def title(self) -> str:
        if self.program == "ibgateway":
            program = "Gateway"
        elif self.program == "tws":
            program = "TWS"
        return f"{program} {self.release.capitalize()} {self.build_version}"

    @property
    def description(self) -> str:
        return f"{self.title}. Build time: {self.build_datetime}"

    @property
    def tag(self) -> str:
        return f"{self.program}-{self.release}-{self.build_version}"

    @property
    def download_url(self) -> str:
        return f"{self.base_url}/{self.program}-{self.release}-standalone-linux-x64.sh"

    @property
    def build_version(self) -> str:
        return self.release_meta["buildVersion"].strip()

    @property
    def build_datetime(self) -> datetime:
        return datetime.fromisoformat(self.release_meta["buildDateTime"].strip())

    @cached_property
    def release_meta(self):
        url = f"{self.base_url}/version.json"
        resp = fetch(url)
        return json.loads(re.search(r"{.*}", resp).group())

    def __repr__(self) -> str:
        return self.tag


@dataclass
class GitHubRelease:
    release: Literal["latest", "stable"]
    build_version: str


@cache
def get_gh_repo():
    gh = Github(github_token)
    return gh.get_repo("DankLabDev/ib-docker")


def fetch(url: str, as_text: str = True):
    try:
        with urlopen(url, timeout=300) as response:
            status_code = response.getcode()
            logger.info("[%i] %s", status_code, url)
            content = response.read()
            if as_text:
                return content.decode("utf-8")
            return content
    except Exception as e:
        logger.info("Error fetching URL: %s", e)


def download(url: str, save_path: str):
    if (not os.getenv("IB_DOCKER_OVERWRITE_DOWNLOADS")) and os.path.exists(save_path):
        logger.info("File already exists: %s. Skipping download.", save_path)
        return
    logger.info("Starting Download: %s", url)
    try:
        urlretrieve(url, save_path)
        logger.info("Downloaded successfully: %s", save_path)
    except Exception as e:
        logger.info("Error downloading file: %s", e)


def download_release_file(ib_release: IBRelease):
    url = ib_release.download_url
    file_name = Path(url).name
    file_name = file_name.replace(
        "-standalone-", f"-{ib_release.build_version}-standalone-"
    )
    file = downloads_dir / file_name
    download(url, file)
    return file


def find_latest_github_releases() -> List[GitHubRelease]:
    """Find latest 'latest' and 'stable' releases."""
    gh_repo = get_gh_repo()
    releases = {}
    for release in gh_repo.get_releases():
        release, version = release.tag_name.split("-")
        if release not in releases:
            releases[release] = version
            logger.info(
                "Found last GitHub release for %s: %s",
                release,
                version,
            )
            if len(releases) == 2:
                # have stable and latest releases for tws and gateway
                break
    return [
        GitHubRelease(release=release, build_version=version)
        for release, version in releases.items()
    ]


def create_github_releases() -> List[IBRelease]:
    """Create GitHub releases for new stable/latest releases."""
    gh_repo = get_gh_repo()
    last_releases = {r.release: r.build_version for r in find_latest_github_releases()}
    new_releases = []
    for program in ("ibgateway", "tws"):
        for release in ("latest", "stable"):
            current_release = IBRelease(release=release, program=program)
            last_release = last_releases.get(release)
            if last_release != current_release.build_version:
                new_releases.append(current_release)
                logger.info(
                    "Found new release for %s %s: %s. Previous release: %s.",
                    program,
                    release,
                    current_release.build_version,
                    last_release,
                )
    if not new_releases:
        logger.info("No new releases found.")
        return

    version_programs = defaultdict(list)
    for r in new_releases:
        version_programs[(r.build_version, r.release)].append(r)
    for (version, release), ib_releases in version_programs.items():
        logger.info("Found releases for %s %s: %s.", release, version, ib_releases)
        with ThreadPoolExecutor(max_workers=len(new_releases)) as executor:
            files = list(executor.map(download_release_file, ib_releases))
        logger.info("Finished downloading files.")
        tag = f"{release}-{version}"
        message = "\n".join([r.description for r in new_releases])
        logger.info("Creating release on GitHub (%s):\n%s", tag, message)
        gh_release = gh_repo.create_git_release(
            tag=tag,
            name=tag,
            message=message,
        )

        def upload_release_file(file):
            logger.info("Uploading %s", file)
            gh_release.upload_asset(path=str(file), label=file.name, name=file.name)
            hash_file = file.with_suffix(file.suffix + ".sha256")
            hash_file.write_text(
                f"{hashlib.sha256(file.read_bytes()).hexdigest()} {file.name}"
            )
            logger.info("Uploading %s", hash_file)
            gh_release.upload_asset(
                path=str(hash_file), label=hash_file.name, name=hash_file.name
            )

        with ThreadPoolExecutor(max_workers=len(files)) as executor:
            executor.map(upload_release_file, files)
    logger.info("Done!")
    return new_releases


def build_image(params):
    program, release, version = params
    image_name = {"ibgateway": "ib-gateway", "tws": "ib-tws"}[program]
    # tag with latest or stable as well as version number.
    major, minor, _ = version.split(".")
    tags = [release, version, f"{major}.{minor}"]
    if release == "latest":
        tags.append(major)
    img_tags = " -t ".join([f"{image_name}:{tag}" for tag in tags])
    os.chdir("build")
    cmd = (
        f"docker buildx build --platform linux/amd64,linux/arm64 "
        f"--build-arg PROGRAM={program} --build-arg RELEASE={release} --build-arg VERSION={version} "
        f"-t {img_tags} --push ."
    )
    logger.info("Building image: %s", cmd)
    res = run(cmd.split(), capture_output=True, check=False, text=True)
    if info := res.stdout.strip():
        logger.info(info)
    if err := res.stderr.strip():
        logger.error(err)
    logger.info("Finished running image build: %s", cmd)


def build_images(
    releases: List[Union[IBRelease, GitHubRelease]], parallel: bool = False
):
    """Build Docker images for each release."""
    params = []
    for release in releases:
        if isinstance(release, GitHubRelease):
            for prog in ("ibgateway", "tws"):
                params.append((prog, release.release, release.build_version))
        else:
            params.append((release.program, release.release, release.build_version))
    if parallel:
        n_workers = min(os.cpu_count(), len(params))
        logger.info("Building images with %i workers.", n_workers)
        with ThreadPoolExecutor(max_workers=n_workers) as executor:
            executor.map(build_image, params)
    else:
        for param in params:
            build_image(param)
    logger.info("Finished building images.")


def build_release_images(tag: str):
    """Build image for release with provided tag, or most recent 'latest' and 'stable' releases if no tag is provided GitHub."""
    if tag:
        logger.info("Building images for provided release: %s", tag)
        release, build_version = tag.split("-")
        releases = [GitHubRelease(release=release, build_version=build_version)]
    else:
        logger.info("No release provided. Finding latest GitHub releases.")
        releases = find_latest_github_releases()
    build_images(releases)


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    # Release subcommand
    subparsers.add_parser("release", help="Create GitHub releases.")
    # Build subcommand
    parser_build = subparsers.add_parser(
        "build", help="Build release image from tag or latest."
    )
    parser_build.add_argument(
        "tag", nargs="?", help="Tag in format <release>-<build_version>"
    )

    args = parser.parse_args()
    if args.command == "release":
        create_github_releases()
    elif args.command == "build":
        build_release_images(args.tag)


if __name__ == "__main__":
    main()
