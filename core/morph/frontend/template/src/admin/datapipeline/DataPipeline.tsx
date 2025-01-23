import { ReactFlowProvider } from "@xyflow/react";
import { useResourcesQuery } from "../common/useResourcesQuery";

import "@xyflow/react/dist/style.css";
import { Flow } from "./Flow";
import { ResourceDetail } from "./ResourceDetail";

export const DataPipeline = () => {
  const resources = useResourcesQuery();

  if (resources.status === "loading") {
    return null;
  }

  if (resources.status === "error") {
    throw resources.error;
  }

  return (
    <ReactFlowProvider>
      {/* TODO: Refactor height calculation, avoid hardcoded values */}
      <div className="grid grid-cols-3 gap-4 h-[calc(100vh-102px)]">
        <div className="col-span-2">
          <Flow resources={resources.data.resources} />
        </div>
        <div className="col-span-1 overflow-x-auto p-2">
          <ResourceDetail resources={resources.data.resources} />
        </div>
      </div>
    </ReactFlowProvider>
  );
};
