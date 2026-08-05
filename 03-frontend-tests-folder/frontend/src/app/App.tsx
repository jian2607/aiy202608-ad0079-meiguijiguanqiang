import { Route, Routes } from "react-router-dom";
import { AppNavigation } from "../widgets/app-navigation/AppNavigation";
import { HomePage } from "../pages/home/HomePage";
import { CompanySearchPage } from "../pages/company-search/CompanySearchPage";
import { DataImportPage } from "../pages/data-import/DataImportPage";
import { RiskAnalysisPage } from "../pages/risk-analysis/RiskAnalysisPage";
import { UserWorkspacePage } from "../pages/user-workspace/UserWorkspacePage";

export function App() {
  return <div className="app-shell"><AppNavigation /><main className="page-container"><Routes>
    <Route path="/" element={<HomePage />} />
    <Route path="/companies" element={<CompanySearchPage />} />
    <Route path="/import" element={<DataImportPage />} />
    <Route path="/analysis" element={<RiskAnalysisPage />} />
    <Route path="/workspace" element={<UserWorkspacePage />} />
  </Routes></main></div>;
}
