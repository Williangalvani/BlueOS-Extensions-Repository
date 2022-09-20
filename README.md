# BlueOS-Extensions-Repository

> **Warning**
> This is still very experimental and subject to changes!

This is a repository for metadata of BlueOS Extensions.

For publishing a new extension, open a pull request agains this repository with the following structure:

## Data in this repository

/repos/yourcompany/yourextension/metadata.json
```
{
    "identifier": "your.uniqueidentifier",
    "name": "The Name Of Your Extension",
    "website": "https://your.extension.website.com/",
    "docker": "your-dockerhub-user/your-extension-docker",
    "description": "A brief description of your extension. This will be shown in the store card."
}
````

/repos/yourcompany/yourextension/company_logo.png
Your company logo

/repos/yourcompany/yourextension/extension_logo.json
Your extension logo

## Data in dockerhub

Additionally, we have versioned data. This data should be in each of your dockerhub tags, and use the following format:

```
LABEL version="1.0.0"
LABEL permissions '{\
  "ExposedPorts": {\
    "80/tcp": {}\          // we have a server at port 80
  },\
  "HostConfig": {\
    "PortBindings": {\
      "80/tcp": [\         // our server at port 80 is automatically bound to a free port in the host
        {\
          "HostPort": ""\
        }\
      ]\
    }\
  }\
}'
LABEL authors='[\
    {\
        "name": "John Doe",\
        "email": "doe@john.com"\
    }\
]'
LABEL docs='http://path.to.your.docs.com'
LABEL company='{\
  "about": "",\
```

 - `version` is the version for the current tag.
 - `permissions`is a json file that follows the [Docker API payload for creating containers](https://docs.docker.com/engine/api/v1.41/#tag/Container/operation/ContainerCreate).
 - `authors` is a json list of authors of your extension
 - `docs` is a url for your docs.
 - `company` is a json, which currently only contains an "about" section for a brief description about your company.

 ## How this repo works

 Every time this repo changes, a Github Action runs and goes through all the .json files in here. For each of them, it reaches out to dockerhub and fetches all the available tags, extracting the metadata in LABELS and crafting a complete `manifest.json`, which is stored in this repo's gh-pages branch.
