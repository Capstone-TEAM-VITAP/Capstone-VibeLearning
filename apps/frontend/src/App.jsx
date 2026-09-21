import {
  SignInButton,
  SignUpButton,
  Show,
} from "@clerk/react";
import Dashboard from "./pages/Dashboard.jsx";
import ThemeToggle from "./components/ThemeToggle.jsx";
import "./App.css";

function App() {
  return (
    <div className="app-container">
      <Show when="signed-out">
        <header className="app-header">
          <div className="brand-container">
            <h1 className="brand-title" data-testid="brand-title">CodeAI</h1>
            <span className="brand-badge">Dashboard</span>
          </div>

          <div className="auth-nav">
            <ThemeToggle />
            <SignInButton mode="modal">
              <button className="btn-sign-in" data-testid="sign-in-btn">Sign In</button>
            </SignInButton>
            <SignUpButton mode="modal">
              <button className="btn-sign-up" data-testid="sign-up-btn">Sign Up</button>
            </SignUpButton>
          </div>
        </header>

        <main className="app-main">
          <div className="hero-card" data-testid="hero-card">
            <h2>Welcome to CodeAI</h2>
            <p>AI-powered coding learning platform that connects GitHub repositories with personalized code analysis, learning paths, and developer insights.</p>
            <div style={{ marginTop: "24px" }}>
              <SignInButton mode="modal">
                <button className="btn-sign-up" data-testid="hero-get-started-btn">Get Started</button>
              </SignInButton>
            </div>
          </div>
        </main>
      </Show>

      <Show when="signed-in">
        <Dashboard />
      </Show>
    </div>
  );
}

export default App;