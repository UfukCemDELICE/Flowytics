import { useAuth } from '@clerk/nextjs';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function useApi() {
  const { getToken } = useAuth();
  
  return async (path: string, options?: RequestInit) => {
    const token = await getToken();
    const headers = new Headers(options?.headers);
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }
    
    return fetch(BASE_URL + path, {
      ...options,
      headers,
    });
  };
}

export async function apiFetch(path: string, token: string): Promise<Response> {
  return fetch(BASE_URL + path, {
    headers: { Authorization: 'Bearer ' + token },
    cache: 'no-store',
  });
}
