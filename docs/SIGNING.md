# Code signing for make-covers.exe

Windows shows "Windows protected your PC / unknown publisher" for programs
that are not signed. The SignPath Foundation signs open source programs for
free, with its own certificate, as long as the program is built from public
source code by GitHub Actions. The build workflow
(`.github/workflows/make-covers.yml`) already has the signing step: it is
skipped until the settings below exist, so nothing changes until then.

## 1. Apply (once, by the repository owner)

1. Read the conditions at <https://signpath.org/terms> and apply at
   <https://signpath.org/apply>. What they check:
   - an OSI approved licence (SuperFW is GPL),
   - the program is built from this public repository by GitHub Actions,
   - a code signing policy is published (section 3 below, link it from the
     README),
   - the people who can start a signing request use two-factor
     authentication on GitHub.
2. Once accepted, SignPath creates an organization and a project for
   SuperFW. In the project:
   - Trusted build system: add **GitHub.com** and link it to the project.
   - Artifact configuration (the GitHub artifact is a zip with the .exe):

     ```xml
     <artifact-configuration xmlns="http://signpath.io/artifact-configuration/v1">
       <zip-file>
         <pe-file path="make-covers.exe">
           <authenticode-sign/>
         </pe-file>
       </zip-file>
     </artifact-configuration>
     ```

   - Signing policy: `release-signing` (manual approval by the owner is
     fine, the build waits for it).
   - Create a CI user and an API token for it, with permission to submit
     signing requests for that policy.

## 2. Repository settings

GitHub, repository **Settings > Secrets and variables > Actions**:

| Kind     | Name                           | Value                          |
|----------|--------------------------------|--------------------------------|
| Secret   | `SIGNPATH_API_TOKEN`           | the CI user's API token        |
| Variable | `SIGNPATH_ORGANIZATION_ID`     | the organization id (a GUID)   |
| Variable | `SIGNPATH_PROJECT_SLUG`        | ie. `superfw`                  |
| Variable | `SIGNPATH_SIGNING_POLICY_SLUG` | `release-signing`              |

From then on every build of the cover tool sends the .exe to SignPath and
publishes the signed one. The release notes stop saying "not signed".

## 3. Code signing policy

Text to publish (SignPath requires it):

> Free code signing provided by [SignPath.io](https://signpath.io),
> certificate by [SignPath Foundation](https://signpath.org).
>
> Only `make-covers.exe`, built by GitHub Actions from this repository, is
> signed. Committers and reviewers: the repository owner. Approvers (who
> approve each signing request): the repository owner.
>
> The program sends no data anywhere. It only downloads box art and game
> lists (libretro-thumbnails and the libretro No-Intro lists) from GitHub
> (api.github.com, raw.githubusercontent.com) while it runs.
