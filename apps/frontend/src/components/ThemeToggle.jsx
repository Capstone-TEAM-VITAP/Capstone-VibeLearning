import { useState, useEffect, useCallback } from "react";
import { Moon, Sun } from "lucide-react";
import { THEME_STORAGE_KEY, getStoredTheme, applyTheme } from "../services/theme.js";
import "./ThemeToggle.css";

export default function ThemeToggle({ showLabel = false, className = "" }) {
  const [theme, setTheme] = useState(() => getStoredTheme());

  // Keep state in sync with DOM / storage changes
  useEffect(() => {
    const handleThemeChange = (e) => {
      if (e.detail?.theme) {
        setTheme(e.detail.theme);
      }
    };

    const handleStorageChange = (e) => {
      if (e.key === THEME_STORAGE_KEY && (e.newValue === "light" || e.newValue === "dark")) {
        setTheme(e.newValue);
        applyTheme(e.newValue);
      }
    };

    window.addEventListener("codeai-theme-change", handleThemeChange);
    window.addEventListener("storage", handleStorageChange);

    return () => {
      window.removeEventListener("codeai-theme-change", handleThemeChange);
      window.removeEventListener("storage", handleStorageChange);
    };
  }, []);

  const handleToggle = useCallback(() => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
    } catch {
      // Ignore storage errors in private browsing
    }
    applyTheme(nextTheme);
    window.dispatchEvent(
      new CustomEvent("codeai-theme-change", { detail: { theme: nextTheme } })
    );
  }, [theme]);

  const isLight = theme === "light";

  return (
    <button
      type="button"
      className={`theme-toggle-btn ${isLight ? "theme-toggle-btn--light" : "theme-toggle-btn--dark"} ${className}`}
      onClick={handleToggle}
      aria-label={isLight ? "Switch to Dark Mode (Terminal Horizon)" : "Switch to Light Mode (Golden Summer Fields)"}
      title={isLight ? "Switch to Dark Mode" : "Switch to Light Mode"}
    >
      <span className="theme-toggle-icon">
        {isLight ? <Moon size={16} /> : <Sun size={16} />}
      </span>
      {showLabel && (
        <span className="theme-toggle-label">
          {isLight ? "Light Mode" : "Dark Mode"}
        </span>
      )}
    </button>
  );
}
