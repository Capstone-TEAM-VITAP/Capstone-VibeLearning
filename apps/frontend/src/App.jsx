import { Show } from "@clerk/react";
import Dashboard from "./pages/Dashboard.jsx";
import LandingPage from "./components/LandingPage.jsx";
import "./App.css";

function App() {
  return (
    <div className="app-container">
      <Show when="signed-out">
        <LandingPage />
      </Show>

      <Show when="signed-in">
        <Dashboard />
      </Show>
    </div>
  );
}

export default App;
