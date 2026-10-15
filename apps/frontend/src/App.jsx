import {
  SignInButton,
  SignUpButton,
  Show,
} from "@clerk/react";
import { ArrowRight, Sparkles } from "lucide-react";
import Dashboard from "./pages/Dashboard.jsx";
import ThemeToggle from "./components/ThemeToggle.jsx";
import { Button } from "./components/ui/button.jsx";
import { Badge } from "./components/ui/badge.jsx";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "./components/ui/card.jsx";
import "./App.css";

function App() {
  return (
    <div className="app-container">
      <Show when="signed-out">
        <header className="app-header">
          <div className="brand-container">
            <h1 className="brand-title" data-testid="brand-title">CodeAI</h1>
            <Badge variant="secondary">Dashboard</Badge>
          </div>

          <div className="auth-nav">
            <ThemeToggle />
            <SignInButton mode="modal">
              <Button variant="outline" data-testid="sign-in-btn">Sign In</Button>
            </SignInButton>
            <SignUpButton mode="modal">
              <Button data-testid="sign-up-btn">Sign Up</Button>
            </SignUpButton>
          </div>
        </header>

        <main className="app-main">
          <Card className="mx-auto w-full max-w-xl text-center" data-testid="hero-card">
            <CardHeader className="items-center text-center">
              <Badge>
                <Sparkles />
                Repository Intelligence
              </Badge>
              <CardTitle className="text-3xl">Welcome to CodeAI</CardTitle>
              <CardDescription className="max-w-md">
                AI-powered coding learning platform that connects GitHub repositories with personalized code analysis, learning paths, and developer insights.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex justify-center pb-8">
              <SignInButton mode="modal">
                <Button size="lg" data-testid="hero-get-started-btn">
                  Get Started
                  <ArrowRight />
                </Button>
              </SignInButton>
            </CardContent>
          </Card>
        </main>
      </Show>

      <Show when="signed-in">
        <Dashboard />
      </Show>
    </div>
  );
}

export default App;
