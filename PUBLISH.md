# Publishing

A release is one command, `./publish.sh`, and one thing to understand: the
script does not upload to PyPI. It creates a GitHub release, and
`.github/workflows/publish.yml` uploads when that release is published. Keeping
the upload in one place is deliberate — doing it locally *and* through the
release is how you end up with every Publish run failing with "400 File
already exists" after the package already went out.

## Where the version lives

`flight_tracer/__init__.py`, in `__version__`, and nowhere else. `setup.py`
parses it from there rather than keeping its own copy, so there's no second
literal to forget.

## Running the script

```bash
./publish.sh
```

It walks through the following, stopping at any answer that isn't yes:

1. Asks for the bump — patch, minor, major, custom or none — and refuses a
   version whose tag already exists.
2. Warns if the working directory is dirty.
3. Rewrites `__version__` and adds a dated `## [X.Y.Z]` heading to
   `CHANGELOG.md` under `[Unreleased]`. Warns if that section is empty,
   because the release notes are pulled from it verbatim.
4. Asks you to confirm the changelog, the testing and the docs.
5. Runs `pytest tests/`. A failure aborts the release.
6. Checks that `build` is installed and notes whether `gh` is available.
7. Commits `chore(release): vX.Y.Z`, pushes `main`, then tags and pushes
   `vX.Y.Z`.
8. Cleans `build/`, `dist/` and `flight_tracer.egg-info/`, then builds.
9. Offers to create the GitHub release, with notes read out of the changelog
   section for that version and the built files attached. **Say yes.** This is
   the step that publishes to PyPI. Skip it and the tag is pushed but nothing
   ships.

Then watch the upload:

```bash
gh run watch $(gh run list --workflow="Publish to PyPI" --limit 1 --json databaseId -q '.[0].databaseId')
```

## Prerequisites

```bash
pip install build
brew install gh   # or https://cli.github.com/
```

The PyPI token is a repository secret named `PYPI_API_TOKEN`, held in GitHub
rather than in your shell:

```bash
gh secret set PYPI_API_TOKEN --repo stiles/flight-tracer
```

## Version numbering

Semver, and flight-tracer is pre-1.0, so:

- **Patch** (0.2.1): bug fixes that don't change what callers pass or get back.
- **Minor** (0.3.0): new features, new arguments, changed output. Also the
  right call for a raised Python floor, a dropped dependency or a
  `summary.json` field that can now be null — anything a user can feel.
- **Major** (1.0.0): reserved for declaring the CLI and API settled.

## If something goes wrong

The tag and the GitHub release can both be removed:

```bash
git tag -d vX.Y.Z
git push origin :refs/tags/vX.Y.Z
gh release delete vX.Y.Z
```

A PyPI release can't be deleted, and it can't be replaced: that version number
is spent even if you yank it. Yanking hides it from resolvers while leaving it
installable by exact pin, and it's done from the project page on PyPI under
Manage, not from the command line. The fix for a bad release is a new patch
version.

## Doing it by hand

Only if the script is broken, and mind the one rule — build and tag locally, but
let the release do the uploading.

```bash
# 1. Bump the single version literal, move [Unreleased] in CHANGELOG.md
# 2. Commit, push, tag
git add flight_tracer/__init__.py CHANGELOG.md
git commit -m "chore(release): vX.Y.Z"
git push origin main
git tag vX.Y.Z && git push origin vX.Y.Z

# 3. Build
rm -rf build dist flight_tracer.egg-info
python3 -m build

# 4. Create the release (triggers the PyPI upload via the workflow)
gh release create vX.Y.Z dist/* --title "Release vX.Y.Z" --notes "..."
```
