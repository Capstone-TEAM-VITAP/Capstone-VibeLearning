# Execution-flow reconstruction

dev: 23 questions; gold edges absent from the independent import oracle: none

heldout: 25 questions; gold edges absent from the independent import oracle: none


## Held-out flows, all (CONFIRMATORY) (n=25)

| System | precision | recall | F1 (mean [95% CI]) | mean predicted edges |
|---|---|---|---|---|
| bfs2 | 0.051 | 0.380 | 0.081 [0.032, 0.146] | 15.7 |
| overlap-top3 | 0.267 | 0.360 | 0.300 [0.181, 0.423] | 2.2 |
| relevance-top3 | 0.227 | 0.300 | 0.256 [0.160, 0.355] | 2.9 |
| pruner-path | 0.080 | 0.073 | 0.072 [0.013, 0.144] | 0.5 |
| pruner-bm25 | 0.173 | 0.240 | 0.200 [0.096, 0.320] | 1.9 |
| pruner-hybrid | 0.307 | 0.433 | 0.353 [0.251, 0.463] | 3.0 |
| pruner-bm25-noroles | 0.173 | 0.240 | 0.200 [0.096, 0.320] | 1.9 |
| pruner-bm25-nocont | 0.227 | 0.320 | 0.264 [0.144, 0.392] | 1.9 |
| pruner-bm25-K2 | 0.220 | 0.207 | 0.212 [0.092, 0.352] | 1.3 |
| pruner-bm25-K5 | 0.130 | 0.300 | 0.180 [0.093, 0.274] | 3.1 |

## Held-out, Python repositories (n=21)

| System | precision | recall | F1 (mean [95% CI]) | mean predicted edges |
|---|---|---|---|---|
| bfs2 | 0.023 | 0.333 | 0.043 [0.019, 0.069] | 16.4 |
| overlap-top3 | 0.159 | 0.254 | 0.192 [0.111, 0.281] | 2.0 |
| relevance-top3 | 0.190 | 0.270 | 0.222 [0.114, 0.337] | 2.9 |
| pruner-path | 0.095 | 0.087 | 0.086 [0.016, 0.171] | 0.6 |
| pruner-bm25 | 0.206 | 0.286 | 0.238 [0.114, 0.381] | 2.3 |
| pruner-hybrid | 0.286 | 0.429 | 0.338 [0.219, 0.467] | 3.0 |
| pruner-bm25-noroles | 0.206 | 0.286 | 0.238 [0.114, 0.381] | 2.3 |
| pruner-bm25-nocont | 0.270 | 0.381 | 0.314 [0.190, 0.457] | 2.3 |
| pruner-bm25-K2 | 0.262 | 0.246 | 0.252 [0.119, 0.410] | 1.6 |
| pruner-bm25-K5 | 0.155 | 0.357 | 0.215 [0.122, 0.321] | 3.7 |

## Held-out, JavaScript repositories (n=4)

| System | precision | recall | F1 (mean [95% CI]) | mean predicted edges |
|---|---|---|---|---|
| bfs2 | 0.196 | 0.625 | 0.283 [0.032, 0.533] | 11.8 |
| overlap-top3 | 0.833 | 0.917 | 0.867 [0.733, 1.000] | 3.0 |
| relevance-top3 | 0.417 | 0.458 | 0.433 [0.333, 0.583] | 3.0 |
| pruner-path | 0.000 | 0.000 | 0.000 [0.000, 0.000] | 0.0 |
| pruner-bm25 | 0.000 | 0.000 | 0.000 [0.000, 0.000] | 0.0 |
| pruner-hybrid | 0.417 | 0.458 | 0.433 [0.333, 0.583] | 3.0 |
| pruner-bm25-noroles | 0.000 | 0.000 | 0.000 [0.000, 0.000] | 0.0 |
| pruner-bm25-nocont | 0.000 | 0.000 | 0.000 [0.000, 0.000] | 0.0 |
| pruner-bm25-K2 | 0.000 | 0.000 | 0.000 [0.000, 0.000] | 0.0 |
| pruner-bm25-K5 | 0.000 | 0.000 | 0.000 [0.000, 0.000] | 0.0 |

## Dev flows, all (n=23)

