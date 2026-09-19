import { useEffect, useState } from "react";
import { ApiError } from "../api/client";

/** 공용 데이터 로딩 훅. deps가 바뀌면 다시 fetch한다. */
export function useFetch<T>(fetcher: () => Promise<T>, deps: unknown[]): {
  data: T | null;
  loading: boolean;
  error: string | null;
} {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    fetcher()
      .then((d) => alive && setData(d))
      .catch((e) => {
        if (!alive) return;
        setError(e instanceof ApiError ? e.message : "데이터를 불러오지 못했습니다.");
      })
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, loading, error };
}
