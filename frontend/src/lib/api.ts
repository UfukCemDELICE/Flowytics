import axios from 'axios';
import { useAuth } from '@clerk/nextjs';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function useApi() {
  const { getToken } = useAuth();
  const client = axios.create({ baseURL: BASE_URL });
  client.interceptors.request.use(async (config) => {
    const token = await getToken();
    if (token) config.headers.Authorization = 'Bearer ' + token;
    return config;
  });
  return client;
}

export async function apiFetch(path: string, token: string): Promise<Response> {
  return fetch(BASE_URL + path, {
    headers: { Authorization: 'Bearer ' + token },
    cache: 'no-store',
  });
}
