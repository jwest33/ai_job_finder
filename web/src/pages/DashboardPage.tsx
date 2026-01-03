import { useQuery } from '@tanstack/react-query';
import { Briefcase, Target, TrendingUp, Clock, CheckCircle, XCircle } from 'lucide-react';
import { Card, CardTitle } from '../components/common/Card';
import { LoadingPage } from '../components/common/LoadingSpinner';
import { jobsApi } from '../api/jobs';
import { applicationsApi } from '../api/applications';
import { Link } from 'react-router-dom';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  description?: string;
  trend?: { value: number; label: string };
  color?: string;
}

function StatCard({ title, value, icon, description, color = 'blue' }: StatCardProps) {
  const colors: Record<string, string> = {
    blue: 'bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400',
    green: 'bg-green-50 dark:bg-green-900/30 text-green-600 dark:text-green-400',
    yellow: 'bg-yellow-50 dark:bg-yellow-900/30 text-yellow-600 dark:text-yellow-400',
    red: 'bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-400',
    purple: 'bg-purple-50 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400',
  };

  return (
    <Card>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">{title}</p>
          <p className="mt-1 text-3xl font-bold text-gray-900 dark:text-white">{value}</p>
          {description && <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{description}</p>}
        </div>
        <div className={`p-3 rounded-lg ${colors[color]}`}>{icon}</div>
      </div>
    </Card>
  );
}

export function DashboardPage() {
  const { data: jobStats, isLoading: loadingJobs } = useQuery({
    queryKey: ['job-stats'],
    queryFn: jobsApi.getStats,
  });

  const { data: appStats, isLoading: loadingApps } = useQuery({
    queryKey: ['application-stats'],
    queryFn: applicationsApi.getStats,
  });

  if (loadingJobs || loadingApps) {
    return <LoadingPage message="Loading dashboard..." />;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Dashboard</h1>
        <p className="text-gray-500 dark:text-gray-400 mt-1">Overview of your job search progress</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Jobs"
          value={jobStats?.total_jobs || 0}
          icon={<Briefcase className="w-6 h-6" />}
          description={`${jobStats?.scored_jobs || 0} scored`}
          color="blue"
        />
        <StatCard
          title="High Matches"
          value={jobStats?.high_matches || 0}
          icon={<Target className="w-6 h-6" />}
          description={`Score ${jobStats?.thresholds?.excellent || 80}+`}
          color="green"
        />
        <StatCard
          title="Average Score"
          value={jobStats?.avg_score ? Math.round(jobStats.avg_score) : 0}
          icon={<TrendingUp className="w-6 h-6" />}
          description="Match score"
          color="purple"
        />
        <StatCard
          title="Applications"
          value={appStats?.total || 0}
          icon={<CheckCircle className="w-6 h-6" />}
          description={`${appStats?.by_status?.interviewing || 0} interviewing`}
          color="yellow"
        />
      </div>

      {/* Application Pipeline */}
      <Card>
        <CardTitle>Application Pipeline</CardTitle>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mt-4">
          {[
            { status: 'applied', label: 'Applied', color: 'bg-blue-500' },
            { status: 'phone_screen', label: 'Phone Screen', color: 'bg-purple-500' },
            { status: 'interviewing', label: 'Interviewing', color: 'bg-yellow-500' },
            { status: 'final_round', label: 'Final Round', color: 'bg-orange-500' },
            { status: 'offer', label: 'Offers', color: 'bg-green-500' },
            { status: 'rejected', label: 'Rejected', color: 'bg-red-500' },
          ].map(({ status, label, color }) => (
            <div key={status} className="text-center">
              <div className={`w-12 h-12 ${color} rounded-full flex items-center justify-center mx-auto text-white font-bold text-lg`}>
                {appStats?.by_status?.[status as keyof typeof appStats.by_status] || 0}
              </div>
              <p className="mt-2 text-sm font-medium text-gray-600 dark:text-gray-400">{label}</p>
            </div>
          ))}
        </div>
      </Card>

      {/* Score Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardTitle>Score Distribution</CardTitle>
          <div className="space-y-4 mt-4">
            {[
              {
                label: `Excellent (${jobStats?.thresholds?.excellent || 80}+)`,
                value: jobStats?.high_matches || 0,
                color: 'bg-green-500'
              },
              {
                label: `Good (${jobStats?.thresholds?.good || 60}-${(jobStats?.thresholds?.excellent || 80) - 1})`,
                value: jobStats?.medium_matches || 0,
                color: 'bg-yellow-500'
              },
              {
                label: `Low (<${jobStats?.thresholds?.good || 60})`,
                value: jobStats?.low_matches || 0,
                color: 'bg-red-500'
              },
            ].map(({ label, value, color }) => (
              <div key={label}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-600 dark:text-gray-400">{label}</span>
                  <span className="font-medium text-gray-900 dark:text-white">{value}</span>
                </div>
                <div className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-full">
                  <div
                    className={`h-full ${color} rounded-full`}
                    style={{
                      width: `${jobStats?.scored_jobs ? (value / jobStats.scored_jobs) * 100 : 0}%`,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <CardTitle>Quick Actions</CardTitle>
          <div className="space-y-3 mt-4">
            <Link
              to={`/jobs?min_score=${jobStats?.thresholds?.excellent || 80}`}
              className="flex items-center gap-3 p-3 rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
            >
              <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-lg">
                <Target className="w-5 h-5 text-green-600 dark:text-green-400" />
              </div>
              <div>
                <p className="font-medium text-gray-900 dark:text-white">View High Matches</p>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {jobStats?.high_matches || 0} jobs with score {jobStats?.thresholds?.excellent || 80}+
                </p>
              </div>
            </Link>
            <Link
              to="/search"
              className="flex items-center gap-3 p-3 rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
            >
              <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                <Briefcase className="w-5 h-5 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <p className="font-medium text-gray-900 dark:text-white">New Job Search</p>
                <p className="text-sm text-gray-500 dark:text-gray-400">Start scraping for new jobs</p>
              </div>
            </Link>
            <Link
              to="/applications"
              className="flex items-center gap-3 p-3 rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
            >
              <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
                <Clock className="w-5 h-5 text-purple-600 dark:text-purple-400" />
              </div>
              <div>
                <p className="font-medium text-gray-900 dark:text-white">Track Applications</p>
                <p className="text-sm text-gray-500 dark:text-gray-400">Manage your application pipeline</p>
              </div>
            </Link>
          </div>
        </Card>
      </div>
    </div>
  );
}
