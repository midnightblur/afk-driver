# Each setting has one owner: team, personal or machine

> Status: Accepted
> Layer: Requirements
> Context ticket: setup-per-repo

A team setting comes from the committed AFK file when one exists, and the developer's files cannot override it there. With no committed file, setup keeps team settings in the repository personal file, so nothing is shared with a team that does not use AFK. A personal setting lives only in the developer's files, and a machine setting only in the machine file; a value at any other place is ignored with a warning. A team change therefore reaches every developer at once, and no private copy can fall behind.

## Considered Options

- Every forge and tracker setting private to the developer: rejected, because a team change to a status name or label leaves private copies behind with no warning.
- The personal file may override a team setting: rejected for the same reason.
