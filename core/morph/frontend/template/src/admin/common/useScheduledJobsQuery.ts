import { useQuery } from "./utils/useQuery";

type ScheduledJob = {
  cron: string;
  is_enabled?: boolean;
  timezone?: string;
  variables?: Record<string, unknown>;
};

type GetScheduledJobsResponse = Record<string, { schedules: ScheduledJob[] }>;

const getScheduledJobs = async () => {
  const response = await fetch("/cli/morph-project/scheduled-jobs");

  if (!response.ok) {
    throw await response.json();
  }

  const data = await response.json();

  if (data.error) {
    throw data.error;
  }

  return data as GetScheduledJobsResponse;
};

const useScheduledJobsQuery = () => {
  return useQuery(getScheduledJobs);
};

export { type ScheduledJob, useScheduledJobsQuery };
