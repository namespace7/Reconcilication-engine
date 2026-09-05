import { useState } from "react";
import { createRun, getRun, uploadFile } from "./api";
import "./styles.css";

const OUR_SOURCE_ID = 1;
const EXTERNAL_SOURCE_ID = 2;
const DEFAULT_RULESET_ID = 1;

const STATUS_LABELS = {
  MATCHED: "Matched",
  MATCHED_WITH_DIFFERENCES: "Within tolerance",
  NEEDS_REVIEW: "Needs review",
  UNMATCHED_OUR_SIDE: "Unmatched",
  UNMATCHED_EXTERNAL_SIDE: "Unmatched",
  EXCLUDED: "Excluded",
};

function App() {
  const [ourFile, setOurFile] = useState(null);
  const [externalFile, setExternalFile] = useState(null);

  const [ourFileId, setOurFileId] = useState(null);
  const [externalFileId, setExternalFileId] = useState(null);

  const [run, setRun] = useState(null);
  const [uploading, setUploading] = useState(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  const handleFileUpload = async (file, source, setFile, setFileId) => {
    if (!file) {
      return;
    }

    setError("");
    setUploading(source);

    try {
      const result = await uploadFile(
        source === "our" ? OUR_SOURCE_ID : EXTERNAL_SOURCE_ID,
        file,
      );

      setFile(file);
      setFileId(result.file.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(null);
    }
  };

  const handleRun = async () => {
    if (!ourFileId || !externalFileId) {
      return;
    }

    setError("");
    setRunning(true);
    setRun(null);

    try {
      const createdRun = await createRun(
        ourFileId,
        externalFileId,
        DEFAULT_RULESET_ID,
      );

      const completedRun = await getRun(createdRun.id);

      setRun(completedRun);
    } catch (err) {
      setError(err.message);
    } finally {
      setRunning(false);
    }
  };

  return (
    <main className="app">
      <header className="header">
        <div>
          <p className="eyebrow">Transaction reconciliation</p>

          <h1>Reconcile</h1>

          <p className="subtitle">
            Compare transactions across two systems and review meaningful
            differences.
          </p>
        </div>
      </header>

      <section className="upload-grid">
        <div className="card">
          <p className="label">Our system</p>

          <h2>Upload transaction file</h2>

          <label className="file-picker">
            <input
              type="file"
              accept=".csv"
              onChange={(event) =>
                handleFileUpload(
                  event.target.files[0],
                  "our",
                  setOurFile,
                  setOurFileId,
                )
              }
            />

            <span>
              {uploading === "our" ? "Uploading..." : "Choose CSV file"}
            </span>
          </label>

          {ourFile && <p className="file-name">✓ {ourFile.name}</p>}
        </div>

        <div className="card">
          <p className="label">External system</p>

          <h2>Upload transaction file</h2>

          <label className="file-picker">
            <input
              type="file"
              accept=".csv"
              onChange={(event) =>
                handleFileUpload(
                  event.target.files[0],
                  "external",
                  setExternalFile,
                  setExternalFileId,
                )
              }
            />

            <span>
              {uploading === "external" ? "Uploading..." : "Choose CSV file"}
            </span>
          </label>

          {externalFile && <p className="file-name">✓ {externalFile.name}</p>}
        </div>
      </section>

      <section className="run-card">
        <div>
          <p className="label">Ruleset</p>

          <h2>Default v1</h2>

          <p className="muted">
            Compare using the configured reconciliation tolerances.
          </p>
        </div>

        <button
          className="primary-button"
          disabled={!ourFileId || !externalFileId || running}
          onClick={handleRun}
        >
          {running ? "Running..." : "Run reconciliation"}
        </button>
      </section>

      {error && <div className="error">{error}</div>}

      {run && <Results run={run} />}
    </main>
  );
}

function Results({ run }) {
  const summary = run.summary || {};

  return (
    <section className="results-section">
      <div className="results-header">
        <div>
          <p className="eyebrow">Reconciliation run #{run.id}</p>

          <h2>Results</h2>
        </div>

        <span className="run-status">{run.status}</span>
      </div>

      <div className="summary-grid">
        <SummaryCard label="Matched" value={summary.MATCHED || 0} />

        <SummaryCard
          label="Within tolerance"
          value={summary.MATCHED_WITH_DIFFERENCES || 0}
        />

        <SummaryCard label="Needs review" value={summary.NEEDS_REVIEW || 0} />

        <SummaryCard
          label="Unmatched"
          value={
            (summary.UNMATCHED_OUR_SIDE || 0) +
            (summary.UNMATCHED_EXTERNAL_SIDE || 0)
          }
        />
      </div>

      <div className="results-list">
        {run.results.map((result) => (
          <ResultRow key={result.id} result={result} />
        ))}
      </div>
    </section>
  );
}

function SummaryCard({ label, value }) {
  return (
    <div className="summary-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ResultRow({ result }) {
  const ourReference = result.our_transaction?.source_reference || "—";

  const externalReference =
    result.external_transaction?.source_reference || "—";

  return (
    <div className="result-row">
      <div className="references">
        <strong>{ourReference}</strong>
        <span>↔</span>
        <strong>{externalReference}</strong>
      </div>

      <div className="result-details">
        <span className={`status status-${result.status}`}>
          {STATUS_LABELS[result.status] || result.status}
        </span>

        {result.match_method && (
          <span className="match-method">
            {result.match_method.replaceAll("_", " ")}
          </span>
        )}
      </div>

      {result.differences?.length > 0 && (
        <div className="difference-summary">
          {result.differences.map((difference) => (
            <span key={difference.field}>
              {difference.field}: {difference.difference}
              {difference.within_tolerance ? " ✓" : " ⚠"}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default App;
