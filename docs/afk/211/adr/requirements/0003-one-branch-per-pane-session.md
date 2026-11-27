# Small asks of one pane session share 1 branch

> Layer: Requirements
> Context ticket: 211

All small asks of one afkv2 pane session land on 1 branch and 1 Draft change, with 1 section per ask. An ask that needs the medium lane gets its own branch. The developer accepted the trade-off: a finished ask cannot merge while another is half done, and 1 review covers unrelated asks.

## Considered Options

- 1 branch per ask. Rejected by the developer in i-branch and again in i-onebranch.
- 1 branch for every ask, a medium-lane ask included. Rejected in i-onebranch, because the medium lane needs its own feature branch and run branch.
