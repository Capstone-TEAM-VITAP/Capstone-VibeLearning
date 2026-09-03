import {
  SignInButton,
  SignUpButton,
  UserButton,
  Show,
} from "@clerk/react";
import Dashboard from "./pages/Dashboard.jsx";
import "./App.css";

function App() {
  return (
    <div className="app-container">
      <header className="app-header">
        <div className="brand-container">
          <h1 className="brand-title" data-testid="brand-title">CodeAI</h1>
          <span className="brand-badge">Dashboard</span>
        </div>

        <div className="auth-nav">
          <Show when="signed-out">
            <SignInButton mode="modal">
              <button className="btn-sign-in" data-testid="sign-in-btn">Sign In</button>
            </SignInButton>
            <SignUpButton mode="modal">
              <button className="btn-sign-up" data-testid="sign-up-btn">Sign Up</button>
            </SignUpButton>
          </Show>

          <Show when="signed-in">
            <div className="user-button-wrapper">
              <span className="user-status-pill">
                <span className="user-status-dot"></span>
                Active
              </span>
              <UserButton
                appearance={{
                  elements: {
                    userButtonAvatarBox: {
                      width: "38px",
                      height: "38px",
                      borderRadius: "50%",
                      border: "2px solid var(--accent, #c084fc)",
                      boxShadow: "0 0 10px rgba(192, 132, 252, 0.35)",
                    },
                    userButtonPopoverCard: {
                      backgroundColor: "var(--bg, #16171d)",
                      border: "1px solid var(--border, #2e303a)",
                      color: "var(--text-h, #f3f4f6)",
                      boxShadow: "0 10px 25px rgba(0, 0, 0, 0.5)",
                    },
                    userButtonPopoverActionButton: {
                      color: "var(--text-h, #f3f4f6)",
                    },
                    userButtonPopoverActionButtonText: {
                      color: "var(--text-h, #f3f4f6)",
                    },
                    userButtonPopoverActionButtonIcon: {
                      color: "var(--accent, #c084fc)",
                    },
                    userButtonPopoverFooter: {
                      borderTop: "1px solid var(--border, #2e303a)",
                      backgroundColor: "var(--bg, #16171d)",
                    },
                  },
                }}
              />
            </div>
          </Show>
        </div>
      </header>

      <main className="app-main">
        <Show when="signed-out">
          <div className="hero-card" data-testid="hero-card">
            <h2>Welcome to CodeAI</h2>
            <p>AI-powered coding learning platform that connects GitHub repositories with personalized code analysis, learning paths, and developer insights.</p>
            <div style={{ marginTop: "24px" }}>
              <SignInButton mode="modal">
                <button className="btn-sign-up" data-testid="hero-get-started-btn">Get Started</button>
              </SignInButton>
            </div>
          </div>
        </Show>

        <Show when="signed-in">
          <Dashboard />
        </Show>
      </main>
    </div>
  );
}

export default App;