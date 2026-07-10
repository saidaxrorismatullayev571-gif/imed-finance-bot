import { env } from '../../env';

export interface GraphResult {
  ok: boolean;
  status: number;
  body: unknown;
}

/**
 * Graph API'ga POST so'rov. Access token Authorization header orqali yuboriladi
 * (URL log'larida token ochilib qolmasligi uchun).
 */
export async function graphPost(
  path: string,
  accessToken: string,
  payload: unknown,
): Promise<GraphResult> {
  const url = `https://graph.facebook.com/${env.META_GRAPH_VERSION}/${path}`;
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify(payload),
  });
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  return { ok: res.ok, status: res.status, body };
}
