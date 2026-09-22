const IST_TIME_ZONE = 'Asia/Kolkata';

export function formatIST(
  timestamp: string | Date,
  options?: Intl.DateTimeFormatOptions,
): string {
  const date = timestamp instanceof Date ? timestamp : new Date(timestamp);

  if (Number.isNaN(date.getTime())) {
    return '—';
  }

  return new Intl.DateTimeFormat('en-IN', {
    timeZone: IST_TIME_ZONE,
    ...options,
  }).format(date);
}

export function formatISTTime(
  timestamp: string | Date,
  includeTimeZone = false,
): string {
  return formatIST(timestamp, {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
    ...(includeTimeZone ? { timeZoneName: 'short' } : {}),
  });
}

export function formatISTDateTime(timestamp: string | Date): string {
  return formatIST(timestamp, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

export function formatISTDateTimeWithZone(timestamp: string | Date): string {
  return formatIST(timestamp, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
    timeZoneName: 'short',
  });
}
