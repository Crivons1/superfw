# Code signing for make-covers.exe

Windows shows "Windows protected your PC / unknown publisher" for programs
that are not signed. The SignPath Foundation signs open source programs for
free, with its own certificate, when they are built from public source code
by GitHub Actions.

Everything on the repository side is ready:

 - `.github/workflows/make-covers.yml` uploads the unsigned .exe as a GitHub
   artifact and sends it to SignPath (`signpath/github-action-submit-signing-request@v2`),
   waits for the signed file and publishes that one. The step is skipped
   while the `SIGNPATH_API_TOKEN` secret does not exist.
 - The .exe carries the product name "SuperFW cover maker" and the tool's
   version (`VERSION` in `tools/make-covers.py`, written by
   `tools/exe-version-info.py`), which SignPath requires.
 - The README has the "Code signing policy" section (attribution, roles,
   privacy) and every release links to it.
 - `tools/make-covers.py` states its licence (GPL-3.0-or-later, like the rest
   of SuperFW).

What is left needs the repository owner's own accounts.

## 1. Before applying

 - Turn on two-factor authentication on GitHub
   (Settings > Password and authentication). SignPath requires it for
   everyone who can change the code or approve signing.

## 2. Apply

At <https://signpath.org/apply>. Answers for the form:

| Question | Answer |
|---|---|
| Project name | SuperFW cover maker (SuperFW carousel fork) |
| Repository | https://github.com/Crivons1/superfw |
| Homepage / download page | https://github.com/Crivons1/superfw#readme and https://github.com/Crivons1/superfw/releases |
| Licence | GPL-3.0-or-later |
| What is signed | `make-covers.exe`, a Windows program that makes cover art files for the SuperFW (GBA flash cart firmware) carousel. One file, built by PyInstaller from `tools/make-covers.py`. |
| Build system | GitHub Actions, `.github/workflows/make-covers.yml` |
| Code signing policy | https://github.com/Crivons1/superfw#code-signing-policy |
| Team | Crivons1 (author, reviewer, approver) |

Be upfront that the repository is a fork of davidgfnet/superfw: the program
to sign (the cover maker) is the fork's own code, upstream has no such
program and publishes no signed builds. SignPath decides whether that counts
as an "own project"; if they ask for it, the cover maker can move to a
repository of its own and keep the same workflow.

## 3. After SignPath approves

In the SignPath web app, in the project they create:

1. **Trusted build system**: add GitHub.com and link it to the project.
2. **Artifact configuration** (the GitHub artifact is a zip with the .exe),
   with the product name restriction SignPath requires:

   ```xml
   <?xml version="1.0" encoding="utf-8"?>
   <artifact-configuration xmlns="http://signpath.io/artifact-configuration/v1">
     <zip-file>
       <pe-file path="make-covers.exe" product-name="SuperFW cover maker">
         <authenticode-sign/>
       </pe-file>
     </zip-file>
   </artifact-configuration>
   ```

   Note its slug (ie. `initial`).
3. **Signing policy**: `release-signing`, approver: yourself. Each build then
   waits until you approve it in SignPath (up to an hour, then it fails;
   run it again after approving).
4. **CI user**: create one, give it "submitter" rights on that policy and
   create an API token for it.

## 4. Repository settings

GitHub, repository **Settings > Secrets and variables > Actions**:

| Kind     | Name                                   | Value                         |
|----------|----------------------------------------|-------------------------------|
| Secret   | `SIGNPATH_API_TOKEN`                   | the CI user's API token       |
| Variable | `SIGNPATH_ORGANIZATION_ID`             | the organization id (a GUID)  |
| Variable | `SIGNPATH_PROJECT_SLUG`                | the project slug              |
| Variable | `SIGNPATH_SIGNING_POLICY_SLUG`         | `release-signing`             |
| Variable | `SIGNPATH_ARTIFACT_CONFIGURATION_SLUG` | the artifact configuration slug |

Or from a terminal with the GitHub CLI (it asks for the token, so it never
ends up in the shell history):

    gh secret set SIGNPATH_API_TOKEN -R Crivons1/superfw
    gh variable set SIGNPATH_ORGANIZATION_ID -R Crivons1/superfw --body "<organization id>"
    gh variable set SIGNPATH_PROJECT_SLUG -R Crivons1/superfw --body "<project slug>"
    gh variable set SIGNPATH_SIGNING_POLICY_SLUG -R Crivons1/superfw --body "release-signing"
    gh variable set SIGNPATH_ARTIFACT_CONFIGURATION_SLUG -R Crivons1/superfw --body "<artifact configuration slug>"

Then run the "make-covers" workflow (Actions > make-covers > Run workflow),
approve the request in SignPath, and the signed .exe replaces the unsigned
one in the make-covers-latest release. The release notes stop saying "not
signed".
