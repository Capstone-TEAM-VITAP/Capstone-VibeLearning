# Analyzer accuracy vs independent oracles

| Repo | Lang | oracle pairs | graph pairs | precision | recall |
|---|---|---|---|---|---|
| hackathon-starter | js | 37 | 37 | 1.000 | 1.000 |
| koa | js | 70 | 69 | 1.000 | 0.986 |
| react-redux-realworld-example-app | js | 82 | 82 | 1.000 | 1.000 |
| express | js | 58 | 58 | 1.000 | 1.000 |
| hapi | js | 43 | 43 | 1.000 | 1.000 |
| axios | js | 371 | 369 | 1.000 | 0.995 |
| react-boilerplate | js | 230 | 225 | 1.000 | 0.978 |
| node-fetch | js | 42 | 41 | 1.000 | 0.976 |
| passport | js | 32 | 32 | 1.000 | 1.000 |
| connect | js | 2 | 2 | 1.000 | 1.000 |
| request | js | 93 | 93 | 1.000 | 1.000 |
| winston | js | 76 | 77 | 0.987 | 1.000 |
| mocha | js | 118 | 117 | 1.000 | 0.992 |
| redux-saga | js | 249 | 237 | 1.000 | 0.952 |
| body-parser | js | 13 | 13 | 1.000 | 1.000 |
| requests | python | 115 | 106 | 1.000 | 0.922 |
| click | python | 176 | 173 | 1.000 | 0.983 |
| flask | python | 219 | 214 | 0.986 | 0.963 |
| httpx | python | 123 | 123 | 1.000 | 1.000 |

Pooled js: recall 0.985 over 1516 pairs, precision 0.999 over 1495 pairs.

Pooled python: recall 0.968 over 633 pairs, precision 0.995 over 616 pairs.

## Python symbols vs ast

| Repo | ast defs | found | recall | precision |
|---|---|---|---|---|
| requests | 720 | 720 | 1.000 | 1.000 |
| click | 1511 | 1511 | 1.000 | 1.000 |
| flask | 1298 | 1298 | 1.000 | 1.000 |
| httpx | 1067 | 1067 | 1.000 | 1.000 |