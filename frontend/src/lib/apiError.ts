import axios from 'axios';

export function redactText(text: string): string {
  return text.replace(/\bsk-[\w-]+/gi, '[redacted]').replace(/Bearer\s+[\w.+/-]+/gi, 'Bearer [redacted]');
}

function errorText(value: unknown): string | null {
  if (typeof value === 'string') return redactText(value);
  if (Array.isArray(value)) return value.map(errorText).filter(Boolean).join('; ') || null;
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    return errorText(record.msg ?? record.message);
  }
  return null;
}

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    return errorText(error.response?.data?.detail) || errorText(error.response?.data?.message) || fallback;
  }
  return error instanceof Error ? redactText(error.message) : fallback;
}

export const isRevisionConflict = (error: unknown) => axios.isAxiosError(error) && error.response?.status === 409;
export const isUnknownOutcome = (error: unknown) => axios.isAxiosError(error) && (!error.response || error.response.status >= 500);