| System | precision | recall | F1 (mean [95% CI]) | mean predicted edges |
|---|---|---|---|---|
| bfs2 | 0.152 | 0.326 | 0.159 [0.075, 0.255] | 10.0 |
| overlap-top3 | 0.319 | 0.348 | 0.325 [0.200, 0.458] | 2.7 |
| relevance-top3 | 0.333 | 0.435 | 0.374 [0.255, 0.501] | 3.0 |
| pruner-path | 0.290 | 0.254 | 0.267 [0.138, 0.404] | 2.3 |
| pruner-bm25 | 0.246 | 0.297 | 0.267 [0.168, 0.368] | 2.8 |
| pruner-hybrid | 0.304 | 0.355 | 0.325 [0.209, 0.449] | 3.0 |
| pruner-bm25-noroles | 0.261 | 0.333 | 0.290 [0.183, 0.403] | 2.8 |
| pruner-bm25-nocont | 0.232 | 0.275 | 0.249 [0.159, 0.339] | 2.8 |
| pruner-bm25-K2 | 0.304 | 0.239 | 0.265 [0.152, 0.378] | 1.9 |
| pruner-bm25-K5 | 0.167 | 0.312 | 0.214 [0.140, 0.290] | 4.5 |

## Paired comparisons on F1 (A minus B)

| Set | A | B | mean diff | 95% CI | p |
|---|---|---|---|---|---|
| heldout | pruner-bm25 | bfs2 | +0.119 | [-0.009, +0.259] | 0.0969 |
| heldout | pruner-bm25 | overlap-top3 | -0.100 | [-0.280, +0.079] | 0.3025 |
| heldout | pruner-bm25 | relevance-top3 | -0.056 | [-0.144, +0.029] | 0.3125 |
| heldout | pruner-bm25 | pruner-path | +0.128 | [-0.011, +0.267] | 0.0928 |
| heldout | pruner-bm25 | pruner-hybrid | -0.153 | [-0.240, -0.075] | 0.0039 |
| heldout | pruner-bm25 | pruner-bm25-noroles | +0.000 | [+0.000, +0.000] | 1.0000 |
| heldout | pruner-bm25 | pruner-bm25-nocont | -0.064 | [-0.128, -0.016] | 0.1250 |
| heldout | pruner-hybrid | bfs2 | +0.272 | [+0.161, +0.380] | 0.0001 |
| heldout | pruner-hybrid | overlap-top3 | +0.053 | [-0.091, +0.197] | 0.4981 |
| heldout | pruner-hybrid | relevance-top3 | +0.097 | [+0.023, +0.177] | 0.0312 |
| dev | pruner-bm25 | bfs2 | +0.107 | [-0.034, +0.247] | 0.1680 |
| dev | pruner-bm25 | overlap-top3 | -0.058 | [-0.220, +0.107] | 0.5362 |
| dev | pruner-bm25 | relevance-top3 | -0.107 | [-0.246, +0.032] | 0.1423 |
| dev | pruner-bm25 | pruner-path | +0.000 | [-0.145, +0.142] | 1.0000 |
| dev | pruner-bm25 | pruner-hybrid | -0.058 | [-0.151, +0.029] | 0.3438 |
| dev | pruner-bm25 | pruner-bm25-noroles | -0.023 | [-0.130, +0.081] | 0.6406 |
| dev | pruner-bm25 | pruner-bm25-nocont | +0.017 | [+0.000, +0.052] | 1.0000 |
| dev | pruner-hybrid | bfs2 | +0.165 | [+0.010, +0.316] | 0.0519 |
| dev | pruner-hybrid | overlap-top3 | +0.000 | [-0.165, +0.162] | 1.0000 |
| dev | pruner-hybrid | relevance-top3 | -0.049 | [-0.232, +0.139] | 0.6331 |

## Edge reduction (held-out)

Mean predicted edges: bfs2 15.7, pruner-bm25 1.9 (87.8% fewer).

## Per-question results

