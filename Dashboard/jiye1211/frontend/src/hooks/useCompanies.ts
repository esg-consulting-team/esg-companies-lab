import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { CompanyRef } from "../types";

export function useCompanies() {
  const [companies, setCompanies] = useState<CompanyRef[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .listCompanies()
      .then((data) => alive && setCompanies(data))
      .catch((e) => alive && setError(e.message))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  return { companies, loading, error };
}
