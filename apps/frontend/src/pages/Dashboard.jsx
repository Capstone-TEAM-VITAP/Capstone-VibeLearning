import { useEffect, useState } from "react";
import { useAuth, UserButton } from "@clerk/react";
import { getCurrentUser } from "../services/api.js";

function Dashboard() {
  const { getToken, isLoaded, isSignedIn } = useAuth();

  const [user, setUser] = useState(null);

  useEffect(() => {
    if (!isLoaded || !isSignedIn) return;

    async function loadUser() {
      try {
        const data = await getCurrentUser(getToken);
        setUser(data.data);
      } catch (error) {
        console.error(error);
      }
    }

    loadUser();
  }, [isLoaded, isSignedIn, getToken]);

  return (
    <div className="dashboard-card">
      <div className="dashboard-header-row">
        <div>
          <h2>Dashboard Overview</h2>
          <p>Welcome to your CodeAI workspace.</p>
        </div>
        <UserButton
          appearance={{
            elements: {
              userButtonAvatarBox: {
                width: "40px",
                height: "40px",
                borderRadius: "50%",
                border: "2px solid var(--accent, #c084fc)",
                boxShadow: "0 0 10px rgba(192, 132, 252, 0.3)",
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

      <div className="profile-box">
        <h3>Authenticated Profile</h3>
        {user ? (
          <p>
            <strong>Clerk User ID:</strong> <code>{user.userId}</code>
          </p>
        ) : (
          <p>
            <strong>Status:</strong> Authenticated with Clerk
          </p>
        )}
      </div>
    </div>
  );
}

export default Dashboard;