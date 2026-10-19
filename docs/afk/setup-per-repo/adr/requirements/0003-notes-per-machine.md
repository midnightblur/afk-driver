# Developer notes are per machine; agent working files stay in the repository

> Status: Accepted
> Layer: Requirements
> Context ticket: setup-per-repo

The note-taking app, the Notion parent page and the Obsidian vault are the developer's own choice for their machine, with no setting per repository. The app holds only developer notes. Agents write every working file for a work item into the repository's spec folder, whatever app is chosen. Otherwise one developer's choice of app would move a repository's requirements out of the repository on that machine only.

## Considered Options

- Notes settings per repository, owned by the team: rejected, because there is no team note-taking practice.
- A folder per repository inside the shared vault: rejected, because agent files no longer go to the vault.
