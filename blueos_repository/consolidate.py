#!/usr/bin/env python3
import asyncio
import dataclasses
import json
from pathlib import Path
from typing import AsyncIterable, Dict, Optional, Tuple

import json5
from docker.models.repo import RepoInfo
from docker.registry import DockerRegistry
from extension import Extension
from extension.models import ExtensionMetadata, ExtensionVersion
from logger import Logger
from utils import EnhancedJSONEncoder

MANIFEST_FILE = "manifest.json"

MANIFEST_LOG = "manifest.log"

REPO_ROOT_URL = "https://williangalvani.github.io/BlueOS-Extensions-Repository/repos"


@dataclasses.dataclass
class RepositoryEntry(ExtensionMetadata):
    """
    Represents a repository entry in the manifest output

    Attributes:
        versions (Dict[str, Version]): Available extension versions.
    """

    versions: Dict[str, ExtensionVersion] = dataclasses.field(default_factory=dict)
    repo_info: Optional[RepoInfo] = None


class Consolidator:
    """
    This class is used to consolidate the BlueOS extensions repository generating
    a manifest file with all the extensions available and their versions.
    """

    @staticmethod
    def repo_folder() -> Path:
        return Path(__file__).parent.parent.joinpath("repos")

    def fetch_remote_extension_logos(
        self, identifier: str, repository: Path, repositories: Path
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Fetch the remote extension and company logos for a given repository.

        Args:
            identifier (str): Extension identifier.
            repository (Path): Path to the repository folder.
            repositories (Path): Path to the repositories folder.

        Returns:
            Tuple[Optional[str], Optional[str]]: Remote extension and company logos URLs.
        """

        company_logo = (repository / "../../company_logo.png").resolve().relative_to(repositories.resolve())
        extension_logo_file = (repository / "../extension_logo.png").resolve()

        if extension_logo_file.exists():
            extension_logo = extension_logo_file.resolve().relative_to(repositories.resolve())
        else:
            Logger.warning(
                identifier, f"Extension logo not found for {identifier}, trying to use company logo as alternative"
            )
            extension_logo = company_logo

        remote_extension_logo = f"{REPO_ROOT_URL}/{extension_logo}" if extension_logo else None
        remote_company_logo = f"{REPO_ROOT_URL}/{company_logo}" if company_logo else None

        if not remote_company_logo or not remote_extension_logo:
            Logger.warning(identifier, f"Unable to find extension or company logo for {identifier}")

        return remote_extension_logo, remote_company_logo

    async def fetch_extensions_metadata(self) -> AsyncIterable[ExtensionMetadata]:
        """
        Fetch the metadata for all the extensions in the repository.

        Returns:
            List[ExtensionMetadata]: List of all the extensions metadata.
        """

        repos = self.repo_folder()

        for repo in repos.glob("**/metadata.json"):
            with open(repo, "r", encoding="utf-8") as metadata_file:
                company, extension_name = repo.as_posix().split("/")[-3:-1]
                identifier = ".".join([company, extension_name])

                Logger.info(identifier, f"Starting metadata processing for {identifier}")

                try:
                    data = json5.load(metadata_file)
                except Exception as error:  # pylint: disable=broad-except
                    Logger.error(identifier, f"Skipping {identifier}, unable to parse metadata file, error: {error}")
                    continue

                extension_logo, company_logo = self.fetch_remote_extension_logos(identifier, repo, repos)

                try:
                    metadata = ExtensionMetadata(
                        identifier=identifier,
                        name=data["name"],
                        docker=data["docker"],
                        description=data["description"],
                        website=data["website"],
                        extension_logo=extension_logo,
                        company_logo=company_logo,
                    )

                    Logger.info(identifier, f"Finished metadata processing for {identifier}")
                    yield metadata
                except Exception as error:  # pylint: disable=broad-except
                    Logger.error(identifier, f"Skipping {identifier}, invalid metadata file, error: {error}")
                    continue

    async def run(self) -> None:
        preview = DockerRegistry.from_preview()

        try:
            Logger.start_docker_rate_limit(await preview.get_rate_limit())
        except Exception as error:  # pylint: disable=broad-except
            print(f"Unable to fetch initial docker rate limit, error: {error}")

        extensions = [Extension(metadata) async for metadata in self.fetch_extensions_metadata()]

        await asyncio.gather(*(ext.inflate() for ext in extensions))

        consolidated_data = [
            RepositoryEntry(
                **dataclasses.asdict(ext.metadata),
                versions=ext.sorted_versions,
                repo_info=ext.repo_info,
            )
            for ext in extensions
            if ext.sorted_versions
        ]

        try:
            Logger.final_docker_rate_limit(await preview.get_rate_limit())
        except Exception as error:  # pylint: disable=broad-except
            print(f"Unable to fetch final docker rate limit, error: {error}")

        with open(MANIFEST_FILE, "w", encoding="utf-8") as manifest_file:
            manifest_file.write(json.dumps(consolidated_data, indent=4, cls=EnhancedJSONEncoder))

        Logger.dump(MANIFEST_LOG)


consolidator = Consolidator()
asyncio.run(consolidator.run())
