# Unlimilist

## Branches (strong rule)

- **Every feature, and every bugfix related to it, is done on the `dev` branch by default.** Never commit feature or fix work directly to `main` unless the user explicitly says so for that change.
- Before starting a feature or fix, switch to `dev` and bring it up to date with `origin/dev` and `origin/main`. Commit and push there.
- When a feature is finished, open a pull request from `dev` to `main` for the user to merge on GitHub. Don't merge it yourself.
- Pre-releases (dogfood builds such as `1.6.0rc1`) and releases are built and tagged on `main`, after the pull request is merged.
