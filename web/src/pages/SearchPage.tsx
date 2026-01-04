import { useState, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Search, Loader2, CheckCircle, XCircle, Zap, Rocket } from 'lucide-react';
import { scraperApi, SearchParams, MatchParams } from '../api/scraper';
import { Card, CardTitle } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { Input } from '../components/common/Input';
import { useToast } from '../store/uiStore';

export function SearchPage() {
  const toast = useToast();

  // Search form state
  const [jobTitles, setJobTitles] = useState<string>('');
  const [locations, setLocations] = useState<string>('');
  const [resultsPerSearch, setResultsPerSearch] = useState(50);
  const [selectedScrapers, setSelectedScrapers] = useState<string[]>(['indeed', 'glassdoor']);

  // Task tracking
  const [searchTaskId, setSearchTaskId] = useState<string | null>(null);
  const [matchTaskId, setMatchTaskId] = useState<string | null>(null);
  const [hasCheckedActiveTasks, setHasCheckedActiveTasks] = useState(false);

  // Match options
  const [reMatchAll, setReMatchAll] = useState(false);

  // Check for active tasks on mount
  const { data: activeTasks } = useQuery({
    queryKey: ['active-tasks'],
    queryFn: scraperApi.getActiveTasks,
    staleTime: 0, // Always fetch fresh on mount
    enabled: !hasCheckedActiveTasks, // Only run once on mount
  });

  // Resume tracking active tasks found on mount
  useEffect(() => {
    if (activeTasks && !hasCheckedActiveTasks) {
      if (activeTasks.search?.task_id) {
        setSearchTaskId(activeTasks.search.task_id);
      }
      if (activeTasks.match?.task_id) {
        setMatchTaskId(activeTasks.match.task_id);
      }
      setHasCheckedActiveTasks(true);
    }
  }, [activeTasks, hasCheckedActiveTasks]);

  // Load config
  const { data: config, isLoading: configLoading } = useQuery({
    queryKey: ['scraper-config'],
    queryFn: scraperApi.getConfig,
  });

  // Pre-populate form with config values
  useEffect(() => {
    if (config) {
      if (config.search_terms?.length > 0 && !jobTitles) {
        setJobTitles(config.search_terms.join(', '));
      }
      if (config.locations?.length > 0 && !locations) {
        setLocations(config.locations.join(', '));
      }
    }
  }, [config]);

  // Search status polling
  const { data: searchStatus } = useQuery({
    queryKey: ['search-status', searchTaskId],
    queryFn: () => scraperApi.getSearchStatus(searchTaskId!),
    enabled: !!searchTaskId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'running' || status === 'pending' ? 2000 : false;
    },
  });

  // Match status polling
  const { data: matchStatus } = useQuery({
    queryKey: ['match-status', matchTaskId],
    queryFn: () => scraperApi.getMatchStatus(matchTaskId!),
    enabled: !!matchTaskId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'running' || status === 'pending' ? 2000 : false;
    },
  });

  // Start search mutation
  const searchMutation = useMutation({
    mutationFn: (params: SearchParams) => scraperApi.startSearch(params),
    onSuccess: (data) => {
      setSearchTaskId(data.task_id);
      toast.info('Job search started');
    },
    onError: () => {
      toast.error('Failed to start search');
    },
  });

  // Start matching mutation
  const matchMutation = useMutation({
    mutationFn: (params: MatchParams) => scraperApi.startMatching(params),
    onSuccess: (data) => {
      setMatchTaskId(data.task_id);
      toast.info('AI matching started');
    },
    onError: () => {
      toast.error('Failed to start matching');
    },
  });

  const handleStartSearch = () => {
    const jobs = jobTitles
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    const locs = locations
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);

    if (jobs.length === 0) {
      toast.error('Please enter at least one job title');
      return;
    }

    searchMutation.mutate({
      jobs,
      locations: locs.length > 0 ? locs : ['Remote'],
      results_per_search: resultsPerSearch,
      scrapers: selectedScrapers,
    });
  };

  const handleQuickSearch = () => {
    if (!config?.search_terms?.length) {
      toast.error('No search terms configured in requirements');
      return;
    }

    searchMutation.mutate({
      jobs: config.search_terms,
      locations: config.locations?.length > 0 ? config.locations : ['Remote'],
      results_per_search: resultsPerSearch,
      scrapers: selectedScrapers,
    });
  };

  const handleStartMatching = () => {
    matchMutation.mutate({
      full_pipeline: true,
      re_match_all: reMatchAll,
    });
  };

  const isSearchRunning =
    searchStatus?.status === 'running' || searchStatus?.status === 'pending';
  const isMatchRunning =
    matchStatus?.status === 'running' || matchStatus?.status === 'pending';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Job Search</h1>
        <p className="text-gray-500 dark:text-gray-400 mt-1">Start a new job search or run AI matching</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Search Form */}
        <Card>
          <CardTitle>New Job Search</CardTitle>
          <div className="space-y-4 mt-4">
            {/* Quick Search Button */}
            {config?.search_terms && config.search_terms.length > 0 && (
              <div className="p-4 bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-800 rounded-lg">
                <p className="text-sm text-blue-700 dark:text-blue-300 mb-3">
                  Search using your profile settings ({config.search_terms.length} job titles, {config.locations?.join(', ') || 'Remote'})
                </p>
                <Button
                  onClick={handleQuickSearch}
                  disabled={isSearchRunning || selectedScrapers.length === 0 || configLoading}
                  variant="primary"
                  className="w-full"
                >
                  {isSearchRunning ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Searching...
                    </>
                  ) : (
                    <>
                      <Rocket className="w-4 h-4 mr-2" />
                      Quick Search
                    </>
                  )}
                </Button>
              </div>
            )}

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-gray-200 dark:border-gray-700" />
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="bg-white dark:bg-gray-800 px-2 text-gray-500 dark:text-gray-400">or customize</span>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Job Titles (comma-separated)
              </label>
              <Input
                value={jobTitles}
                onChange={(e) => setJobTitles(e.target.value)}
                placeholder="e.g., Software Engineer, Data Scientist"
                disabled={isSearchRunning}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Locations (comma-separated)
              </label>
              <Input
                value={locations}
                onChange={(e) => setLocations(e.target.value)}
                placeholder="e.g., Remote, New York, San Francisco"
                disabled={isSearchRunning}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Results per search
              </label>
              <Input
                type="number"
                value={resultsPerSearch}
                onChange={(e) => setResultsPerSearch(Number(e.target.value))}
                min={10}
                max={100}
                disabled={isSearchRunning}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Job Sources
              </label>
              <div className="flex gap-4">
                {['indeed', 'glassdoor'].map((scraper) => (
                  <label key={scraper} className="flex items-center gap-2 text-gray-900 dark:text-gray-100">
                    <input
                      type="checkbox"
                      checked={selectedScrapers.includes(scraper)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedScrapers([...selectedScrapers, scraper]);
                        } else {
                          setSelectedScrapers(selectedScrapers.filter((s) => s !== scraper));
                        }
                      }}
                      disabled={isSearchRunning}
                      className="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500 dark:bg-gray-700"
                    />
                    <span className="capitalize">{scraper}</span>
                  </label>
                ))}
              </div>
            </div>

            <Button
              onClick={handleStartSearch}
              disabled={isSearchRunning || selectedScrapers.length === 0}
              className="w-full"
            >
              {isSearchRunning ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Searching...
                </>
              ) : (
                <>
                  <Search className="w-4 h-4 mr-2" />
                  Start Search
                </>
              )}
            </Button>

            {/* Search Status */}
            {searchTaskId && searchStatus && (
              <div className="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                <div className="flex items-center gap-2">
                  {searchStatus.status === 'running' && (
                    <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />
                  )}
                  {searchStatus.status === 'completed' && (
                    <CheckCircle className="w-4 h-4 text-green-600" />
                  )}
                  {searchStatus.status === 'failed' && (
                    <XCircle className="w-4 h-4 text-red-600" />
                  )}
                  <span className="font-medium capitalize text-gray-900 dark:text-white">{searchStatus.status}</span>
                </div>
                {searchStatus.progress && (
                  <div className="mt-2">
                    <div className="flex justify-between text-sm text-gray-500 dark:text-gray-400 mb-1">
                      <span>{searchStatus.progress.message}</span>
                      <span>
                        {searchStatus.progress.current} / {searchStatus.progress.total}
                      </span>
                    </div>
                    <div className="w-full h-2 bg-gray-200 dark:bg-gray-600 rounded-full">
                      <div
                        className="h-full bg-blue-600 rounded-full transition-all"
                        style={{
                          width: `${
                            (searchStatus.progress.current / searchStatus.progress.total) * 100
                          }%`,
                        }}
                      />
                    </div>
                  </div>
                )}
                {searchStatus.error && (
                  <p className="mt-2 text-sm text-red-600 dark:text-red-400">{searchStatus.error}</p>
                )}
              </div>
            )}
          </div>
        </Card>

        {/* AI Matching */}
        <Card>
          <CardTitle>AI Matching Pipeline</CardTitle>
          <div className="space-y-4 mt-4">
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Run the AI matching pipeline to score jobs against your resume and requirements.
              This includes:
            </p>
            <ul className="space-y-2 text-sm text-gray-600 dark:text-gray-400">
              <li className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900/50 flex items-center justify-center text-blue-600 dark:text-blue-400 text-xs font-bold">
                  1
                </div>
                <span>Score jobs (0-100 match score)</span>
              </li>
              <li className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900/50 flex items-center justify-center text-blue-600 dark:text-blue-400 text-xs font-bold">
                  2
                </div>
                <span>Analyze gaps and strengths</span>
              </li>
              <li className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900/50 flex items-center justify-center text-blue-600 dark:text-blue-400 text-xs font-bold">
                  3
                </div>
                <span>Generate resume suggestions</span>
              </li>
            </ul>

            <div className="pt-2 border-t border-gray-200 dark:border-gray-700">
              <label className="flex items-center gap-2 text-gray-900 dark:text-gray-100">
                <input
                  type="checkbox"
                  checked={reMatchAll}
                  onChange={(e) => setReMatchAll(e.target.checked)}
                  disabled={isMatchRunning}
                  className="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500 dark:bg-gray-700"
                />
                <span className="text-sm">Re-match all jobs (ignore previous scores)</span>
              </label>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-6">
                When checked, all jobs will be re-scored regardless of whether they were previously processed.
              </p>
            </div>

            <Button
              onClick={handleStartMatching}
              disabled={isMatchRunning}
              variant="primary"
              className="w-full"
            >
              {isMatchRunning ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Running Pipeline...
                </>
              ) : (
                <>
                  <Zap className="w-4 h-4 mr-2" />
                  Run AI Matching
                </>
              )}
            </Button>

            {/* Match Status */}
            {matchTaskId && matchStatus && (
              <div className="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                <div className="flex items-center gap-2">
                  {matchStatus.status === 'running' && (
                    <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />
                  )}
                  {matchStatus.status === 'completed' && (
                    <CheckCircle className="w-4 h-4 text-green-600" />
                  )}
                  {matchStatus.status === 'failed' && (
                    <XCircle className="w-4 h-4 text-red-600" />
                  )}
                  <span className="font-medium capitalize text-gray-900 dark:text-white">{matchStatus.status}</span>
                </div>
                {matchStatus.progress && (
                  <div className="mt-2">
                    <div className="flex justify-between text-sm text-gray-500 dark:text-gray-400 mb-1">
                      <span>{matchStatus.progress.message}</span>
                      <span>
                        {matchStatus.progress.current} / {matchStatus.progress.total}
                      </span>
                    </div>
                    <div className="w-full h-2 bg-gray-200 dark:bg-gray-600 rounded-full">
                      <div
                        className="h-full bg-blue-600 rounded-full transition-all"
                        style={{
                          width: `${
                            (matchStatus.progress.current / matchStatus.progress.total) * 100
                          }%`,
                        }}
                      />
                    </div>
                  </div>
                )}
                {matchStatus.error && (
                  <p className="mt-2 text-sm text-red-600 dark:text-red-400">{matchStatus.error}</p>
                )}
              </div>
            )}
          </div>
        </Card>
      </div>

      {/* Current Config */}
      {config && (
        <Card>
          <CardTitle>Current Configuration</CardTitle>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4 text-sm">
            <div>
              <p className="font-medium text-gray-700 dark:text-gray-300">Default Search Terms</p>
              <p className="text-gray-500 dark:text-gray-400">{config.search_terms?.join(', ') || 'None configured'}</p>
            </div>
            <div>
              <p className="font-medium text-gray-700 dark:text-gray-300">Default Locations</p>
              <p className="text-gray-500 dark:text-gray-400">{config.locations?.join(', ') || 'None configured'}</p>
            </div>
            <div>
              <p className="font-medium text-gray-700 dark:text-gray-300">Available Scrapers</p>
              <p className="text-gray-500 dark:text-gray-400">{config.scrapers?.join(', ') || 'None'}</p>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
