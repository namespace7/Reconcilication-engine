import { useState } from "react";
import { createManualDecision, createRun, getRun, uploadFile } from "./api";
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
      {run && <Results run={run} setError={setError} />}{" "}
    </main>
  );
}

function Results({ run, setError }) {
  const summary = run.summary || {};

  return (
    <section className="results-section">
      {/* existing summary/header code */}

      <div className="results-list">
        {run.results.map((result) => (
          <ResultRow key={result.id} result={result} setError={setError} />
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

function ResultRow({ result, setError }) {
  const [reviewing, setReviewing] = useState(false);
  const [saving, setSaving] = useState(false);

  const ourReference = result.our_transaction?.source_reference || "—";

  const externalReference =
    result.external_transaction?.source_reference || "—";

  const isReviewable = result.status === "NEEDS_REVIEW";

  const isManualMatch = result.match_method === "manual";

  const handleDecision = async (decision, externalTransactionId = null) => {
    setSaving(true);
    setError("");

    try {
      await createManualDecision(
        result.id,
        decision,
        externalTransactionId,
        decision === "MATCH"
          ? "Confirmed manually"
          : "Confirmed as genuinely unmatched",
        "Yashwant",
      );

      setReviewing(false);

      window.alert(
        decision === "MATCH"
          ? "Manual match saved. Run reconciliation again to apply it."
          : "Unmatched decision saved. Run reconciliation again to apply it.",
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className={`result-row ${isReviewable ? "result-row-reviewable" : ""}`}
    >
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

        {isReviewable && !isManualMatch && (
          <button
            className="review-button"
            onClick={() => setReviewing(!reviewing)}
          >
            {reviewing ? "Close review" : "Review"}
          </button>
        )}

        {isManualMatch && (
          <button
            className="review-button"
            onClick={() => setReviewing(!reviewing)}
          >
            {reviewing ? "Close review" : "View decision"}
          </button>
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

      {reviewing && (
        <ReviewPanel
          result={result}
          saving={saving}
          onDecision={handleDecision}
        />
      )}
    </div>
  );
}

function ReviewPanel({ result, saving, onDecision }) {
  const ourTransaction = result.our_transaction;
  const externalTransaction = result.external_transaction;

  const isManualMatch = result.match_method === "manual";

  const hasSelectedExternal = Boolean(externalTransaction);

  const candidates = result.candidates || [];

  return (
    <div className="review-panel">
      <div className="review-heading">
        <div>
          <p className="eyebrow">Manual review</p>

          <h3>
            {isManualMatch
              ? "Review confirmed match"
              : hasSelectedExternal
                ? "Review the proposed match"
                : "Choose the correct external transaction"}
          </h3>
        </div>
      </div>

      {ourTransaction && (
        <div
          className={`transaction-comparison ${
            hasSelectedExternal ? "transaction-comparison-paired" : ""
          }`}
        >
          <div className="transaction-card">
            <div className="transaction-card-header">
              <span>Our transaction</span>

              <strong>{ourTransaction.source_reference}</strong>
            </div>

            <TransactionDetails transaction={ourTransaction} />
          </div>

          {externalTransaction && (
            <div className="transaction-card external-transaction">
              <div className="transaction-card-header">
                <span>External transaction</span>

                <strong>{externalTransaction.source_reference}</strong>
              </div>

              <TransactionDetails transaction={externalTransaction} />
            </div>
          )}
        </div>
      )}

      {result.differences?.length > 0 && (
        <div className="review-differences">
          <h4>Differences</h4>

          {result.differences.map((difference) => (
            <div className="review-difference" key={difference.field}>
              <strong>{formatFieldName(difference.field)}</strong>

              <span>Our: {difference.our_value}</span>

              <span>External: {difference.external_value}</span>

              <span>Difference: {difference.difference}</span>

              <span>Tolerance: {difference.tolerance}</span>
            </div>
          ))}
        </div>
      )}

      {!isManualMatch && candidates.length > 0 && (
        <div className="candidate-section">
          <div className="candidate-heading">
            <h4>
              {candidates.length > 1 ? "Possible matches" : "Proposed match"}
            </h4>

            <p className="muted">
              {candidates.length} plausible candidate
              {candidates.length === 1 ? "" : "s"} found.
            </p>
          </div>

          {candidates.map((candidate) => (
            <CandidateCard
              key={candidate.transaction_id}
              candidate={candidate}
              saving={saving}
              onMatch={() => onDecision("MATCH", candidate.transaction_id)}
            />
          ))}
        </div>
      )}

      {isManualMatch && (
        <div className="manual-decision-note">
          <strong>Manual decision recorded</strong>

          <p>
            This transaction was manually confirmed as a match. The remaining
            differences are evaluated against the configured tolerances.
          </p>
        </div>
      )}

      {!isManualMatch && (
        <div className="review-footer">
          <div>
            <strong>None of these are correct?</strong>

            <p className="muted">
              Leave this transaction unmatched and record the decision.
            </p>
          </div>

          <button
            className="secondary-button"
            disabled={saving}
            onClick={() => onDecision("NO_MATCH")}
          >
            {saving ? "Saving..." : "Leave unmatched"}
          </button>
        </div>
      )}
    </div>
  );
}

function CandidateCard({ candidate, saving, onMatch }) {
  return (
    <div className="candidate-card">
      <div className="candidate-card-header">
        <div>
          <strong className="candidate-reference">
            {candidate.source_reference}
          </strong>

          <p className="candidate-summary">
            {candidate.instrument} · {candidate.side}
            {" · "}
            {candidate.quantity} @ {candidate.unit_price}
            {" · "}
            Amount: {candidate.amount}
          </p>

          <p className="candidate-meta">
            Score: {candidate.score}
            {" · "}
            Time difference: {candidate.timestamp_difference_seconds}s
          </p>
        </div>

        <button
          className="primary-button candidate-button"
          disabled={saving}
          onClick={onMatch}
        >
          {saving ? "Saving..." : "Confirm match"}
        </button>
      </div>

      <div className="candidate-timestamp">
        Timestamp: {candidate.timestamp}
      </div>

      {candidate.reasons?.length > 0 && (
        <div className="candidate-reasons">
          {candidate.reasons.map((reason) => (
            <span key={reason}>{reason}</span>
          ))}
        </div>
      )}
    </div>
  );
}

function TransactionDetails({ transaction }) {
  return (
    <div className="transaction-details">
      <div>
        <span>Instrument</span>
        <strong>{transaction.instrument}</strong>
      </div>

      <div>
        <span>Side</span>
        <strong>{transaction.side}</strong>
      </div>

      <div>
        <span>Quantity</span>
        <strong>{transaction.quantity}</strong>
      </div>

      <div>
        <span>Unit price</span>
        <strong>{transaction.unit_price}</strong>
      </div>

      <div>
        <span>Amount</span>
        <strong>{transaction.amount}</strong>
      </div>

      <div>
        <span>Timestamp</span>
        <strong>{transaction.timestamp}</strong>
      </div>
    </div>
  );
}

function formatFieldName(field) {
  return field
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export default App;
