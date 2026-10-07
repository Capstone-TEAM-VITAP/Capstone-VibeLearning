// Blocks loading spinner, vendored from loading-dev v0.3.5 (MIT License).
// Source: https://loading.dev/spinners/blocks / https://github.com/jakubkrehel/loading
// Copyright (c) Jakub Krehel. Vendored to avoid an extra dependency; behavior
// matches the upstream `Blocks` API: size, color, duration, playState, sweep.
import "./Blocks.css";

const SIDE = 3;
const CELLS = Array.from({ length: SIDE * SIDE }, (_, index) => ({
  col: index % SIDE,
  row: Math.floor(index / SIDE),
}));

const SWEEPS = {
  columns: { count: SIDE, place: ({ col }) => col },
  diagonal: { count: SIDE * 2 - 1, place: ({ col, row }) => row + col },
  rows: { count: SIDE, place: ({ row }) => row },
};

function Blocks({
  size = 20,
  color,
  duration,
  playState,
  sweep = "diagonal",
  className,
}) {
  const { place } = SWEEPS[sweep] || SWEEPS.diagonal;
  return (
    <div
      aria-hidden="true"
      className={["ld-blocks", className].filter(Boolean).join(" ")}
      style={{
        "--ld-size": `${size}px`,
        ...(color === undefined ? null : { color }),
        ...(duration === undefined ? null : { "--ld-duration": `${duration}ms` }),
        ...(playState === undefined ? null : { "--ld-play-state": playState }),
      }}
    >
      {CELLS.map((cell) => (
        <div
          key={`${cell.col}-${cell.row}`}
          className={`ld-blocks-cell ld-blocks-cell-${sweep}`}
          style={{ "--ld-step": place(cell) }}
        />
      ))}
    </div>
  );
}

export default Blocks;
export { Blocks };
