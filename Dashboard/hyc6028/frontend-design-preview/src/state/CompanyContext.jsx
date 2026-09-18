import { createContext, useContext, useEffect, useState } from "react";
import { api } from "../api/client";

const CompanyContext = createContext(null);

export function CompanyProvider({ children }) {
  const [companies, setCompanies] = useState([]);
  const [company, setCompany] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [urgencyCriteria, setUrgencyCriteria] = useState({});

  useEffect(() => {
    api
      .companies()
      .then((list) => {
        setCompanies(list);
        if (list.length > 0) setCompany(list[0].company);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!company) return;
    api
      .urgencyCriteria(company)
      .then((res) => setUrgencyCriteria(res.criteria || {}))
      .catch(() => setUrgencyCriteria({}));
  }, [company]);

  return (
    <CompanyContext.Provider
      value={{ companies, company, setCompany, loading, error, urgencyCriteria }}
    >
      {children}
    </CompanyContext.Provider>
  );
}

export function useCompany() {
  const ctx = useContext(CompanyContext);
  if (!ctx) throw new Error("useCompany must be used within CompanyProvider");
  return ctx;
}
