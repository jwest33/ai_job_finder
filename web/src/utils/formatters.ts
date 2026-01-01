import { format, formatDistanceToNow, parseISO } from 'date-fns';

export function formatDate(date: string | Date): string {
  const d = typeof date === 'string' ? parseISO(date) : date;
  return format(d, 'MMM d, yyyy');
}

export function formatDateTime(date: string | Date): string {
  const d = typeof date === 'string' ? parseISO(date) : date;
  return format(d, 'MMM d, yyyy h:mm a');
}

export function formatRelativeTime(date: string | Date): string {
  const d = typeof date === 'string' ? parseISO(date) : date;
  return formatDistanceToNow(d, { addSuffix: true });
}

export function formatSalary(
  min?: number | null,
  max?: number | null,
  currency = '$',
  period = 'yearly'
): string | null {
  if (!min && !max) return null;

  const formatK = (n: number) => {
    if (n >= 1000) {
      return `${(n / 1000).toFixed(0)}k`;
    }
    return n.toLocaleString();
  };

  if (min && max) {
    return `${currency}${formatK(min)} - ${currency}${formatK(max)} ${period}`;
  }
  if (min) {
    return `From ${currency}${formatK(min)} ${period}`;
  }
  return `Up to ${currency}${formatK(max!)} ${period}`;
}

export function formatNumber(n: number): string {
  return n.toLocaleString();
}

export function formatPercentage(n: number, decimals = 0): string {
  return `${n.toFixed(decimals)}%`;
}

export function truncate(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str;
  return str.slice(0, maxLength - 3) + '...';
}

export function slugify(str: string): string {
  return str
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '');
}
