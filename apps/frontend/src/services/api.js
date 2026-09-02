const API_URL =
  import.meta.env.VITE_API_URL || "http://localhost:5000/api/v1";

export async function getCurrentUser(getToken) {
  const token = await getToken();

  const response = await fetch(`${API_URL}/auth/me`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error("Failed to fetch current user");
  }

  return response.json();
}