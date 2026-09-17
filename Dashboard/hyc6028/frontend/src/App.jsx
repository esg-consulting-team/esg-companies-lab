import { Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./components/AppShell";
import L1Dashboard from "./pages/L1Dashboard";
import L2DomainDiagnosis from "./pages/L2DomainDiagnosis";
import L3ItemDetail from "./pages/L3ItemDetail";
import L4ComparisonAnalysis from "./pages/L4ComparisonAnalysis";
import L5ImprovementRoadmap from "./pages/L5ImprovementRoadmap";
import L6EvidenceDataRoom from "./pages/L6EvidenceDataRoom";
import L7Report from "./pages/L7Report";
import { CompanyProvider } from "./state/CompanyContext";

export default function App() {
  return (
    <CompanyProvider>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/l1" replace />} />
          <Route path="/l1" element={<L1Dashboard />} />
          <Route path="/l2" element={<L2DomainDiagnosis />} />
          <Route path="/l3" element={<L3ItemDetail />} />
          <Route path="/l4" element={<L4ComparisonAnalysis />} />
          <Route path="/l5" element={<L5ImprovementRoadmap />} />
          <Route path="/l6" element={<L6EvidenceDataRoom />} />
          <Route path="/l7" element={<L7Report />} />
        </Route>
      </Routes>
    </CompanyProvider>
  );
}
