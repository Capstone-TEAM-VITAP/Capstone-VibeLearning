/**
 * Pure parsers for `git diff` outputs.
 * Kept dependency-free so the AI-service stages (AST, ranking)
 * can reuse the same changed-file/line contract.
 */

const HUNK_HEADER_RE = /^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@/;

/**
 * Parse `git diff --name-status` output.
 * @param {string} output
 * @returns {Array<{ path: string, status: string, oldPath?: string }>}
 */
export function parseNameStatus(output) {
  if (!output || !output.trim()) return [];
  return output
    .split("\n")
    .map((line) => line.trimEnd())
    .filter(Boolean)
    .map((line) => {
      const [statusRaw, ...rest] = line.split("\t");
      const statusLetter = (statusRaw || "").trim().charAt(0) || "M";
      // Renames/copies: "R100\told\tnew"
      if ((statusLetter === "R" || statusLetter === "C") && rest.length >= 2) {
        return { path: rest[1], status: statusLetter, oldPath: rest[0] };
      }
      return { path: rest.join("\t"), status: statusLetter };
    })
    .filter((f) => f.path);
}

/**
 * Parse a unified diff into per-file hunks with line numbers.
 * @param {string} diffText
 * @returns {Array<{ path: string, oldPath?: string, hunks: Array, additions: number, deletions: number }>}
 */
export function parseUnifiedDiff(diffText) {
  if (!diffText || !diffText.trim()) return [];
  const files = [];
  let current = null;
  let oldPath = null;
  let newPath = null;

  const pushFile = () => {
    if (current) files.push(current);
    current = null;
    oldPath = null;
    newPath = null;
  };

  const lines = diffText.split("\n");
  for (const rawLine of lines) {
    const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;

    if (line.startsWith("diff --git ")) {
      pushFile();
      const m = line.match(/diff --git a\/(.*) b\/(.*)/);
      oldPath = m ? m[1] : null;
      newPath = m ? m[2] : null;
      current = { path: newPath || oldPath, hunks: [], additions: 0, deletions: 0 };
      if (oldPath && newPath && oldPath !== newPath) current.oldPath = oldPath;
      continue;
    }
    if (!current) continue;
    if (line.startsWith("--- ")) {
      const p = line.slice(4).trim().replace(/^a\//, "");
      if (p !== "/dev/null" && !current.oldPath && oldPath && p !== current.path) current.oldPath = p;
      continue;
    }
    if (line.startsWith("+++ ")) {
      const p = line.slice(4).trim().replace(/^b\//, "");
      if (p !== "/dev/null") current.path = p;
      continue;
    }
    const hunk = line.match(HUNK_HEADER_RE);
    if (hunk) {
      current.hunks.push({
        oldStart: Number(hunk[1]),
        oldLines: hunk[2] === undefined ? 1 : Number(hunk[2]),
        newStart: Number(hunk[3]),
        newLines: hunk[4] === undefined ? 1 : Number(hunk[4]),
        lines: [],
      });
      continue;
    }
    const active = current.hunks[current.hunks.length - 1];
    if (!active) continue;
    const marker = line.charAt(0);
    if (marker === "+" && !line.startsWith("+++")) {
      active.lines.push({ type: "add", text: line.slice(1) });
      current.additions += 1;
    } else if (marker === "-" && !line.startsWith("---")) {
      active.lines.push({ type: "del", text: line.slice(1) });
      current.deletions += 1;
    } else if (marker === " ") {
      active.lines.push({ type: "context", text: line.slice(1) });
    } else if (line === "" || marker === "\\") {
      // "\ No newline at end of file" or blank — keep position, no count
      if (marker === "\\") active.lines.push({ type: "context", text: line });
    } else {
      active.lines.push({ type: "context", text: line });
    }
  }
  pushFile();

  // Assign line numbers within each hunk
  for (const file of files) {
    for (const hunk of file.hunks) {
      let oldLine = hunk.oldStart;
      let newLine = hunk.newStart;
      for (const entry of hunk.lines) {
        if (entry.type === "add") entry.newLine = newLine++;
        else if (entry.type === "del") entry.oldLine = oldLine++;
        else if (entry.type === "context") {
          entry.oldLine = oldLine++;
          entry.newLine = newLine++;
        }
      }
    }
  }

  return files;
}

/**
 * Merge name-status list with parsed hunks for the Changed Files/Lines contract.
 * @param {Array} nameStatus
 * @param {Array} hunksByFile
 */
export function mergeChangedFiles(nameStatus, hunksByFile) {
  const hunks = new Map((hunksByFile || []).map((f) => [f.path, f]));
  return (nameStatus || []).map((f) => {
    const h = hunks.get(f.path);
    return {
      path: f.path,
      status: f.status,
      ...(f.oldPath ? { oldPath: f.oldPath } : {}),
      additions: h ? h.additions : 0,
      deletions: h ? h.deletions : 0,
      hunks: h ? h.hunks : [],
    };
  });
}

/**
 * Changed-line ranges per file for downstream AST / semantic search stages.
 * @param {Array} mergedFiles
 * @returns {Array<{ path: string, status: string, addedRanges: Array<{start:number,end:number}>, deletedRanges: Array }>}
 */
export function toChangedLineRanges(mergedFiles) {
  return (mergedFiles || []).map((f) => {
    const added = [];
    const deleted = [];
    for (const hunk of f.hunks || []) {
      let rangeStart = null;
      let prev = null;
      const flush = () => {
        if (rangeStart !== null) added.push({ start: rangeStart, end: prev });
        rangeStart = null;
      };
      for (const l of hunk.lines || []) {
        if (l.type === "add" && l.newLine != null) {
          if (rangeStart === null) rangeStart = l.newLine;
          prev = l.newLine;
        } else flush();
      }
      flush();
      for (const l of hunk.lines || []) {
        if (l.type === "del" && l.oldLine != null) deleted.push({ start: l.oldLine, end: l.oldLine });
      }
    }
    return { path: f.path, status: f.status, addedRanges: added, deletedRanges: deleted };
  });
}

export default { parseNameStatus, parseUnifiedDiff, mergeChangedFiles, toChangedLineRanges };
