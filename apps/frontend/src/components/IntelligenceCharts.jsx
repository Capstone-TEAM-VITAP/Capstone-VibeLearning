import { useMemo } from "react";
import BarList from "./BarList.jsx";
import { computeGraphStats } from "../utils/graphStats.js";
import "./IntelligenceCharts.css";

function ChartCard({ title, note, children }) {
  return (
    <section className="console-card intel-chart-card">
      <div className="console-card-head">
        <h2 className="console-card-title">{title}</h2>
        {note && <span className="intel-chart-note">{note}</span>}
      </div>
      <div className="intel-chart-body">{children}</div>
    </section>
  );
}

/**
 * `charts` limits which charts render (by id) and hides the totals line;
 * without it, every chart and the totals are shown.
 */
function IntelligenceCharts({ graphData, charts = null }) {
  const stats = useMemo(() => computeGraphStats(graphData), [graphData]);
  const { totals } = stats;
  const show = (id) => !charts || charts.includes(id);

  return (
    <div className="intel-charts">
      {!charts && (
        <div className="intel-charts-totals">
          <span><b>{totals.files.toLocaleString()}</b> files</span>
          <span><b>{totals.symbols.toLocaleString()}</b> symbols</span>
          <span><b>{totals.packages.toLocaleString()}</b> packages</span>
          <span><b>{totals.relationships.toLocaleString()}</b> relationships</span>
        </div>
      )}

      <div className="intel-charts-grid">
        {show("languages") && (
          <ChartCard title="Files by language" note={`${totals.files} files`}>
            <BarList items={stats.languages} unit="files" total={totals.files} />
          </ChartCard>
        )}

        {show("roles") && (
          <ChartCard title="Files by architecture role" note="classified files">
            <BarList items={stats.roles} unit="files" />
          </ChartCard>
        )}

        {show("directories") && (
          <ChartCard title="Largest areas" note="files per directory">
            <BarList items={stats.directories} unit="files" total={totals.files} mono />
          </ChartCard>
        )}

        {show("mostImported") && (
          <ChartCard title="Most imported files" note="imported by N files">
            <BarList
              items={stats.mostImported}
              unit="importers"
              mono
              emptyText="No file-to-file imports found"
            />
          </ChartCard>
        )}

        {show("packages") && (
          <ChartCard title="Most used packages" note="imported by N files">
            <BarList
              items={stats.packages}
              unit="imports"
              mono
              emptyText="No external packages found"
            />
          </ChartCard>
        )}

        {show("symbolsPerFile") && (
          <ChartCard title="Files with the most symbols" note="functions, classes, constants">
            <BarList
              items={stats.symbolsPerFile}
              unit="symbols"
              mono
              emptyText="No symbols extracted"
            />
          </ChartCard>
        )}

        {show("symbolKinds") && (
          <ChartCard title="Symbols by kind" note={`${totals.symbols} symbols`}>
            <BarList items={stats.symbolKinds} unit="symbols" total={totals.symbols} />
          </ChartCard>
        )}

        {show("relationshipTypes") && (
          <ChartCard title="Relationships by type" note={`${totals.relationships} edges`}>
            <BarList items={stats.relationshipTypes} unit="edges" total={totals.relationships} />
          </ChartCard>
        )}
      </div>
    </div>
  );
}

export default IntelligenceCharts;
