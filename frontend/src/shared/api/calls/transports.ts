import { apiFetch, parseFastApiDetail } from '../client';

export type TransportView = {
  transportId: number | null;
  telegramConfigured: boolean;
  telegramChatId: string | null;
};

export async function getTransport(): Promise<TransportView | null> {
  const response = await apiFetch('/transports');

  if (!response.ok) return null;

  return (await response.json()) as TransportView;
}

export async function patchTransport(
  body: Record<string, string>,
): Promise<TransportView> {
  const response = await apiFetch('/transports', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const json = (await response.json().catch(() => ({}))) as { detail?: unknown };
    throw new Error(parseFastApiDetail(json));
  }

  return (await response.json()) as TransportView;
}

export type TelegramCaptureHelloResponse = {
  linked?: boolean;
  chatId?: string;
  hint?: string;
  detail?: unknown;
};

export async function postTelegramCaptureMessage(): Promise<{
  response: Response;
  body: TelegramCaptureHelloResponse;
}> {
  const response = await apiFetch('/transports/telegram/capture-user-id', {
    method: 'POST',
  });

  const body = (await response.json().catch(() => ({}))) as TelegramCaptureHelloResponse;

  return { response: response, body };
}

export type TelegramTestResponse = {
  botUsername?: string;
  botId?: number;
  detail?: unknown;
};

export async function postTelegramTest(): Promise<TelegramTestResponse> {
  const response = await apiFetch('/transports/telegram/test', { method: 'POST' });
  const json = (await response.json().catch(() => ({}))) as TelegramTestResponse;

  if (!response.ok) {
    throw new Error(parseFastApiDetail(json));
  }

  return json;
}

export type SendMessageResponse = {
  telegramMessageId?: number;
  detail?: unknown;
};

export async function postTransportSendMessage(
  text: string,
): Promise<SendMessageResponse> {
  const response = await apiFetch('/transports/telegram/send-message', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
  const json = (await response.json().catch(() => ({}))) as SendMessageResponse;

  if (!response.ok) {
    throw new Error(parseFastApiDetail(json));
  }

  return json;
}
