# Paired tests (Holm-adjusted over the whole family)

| Comparison | n | metric | diff | 95% CI | p | p (Holm) |
|---|---|---|---|---|---|---|
| Locate: dense − BM25 (held-out JS) | 79 | MRR | +0.178 | [+0.079, +0.276] | 0.0011 | 0.0149 |
| Locate: dense − LSA (held-out JS) | 79 | MRR | +0.251 | [+0.156, +0.347] | <0.0001 | 0.0009 |
| Locate: RRF all three − BM25 (held-out JS) | 79 | MRR | +0.260 | [+0.163, +0.353] | <0.0001 | 0.0009 |
| Locate: RRF LSA+graph − BM25 (held-out JS) | 79 | MRR | +0.055 | [-0.030, +0.142] | 0.2177 | 1.0000 |
| Locate: dense − BM25 (Python) | 120 | MRR | +0.191 | [+0.121, +0.258] | <0.0001 | 0.0009 |
| Importers: graph − BM25 (held-out JS) | 48 | MRR | +0.294 | [+0.190, +0.401] | <0.0001 | 0.0009 |
| Importers: RRF LSA+graph − graph (held-out JS) | 48 | MRR | -0.100 | [-0.186, -0.018] | 0.0269 | 0.3223 |
| Impact: graph − BM25 (held-out JS) | 37 | nDCG\@10 | +0.158 | [-0.022, +0.317] | 0.0834 | 0.6672 |
| Impact: RRF LSA+graph − graph (held-out JS) | 37 | nDCG\@10 | +0.087 | [-0.027, +0.219] | 0.1735 | 1.0000 |
| Impact: RRF dense+graph − graph (held-out JS) | 37 | nDCG\@10 | -0.013 | [-0.084, +0.068] | 0.7457 | 1.0000 |
| Impact: RRF LSA+graph − graph (Python) | 60 | nDCG\@10 | -0.107 | [-0.152, -0.060] | <0.0001 | 0.0009 |
| Flows: primary pruner − its candidate pool | 25 | F1 | +0.054 | [-0.082, +0.206] | 0.4572 | 1.0000 |
| Flows: primary pruner − 2-hop traversal (BM25 seeds) | 25 | F1 | +0.136 | [+0.012, +0.271] | 0.0521 | 0.4686 |
| Flows: primary pruner − random 3 edges | 25 | F1 | +0.155 | [+0.024, +0.304] | 0.0386 | 0.3857 |
| Flows: primary pruner − top 3 by BM25 | 25 | F1 | -0.056 | [-0.144, +0.029] | 0.3125 | 1.0000 |
| Flows: primary pruner − top 3 by path words | 25 | F1 | -0.100 | [-0.280, +0.079] | 0.3025 | 1.0000 |
| Flows: threshold-0 pruner − top 3 by BM25 (post hoc) | 25 | F1 | +0.029 | [-0.032, +0.091] | 0.6250 | 1.0000 |
| Flows: fused-relevance pruner − top 3 by BM25 (post hoc) | 25 | F1 | +0.097 | [+0.023, +0.177] | 0.0312 | 0.3438 |

# CodeAI v2 (deployed) vs v1 (held-out JS; confirmation of the chosen design; separate Holm family of 3)

| Comparison | n | diff | 95% CI | p | p (Holm) |
|---|---|---|---|---|---|
| Locate: CodeAI v2 − v1 | 79 | +0.157 | [+0.074, +0.237] | 0.0005 | 0.0005 |
| Importers: CodeAI v2 − v1 | 48 | +0.296 | [+0.187, +0.407] | <0.0001 | 0.0001 |
| Impact: CodeAI v2 − v1 | 37 | +0.195 | [+0.122, +0.268] | <0.0001 | 0.0001 |
