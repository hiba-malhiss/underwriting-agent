import { Navigate, Route, Routes } from "react-router-dom";
import { ApplicationPage } from "./pages/ApplicationPage";
import { Layout } from "./pages/Layout";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<ApplicationPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
