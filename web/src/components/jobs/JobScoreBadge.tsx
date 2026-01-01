import clsx from 'clsx';

interface JobScoreBadgeProps {
  score: number | undefined | null;
  size?: 'sm' | 'md' | 'lg';
}

export function JobScoreBadge({ score, size = 'md' }: JobScoreBadgeProps) {
  if (score === undefined || score === null) {
    return (
      <span className="px-2 py-1 rounded-full bg-gray-100 text-gray-500 text-xs font-medium">
        Unscored
      </span>
    );
  }

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'bg-green-100 text-green-700 border-green-200';
    if (score >= 60) return 'bg-yellow-100 text-yellow-700 border-yellow-200';
    if (score >= 40) return 'bg-orange-100 text-orange-700 border-orange-200';
    return 'bg-red-100 text-red-700 border-red-200';
  };

  const getScoreLabel = (score: number) => {
    if (score >= 80) return 'Excellent';
    if (score >= 60) return 'Good';
    if (score >= 40) return 'Fair';
    return 'Low';
  };

  const sizes = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-sm',
    lg: 'px-3 py-1.5 text-base',
  };

  return (
    <span
      className={clsx(
        'inline-flex items-center font-semibold rounded-full border',
        getScoreColor(score),
        sizes[size]
      )}
    >
      <span className="mr-1">{Math.round(score)}</span>
      <span className="text-xs font-normal opacity-75">/ 100</span>
    </span>
  );
}

export function JobScoreBar({ score }: { score: number | undefined | null }) {
  if (score === undefined || score === null) {
    return (
      <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
        <div className="h-full bg-gray-300 w-0" />
      </div>
    );
  }

  const getBarColor = (score: number) => {
    if (score >= 80) return 'bg-green-500';
    if (score >= 60) return 'bg-yellow-500';
    if (score >= 40) return 'bg-orange-500';
    return 'bg-red-500';
  };

  return (
    <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
      <div
        className={clsx('h-full transition-all duration-300', getBarColor(score))}
        style={{ width: `${score}%` }}
      />
    </div>
  );
}
