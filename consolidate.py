import asyncio
import dataclasses
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
from registry import Registry

REPO_ROOT = "https://raw.githubusercontent.com/Williangalvani/BlueOS-Extensions-Repository/master/repos"


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)


@dataclasses.dataclass
class Author:
    name: str
    email: str

    @staticmethod
    def from_json(json_dict: Dict):
        return Author(name=json_dict["name"], email=json_dict["email"])


@dataclasses.dataclass
class Company:
    name: str
    about: str
    email: str

    @staticmethod
    def from_json(json_dict: Dict):
        if json_dict is None:
            return None
        return Company(name=json_dict["name"], email=json_dict.get("email", None), about=json_dict.get("about", None))


# pylint: disable=too-many-instance-attributes
@dataclasses.dataclass
class Version:
    permissions: Optional[Dict[str, Any]]
    requirements: Optional[str]
    tag: Optional[str]
    website: str
    authors: List[Author]
    docs: Optional[str]
    readme: Optional[str]
    company: Optional[Company]
    support: Optional[str]


@dataclasses.dataclass
class RepositoryEntry:
    identifier: str
    name: str
    description: str
    docker: str
    versions: Dict[str, Version]
    extension_logo: Optional[str]
    company_logo: Optional[str]


class Consolidator:
    registry = Registry()
    consolidated_data: List[Dict[str, Any]] = []

    async def fetch_readme(self, url):
        if not url.startswith("http"):
            print(f"This is not a valid url: '{url}'; Assuming it is an inline readme")
            return url
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    print(f"Error status {resp.status}")
                    raise Exception(f"Could not get readme {url}")
                return await resp.text()

    async def all_repositories(self):
        repos = Path("./repos")
        for repo in repos.glob("**/*.json"):
            with open(repo, "r", encoding="utf-8") as individual_file:
                try:
                    data = json.load(individual_file)
                except Exception as exc:
                    raise Exception(f"Unable to parse file {repo}") from exc
                extension_logo = (repo / "../extension_logo.png").resolve().relative_to(repos.resolve())
                company_logo = (repo / "../company_logo.png").resolve().relative_to(repos.resolve())
                readme = data.get("readme", None)
                if readme:
                    readme = await self.fetch_readme(readme)
                try:
                    new_repo = RepositoryEntry(
                        identifier=data["identifier"],
                        name=data["name"],
                        docker=data["docker"],
                        description=data["description"],
                        extension_logo=f"{REPO_ROOT}/{extension_logo}" if extension_logo else "",
                        versions={},
                        company_logo=f"{REPO_ROOT}/{company_logo}" if company_logo else None,
                    )
                    yield new_repo
                except Exception as error:
                    raise Exception(f"unable to read file {individual_file}: {error}") from error

    async def run(self):
        async for repository in self.all_repositories():
            for tag in await self.registry.fetch_remote_tags(repository.docker):
                try:
                    raw_labels = await self.registry.fetch_labels(f"{repository.docker}:{tag}")
                    permissions = raw_labels.get("permissions", None)
                    website = raw_labels.get("website", None)
                    authors = raw_labels.get("authors", None)
                    docs = raw_labels.get("docs", None)
                    readme = raw_labels.get("readme", "").replace(r"{tag}", tag)
                    company_raw = raw_labels.get("company", None)
                    company = Company.from_json(json.loads(company_raw)) if company_raw is not None else None
                    support = raw_labels.get("support", None)

                    new_version = Version(
                        permissions=json.loads(permissions) if permissions else None,
                        website=website,
                        authors=json.loads(authors) if authors else [],
                        docs=json.loads(docs) if docs else None,
                        readme=await self.fetch_readme(readme),
                        company=company,
                        support=support,
                        requirements=raw_labels.get("requirements", None),
                        tag=tag,
                    )
                    repository.versions[tag] = new_version
                except KeyError as error:
                    raise Exception(f"unable to parse repository {repository}: {error}") from error
            self.consolidated_data.append(repository)

        with open("manifest.json", "w", encoding="utf-8") as manifest_file:
            manifest_file.write(json.dumps(self.consolidated_data, indent=4, cls=EnhancedJSONEncoder))


consolidator = Consolidator()
asyncio.run(consolidator.run())
