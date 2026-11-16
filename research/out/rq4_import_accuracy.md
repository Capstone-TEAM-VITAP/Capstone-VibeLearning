# RQ4: import-resolution accuracy vs regex oracle

| Repo | analysis s | nodes | oracle ESM pairs | oracle CJS pairs | graph pairs | precision | recall (ESM) | recall (CJS) | recall (all) |
|---|---|---|---|---|---|---|---|---|---|
| hackathon-starter | 2.209 | 1182 | 0 | 37 | 37 | 1.000 | n/a | 1.000 | 1.000 |
| koa | 1.066 | 536 | 0 | 70 | 69 | 1.000 | n/a | 0.986 | 0.986 |
| react-redux-realworld-example-app | 0.279 | 284 | 82 | 0 | 82 | 1.000 | 1.000 | n/a | 1.000 |
| express | 2.468 | 1070 | 0 | 58 | 58 | 1.000 | n/a | 1.000 | 1.000 |
| hapi | 3.978 | 587 | 0 | 43 | 43 | 1.000 | n/a | 1.000 | 1.000 |
| axios | 5.41 | 2486 | 370 | 1 | 369 | 1.000 | 0.995 | 1.000 | 0.995 |
| react-boilerplate | 1.169 | 1131 | 198 | 32 | 225 | 1.000 | 0.975 | 1.000 | 0.978 |
| node-fetch | 0.941 | 339 | 42 | 0 | 41 | 1.000 | 0.976 | n/a | 0.976 |
| passport | 1.12 | 198 | 0 | 32 | 32 | 1.000 | n/a | 1.000 | 1.000 |
| connect | 0.115 | 77 | 0 | 2 | 2 | 1.000 | n/a | 1.000 | 1.000 |
| request | 1.398 | 906 | 0 | 93 | 93 | 1.000 | n/a | 1.000 | 1.000 |
| winston | 0.904 | 607 | 0 | 76 | 77 | 0.987 | n/a | 1.000 | 1.000 |
| mocha | 1.581 | 1577 | 118 | 0 | 117 | 1.000 | 0.992 | n/a | 0.992 |
| redux-saga | 2.065 | 1705 | 247 | 5 | 240 | 0.996 | 0.951 | 1.000 | 0.952 |
| body-parser | 0.568 | 192 | 0 | 13 | 13 | 1.000 | n/a | 1.000 | 1.000 |

Pooled: ESM recall 0.980 over 1057 pairs; CommonJS recall 0.998 over 462 pairs. Analysis crashes: 0/15.
