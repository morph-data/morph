import { useQuery } from "./utils/useQuery";

type Resource = {
  alias: string;
  path: string;
  connection?: string | null;
  output_paths: string[];
  public?: boolean | null;
  output_type?: string | null;
  data_requirements?: string[] | null;
};

type GetResourcesResponse = {
  resources: Resource[];
};

const getResources = async () => {
  const response = await fetch("/cli/resource");

  if (!response.ok) {
    throw await response.json();
  }

  const data = await response.json();

  if (data.error) {
    throw data.error;
  }

  return data as GetResourcesResponse;
};

const useResourcesQuery = () => {
  return useQuery(getResources);
};

export { type Resource, useResourcesQuery };