| set | id | gold | bfs2 F1 | relevance-top3 F1 | primary F1 | primary edges |
|---|---|---|---|---|---|---|
| dev | self:B1 | 3 | 0.00 | 0.00 | 0.33 | 3 |
| dev | self:B2 | 3 | 0.00 | 0.33 | 0.00 | 3 |
| dev | self:B3 | 3 | 0.00 | 0.00 | 0.67 | 3 |
| dev | self:B4 | 3 | 0.19 | 0.00 | 0.00 | 3 |
| dev | self:B5 | 3 | 0.00 | 0.67 | 0.67 | 3 |
| dev | self:B6 | 3 | 0.40 | 0.33 | 0.33 | 3 |
| dev | self:B7 | 3 | 0.46 | 0.33 | 0.00 | 3 |
| dev | self:B8 | 2 | 0.67 | 0.00 | 0.00 | 1 |
| dev | self:B9 | 3 | 0.00 | 0.33 | 0.33 | 3 |
| dev | self:B10 | 3 | 0.00 | 0.00 | 0.33 | 3 |
| dev | self:P1 | 3 | 0.19 | 0.33 | 0.33 | 3 |
| dev | self:P2 | 2 | 0.18 | 0.40 | 0.40 | 3 |
| dev | self:P3 | 2 | 0.00 | 0.40 | 0.00 | 3 |
| dev | self:P4 | 3 | 0.00 | 0.67 | 0.00 | 3 |
| dev | self:P5 | 2 | 0.09 | 0.40 | 0.00 | 3 |
| dev | self:P6 | 2 | 0.17 | 0.00 | 0.00 | 1 |
| dev | hs:H1 | 2 | 0.25 | 0.80 | 0.40 | 3 |
| dev | hs:H2 | 2 | 0.00 | 0.80 | 0.40 | 3 |
| dev | hs:H3 | 2 | 0.67 | 0.80 | 0.40 | 3 |
| dev | hs:H4 | 3 | 0.40 | 0.00 | 0.33 | 3 |
| dev | hs:H5 | 2 | 0.00 | 0.40 | 0.40 | 3 |
| dev | hs:H6 | 2 | 0.00 | 0.80 | 0.80 | 3 |
| dev | hs:H7 | 2 | 0.00 | 0.80 | 0.00 | 3 |
| heldout | requests:F1 | 2 | 0.08 | 0.00 | 0.00 | 3 |
| heldout | requests:F2 | 2 | 0.06 | 0.00 | 0.00 | 3 |
| heldout | requests:F3 | 2 | 0.13 | 0.40 | 0.40 | 3 |
| heldout | requests:F4 | 2 | 0.08 | 0.40 | 0.40 | 3 |
| heldout | requests:F5 | 2 | 0.11 | 0.40 | 0.40 | 3 |
| heldout | flask:F1 | 2 | 0.00 | 0.00 | 0.00 | 3 |
| heldout | flask:F2 | 2 | 0.16 | 0.40 | 0.80 | 3 |
| heldout | flask:F3 | 2 | 0.00 | 0.00 | 0.00 | 3 |
| heldout | flask:F4 | 2 | 0.00 | 0.40 | 0.40 | 3 |
| heldout | flask:F5 | 3 | 0.13 | 0.67 | 1.00 | 3 |
| heldout | flask:F6 | 2 | 0.00 | 0.40 | 0.40 | 3 |
| heldout | httpx:F1 | 2 | 0.00 | 0.00 | 0.00 | 1 |
| heldout | httpx:F2 | 2 | 0.00 | 0.00 | 0.00 | 0 |
| heldout | httpx:F3 | 2 | 0.00 | 0.80 | 0.80 | 3 |
| heldout | httpx:F4 | 2 | 0.00 | 0.00 | 0.00 | 2 |
| heldout | httpx:F5 | 1 | 0.00 | 0.00 | 0.00 | 0 |
| heldout | click:F1 | 2 | 0.00 | 0.00 | 0.00 | 3 |
| heldout | click:F2 | 2 | 0.14 | 0.40 | 0.00 | 3 |
| heldout | click:F3 | 2 | 0.00 | 0.00 | 0.00 | 0 |
| heldout | click:F4 | 2 | 0.00 | 0.00 | 0.00 | 0 |
| heldout | click:F5 | 2 | 0.00 | 0.40 | 0.40 | 3 |
| heldout | koa:F1 | 3 | 0.00 | 0.33 | 0.00 | 0 |
| heldout | express:F1 | 3 | 0.67 | 0.67 | 0.00 | 0 |
| heldout | hapi:F1 | 3 | 0.40 | 0.33 | 0.00 | 0 |
| heldout | hapi:F2 | 2 | 0.06 | 0.40 | 0.00 | 0 |