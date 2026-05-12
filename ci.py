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
from subprocess import CompletedProcess, run
from typing import Any, Literal
from urllib.request import urlopen, urlretrieve

from github import Github

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s][%(levelname)s] %(message)s"
)
logger = logging.getLogger("CI")

downloads_dir = Path(__file__).parent / "downloads"
ReleaseChannel = Literal["latest", "stable", "beta"]
ScheduledReleaseChannel = Literal["latest", "stable"]
BUILD_VERSION_RE = re.compile(r"^[0-9]+[.][0-9]+[.][0-9]+[a-z]?$")
RELEASE_TAG_RE = re.compile(r"^(latest|stable|beta)-([0-9]+[.][0-9]+[.][0-9]+[a-z]?)$")


def require_env(name: str) -> str:
    """Return a required environment value or fail with a clear message."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


class IBRelease:
    def __init__(
        self,
        release: ScheduledReleaseChannel,
        program: Literal["ibgateway", "tws"],
    ) -> None:
        self.release = release
        self.program = program
        self.base_url = (
            "https://download2.interactivebrokers.com/installers/"
            f"{program}/{release}-standalone"
        )

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
        return parse_build_version(
            self.release_meta["buildVersion"].strip(),
            f"{self.program} {self.release} version metadata",
        )

    @property
    def build_datetime(self) -> datetime:
        return datetime.fromisoformat(self.release_meta["buildDateTime"].strip())

    @cached_property
    def release_meta(self) -> dict[str, Any]:
        url = f"{self.base_url}/version.json"
        resp = fetch(url)
        match = re.search(r"{.*}", resp)
        if match is None:
            raise RuntimeError(f"Could not parse release metadata from {url}")
        return json.loads(match.group())

    def __repr__(self) -> str:
        return self.tag


@dataclass
class GitHubRelease:
    release: ReleaseChannel
    build_version: str


@cache
def get_gh_repo() -> Any:
    gh = Github(require_env("GITHUB_TOKEN"))
    return gh.get_repo("djkelleher/ib-docker")


def fetch(url: str, as_text: bool = True) -> str | bytes:
    try:
        with urlopen(url, timeout=300) as response:
            status_code = response.getcode()
            logger.info(f"[{status_code}] {url}")
            content = response.read()
            if as_text:
                return content.decode("utf-8")
            return content
    except Exception as exc:
        raise RuntimeError(f"Error fetching URL {url}: {exc}") from exc


def download(url: str, save_path: Path) -> None:
    if (not os.getenv("IB_DOCKER_OVERWRITE_DOWNLOADS")) and save_path.exists():
        if save_path.stat().st_size > 0:
            logger.info(f"File already exists: {save_path}. Skipping download.")
            return
        logger.info(f"Existing download is empty: {save_path}. Re-downloading.")

    temporary_path = save_path.with_suffix(save_path.suffix + ".tmp")
    if temporary_path.exists():
        temporary_path.unlink()

    logger.info(f"Starting Download: {url}")
    try:
        urlretrieve(url, temporary_path)
        if temporary_path.stat().st_size == 0:
            raise RuntimeError("downloaded file is empty")
        temporary_path.replace(save_path)
        logger.info(f"Downloaded successfully: {save_path}")
    except Exception as exc:
        if temporary_path.exists():
            temporary_path.unlink()
        raise RuntimeError(f"Error downloading file {url}: {exc}") from exc


def download_release_file(ib_release: IBRelease) -> Path:
    downloads_dir.mkdir(exist_ok=True)
    url = ib_release.download_url
    file_name = Path(url).name
    file_name = file_name.replace(
        "-standalone-", f"-{ib_release.build_version}-standalone-"
    )
    file = downloads_dir / file_name
    download(url, file)
    return file


def parse_release_tag(tag_name: str) -> GitHubRelease:
    """Parse a GitHub release tag into release channel and IB build version."""
    match = RELEASE_TAG_RE.match(tag_name)
    if match is None:
        raise ValueError(f"Invalid release tag: {tag_name}")
    release, version = match.groups()
    return GitHubRelease(release=release, build_version=version)


def parse_build_version(version: str, source: str) -> str:
    """Validate an IB build version string before using it in release tags."""
    if not BUILD_VERSION_RE.match(version):
        raise ValueError(f"Invalid IB build version from {source}: {version}")
    return version


def docker_platforms(program: str) -> str:
    """Return supported Docker platforms for an IB product image."""
    if program == "ibgateway":
        return "linux/amd64,linux/arm64"
    if program == "tws":
        return "linux/amd64"
    raise ValueError(f"Unsupported PROGRAM: {program}")


def find_latest_github_releases() -> list[GitHubRelease]:
    """Find latest 'latest' and 'stable' releases."""
    gh_repo = get_gh_repo()
    releases: dict[str, str] = {}
    for gh_release in gh_repo.get_releases():
        try:
            release = parse_release_tag(gh_release.tag_name)
        except ValueError:
            logger.info(
                "Skipping release with unsupported tag: %s", gh_release.tag_name
            )
            continue
        if release.release == "beta":
            logger.info("Skipping beta release during scheduled release discovery")
            continue
        if release.release not in releases:
            releases[release.release] = release.build_version
            logger.info(
                "Found last GitHub release for %s: %s",
                release.release,
                release.build_version,
            )
            if len(releases) == 2:
                # have stable and latest releases for tws and gateway
                break
    return [
        GitHubRelease(release=release, build_version=version)
        for release, version in releases.items()
    ]


def create_github_releases() -> list[IBRelease]:
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
        return []

    created_releases = []
    version_programs = defaultdict(list)
    for r in new_releases:
        version_programs[(r.build_version, r.release)].append(r)
    for (version, release), ib_releases in version_programs.items():
        release_programs = {ib_release.program for ib_release in ib_releases}
        if release_programs != {"ibgateway", "tws"}:
            logger.info(
                "Skipping %s-%s release until both Gateway and TWS artifacts are available: %s",
                release,
                version,
                sorted(release_programs),
            )
            continue
        logger.info(f"Found releases for {release} {version}: {ib_releases}.")
        with ThreadPoolExecutor(max_workers=len(ib_releases)) as executor:
            files = list(executor.map(download_release_file, ib_releases))
        logger.info("Finished downloading files.")
        tag = f"{release}-{version}"
        message = "\n".join([r.description for r in ib_releases])
        logger.info(f"Creating release on GitHub ({tag}):\n{message}")
        gh_release = gh_repo.create_git_release(
            tag=tag,
            name=tag,
            message=message,
        )

        def upload_release_file(file: Path) -> None:
            logger.info(f"Uploading {file}")
            gh_release.upload_asset(path=str(file), label=file.name, name=file.name)
            hash_file = file.with_suffix(file.suffix + ".sha256")
            hash_file.write_text(
                f"{hashlib.sha256(file.read_bytes()).hexdigest()} {file.name}\n"
            )
            logger.info(f"Uploading {hash_file}")
            gh_release.upload_asset(
                path=str(hash_file), label=hash_file.name, name=hash_file.name
            )

        with ThreadPoolExecutor(max_workers=len(files)) as executor:
            list(executor.map(upload_release_file, files))
        created_releases.extend(ib_releases)
    logger.info("Done!")
    return created_releases


def build_image(params: tuple[str, str, str]) -> None:
    program, release, version = params
    version = parse_build_version(version, "Docker image build")
    dockerhub_username = require_env("DOCKERHUB_USERNAME")
    image_name = (
        f"{dockerhub_username}/"
        + {
            "ibgateway": "ib-gateway",
            "tws": "ib-tws",
        }[program]
    )
    platforms = docker_platforms(program)
    # tag with latest or stable as well as version number.
    major, minor, _ = version.split(".")
    tags = [release, version, f"{major}.{minor}"]
    if release == "latest":
        tags.append(major)

    cmd = [
        "docker",
        "buildx",
        "build",
        "--platform",
        platforms,
        "--build-arg",
        f"PROGRAM={program}",
        "--build-arg",
        f"RELEASE={release}",
        "--build-arg",
        f"VERSION={version}",
    ]
    for tag in tags:
        cmd.extend(["-t", f"{image_name}:{tag}"])
    cmd.extend(["--push", "."])

    logger.info("Building image: %s", " ".join(cmd))
    build_dir = Path(__file__).parent.joinpath("build").resolve()
    res: CompletedProcess[str] = run(
        cmd, capture_output=True, check=False, text=True, cwd=str(build_dir)
    )
    if info := res.stdout.strip():
        logger.info(info)
    if err := res.stderr.strip():
        logger.error(err)
    if res.returncode != 0:
        raise RuntimeError(f"Docker image build failed with exit code {res.returncode}")
    logger.info("Finished running image build: %s", " ".join(cmd))


def build_images(
    releases: list[IBRelease | GitHubRelease], parallel: bool = False
) -> None:
    """Build Docker images for each release."""
    params = []
    for release in releases:
        if isinstance(release, GitHubRelease):
            for prog in ("ibgateway", "tws"):
                params.append((prog, release.release, release.build_version))
        else:
            params.append((release.program, release.release, release.build_version))
    if not params:
        logger.info("No images to build.")
        return
    if parallel:
        n_workers = min(os.cpu_count() or 1, len(params))
        logger.info(f"Building images with {n_workers} workers.")
        with ThreadPoolExecutor(max_workers=n_workers) as executor:
            list(executor.map(build_image, params))
    else:
        for param in params:
            build_image(param)
    logger.info("Finished building images.")


def build_release_images(tag: str | None) -> None:
    """Build images for a release tag, or the most recent GitHub releases."""
    if tag:
        logger.info(f"Building images for provided release: {tag}")
        releases: list[IBRelease | GitHubRelease] = [parse_release_tag(tag)]
    else:
        logger.info("No release provided. Finding latest GitHub releases.")
        releases = find_latest_github_releases()
    build_images(releases)


def main() -> None:
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
