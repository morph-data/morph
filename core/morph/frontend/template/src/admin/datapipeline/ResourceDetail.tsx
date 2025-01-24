import { Node, useOnSelectionChange } from "@xyflow/react";
import React from "react";
import { useScheduledJobsQuery } from "../common/useScheduledJobsQuery";
import { Resource } from "../common/useResourcesQuery";

export const ResourceDetail = ({ resources }: { resources: Resource[] }) => {
  const [selectedAlias, setSelectedAlias] = React.useState<string | null>(null);

  const onChange = React.useCallback(({ nodes }: { nodes: Node[] }) => {
    if (nodes.length === 0) {
      setSelectedAlias(null);
    } else {
      setSelectedAlias(nodes[0].id);
    }
  }, []);

  useOnSelectionChange({
    onChange,
  });

  if (!selectedAlias) {
    return (
      <div className="mt-8">
        <p className="text-center text-gray-900">Select cell to view details</p>
      </div>
    );
  }

  return (
    <div>
      <h2>{selectedAlias}</h2>
      <BasicInfo resources={resources} alias={selectedAlias} />
      {/* <ScheduledJobs alias={selectedAlias} /> */}
    </div>
  );
};

const BasicInfo = ({
  alias,
  resources,
}: {
  alias: string;
  resources: Resource[];
}) => {
  const resource = resources.find((r) => r.alias === alias);

  if (!resource) {
    return <p className="text-red-700">Something went wrong</p>;
  }

  return (
    <div>
      <p className="text-sm text-gray-900">
        Defined at <code className="break-all">{resource.path}</code>
      </p>
    </div>
  );
};

const ScheduledJobs = ({ alias }: { alias: string }) => {
  const scheduledJobs = useScheduledJobsQuery();

  if (scheduledJobs.status === "loading") {
    return null;
  }

  if (scheduledJobs.status === "error") {
    return <p className="text-red-700">Something went wrong</p>;
  }

  const scheduledJobsForAlias = scheduledJobs.data[alias]?.schedules ?? [];

  return (
    <div className="mt-6">
      <h3 className="mb-6">Scheduled Jobs</h3>
      {scheduledJobsForAlias.length === 0 && (
        <p className="text-sm">No scheduled jobs</p>
      )}
      {scheduledJobsForAlias.map((job, i) => (
        <div key={i}>
          <h4 className="font-semibold">{`${job.cron} (${
            job.timezone ?? "UTC"
          })`}</h4>

          {job.variables ? (
            <div className="mt-4">
              <span className="block text-sm text-semibold mb-1">
                Variables
              </span>
              <table className="bg-gray-100 rounded-sm">
                <thead>
                  <tr>
                    <th>Key</th>
                    <th>Value</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(job.variables).map(([key, value]) => (
                    <tr key={key}>
                      <td>{key}</td>
                      <td>{String(value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <span className="block text-sm text-semibold mb-2">
              No variables
            </span>
          )}

          {i < scheduledJobsForAlias.length - 1 && (
            <hr className="border-gray-300 my-4" />
          )}
        </div>
      ))}
    </div>
  );
};
