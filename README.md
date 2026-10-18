<p align="center">
  <img alt="Yggdrasilcore" src="https://github.com/user-attachments/assets/6f96adf9-1867-4ca6-b627-1bd0ab7ee494" />
</p>

# Yggdrasilcore

Welcome to Yggdrasilcore. This repository is the organisation's public home page: a single, automatically generated index of every public [Yggdrasilcore](https://github.com/yggdrasilcore) project, grouped by topic.

Yggdrasilcore is an open-source, modular MMORPG framework for the abandonware WotLK 3.3.5a (build 12340) client, grown on four generations of World of Warcraft emulation:

`MaNGOS` -> `TrinityCore` -> `SunwellCore` -> `AzerothCore` -> `Yggdrasilcore`

Read more about Yggdrasil WoW and see Yggdrasilcore in action [here](https://yggdrasilwow.com/).

<p align="center">
  <a href="https://github.com/yggdrasilcore/yggdrasilcore.github.io/actions/workflows/pages.yml"><img src="https://github.com/yggdrasilcore/yggdrasilcore.github.io/actions/workflows/pages.yml/badge.svg" alt="Pages"></a>
</p>

## What this is

The site lists every public repository that carries the `yggdrasilcore` topic. Each repository is classified by its remaining topics, with `wow` and `yggdrasilcore` ignored, so a repository tagged `wow yggdrasilcore modules` is shown as `modules`. Repositories without a topic of their own, or without the `yggdrasilcore` topic, are left out.

Each project card opens a page with a short README summary and links to the project source, to its generated documentation when GitHub Pages is available, or to a direct `.zip` download for addons.

## How it works

The [`pages`](.github/workflows/pages.yml) workflow runs once every 24 hours, and can be dispatched by hand from the Actions tab. It gathers the public repositories from the GitHub API, then asks a local [Qwen](https://github.com/QwenLM/Qwen) model running on the CI runner for a two to three sentence summary of each README. Summaries are cached by README hash and by category, so only repositories that actually changed are sent to the model, and the refreshed cache is committed back to this branch. The generated site is deployed to GitHub Pages.

## Documentation

- [Yggdrasilcore home page](https://yggdrasilcore.github.io/)

## Support

If a project is missing from the index, or a summary or link is wrong, feel free to open an issue or a pull request here.

## Contributing

This repository is privately managed. We do not recommend that emulation enthusiasts follow it. Instead, we recommend that enthusiasts contribute to the individual projects listed on the home page.

## Acknowledgements

- [GitHub Pages](https://pages.github.com/)
- [Ollama](https://ollama.com/)
- [Qwen](https://github.com/QwenLM/Qwen)

## License

- Source: This repository is distributed under the MIT License.
- Intellectual property: Yggdrasil WoW and its derivative projects are not related to Blizzard Entertainment and lay no claim to Blizzard Entertainment's copyrights or intellectual property. They operate solely as an avenue for exploring the functionality of the abandonware WotLK 3.3.5a client in an educational capacity.
