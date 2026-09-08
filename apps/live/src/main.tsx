import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { StagePage } from './pages/StagePage';
import { ThreeWsStagePage as StageWsPage } from './pages/ThreeWsStagePage';
import { ControlPage } from './pages/ControlPage';
import { LivePage } from './pages/LivePage';
import { NotFound } from './pages/NotFound';

// NOTE (migration): creator routes (/ /studio /green-room /demo) are
// deliberately ABSENT. Freak Town Studio is the one creator. This app
// serves production surfaces only: stage, control, live audience.

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        {/* Live show views */}
        <Route path="/stage/:episodeId" element={<StagePage />} />
        <Route path="/stage-ws/:episodeId" element={<StageWsPage />} />
        <Route path="/control/:episodeId" element={<ControlPage />} />
        <Route path="/live/:episodeId" element={<LivePage />} />

        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
