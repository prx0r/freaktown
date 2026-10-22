import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { StagePage } from './pages/StagePage';
import { ControlPage } from './pages/ControlPage';
import { LivePage } from './pages/LivePage';
import { HomePage } from './pages/HomePage';
import { NotFound } from './pages/NotFound';
import { PlayPage } from './pages/PlayPage';
import { NewsroomPage } from './pages/NewsroomPage';
import { SketchPage } from './pages/SketchPage';
import { TntsPage } from './pages/TntsPage';
import { WatchPage } from './pages/WatchPage';
import { RoomsPage } from './pages/RoomsPage';
import { MinutePage } from './pages/MinutePage';
import { CharactersPage } from './pages/CharactersPage';

// NOTE (migration): creator routes (/studio /green-room /demo) are
// deliberately ABSENT. FUNNIER Studio is the one creator. This app
// serves production surfaces only: stage, control, live audience.
// /stage-ws (ThreeWsStagePage) is parked: its <agent-3d> component was not
// carried over from killella (see docs/LIVE-STAGE.md "what's left").

const basename = import.meta.env.BASE_URL.replace(/\/$/, '') || undefined;

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter basename={basename}>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/stage/:episodeId" element={<StagePage />} />
        <Route path="/stage" element={<StagePage />} />
        <Route path="/control/:episodeId" element={<ControlPage />} />
        <Route path="/control" element={<ControlPage />} />
        <Route path="/live/:episodeId" element={<LivePage />} />
        <Route path="/play/:episodeId/seat/:seat" element={<PlayPage />} />
        <Route path="/watch" element={<WatchPage />} />
        <Route path="/watch/:setId" element={<WatchPage />} />
        <Route path="/newsroom/:showId" element={<NewsroomPage />} />
        <Route path="/sketch" element={<SketchPage />} />
        <Route path="/sketch/:sketchId" element={<SketchPage />} />
        <Route path="/tnts" element={<TntsPage />} />
        <Route path="/minute" element={<MinutePage />} />
        <Route path="/characters3" element={<CharactersPage />} />
        <Route path="/characters3/:slug" element={<CharactersPage />} />
        <Route path="/rooms" element={<RoomsPage />} />
        <Route path="/rooms/:roomId" element={<RoomsPage />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
