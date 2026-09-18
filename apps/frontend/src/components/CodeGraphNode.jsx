import { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import "./CodeGraphView.css";

function CodeGraphNode({ data, selected }) {
  const {
    label,
    type = "node",
    role,
    path,
    isDimmed,
    isHighlighted,
    badgeText,
  } = data;

  const nodeType = type.toLowerCase();

  function getNodeIcon() {
    if (role) {
      switch (role.toUpperCase()) {
        case "CONTROLLER":
          return "tune";
        case "SERVICE":
          return "build_circle";
        case "MODEL":
        case "ENTITY":
          return "database";
        case "COMPONENT":
          return "widgets";
        case "HOOK":
          return "anchor";
        case "ROUTE":
          return "alt_route";
        case "MIDDLEWARE":
          return "security";
        case "UTILITY":
          return "construction";
        case "ENTRYPOINT":
          return "play_arrow";
        default:
          break;
      }
    }
    switch (nodeType) {
      case "file":
        return "description";
      case "function":
        return "code";
      case "class":
        return "category";
      case "method":
        return "data_object";
      case "variable":
      case "constant":
        return "tag";
      case "external":
        return "output";
      case "unresolved":
        return "warning";
      case "repository":
        return "folder_special";
      default:
        return "hub";
    }
  }

  const classNames = [
    "codegraph-node",
    `codegraph-node--${nodeType}`,
    role ? `codegraph-node--role-${role.toLowerCase()}` : "",
    selected ? "codegraph-node--selected" : "",
    isHighlighted ? "codegraph-node--highlighted" : "",
    isDimmed ? "codegraph-node--dimmed" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={classNames}>
      <Handle
        type="target"
        position={Position.Top}
        className="codegraph-handle codegraph-handle--target"
      />

      <div className="codegraph-node-inner">
        <div className="codegraph-node-header">
          <span className="material-symbols-outlined codegraph-node-icon">
            {getNodeIcon()}
          </span>
          <div className="codegraph-node-label font-mono" title={label}>
            {label}
          </div>
        </div>

        <div className="codegraph-node-badges">
          <span className="codegraph-type-tag font-mono">
            {badgeText || type.toUpperCase()}
          </span>
          {role && (
            <span className="codegraph-role-tag font-mono">
              {role.toUpperCase()}
            </span>
          )}
        </div>

        {path && nodeType === "file" && (
          <div className="codegraph-node-path font-mono" title={path}>
            {path}
          </div>
        )}
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        className="codegraph-handle codegraph-handle--source"
      />
    </div>
  );
}

export default memo(CodeGraphNode);
