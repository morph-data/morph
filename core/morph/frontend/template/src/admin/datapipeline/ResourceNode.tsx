import { tv } from "tailwind-variants";
import { Resource } from "../common/useResourcesQuery";
import {
  Handle,
  Node,
  NodeProps,
  Position,
  useOnSelectionChange,
} from "@xyflow/react";
import React from "react";
import databaseIcon from "../../assets/icons/database.svg";
import pythonIcon from "../../assets/icons/python.svg";

export type ResourceNode = Node<
  {
    resource: Resource;
  },
  "resource"
>;

const useSelected = (id: string) => {
  const [selected, setSelected] = React.useState(false);

  useOnSelectionChange({
    onChange: React.useCallback(({ nodes }) => {
      setSelected(nodes.some((node) => node.id === id));
    }, []),
  });

  return selected;
};

const ResourceNode = ({ id, data }: NodeProps<ResourceNode>) => {
  const { resource } = data;

  const selected = useSelected(id);

  return (
    <div className={card({ selected })}>
      <Icon resource={resource} />
      <span className="font-semibold text-sm ">{resource.alias}</span>
      <Handle
        type="target"
        className="!bg-gray-300 !border-none"
        position={Position.Top}
        id={id}
      />
      <Handle
        type="source"
        className="!bg-gray-300 !border-none"
        position={Position.Bottom}
        id={id}
      />
    </div>
  );
};

const Icon = ({ resource }: { resource: Resource }) => {
  if (resource.path.endsWith(".py")) {
    return <img src={pythonIcon} className="h-4 w-4 my-auto" />;
  }

  if (resource.path.endsWith(".sql")) {
    return <img src={databaseIcon} className="w-4 h-4 my-auto" />;
  }

  return null;
};

const card = tv({
  base: "bg-gray-200 p-2 rounded-md flex align-center justify-center gap-2",
  variants: {
    selected: {
      true: "outline outline-gray-400",
    },
  },
});

export { ResourceNode };
