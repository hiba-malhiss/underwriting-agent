import { Navigate, Route, Routes } from "react-router-dom";
import { ApplicantPage } from "./pages/ApplicantPage";
import { Layout } from "./pages/Layout";
import { RequirementsPage } from "./pages/RequirementsPage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<ApplicantPage />} />
        <Route path="/requirements" element={<RequirementsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
