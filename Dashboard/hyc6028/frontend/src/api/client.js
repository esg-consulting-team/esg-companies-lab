const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function request(path, options) {
  const res = await fetch(`${BASE_URL}${path}`, options);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `요청 실패 (${res.status})`);
  }
  return res.json();
}

function postJson(path, body) {
  return request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export const api = {
  companies: () => request("/api/companies"),
  summary: (company) => request(`/api/companies/${encodeURIComponent(company)}/summary`),
  domainItems: (company, domainKey) =>
    request(`/api/companies/${encodeURIComponent(company)}/domains/${domainKey}/items`),
  itemDetail: (company, itemCode) =>
    request(`/api/companies/${encodeURIComponent(company)}/items/${encodeURIComponent(itemCode)}`),
  comparison: (company) => request(`/api/companies/${encodeURIComponent(company)}/comparison`),
  roadmap: (company) => request(`/api/companies/${encodeURIComponent(company)}/roadmap`),
  roadmapRoi: (company) => request(`/api/companies/${encodeURIComponent(company)}/roadmap/roi`),
  simulate: (company, taskIds) =>
    postJson(`/api/companies/${encodeURIComponent(company)}/simulations`, { task_ids: taskIds }),
  documents: (company) => request(`/api/companies/${encodeURIComponent(company)}/documents`),
  reportConfig: (company) => request(`/api/companies/${encodeURIComponent(company)}/report/config`),
  exportReport: async (company, format, sectionNos) => {
    const res = await fetch(
      `${BASE_URL}/api/companies/${encodeURIComponent(company)}/report/export`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ format, section_nos: sectionNos }),
      }
    );
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `요청 실패 (${res.status})`);
    }
    return res.blob();
  },
};
