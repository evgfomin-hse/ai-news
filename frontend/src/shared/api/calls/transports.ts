import { apiFetch, parseFastApiDetail } from '../client';

export type TransportMe = {
  transportId: number | null;
  telegramConfigured: boolean;
  telegramChatId: string | null;
};

export async function getTransportMe(): Promise<TransportMe | null> {
  const response = await apiFetch('/transports/me');
  
  if (!response.ok) return null;

  return (await response.json()) as TransportMe;
}

export async function patchTransportMe(
  body: Record<string, string>,
): Promise<TransportMe> {
  const response = await apiFetch('/transports/me', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const json = (await response.json().catch(() => ({}))) as { detail?: unknown };
    throw new Error(parseFastApiDetail(json));
  }

  return (await response.json()) as TransportMe;
}

export type TelegramCaptureHelloResponse = {
  linked?: boolean;
  chatId?: string;
  hint?: string;
  detail?: unknown;
};

export async function postTelegramCaptureHello(): Promise<{
  response: Response;
  body: TelegramCaptureHelloResponse;
}> {
  const response = await apiFetch('/transports/me/telegram-capture-hello', {
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
  const response = await apiFetch('/transports/me/telegram-test', { method: 'POST' });
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
  const response = await apiFetch('/transports/me/send-message', {
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
