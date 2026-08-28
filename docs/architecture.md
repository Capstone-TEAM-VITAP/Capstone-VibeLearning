# Project resource optimization: 

- We will use pnpm  reasoning: since the project will be built and installed multiple times, and dependencies would otherwise need to be reinstalled every time, using pnpm ensures dependencies are stored in a global cache. This reduces the need to download and install dependencies from scratch each time, saving both disk space and install time across projects.