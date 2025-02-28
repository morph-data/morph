import {
  Accordion,
  Callout,
  Card,
  DataTable,
  Embed,
  Grid,
  LLM,
  Chat,
  Metrics,
  MetricsGrid,
  Panel,
  Input,
  Select,
  SelectGroup,
  SelectGroupLabel,
  SelectItem,
  SelectSeparator,
  SelectItems,
  DatePicker,
  DateRangePicker,
  Pre,
} from "@morph-data/components";
import { MDXComponents } from "mdx/types";

const builtinComponents = {
  DataTable,
  Embed,
  Metrics,
  MetricsGrid,
  Input,
  Select,
  SelectGroup,
  SelectGroupLabel,
  SelectItem,
  SelectSeparator,
  SelectItems,
  Card,
  Grid,
  Panel,
  Accordion,
  Callout,
  LLM,
  Chat,
  DatePicker,
  DateRangePicker,
  pre: Pre,
} as const;

type PluginModule = {
  components?: Record<string, React.FunctionComponent>;
};

type Plugins = {
  [pluginName: string]: PluginModule;
};

const plugins: Plugins = Object.entries(
  import.meta.glob<true, string, PluginModule>(
    "/../../src/plugin/**/react/index.ts",
    {
      eager: true,
    }
  )
).reduce((acc, [reactEntryPath, module]) => {
  // /path/to/plugin-name/react/index.ts -> plugin-name
  const pluginName = reactEntryPath.match(/plugin\/(.+?)\//)?.[1] ?? "";
  return {
    ...acc,
    [pluginName]: module,
  };
}, {} as Plugins);

const pluginsComponents = Object.entries(plugins).reduce(
  (mdxComponents, [pluginName, module]) => {
    if (!module.components) {
      return mdxComponents;
    }

    return Object.entries(module.components).reduce(
      (mdxComponents, [componentName, component]) => {
        const isComponentNameConflict =
          Object.keys(mdxComponents).includes(componentName);

        if (isComponentNameConflict) {
          console.warn(
            `Component name conflict: ${componentName} in plugin ${pluginName}`
          );
        }

        return {
          ...mdxComponents,
          [componentName]: component,
        };
      },
      mdxComponents
    );
  },
  {} as Record<string, React.FunctionComponent>
);

export const mdxComponents: MDXComponents = {
  ...builtinComponents,
  ...pluginsComponents,
};
