# fonts

Self-hosted woff2, no CDN and no `<link>` to Google Fonts — the app must render
correctly with the network off (DESIGN.md §2).

Three families, all SIL OFL 1.1, licence text beside them:

| family | cuts here | why these |
|---|---|---|
| Fraunces | 600 normal, 600 italic | §2 uses Fraunces at 600 only. The record-name role bakes the italic in, because a monograph's title *is* a binomial. |
| IBM Plex Sans | 400, 500, 600 normal · 400 italic | The body, table and emphasis roles; the italic is for binomials appearing inline in prose. |
| IBM Plex Mono | 400 normal | Every date, DOI, InChIKey, minute count and percentage. §2 never asks for another weight. |

`latin` and `latin-ext` subsets each. `latin-ext` is not optional: vernacular
names and authority strings carry diacritics that plain `latin` drops.

Nothing else is here. Adding a cut means a line in DESIGN.md §2 first.

## Where they came from

The files were vendored from the `@fontsource` npm packages, which redistribute
the upstream OFL releases:

```
npm pack @fontsource/fraunces @fontsource/ibm-plex-sans @fontsource/ibm-plex-mono
```

then the `files/*.woff2` cuts listed above were copied here. `@fontsource` is
**not** a dependency of this project — the files are checked in, which is what
"self-hosted" means.
