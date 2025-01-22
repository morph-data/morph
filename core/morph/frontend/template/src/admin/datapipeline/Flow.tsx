import { ReactFlow, Background, Node, Edge } from "@xyflow/react";
import dagre from "@dagrejs/dagre";
import { Resource } from "../common/useResourcesQuery";

import "@xyflow/react/dist/style.css";
import { ResourceNode } from "./ResourceNode";

const nodeTypes = {
  resource: ResourceNode,
};

export const Flow = ({ resources }: { resources: Resource[] }) => {
  const nodes = convertResourcesToNodes(resources);
  const edges = convertResourcesToEdges(resources);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      className="rounded-lg"
      fitView
    >
      <Background bgColor="#f5f5f5" />
    </ReactFlow>
  );
};

const convertResourcesToNodes = (resources: Resource[]): Node[] => {
  const WIDTH = 200;
  const HEIGHT = 40;

  const graph = new dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));

  graph.setGraph({ rankdir: "TB", ranksep: HEIGHT, nodesep: WIDTH / 2 });

  resources.forEach((resource) =>
    graph.setNode(resource.alias, {
      width: WIDTH,
      height: HEIGHT,
    })
  );

  resources.forEach((resource) => {
    resource.data_requirements?.forEach((parentAlias) => {
      graph.setEdge(parentAlias, resource.alias);
    });
  });

  dagre.layout(graph);

  const nodes: ResourceNode[] = resources.map((resource) => {
    return {
      id: resource.alias,
      type: "resource",
      position: {
        x: graph.node(resource.alias).x,
        y: graph.node(resource.alias).y,
      },
      width: WIDTH,
      height: HEIGHT,
      connectable: false,
      draggable: false,
      handles: [],
      data: { resource },
    };
  });

  return nodes;
};

const convertResourcesToEdges = (resources: Resource[]): Edge[] => {
  return resources.reduce((edges, resource) => {
    const addedEdges =
      resource.data_requirements?.map((parentAlias) => ({
        id: `${parentAlias}-${resource.alias}`,
        source: parentAlias,
        target: resource.alias,
      })) ?? [];

    return [...edges, ...addedEdges];
  }, [] as Edge[]);
};
