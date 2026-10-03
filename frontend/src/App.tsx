import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import { lazy, Suspense } from 'react';
import Layout from "./components/Layout";
import { Loading } from './components/workbench/Common';

const Projects = lazy(() => import('./pages/Projects').then(module => ({ default: module.Projects })));
const ProjectWorkspace = lazy(() => import('./pages/ProjectWorkspace').then(module => ({ default: module.ProjectWorkspace })));
const ColorSchemes = lazy(() => import('./pages/ColorSchemes').then(module => ({ default: module.ColorSchemes })));
const Settings = lazy(() => import('./pages/Settings').then(module => ({ default: module.Settings })));
const Generate = lazy(() => import('./pages/Generate').then(module => ({ default: module.Generate })));

function App() {
  return (
    <Router>
      <Suspense fallback={<Loading />}>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Navigate to="/projects" replace />} />
          <Route path="/projects" element={<Projects />} />
          <Route path="/projects/:id" element={<ProjectWorkspace />} />
          <Route path="/color-schemes" element={<ColorSchemes />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/generate" element={<Generate />} />
        </Route>
      </Routes>
      </Suspense>
    </Router>
  );
}

export default App;
