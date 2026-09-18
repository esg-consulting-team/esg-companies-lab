import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { L1Dashboard } from "./pages/L1Dashboard";
import { L2DomainDiagnosis } from "./pages/L2DomainDiagnosis";
import { L3ItemDetail } from "./pages/L3ItemDetail";
import { L4ComparisonAnalysis } from "./pages/L4ComparisonAnalysis";
import { L5RoadmapImprovement } from "./pages/L5RoadmapImprovement";
import { L6EvidenceDataRoom } from "./pages/L6EvidenceDataRoom";
import { L7Report } from "./pages/L7Report";

const DEFAULT_COMPANY = "DN오토모티브";

function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to={`/companies/${encodeURIComponent(DEFAULT_COMPANY)}/l1`} replace />} />
      <Route path="/companies/:company" element={<AppShell />}>
        <Route path="l1" element={<L1Dashboard />} />
        <Route path="l2" element={<Navigate to="environment" replace />} />
        <Route path="l2/:bucket" element={<L2DomainDiagnosis />} />
        <Route path="l3" element={<L3ItemDetail />} />
        <Route path="l3/:code" element={<L3ItemDetail />} />
        <Route path="l4" element={<L4ComparisonAnalysis />} />
        <Route path="l5" element={<L5RoadmapImprovement />} />
        <Route path="l6" element={<L6EvidenceDataRoom />} />
        <Route path="l7" element={<L7Report />} />
        <Route index element={<Navigate to="l1" replace />} />
      </Route>
      <Route path="*" element={<Navigate to={`/companies/${encodeURIComponent(DEFAULT_COMPANY)}/l1`} replace />} />
    </Routes>
  );
}

export default App;
