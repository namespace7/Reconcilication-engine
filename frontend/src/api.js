const apiRequest = async (url, options = {}) => {
  const response = await fetch(url, options);

  let data = {};

  try {
    data = await response.json();
  } catch {
    // Some responses may not contain JSON.
  }

  if (!response.ok) {
    throw new Error(data.error || `Request failed: ${response.status}`);
  }

  return data;
};

export const uploadFile = async (sourceId, file) => {
  const formData = new FormData();

  formData.append("source_id", sourceId);
  formData.append("file", file);

  return apiRequest("/api/files/", {
    method: "POST",
    body: formData,
  });
};

export const createRun = async (ourFileId, externalFileId, rulesetId) => {
  return apiRequest("/api/runs/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      our_file_id: ourFileId,
      external_file_id: externalFileId,
      ruleset_id: rulesetId,
    }),
  });
};

export const getRun = async (runId) => {
  return apiRequest(`/api/runs/${runId}/`);
};

export const createManualDecision = async (
  resultId,
  decision,
  externalTransactionId,
  reason,
  decidedBy,
) => {
  return apiRequest(`/api/results/${resultId}/decision/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      decision,
      ...(externalTransactionId
        ? { external_transaction_id: externalTransactionId }
        : {}),
      reason,
      decided_by: decidedBy,
    }),
  });
};

export const getCurrentRuleset = async () => {
  return apiRequest("/api/rulesets/current/");
};

export const updateRuleset = async (rulesetId, values) => {
  return apiRequest(`/api/rulesets/${rulesetId}/`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(values),
  });
};
