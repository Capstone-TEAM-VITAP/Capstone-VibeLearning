import "./BarList.css";

/**
 * Ranked horizontal bars for one series: label, bar, value.
 * Each row is focusable and shows a tooltip with the exact count and share.
 */
function BarList({ items = [], unit = "", total = null, mono = false, emptyText = "No data" }) {
  if (!items.length) return <p className="bar-list-empty">{emptyText}</p>;
  const max = Math.max(...items.map((i) => i.value), 1);
  const sum = total ?? items.reduce((a, b) => a + b.value, 0);

  return (
    <ul className="bar-list">
      {items.map((item) => {
        const share = sum > 0 ? Math.round((item.value / sum) * 1000) / 10 : 0;
        const tip = `${item.value.toLocaleString()}${unit ? ` ${unit}` : ""} · ${share}%`;
        return (
          <li key={item.label} className="bar-row" tabIndex={0} aria-label={`${item.label}: ${tip}`}>
            <span className={`bar-label ${mono ? "mono" : ""}`} title={item.label}>
              {item.label}
            </span>
            <span className="bar-track">
              <span className="bar-fill" style={{ width: `${Math.max((item.value / max) * 100, 1.5)}%` }} />
              <span className="bar-tip" role="tooltip">
                {tip}
              </span>
            </span>
            <span className="bar-value">{item.value.toLocaleString()}</span>
          </li>
        );
      })}
    </ul>
  );
}

export default BarList;
